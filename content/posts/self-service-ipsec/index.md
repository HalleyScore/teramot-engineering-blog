---
title: "Building Self-Service IPsec Connectivity for External Databases"
date: 2026-09-11
draft: false
authors:
  - facundo-vivas
tags:
  - networking
  - infrastructure
  - ipsec
  - linux
  - systems
categories:
  - infrastructure
summary: "How we turned a manual VPN runbook into a reconciled, fail-closed data path for database extraction."
showTableOfContents: true
---

Connecting to a database is easy when the database is inside the same network as the application. It becomes a different class of problem when the database lives behind a customer's firewall, uses private address space, and can only be reached through a site-to-site VPN.

At Teramot, we wanted that connectivity to feel like a normal data-source configuration for the person using the platform, while still meeting the expectations of an infrastructure team: no hand-edited bastion, no process per database, no arbitrary private-network access from a worker, and no secrets baked into a server image.

The result is a self-service path that provisions an IKEv2/IPsec tunnel, isolates each customer network inside Linux, and lets extraction workers reach an approved database through a short-lived, mutually authenticated data path. This post explains the engineering behind it.

## The problem was larger than “set up a VPN”

The original operational pattern was familiar: exchange a pre-shared key, edit a gateway, create a TCP forward for a database endpoint, and configure the extractor to use that forward. It works for one customer, but becomes fragile when every connection depends on remembering which host, namespace, route, and local port belong together.

It also creates the wrong security boundary: a worker-provided host and port turns the proxy into a general-purpose scanner, while a local-disk source of truth makes machine replacement a recovery project.

We therefore treated the problem as two related systems:

1. **A control plane** that turns a user intent into an observed, recoverable network state.
2. **A data plane** that carries database bytes without exposing network authority to the extractor.

The distinction matters. The control plane decides *what should exist*. The data plane moves bytes only through paths that the control plane has already authorized.

The sequence below shows the steady-state data path after the control plane has provisioned the tunnel and installed the server-side binding.

![Sequence diagram showing self-service IPsec provisioning and a database connection](/diagrams/self-service-ipsec-sequence.png)

*The extractor sees a local socket, while only the namespace dialer reaches the customer database through the IPsec tunnel. The two flows share state, but they do not share responsibilities.*

## 1. Reconciliation makes tunnel provisioning repeatable

The user-facing operation describes a connection in terms of things a customer actually knows: a peer address, IKE identities, local and remote traffic selectors, optional private DNS servers, and a cryptographic profile. The system validates that configuration and stores it as desired state.

The gateway does not wait for a one-off command to arrive. It periodically pulls desired state from an authenticated internal endpoint and reports observed state back. Each change carries monotonically increasing generations and fencing information, so an older reconciliation cannot overwrite a newer one.

The reconciliation loop is deliberately boring:

1. Fetch the latest desired state.
2. Ensure the customer's network namespace and routing context exist.
3. Ensure the XFRM interface and routes match the requested selectors.
4. Retrieve the specific credential needed for the peer over the control plane.
5. Load the connection into [strongSwan](https://docs.strongswan.org/docs/latest/index.html) through its local [VICI](https://docs.strongswan.org/docs/latest/plugins/vici.html) socket.
6. Initiate or update the IKEv2 and CHILD SAs.
7. Inspect the resulting Linux and IPsec state.
8. Report observed state and stable diagnostic codes.

The gateway controller is the only writer for this managed runtime. We do not edit connection files by hand, restart the IPsec daemon for every update, or let several services “help” by writing overlapping pieces of state.

This pull-based model is also our recovery mechanism. After a reboot or instance replacement, the controller rebuilds the runtime from durable desired state instead of trying to recover a collection of local files. The machine is replaceable; the intent is not.

### What IKEv2 contributes

[strongSwan](https://docs.strongswan.org/docs/latest/index.html) provides the open-source [IKEv2](https://www.rfc-editor.org/rfc/rfc7296.html) implementation. Peers negotiate an IKE security association, authenticate with a pre-shared key, and establish CHILD SAs for the traffic selectors; the Linux kernel handles the resulting ESP traffic through [XFRM](https://docs.kernel.org/networking/xfrm/index.html).

strongSwan negotiates the security associations while the controller owns the surrounding Linux routing context. A normal connection change becomes a live reconciliation, not a host-wide restart.

## 2. Linux namespaces solve overlapping customer networks

Overlapping private address ranges are normal in enterprise environments. Two customers may both use `10.0.0.0/8`, and a single host routing table cannot safely decide which customer owns a packet destined for `10.12.4.20`.

We give every connection its own [network namespace](https://man7.org/linux/man-pages/man7/network_namespaces.7.html), XFRM interface, routes, and DNS view. The same address can therefore exist in two isolated routing contexts without ambiguity:

```text
customer A namespace: 10.12.4.20 -> customer A tunnel
customer B namespace: 10.12.4.20 -> customer B tunnel
```

The namespace is part of the authorization design. The final TCP dial and private DNS resolution happen inside the namespace selected by the server-side binding.

Privilege separation keeps that mechanism contained:

- The controller has the capabilities needed to manage namespaces, routes, XFRM, and the strongSwan control socket.
- The connector proxy terminates mTLS and dispatches requests, but runs without Linux network capabilities.
- The per-namespace dialer opens the approved TCP connection without being able to reconfigure the host or another namespace.

A bug in the incoming-connection component should not automatically become a bug in the component that can rewire IPsec.

## 3. A local forwarder keeps database drivers ordinary

Database drivers expect to speak their native protocol from the first byte. They cannot send a custom gateway handshake and then seamlessly switch the same socket to PostgreSQL, MySQL, or TDS.

Instead, the extraction runtime starts a small forwarder on loopback and points the existing driver at its ephemeral port:

```text
database driver
      |
      v
127.0.0.1:ephemeral
      |
      v
local forwarder -- mTLS + CONNECT --> private gateway
                                         |
                                         v
                                  namespace dialer
                                         |
                                         v
                                  customer database
```

The forwarder opens one gateway session for each driver socket. It authenticates with a workload certificate and presents an opaque reference for the already-created source binding. The reference intentionally says nothing about the workspace, customer network, namespace, hostname, or port.

The gateway proxy checks the certificate, reference, binding epoch, expiry, and session limits. Only then does it ask the unprivileged dialer to connect to the server-selected target. After success, the stream contains only the database protocol; the network load balancer passes it through without terminating workload TLS.

This design gave us an important compatibility property: the extraction code still uses normal database drivers. Private connectivity is a transport concern, not a new SQL integration.

## 4. The security boundary is the binding, not the tunnel

An established IPsec tunnel proves that two networks can exchange authenticated packets. It does not prove that a particular worker should be allowed to reach a particular database.

We enforce that second decision with a server-side binding:

- The control plane derives the authorized network, target host, target port, and namespace from persisted source configuration.
- The worker receives only an opaque reference and a workload identity.
- The proxy never accepts a target from the worker.
- The dialer checks the reference and binding epoch against a controller-owned policy.
- Loopback, metadata, management ranges, and destinations outside the authorized customer CIDRs are rejected.

That prevents a compromised extractor from turning a valid connection into an arbitrary port scanner. Possessing the opaque reference alone is not enough; the caller also needs an authorized mTLS identity.

Secrets follow the same principle of least authority. Pre-shared keys are retrieved only for the reconciliation that needs them; they are absent from desired-state documents, images, logs, command lines, and infrastructure state. Workload and gateway certificates are materialized at runtime.

The proxy also fails closed. After a restart it can listen, but it cannot authorize a new CONNECT session until the controller has installed a fresh binding snapshot and trust bundle. “The port is open” is not the same as “the data plane is ready.”

## 5. Reproducible infrastructure is part of the feature

The runtime is only useful if the machine hosting it can be rebuilt without a private operator ritual. We made the host a versioned artifact and kept environment-specific state outside it.

### [Packer](https://developer.hashicorp.com/packer/docs) and [Ansible Core](https://docs.ansible.com/projects/ansible-core/)

Packer builds an immutable Ubuntu-based image from an exact base-image ID and pinned package sources. strongSwan comes from the distribution, along with its security updates and mandatory access-control profile.

Ansible configures service accounts, systemd units, filesystem permissions, AppArmor, the allowlisted strongSwan plugins, logging, and Systems Manager. The image contains binaries and safe defaults, but no customer peer, PSK, certificate, private key, endpoint, or environment-specific URL.

### [Terraform](https://developer.hashicorp.com/terraform/docs) and deployment

Terraform provisions a deliberately small Auto Scaling Group, a stable IKE/NAT-T address, internal load balancers for data and control traffic, security groups, private DNS, managed prefix lists, and IAM/KMS permissions.

The image is promoted unchanged between environments. Terraform pins the exact image ID instead of resolving a moving “latest” value. Updating the gateway is therefore a reviewable change from one immutable artifact to another, with a clear rollback target.

GitHub Actions assumes short-lived AWS permissions through OIDC for image builds. Systems Manager is the operational access path, rather than a permanently open SSH path.

Our first version uses one gateway with automated replacement and a measured recovery target. An internal load balancer with one target is not high availability, and we say so explicitly.

## 6. Failure behavior is part of the protocol

The most subtle failures happen at the boundary between a database driver and a TCP stream.

Before the first database byte is sent, a refused CONNECT, a temporary gateway outage, or a failed dial can be classified and retried within a bounded budget. After bytes have crossed the relay, transparent reconnection is unsafe: the driver may have an open transaction, partial results, or protocol state that cannot be reconstructed.

The forwarder therefore has an explicit before-bytes/after-bytes taxonomy:

| Failure point | Behavior |
| --- | --- |
| Before the stream is established | Retry only when the failure is known to be temporary. |
| Authorization, protocol, or certificate rejection | Fail immediately; retrying the same identity cannot help. |
| After database bytes have crossed the relay | Fail the operation; never reconnect transparently. |

An interrupted TCP stream may look like a normal EOF to the driver. The transport layer records the first typed failure and correlates it with the driver's error so operators see both the infrastructure cause and the database symptom.

We also keep provisioning, tunnel, and source connectivity as separate health facets. A healthy tunnel does not imply that a particular database is listening, and a database outage should not make the whole connection look unprovisioned.

## What this changed

For Teramot, private connectivity became an infrastructure capability instead of a collection of host-specific exceptions:

- gateway state is reproducible and reviewable;
- a customer network can be isolated without assigning a new host or inventing a new port for every database;
- the control plane can recover the runtime after replacement;
- the data plane has a stable contract between the control plane, gateway, and extraction runtime;
- security decisions are enforced at the point where a connection is requested, not only when the VPN is created.

For users, the experience is simpler:

- configure the peer and network once instead of opening a support ticket;
- associate a database source with that private path without editing gateway infrastructure;
- keep using the database engine and driver they already use;
- avoid exposing the database directly to the public internet;
- get actionable provisioning, tunnel, and source diagnostics when something is wrong.

## Lessons from building it

### A VPN is a building block, not the product

Negotiating IKEv2 is only one step. A usable capability also needs lifecycle management, target authorization, driver compatibility, observability, cleanup, and recovery. The engineering value is in the contract around the tunnel.

### Opaque references reduce coupling

The extractor does not need to understand networking concepts that belong to the control plane. The opaque reference also prevents a caller from smuggling authority through an identifier.

### Recovery should be the normal path

Once desired state and credentials are durable, replacement is another reconciliation cycle. The host's local disk is a cache, not a database.

### Preserve native protocols whenever possible

The loopback forwarder was less invasive than teaching every database driver about private networking. It lets us test the boundary once while preserving existing extraction paths.

### Real boundaries need real tests

The most useful tests run the actual proxy and dialer, exercise network namespaces, and drive real database engines through the path. We validate PostgreSQL, MySQL, and SQL Server across servers with TLS disabled, optional, and required, plus identity rejection, revocation, overlapping CIDRs, and mid-stream interruption.

Database certificate hostname verification is deliberately not downgraded: drivers must decouple the logical hostname from the loopback address before we enable strict verification.

Self-service private connectivity is ultimately a systems problem. It crosses public-key authentication, IKEv2, Linux kernel networking, process privileges, database driver behavior, immutable images, cloud infrastructure, and user experience. The solution became manageable when each layer had a clear authority, a small contract, and a recovery story.

*— Facundo Vivas*

## References and further reading

- [strongSwan documentation](https://docs.strongswan.org/docs/latest/index.html), including [VICI](https://docs.strongswan.org/docs/latest/plugins/vici.html), [swanctl](https://docs.strongswan.org/docs/latest/swanctl/swanctl.html), and the [`charon` daemon](https://docs.strongswan.org/docs/latest/daemons/charon.html).
- [RFC 7296: Internet Key Exchange Protocol Version 2 (IKEv2)](https://www.rfc-editor.org/rfc/rfc7296.html).
- [Linux network namespaces](https://man7.org/linux/man-pages/man7/network_namespaces.7.html).
- [Linux kernel XFRM framework](https://docs.kernel.org/networking/xfrm/index.html).
- [Packer documentation](https://developer.hashicorp.com/packer/docs).
- [Ansible Core documentation](https://docs.ansible.com/projects/ansible-core/).
- [Terraform documentation](https://developer.hashicorp.com/terraform/docs).
