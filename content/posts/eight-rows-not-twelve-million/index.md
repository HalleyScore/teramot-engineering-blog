---
title: "Eight Rows, Not Twelve Million: The Cache Behind Teramot Beacon"
date: 2026-09-16
draft: false
authors:
  - sol-soletti
tags:
  - data
  - caching
  - duckdb
  - on-premise
  - architecture
categories:
  - data
summary: "Some customers needed Teramot inside their own perimeter, on their own cloud. Beacon is the node that asks first and moves only the rows the answer needs — and a cache that stopped trusting the clock. With charts, a comic, and one galaxy brain."
showTableOfContents: true
---

{{< intro >}}
Teramot Beacon answers business questions against live data by pulling only the slice a question needs into an embedded DuckDB, inside the customer's own network, on any cloud or a laptop. The interesting engineering is not the pull. It is what happens on the second question: a slice registry with a strict containment law, column widening instead of re-pulls, and a cache that is invalidated by the version of the source, never by a timer.
{{< /intro >}}

Some of our customers cannot let their data leave the building. Some run on AWS, some on GCP, some on Azure, one on Oracle Cloud, and at least one on a server with a sticker on it. All of them wanted to ask a question about their business in plain Spanish and get a correct number back. That need (**on-premise and multicloud**) is where Teramot Beacon comes from. This is the story of the part I find most fun: the cache.

{{< stats columns="4" >}}
{{< stat value="Dozens" label="Rows moved" >}}To answer aggregate questions over fact tables of millions of rows, on real customer data, exact to the cent.{{< /stat >}}
{{< stat value="1" label="Container" >}}The whole node ships as one image with DuckDB inside. State is a directory. Any cloud, or a laptop.{{< /stat >}}
{{< stat value="25" label="Source connectors" >}}From Postgres and SAP HANA to Salesforce, Google Sheets, Iceberg on S3 and a CSV somebody emailed.{{< /stat >}}
{{< stat value="53" label="Days to 1.0" >}}First commit 5 July 2026. Version 1.0.0 tagged 27 August 2026. Three engineers.{{< /stat >}}
{{< /stats >}}

## 1. The two ways of Teramot

Teramot's promise has always been one sentence: a correct number about your business, without months of data engineering first. There are two shapes to deliver it.

**The Teramot way** builds the company's curated data infrastructure and keeps it alive: sources are ingested, cleaned, modelled and served, and every question, dashboard and agent works on top of that map. It is the shape you want when you want to build your warehouse.

**The Teramot Beacon way** is for the customers whose data cannot leave their perimeter, who run on whatever cloud they already have. A single node runs inside their network, reads the source's *metadata* to learn what is there, lets an agent decide which tables, columns and filters the question needs, pulls exactly that into an embedded DuckDB, and writes SQL against the local slice. The answer travels back with its SQL, its row counts per table and a trace. The source only ever sees `SELECT` statements with bind parameters, and the rows that leave it are the ones the answer is made of.

## 2. The galaxy-brain ladder

Every engineer who hears "pull only what you need" climbs the same four rungs. We climbed them in about nine days.

{{< inlinesvg src="svg/ladder.svg" caption="The four rungs. The node lives on the bottom one, and this article is mostly about keeping it there on the second question." >}}

The last rung matters more than it looks. For "revenue by region for 2025" the node does not pull the 2025 rows and group them locally. It asks the source to run the `GROUP BY` and ships back the groups. In our first three-customer test on production data, aggregate questions moved **a few dozen rows at most** against fact tables of **millions**. One of those sources was a multi-gigabyte CSV, and the answer matched the customer's own number to the cent.

{{< chart >}}
type: 'bar',
data: {
  labels: ['Sales fact, CSV files', 'Sales fact, Iceberg tables', 'Demand table, ERP', 'Cohort question, public benchmark'],
  datasets: [
    { label: 'Rows in the source table (order of magnitude)', data: [10000000, 10000000, 10000000, 10000], backgroundColor: 'rgba(148, 163, 184, 0.7)', borderWidth: 0, borderRadius: 4 },
    { label: 'Rows that crossed the wire (order of magnitude)', data: [10, 50, 70, 400], backgroundColor: 'rgba(37, 61, 229, 0.9)', borderWidth: 0, borderRadius: 4 }
  ]
},
options: {
  responsive: true,
  plugins: {
    legend: { position: 'bottom' },
    title: { display: true, text: 'Rows in the source vs. rows moved to the node (log scale, rounded)' },
    tooltip: { callbacks: { label: (c) => c.dataset.label + ': ' + c.parsed.y.toLocaleString('en-US') } }
  },
  scales: { y: { type: 'logarithmic', title: { display: true, text: 'rows (log)' } } }
}
{{< /chart >}}

The funnel that gets there has eight stages. Two carry this story: **decide**, where the cache lives, and **estimate**, which counts the rows a filter would return *before* pulling them, so the node can refuse, tighten, or push the aggregation to the source.

{{< inlinesvg src="svg/funnel.svg" caption="The eight stages of one question. Everything before pull is metadata and cache. Customer rows move in exactly one box." >}}

## 3. Then we measured, and felt silly

The obvious optimisation target was the pull. Pulling is I/O, I/O is slow. Then we instrumented nine real runs of the same question against a customer's data.

{{< chart >}}
type: 'bar',
data: {
  labels: ['discover (catalog)', 'select (agent picks tables + columns)', 'pull (rows move)', 'model (agent writes + checks SQL)'],
  datasets: [{
    label: 'median seconds',
    data: [30, 41, 30, 146],
    backgroundColor: ['rgba(148, 163, 184, 0.7)', 'rgba(148, 163, 184, 0.7)', 'rgba(37, 61, 229, 0.9)', 'rgba(235, 104, 52, 0.9)'],
    borderWidth: 0,
    borderRadius: 4
  }]
},
options: {
  indexAxis: 'y',
  responsive: true,
  plugins: { legend: { display: false }, title: { display: true, text: 'Where a cold question spends its time (median of nine runs, seconds)' } },
  scales: { x: { title: { display: true, text: 'seconds' } } }
}
{{< /chart >}}

The pull was **8 percent** of the clock. **78 percent** was a language model writing tokens at a steady 123 per second, and most of those tokens were the model thinking, not the final SQL. Making the pull twice as fast would have saved fifteen seconds out of four minutes. The only way to make a repeated question dramatically faster is to **not call the model at all**. So the cache had to remember more than rows. It had to remember the plan.

## 4. A cache with a legal department

The cache is a **slice registry**. Every pull is described by what it asked for: which tables, which columns, which filter, which aggregation. A new question is not hashed and looked up. It is checked for **containment**: does something we already hold cover what this question needs? And the law is strict.

{{< inlinesvg src="svg/containment.svg" caption="The containment law in three requests: a hit, a widening, and a miss. A cached slice may never serve fewer rows than the question asked for." >}}

Three outcomes fall out of that law. A **hit** means the slice already holds everything the question needs and nothing moves. A near-miss on columns is not a miss: it triggers **widening**, which fetches only the gap and leaves the rest of the slice untouched. In the replay that proved it, widening moved 830 rows where a fresh pull moved 2,985; the commit said *"a missing column no longer re-pulls the world"*. And anything that would make the slice serve fewer rows than the question asked for, a different filter, a different grouping, is a **miss**, no matter how tempting the shortcut. We learned the cost of a tempting shortcut from a benchmark question that answered 116 where the truth was 51.

Under the registry sits a **plan cache** that remembers how a question was answered, not just which rows it needed. When a question comes back and nothing underneath has changed, the answer is recomputed without calling the model at all. A follow-up inside a conversation works on the slice it already has.

{{< chart >}}
type: 'bar',
data: {
  labels: ['Cold question on a multi-GB CSV', 'Next question, same fact table', 'Follow-up on a cached slice'],
  datasets: [{
    label: 'seconds to answer (approximate)',
    data: [557, 22, 20],
    backgroundColor: ['rgba(148, 163, 184, 0.7)', 'rgba(37, 61, 229, 0.9)', 'rgba(37, 61, 229, 0.9)'],
    borderWidth: 0,
    borderRadius: 4
  }]
},
options: {
  responsive: true,
  plugins: { legend: { display: false }, title: { display: true, text: 'First question vs. the ones after it (real customer files, approximate seconds)' } },
  scales: { y: { title: { display: true, text: 'seconds' } } }
}
{{< /chart >}}

The cold number is honest: streaming a multi-gigabyte CSV from object storage takes minutes, and the node says so while it works. The next question on the same data takes about twenty seconds, and a follow-up on a warm slice about the same, with **zero reads from object storage**.

## 5. Validate, don't expire

This is the part I am proudest of, because it is the part where we deleted code.

Our first cache had a TTL of 900 seconds. Fifteen minutes is a perfectly reasonable number to type. It is also completely wrong for how people ask questions about their business.

{{< inlinesvg src="svg/ttl-comic.svg" caption="Nine real runs of the same question, hours apart. The 900-second TTL never hit once. The cache worked perfectly and served nobody." >}}

> **Nobody:**
>
> **Absolutely nobody:**
>
> **The 900-second TTL:** *expires quietly at 10:15, three hours and forty-five minutes before anyone needs the data again.*

The temptation is a longer TTL. That is the wrong fix, because age was never what made a slice invalid. **A slice is invalid when the source changed.** So the clock was replaced by a **source version** with two parts, on purpose, because a slice and a plan break for different reasons:

| Part | What it fingerprints | What it invalidates |
| --- | --- | --- |
| Shape | A fingerprint of the catalog: which tables and columns exist, and their types. | Cached **plans**. A stored answer against a shape that moved is wrong. |
| Content | A per-table marker that advances when a refresh actually lands new data. It describes *that* something changed, never *what*, so it can never leak a value. | Cached **slices** of that table only. A hot table does not evict the other nineteen. |

The rule that now governs the node, in one sentence from the commit that shipped it: *"the clock stops invalidating and starts triggering validation."* A slice serves for as long as it is **valid**, and age is not part of validity. The cache stays on until somebody refreshes, by hand or on a schedule; a question that cannot tolerate that asks in `live` mode. Every answer carries the version it was served from. The correct model **deleted more lines than it added**.

## 6. ETL at question time

"Pull only what you need" also changed *what gets cleaned*. An up-front pipeline has to transform every table it ingests, because it cannot know which questions will arrive. Beacon runs its ETL on the slice, and only on the slice: the columns a question selected, the rows that passed its filter, the groups the source returned. If the answer is eight rows, eight rows get typed, normalised and checked. The other twelve million never enter the pipeline, because they never entered the node.

That has two consequences we did not fully appreciate at first. The obvious one is cost: cleaning the fraction of a source that a question touches is cheap enough to do on every question, so nothing has to be pre-computed or kept in sync. The less obvious one is context. When the transformation runs at question time, it runs with the question in hand and the real values in front of it, and whatever it decides is recorded in that answer's trace. A decision that turns out to be wrong affects one answer, where it can be seen and corrected, instead of being baked into a table that everybody reads for a year.

## 7. What grew around the cache

A fast, honest answer is the seed. Around it, in about eight weeks, the node grew what a company needs to actually run on those answers:

- **Organizations and permissions.** Members, roles and workspaces, signed in with the company's identity provider. A results table has an owner and can be shared.
- **Row-and-column policies**, enforced inside the funnel, not in the UI. A slice pulled under one policy is never served under another, so the cache cannot be used to look around a permission.
- **Dashboards.** A saved answer gets a place to live, controls the reader can move, a click that filters the rest, a link to share. As one release note put it, *a dashboard stopped being a photo.*
- **Alerts.** A monitor watches a results table and speaks first. The organization writes the message, the node owns the words, and no model runs at trigger time.
- **Bring your own model.** The reasoning model is chosen per node, and an organization can bring its own key.

And every answer still carries its SQL, its rows per table and a trace id. Sources are read-only, and budgets refuse *before* rows are in memory.

## 8. The milestones

{{< timeline >}}

{{< timelineItem icon="star" header="The thin loop" badge="5–6 July 2026" >}}
Four repos in one day. The first real commit is the architecture that never changed: <em>harvest → narrow → select → pull → model</em>. Next morning the eval goes from 20% to <strong>25/25</strong>, the protocol freezes 1.0, and the first slice cache replays a repeated question <strong>1,274× faster</strong>.
{{< /timelineItem >}}

{{< timelineItem icon="check" header="Files are sources, and three real customers" badge="14 July" >}}
CSV, Excel, JSON, Parquet, buckets and Apache Iceberg in one day, read in situ. The same day, three customers' production data answered exact to the cent with <strong>a few dozen rows moved</strong>.
{{< /timelineItem >}}

{{< timelineItem icon="lock" header="Organizations, policies and dashboards" badge="4–13 August" >}}
Organizations managed from the product. Row-and-column policies enforced in the funnel. Dashboards land, then bring-your-own-model.
{{< /timelineItem >}}

{{< timelineItem icon="star" header="The source-version cache" badge="20 August" >}}
Five PRs in a day. The clock leaves the serving path, and every answer says how current it is.
{{< /timelineItem >}}

{{< timelineItem icon="star" header="1.0" badge="27 August" >}}
<strong>v1.0.0</strong>: the node has its own assistant and knows what it spends. Fifty-three days after the first commit.
{{< /timelineItem >}}

{{< /timeline >}}

## 9. What a cache taught me

A cache is a theory about what will be asked next. Ours started as a theory about time, and time turned out to be the wrong axis: nobody asks a business question every fifteen minutes, and nothing about a number becomes false because a quarter of an hour passed. What makes a number false is that the world it described has moved. Once we stopped asking *how old is this* and started asking *is this still true*, the code got shorter and the answers got more honest, and I suspect that trade shows up everywhere we build systems that remember things on behalf of people. The other lesson is quieter. We set out to move as little data as possible, and ended up with a node that holds exactly the pieces of a company's data that somebody, at some point, genuinely needed: small, correct, versioned against their source, and shaped like questions. That is a strange and rather beautiful kind of memory. It knows nothing the business never cared about, and everything it does know, it knows because someone asked. What happens when you let that memory grow on purpose, one question at a time, is the next thing we are building. More on that soon.

*— Sol Soletti*
