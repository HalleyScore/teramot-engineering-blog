---
title: "How to Get SOC 2 Certified Without Dying in the Attempt"
date: 2026-09-14
draft: false
authors:
  - valentin-torassa
tags:
  - soc2
  - compliance
  - security
  - process
categories:
  - security
summary: "SOC 2 Type II is a recorded fight, not a screenshot. A short field guide to the boss run, with binding vows, one domain expansion, and two charts you will recognise."
showTableOfContents: true
---

Somewhere in your sales pipeline there is a deal parked behind a single sentence: *"we'll need your SOC 2 report before we can sign."* Nobody on the engineering side asked for this. Everybody on the engineering side is now doing it.

The good news is that SOC 2 is survivable. The bad news is that most teams lose the run in the first ten minutes, during character creation, before a single control has been tested.

{{< stats columns="3" >}}
{{< stat value="3–12" label="Months of observation" >}}The window a Type II report covers. The part you cannot redo.{{< /stat >}}
{{< stat value="1 of 5" label="Criteria that are mandatory" >}}Security. The other four are opt-in — usually by accident.{{< /stat >}}
{{< stat value="0" label="Do-overs" >}}March is already in the report. It always was.{{< /stat >}}
{{< /stats >}}


## 1. Type I is the tutorial. Type II is the boss run.

These are not two difficulty levels of the same report. They measure different things.

**Type I** asks: *on this one day, were your controls designed sensibly?* It is a photograph of your dojo. You can tidy the dojo the night before. Plenty of teams do.

**Type II** asks: *over the next three to twelve months, did those controls actually operate?* It is the whole fight, on tape, including the part where you fumbled.

{{< chart >}}
type: 'bar',
data: {
  labels: ['Elapsed time', 'Evidence required', 'Can be tidied up the night before', 'What enterprise buyers accept'],
  datasets: [
    {
      label: 'Type I',
      data: [8, 12, 90, 25],
      backgroundColor: 'rgba(148, 163, 184, 0.85)',
      borderWidth: 0
    },
    {
      label: 'Type II',
      data: [100, 100, 5, 100],
      backgroundColor: 'rgba(56, 189, 248, 0.85)',
      borderWidth: 0
    }
  ]
},
options: {
  indexAxis: 'y',
  responsive: true,
  plugins: {
    legend: { position: 'bottom' },
    title: { display: true, text: 'Type I vs. Type II, relative' }
  },
  scales: {
    x: { max: 100, title: { display: true, text: 'Relative' } }
  }
}
{{< /chart >}}


This is the detail that catches people: **the observation window is a roguelike run.** There is no save scumming. When the auditor pulls a sample from March and you offboarded someone in March without revoking their access, you cannot go back and fix March. March is done. March is in the report.

## 2. Your controls are binding vows — so stop making them harsher

In *Jujutsu Kaisen*, a binding vow grants you power in exchange for a restriction you impose on yourself. The vow is only as strong as it is specific, and once you make it, you are held to it. Whether you meant it that way is not relevant.

SOC 2 controls are binding vows. **You write them.** Then an auditor spends a year checking whether you honoured your own words.

Which is why the single most expensive mistake in SOC 2 is not laziness. It is *enthusiasm*. A nervous team writes the most impressive-sounding policy it can imagine, and only later discovers it has signed a contract with its own future self.

| The vow you were tempted to make | The vow that survives the run |
| --- | --- |
| "Access reviews are performed monthly." | "Access reviews are performed quarterly." |
| "All findings are remediated within 24 hours." | "Findings are triaged within 5 business days, with severity-based SLAs." |
| "Every production change is reviewed by two engineers." | "Every production change is reviewed by at least one engineer who is not the author." |
| "We log everything." | *(delete this, it is not a control, it is a mood)* |

The monthly access review does not get you a better report than the quarterly one. It gets you **twelve chances to fail instead of four.** Same power, triple the restriction. That is a bad vow.

Write the weakest vow you can defend, honour it perfectly, and tighten it next year.


## 3. Character creation: do not pick all five criteria

SOC 2 has five Trust Services Criteria. Exactly one of them is mandatory:

- **Security** — the Common Criteria. Required. This is the run.
- **Availability** — optional.
- **Confidentiality** — optional.
- **Processing Integrity** — optional.
- **Privacy** — optional, and the most expensive of the four by a wide margin.

Selecting all five on your first audit is choosing Ultra Hard on a fresh save file with no New Game+, no gear, and no idea where the checkpoints are. Your customer almost certainly asked for *"a SOC 2 report."* They did not ask for Processing Integrity. Ask them before you volunteer for it.

{{< chart >}}
type: 'bar',
data: {
  labels: ['Security', 'Availability', 'Confidentiality', 'Processing Integrity', 'Privacy'],
  datasets: [{
    label: 'Relative effort added to the run',
    data: [100, 25, 20, 45, 90],
    backgroundColor: [
      'rgba(56, 189, 248, 0.85)',
      'rgba(148, 163, 184, 0.75)',
      'rgba(148, 163, 184, 0.75)',
      'rgba(249, 168, 37, 0.85)',
      'rgba(239, 68, 68, 0.9)'
    ],
    borderWidth: 0
  }]
},
options: {
  responsive: true,
  plugins: {
    legend: { display: false },
    title: { display: true, text: 'What each criterion costs you (Security = the baseline run)' }
  },
  scales: {
    y: { title: { display: true, text: 'Relative effort' } }
  }
}
{{< /chart >}}


Start with Security. Add criteria in year two, when evidence collection is boring instead of terrifying.

## 4. The chart every team recognises

Here is the strategy teams instinctively reach for, plotted against what a Type II audit actually samples:

{{< chart >}}
type: 'line',
data: {
  labels: ['M1','M2','M3','M4','M5','M6','M7','M8','M9','M10','M11','M12'],
  datasets: [
    {
      label: 'Evidence you produced (the panic strategy)',
      data: [3, 1, 0, 2, 0, 1, 1, 0, 2, 4, 38, 95],
      borderColor: 'rgb(239, 68, 68)',
      backgroundColor: 'rgba(239, 68, 68, 0.15)',
      tension: 0.3,
      fill: true
    },
    {
      label: 'Evidence the auditor samples',
      data: [8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8],
      borderColor: 'rgb(56, 189, 248)',
      backgroundColor: 'rgba(56, 189, 248, 0.15)',
      borderDash: [6, 4],
      tension: 0,
      fill: true
    }
  ]
},
options: {
  responsive: true,
  plugins: {
    legend: { position: 'bottom' },
    title: { display: true, text: 'Observation window: effort vs. sampling' }
  },
  scales: {
    y: { title: { display: true, text: 'Relative volume' } }
  }
}
{{< /chart >}}

The auditor samples **uniformly**. That heroic spike in month eleven is worth nothing for months one through ten, because months one through ten are where the sample came from. The dashed line is the only line that matters, and it is flat, which means the work has to be flat too.

## 5. Domain Expansion: the audit itself

Megumi's Ten Shadows can only summon what has already been trained. You do not get a new shikigami during the fight. You get the ones you did the work for.

An audit is a domain expansion in the most annoying sense: **inside it, attacks land automatically.** You cannot dodge a question about March by being excellent in September. You cannot out-argue a missing offboarding ticket. Being genuinely good at security and having no record of being good at security produce the same report.

There is also the manoeuvre every engineer tries exactly once:

> *"But our cloud provider is SOC 2 certified."*

That is their Infinity, not yours. A vendor's report covers the vendor's controls. Yours still has to explain who at your company can reach production, and when you last checked.

## 6. Where the year actually goes

{{< chart >}}
type: 'doughnut',
data: {
  labels: [
    'Chasing screenshots from 9 people on Slack',
    'Writing policies nobody will read',
    'Actual security engineering',
    'The audit itself',
    'Reading the criteria'
  ],
  datasets: [{
    data: [45, 20, 18, 10, 7],
    backgroundColor: [
      'rgb(239, 68, 68)',
      'rgb(249, 168, 37)',
      'rgb(56, 189, 248)',
      'rgb(139, 92, 246)',
      'rgb(148, 163, 184)'
    ],
    borderWidth: 0
  }]
},
options: {
  responsive: true,
  plugins: {
    legend: { position: 'bottom' },
    title: { display: true, text: 'How SOC 2 time is really spent' }
  }
}
{{< /chart >}}

Every screenshot you take by hand is a control that will fail the moment the person who takes it goes on holiday. **Evidence should be a side effect of the system, not a chore appended to it.** Access reviews come out of your identity provider. Change management comes out of your pull requests. Vulnerability management comes out of your scanner. If a human is pasting an image into Slack once a month, that control is not automated — it is *scheduled*, and schedules break.

## 7. The actual survival kit

1. **Security only, year one.** Add criteria later, from a position of boredom.
2. **Weakest defensible vow.** Quarterly beats monthly. Always.
3. **Say "not applicable" out loud.** No physical datacenter means no physical access control. Write that down instead of inventing a policy about a building you do not have.
4. **One owner with real calendar time.** SOC 2 distributed evenly across a team is SOC 2 owned by nobody, discovered in month eleven.
5. **Automate at the source.** If evidence cannot be exported from a system, the control is already broken.
6. **Start the window when you are ready**, not when the deal is signed. The window is the only part of the schedule you control.
