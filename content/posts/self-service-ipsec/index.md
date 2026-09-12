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
summary: "How we replaced manual VPN configuration with a recoverable system that connects workers only to approved databases."
showTableOfContents: true
---

Teramot extracts data from sources operated by its customers. Some databases live inside private networks and are reachable only through a site-to-site VPN. Connecting them used to require an operator to configure our gateway, create a TCP forward for the database, and give its local port to the extraction worker.

We replaced that runbook with a control plane that stores the requested connection and a gateway controller that applies it. The controller creates the isolated Linux networking resources, configures strongSwan, and reports the resulting state. If the gateway is replaced, its configuration can be reconstructed from the same stored request instead of being rebuilt by hand.

The important change was not automating a sequence of commands. It was making a private connection a state the system maintains. This article explains how we provision and maintain that connection, then how extraction workers use it without gaining unrestricted access to the customer's network.

## 1. From a manual runbook to a managed connection

In the original process, an operator exchanged a pre-shared key, configured the Teramot gateway, and set up forwarding for each database endpoint. Operators had to track which network configuration and local ports belonged to each connection. The gateway's local disk held its configuration, so replacing the machine also meant reconstructing that setup.

A script could automate those setup steps, but running them once would not answer the ongoing questions: does the gateway still match the requested configuration? Which update is current? What should a replacement machine recreate?

We split those responsibilities between a **control plane**, which stores what should exist, and a **gateway controller**, which manages the corresponding network resources:

| Manual responsibility | Managed replacement |
| --- | --- |
| Edit the gateway configuration | Validate and store the requested connection outside the gateway. |
| Prepare the network environment | Have the controller manage namespaces, interfaces, and routes. |
| Configure the IPsec connection | Load or update strongSwan through its control API. |
| Inspect the machine to understand its state | Report the applied configuration and tunnel health. |
| Rebuild configuration after a gateway failure | Reconstruct the runtime from the stored request. |

Self-service describes the Teramot side of this process. The customer-side gateway still needs compatible configuration; storing a request in Teramot does not configure the remote peer. The connection parameters describe the agreement between those two sides.

Using the tunnel is a separate responsibility. The **data plane** carries database traffic through the provisioned connection. Keeping it separate from provisioning lets a worker use an approved destination without giving it authority to configure the gateway or choose arbitrary destinations inside the private network.

## 2. How the controller provisions and maintains a tunnel

Consider a customer connecting a private network that contains a database at `10.12.4.20`. Before an extraction can reach that database, Teramot needs a tunnel to the customer's gateway and a routing context for its private network.

The user supplies the peer address, Internet Key Exchange (IKE) identities, approved network ranges, optional private DNS servers, and cryptographic settings. The control plane validates and stores that configuration as **desired state**: what the gateway should maintain, not a copy of files from the gateway's disk.

### Turning the request into network state

The controller reads the desired state and performs the work previously done on the gateway by an operator:

1. Ensure the connection's isolated network namespace exists.
2. Ensure its Linux IPsec interface (XFRM) and routes match the requested network ranges.
3. Retrieve the connection's pre-shared key and load or update its configuration in strongSwan through [VICI](https://docs.strongswan.org/docs/latest/plugins/vici.html), strongSwan's local control API.
4. Inspect the resulting Linux and IPsec state and report what was applied.

The controller manages the configuration around the tunnel; [strongSwan](https://docs.strongswan.org/docs/latest/index.html) handles negotiation with the remote gateway. Its [IKEv2](https://www.rfc-editor.org/rfc/rfc7296.html) implementation uses the pre-shared key to authenticate the peers and establish an IKE security association. CHILD security associations then define protection for the approved traffic. The Linux kernel encrypts that traffic using Encapsulating Security Payload (ESP) and its [XFRM](https://docs.kernel.org/networking/xfrm/index.html) framework.

We did not build a new IPsec implementation. We built the system that supplies its configuration, manages the surrounding Linux network environment, and connects its runtime state back to the product.

### Maintaining state instead of running setup once

The controller repeats this process, fetching the latest desired state and reporting **observed state**: what actually exists on the gateway. This reconciliation loop also supports recovery. After a restart or instance replacement, the controller reconstructs the runtime from the stored configuration instead of requiring an operator to restore local files.

Updates can overlap in time. If a user changes a connection while an earlier update is still running, the older result must not become authoritative. Each update therefore carries an increasing generation number, which the controller checks before applying or reporting a result.

The controller is also the only component that changes this managed network state. The proxy does not write routes, and operators do not need to edit connection files for ordinary updates. A connection can be updated without restarting the entire IPsec service or interrupting unrelated tunnels.

Credentials follow a different lifecycle from configuration. The controller retrieves a pre-shared key only while configuring its tunnel. Desired-state documents, server images, logs, command lines, and Terraform state do not contain these keys. Certificate files are written only when the runtime starts.

### Knowing what “ready” means

Applying configuration does not prove that the remote peer accepted it, and an established tunnel does not prove that a database accepts connections. We report these separately:

| Status | Question it answers |
| --- | --- |
| Provisioning | Did the gateway apply the requested configuration? |
| Tunnel health | Is IPsec active? |
| Source health | Does the database accept connections? |

For our example, the gateway may have the correct routes while the remote peer is unavailable. Or the tunnel may be active while the database at `10.12.4.20` is unreachable. A single “healthy” flag would hide the distinction an operator needs to diagnose the failure.

## 3. Keeping overlapping private networks separate

The controller needs an isolated routing context because private addresses are not globally unique. A second customer may also have a database at `10.12.4.20`. In one shared routing table, that destination alone would not identify which customer network to use.

Each private connection therefore gets a [network namespace](https://man7.org/linux/man-pages/man7/network_namespaces.7.html) with its own interfaces, routes, DNS view, and XFRM interface:

```text
customer A namespace: 10.12.4.20 -> customer A tunnel
customer B namespace: 10.12.4.20 -> customer B tunnel
```

The destination must identify both a database and its network context. When a worker requests a connection, the gateway selects that context from a server-side authorization record rather than from a namespace or address chosen by the worker.

We separate privileges along the same boundary:

- The **controller** has the capabilities needed to manage namespaces, routes, XFRM, and the strongSwan control socket.
- The **connector proxy** authenticates and dispatches requests without Linux network capabilities.
- A **per-namespace dialer** opens TCP connections inside its assigned namespace without permission to reconfigure the host or another namespace.

The network-facing proxy therefore does not hold the controller's authority to change routing or IPsec configuration. Isolation is part of provisioning, not something an extraction worker sets up for itself.

## 4. Connecting existing drivers to one approved database

Once the tunnel exists, an extraction still needs a way to use it. Our original proxy accepted a destination host and port from the worker. That gave the worker too much control: a compromised worker could request other destinations inside the customer's network.

The replacement separates three questions: who is connecting, which database they may use, and which isolated network contains it.

### Authorizing the destination before opening a socket

When a user associates a data source with a private connection, the control plane creates a **source binding**. This server-side record stores the network, namespace, database host, and port. The worker receives an opaque reference to the approved source, not authority to supply a different destination.

For every request, the gateway:

- Authenticates the worker through mutual TLS (mTLS) and checks that its workload certificate is authorized to use the binding.
- Rejects a binding that has expired or been replaced by a newer version.
- Resolves the destination and namespace from the stored binding, never from a worker-supplied host and port.
- Rejects loopback, cloud metadata, management networks, and addresses outside the approved private network ranges.

The tunnel supplies network connectivity; the binding restricts its use to the approved database. After a restart, the proxy rejects connections until the controller supplies current bindings and trusted certificate authorities. Listening on a port is not enough to start accepting database requests.

### Adapting the connection without changing database drivers

Database drivers speak their own database protocol. They cannot first perform Teramot's gateway authorization exchange and then switch protocols on the same socket. We put that exchange in a local forwarder and give the driver a temporary loopback port.

For each driver socket, the forwarder authenticates to the gateway with a workload certificate and sends the source reference. The proxy validates the request, then asks the dialer in the selected namespace to open the stored database host and port. Once the connection is established, the forwarder relays database traffic.

![Sequence diagram showing a database connection through the local forwarder, private gateway, and IPsec tunnel](/diagrams/self-service-ipsec-sequence.png)

*This is the extraction path after provisioning. The driver sees a local socket; the namespace dialer reaches the approved private database through IPsec.*

Existing drivers therefore need no knowledge of namespaces or Teramot's gateway protocol. Forwarding introduces a TLS naming detail: the local socket is at `127.0.0.1`, while a database certificate identifies the real database host. When hostname verification is used, it must verify that logical hostname rather than the loopback address; forwarding is not a reason to disable verification.

## 5. Recovering the gateway without hiding connection failures

Storing desired state outside the gateway solves only part of recovery. A replacement host also needs the correct software, services, and permissions before the controller can recreate the connections.

[Packer](https://developer.hashicorp.com/packer/docs) and [Ansible Core](https://docs.ansible.com/projects/ansible-core/) build a versioned Ubuntu image containing strongSwan, systemd services, permissions, and safe defaults. It contains no peer configuration, credentials, or environment endpoints. [Terraform](https://developer.hashicorp.com/terraform/docs) deploys the exact image ID and adds environment-specific network and access configuration.

The image restores the host software; reconciliation restores the connection configuration. We promote the same image between environments, and the previous image ID remains an explicit rollback target.

This is recoverability, not uninterrupted availability. The first version has one active gateway, so connections remain unavailable while automated replacement restores it. A load balancer with one target does not provide high availability.

### A restored tunnel cannot restore a database session

Even when connectivity returns, the forwarder cannot safely reconstruct an interrupted database session. The database may have an open transaction or may already have returned partial results. Transparently reconnecting and repeating work could duplicate an operation or produce an incorrect result.

| Failure point | Behavior |
| --- | --- |
| Before the stream is established | Retry only when the failure is known to be temporary. |
| Authorization, protocol, or certificate rejection | Fail immediately; retrying the same identity cannot help. |
| After database bytes have crossed the relay | Fail the operation; never reconnect transparently. |

An interrupted stream can look like a normal end-of-file (EOF) signal to the driver. The transport layer preserves its first specific failure so operators can see the network cause together with the database symptom. Recovery must restore future connectivity without pretending that an interrupted operation succeeded.

## 6. What staging taught us

Integration tests start the real proxy and namespace dialer, create Linux network namespaces, and connect through PostgreSQL, MySQL, and SQL Server. They cover different TLS modes, rejected identities, revoked certificates, overlapping private networks, and interrupted streams. These tests exercise the components, but not every interaction in the deployed system.

In staging, we test the complete path from the control plane to an extraction worker. That exposed two failures the isolated tests had missed:

- **Healthy processes, broken handoff.** Both the proxy and namespace dialer were healthy, but Linux permissions prevented the proxy from opening the dialer's Unix socket. Process health did not prove that the components could communicate.
- **Unchanged configuration, rejected refresh.** The control plane refreshed timestamps without changing the configuration generation. The gateway treated each refresh as a conflicting update and eventually rejected new connections. The test fixtures had not reproduced that control-plane behavior.

These failures are why complete staging extractions are part of release validation before promotion. Component tests establish important properties; an end-to-end extraction checks that the deployed permissions, state exchanges, and data path work together.

## Conclusion

The original runbook produced a working tunnel, but left its configuration and recovery dependent on an operator. The new system stores the intended connection outside the gateway, gives one controller responsibility for maintaining it, and reconstructs the runtime when the machine is replaced.

That managed tunnel is only the foundation. Isolated routing contexts distinguish overlapping customer networks, server-side bindings restrict workers to approved databases, and the forwarder keeps existing drivers compatible. Explicit failure behavior and staging validation make the operational limits visible rather than hiding them behind a successful VPN handshake.

IPsec provides the encrypted path. The system around it turns that path into a repeatable capability for Teramot customers.

*— Facundo Vivas*

## References and further reading

- [strongSwan documentation](https://docs.strongswan.org/docs/latest/index.html), including [VICI](https://docs.strongswan.org/docs/latest/plugins/vici.html), [swanctl](https://docs.strongswan.org/docs/latest/swanctl/swanctl.html), and the [`charon` daemon](https://docs.strongswan.org/docs/latest/daemons/charon.html).
- [RFC 7296: Internet Key Exchange Protocol Version 2 (IKEv2)](https://www.rfc-editor.org/rfc/rfc7296.html).
- [Linux network namespaces](https://man7.org/linux/man-pages/man7/network_namespaces.7.html).
- [Linux kernel XFRM framework](https://docs.kernel.org/networking/xfrm/index.html).
- [Packer documentation](https://developer.hashicorp.com/packer/docs).
- [Ansible Core documentation](https://docs.ansible.com/projects/ansible-core/).
- [Terraform documentation](https://developer.hashicorp.com/terraform/docs).
