# qOrbital GitHub Setup Guide

> Companion to the Notion blueprint. This document walks through setting up the GitHub side of the hybrid architecture: Project board, milestones, labels, issue templates, ADR folder, and hardware run logs.

---

## 1. Repository structure

Set up the repo with this layout from day one. It separates code, data, decisions, and ops cleanly.

```
qorbital/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   ├── task.md
│   │   ├── bug.md
│   │   └── hardware_run.md
│   ├── workflows/              # CI/CD
│   └── PULL_REQUEST_TEMPLATE.md
├── qorbital/                   # main package
│   ├── __init__.py
│   ├── chemistry/              # PySCF + Qiskit Nature
│   ├── vqe/                    # VQE solver + IonQ submission
│   ├── bohmian/                # velocity field + trajectory integrator
│   ├── viz/                    # Three.js + PyVista renderers
│   └── webapp/                 # Streamlit/Panel shell
├── notebooks/
│   ├── 01_h2_pipeline.ipynb
│   ├── 02_bohmian_intro.ipynb
│   └── …
├── data/
│   └── runs/                   # hardware run logs (committed)
│       ├── h2/
│       ├── heh+/
│       ├── lih/
│       └── beh2/
├── docs/
│   ├── decisions/              # ADRs (see section 5)
│   │   ├── ADR-template.md
│   │   ├── ADR-001-mapper-choice.md
│   │   └── …
│   ├── log/                    # optional weekly retro notes
│   ├── api/
│   └── tutorials/
├── tests/
├── pyproject.toml
├── README.md
├── LICENSE                     # MIT
└── CONTRIBUTING.md
```

---

## 2. GitHub Projects setup

GitHub Projects is the new task-tracker (the v2 version, not the older "Projects classic"). It does kanban + table + roadmap views over issues with custom fields.

### 2.1 Create the project

1. Go to your repo → **Projects** tab → **New project**
2. Pick **Board** as the starting template
3. Name it `qOrbital Build Plan`

### 2.2 Custom fields to add

Open the project, click `+` next to existing fields, add these:

| Field | Type | Options / notes |
|-------|------|-----------------|
| Status | Single select | Backlog · This Week · In Progress · Blocked · In Review · Done |
| Week | Single select | Week 1–2 · Week 3 · Week 4 · Week 5 · Week 6 · Backlog |
| Owner | Single select | Aryan · Arnav · Both |
| Priority | Single select | P0 (must) · P1 (should) · P2 (nice) |
| Type | Single select | Feature · Bug · Hardware · Docs · Infra · Research |
| Estimate | Number | rough hours, optional |
| Linked ADR | Text | ADR number if relevant, e.g. "ADR-003" |

### 2.3 Views to create

GitHub Projects supports multiple views over the same issues. Create these:

1. **Board (default)** — group by Status. Day-to-day kanban.
2. **By Week** — group by Week field. Your weekly planning view, replaces the per-week pages I had in the old Notion design.
3. **Roadmap** — timeline view, group by Week. Visual Gantt of the 6 weeks.
4. **My queue** — filter `Owner = Aryan` (or Arnav) and `Status != Done`, sort by Priority.
5. **Blocked** — filter `Status = Blocked`. Should be empty most of the time.
6. **Hardware runs** — filter `Type = Hardware`. Tracks IonQ submissions.

### 2.4 Daily/weekly workflow on the board

- **Start of week:** open the **By Week** view, drag this week's items into Status `This Week`.
- **Start of work session:** drag what you're picking up into `In Progress`.
- **End of work session:** update Status (`In Review`, `Blocked`, `Done`). Add a comment on the issue if context matters.
- **End of week:** drag unfinished items into next week or back to Backlog. Hold a 15-min retro, capture in Notion meeting note.

---

## 3. Milestones — the 6-week scaffold

Milestones in GitHub group issues toward a deadline. Create one per phase:

| Milestone | Due date | Description |
|-----------|----------|-------------|
| `Week 1-2: Core Pipeline` | May 10, 2026 | H₂ pipeline + Bohmian engine + Jupyter demo |
| `Week 3: Visualization (Midpoint)` | May 17, 2026 | 3 molecules, dual-view rendering, midpoint demo |
| `Week 4: Hardware Ensemble` | May 24, 2026 | Convergence dashboard + first hardware ensembles |
| `Week 5: Full Hardware Campaign` | May 31, 2026 | LiH ensemble + Lab Mode + docs draft |
| `Week 6: Final Delivery` | June 7, 2026 | PyPI release + web demo + dataset + Qollab listing |

To create: repo → **Issues** tab → **Milestones** → **New milestone**.

**Pre-populating issues:** I'd recommend opening Week 1–2 and Week 3 milestones first and creating one issue per goal from the proposal. Don't pre-fill weeks 4–6 yet — those will shift based on what you learn early on.

### Suggested seed issues for Week 1–2

Copy these into GitHub Issues, assign to the `Week 1-2: Core Pipeline` milestone:

**Infra (Arnav):**
- Set up GitHub repo skeleton with package structure
- Configure CI/CD (lint, test, build) via GitHub Actions
- Set up `pyproject.toml` and dependency pinning
- Add issue + PR templates

**Chemistry pipeline (Aryan):**
- Wire up PySCF integral computation for H₂
- Build Qiskit Nature Hamiltonian construction (JW + parity mapping)
- Implement VQE solver on Aer simulator with UCCSD ansatz
- Extract 1-RDM + reconstruct orbital coefficients from VQE state

**Bohmian engine (Aryan):**
- Implement Bohmian velocity field computation from wavefunction
- Implement adaptive RK trajectory integrator
- Validate against analytical H₂ baseline

**Visualization scaffolding (Arnav):**
- Set up Three.js renderer skeleton
- Set up PyVista renderer skeleton
- Plumb statevector → density grid → renderer

**Integration (Both):**
- Build first end-to-end Jupyter notebook demonstrating H₂ pipeline
- Document install + run instructions in README

---

## 4. Labels

Issue labels for filtering and triage. Set these up under **Issues → Labels**.

**Type:**
- `type: feature` (green)
- `type: bug` (red)
- `type: hardware` (purple) — for IonQ submissions
- `type: docs` (blue)
- `type: infra` (gray)
- `type: research` (yellow)

**Component:**
- `comp: chemistry`
- `comp: vqe`
- `comp: bohmian`
- `comp: viz`
- `comp: webapp`
- `comp: data`

**Status flags:**
- `needs-discussion` — flag for next sync
- `blocked` — explain why in comments
- `good-first-issue` — for if anyone joins later

**Molecule (for hardware issues):**
- `mol: h2`
- `mol: heh+`
- `mol: lih`
- `mol: beh2`

---

## 5. Decision Records (ADRs)

ADRs are short markdown files capturing why you made a non-obvious choice. They're a respected pattern in software projects and are exactly right for a research-y build like this where you'll keep facing forks ("JW or parity mapping?", "RK4 or RK45?", "Streamlit or Panel?").

Place them in `/docs/decisions/`.

### 5.1 ADR template

Create `/docs/decisions/ADR-template.md`:

```markdown
# ADR-NNN: [Short title]

**Status:** Proposed | Accepted | Deprecated | Superseded by ADR-XXX
**Date:** YYYY-MM-DD
**Deciders:** Aryan, Arnav
**Related:** [GitHub issue / PR / meeting note]

## Context

What's the problem? Why is a decision needed now? What constraints apply
(IonQ credit budget, performance needs, time-to-midpoint, etc.)?

## Options considered

### Option A: [name]
- Pros: …
- Cons: …

### Option B: [name]
- Pros: …
- Cons: …

### Option C: [name]
- Pros: …
- Cons: …

## Decision

We chose [option] because …

## Consequences

What does this enable? What does this rule out? What do we need to revisit
later, and under what conditions?
```

### 5.2 Likely early ADRs

Some decisions you'll probably want to record:

- **ADR-001:** Fermion-to-qubit mapping choice (JW vs parity vs BK) per molecule
- **ADR-002:** UCCSD ansatz vs hardware-efficient ansatz tradeoff
- **ADR-003:** Optimizer choice (SLSQP vs COBYLA vs SPSA)
- **ADR-004:** Bohmian trajectory integrator (RK4 fixed vs RK45 adaptive)
- **ADR-005:** Multi-electron projection scheme (natural orbitals from 1-RDM)
- **ADR-006:** Web framework — Streamlit vs Panel
- **ADR-007:** Shot count strategy per molecule (cost/fidelity tradeoff)
- **ADR-008:** Hardware run data format (JSON schema for `/data/runs/`)

You don't need to write these all upfront. Write one when you actually face the choice. The ADR is the artifact of having seriously thought about it.

### 5.3 Linking ADRs

When an ADR exists:
- Reference the ADR number in code comments where the decision is implemented
- Link it from the relevant Notion meeting note (where the discussion happened)
- Link it from the GitHub issue that surfaced the decision

---

## 6. Hardware run logs

Every IonQ submission produces data that's both an experimental result *and* something you'll want to reproduce or audit later. Store run logs as JSON files in the repo so they're version-controlled, diffable, and shippable as part of the gallery dataset.

### 6.1 Folder structure

```
data/runs/
├── h2/
│   ├── 2026-04-29_aria_001.json
│   ├── 2026-04-29_aria_002.json
│   └── …
├── heh+/
├── lih/
└── beh2/
```

### 6.2 Run log JSON schema

Each run gets one file. Suggested schema:

```json
{
  "run_id": "2026-04-29_aria_001",
  "timestamp_utc": "2026-04-29T14:23:11Z",
  "molecule": "H2",
  "geometry": {
    "atoms": [["H", [0, 0, 0]], ["H", [0, 0, 0.74]]],
    "bond_length_angstrom": 0.74,
    "basis": "sto-3g"
  },
  "ansatz": {
    "type": "UCCSD",
    "parameters_initial": [0.0, 0.0, 0.0],
    "parameters_final": [0.114, -0.027, 0.083]
  },
  "mapper": "parity_with_2q_reduction",
  "backend": {
    "provider": "ionq",
    "device": "aria-1",
    "shots": 10000
  },
  "optimizer": {
    "method": "SLSQP",
    "iterations": 47,
    "convergence_history": "h2/2026-04-29_aria_001_convergence.csv"
  },
  "results": {
    "energy_hartree": -1.13728,
    "energy_std_error": 0.00031,
    "classical_reference_hf": -1.11675,
    "classical_reference_fci": -1.13728,
    "wavefunction_amplitudes": "h2/2026-04-29_aria_001_state.npz"
  },
  "cost_credits": 14.20,
  "notes": "Clean run, matches FCI within 1e-5",
  "linked_issue": "#42"
}
```

Store large arrays (convergence history, state vectors, density grids) as separate files referenced by relative path. Keeps the JSON readable.

### 6.3 Hardware run issue template

`.github/ISSUE_TEMPLATE/hardware_run.md`:

```markdown
---
name: Hardware Run
about: Track an IonQ hardware submission
title: "[HW] [Molecule] — [Bond length] — [Date]"
labels: type: hardware
---

## Run Plan
- **Molecule:** 
- **Bond length(s):** 
- **Backend:** Aria / Forte / simulator
- **Shots:** 
- **Estimated cost:** $___ credits

## Pre-flight checklist
- [ ] Circuit compiled and validated on simulator
- [ ] Mapper + ansatz consistent with prior runs (or ADR updated)
- [ ] Cost estimate within budget

## Submission
- **Run ID:** 
- **Submission timestamp:** 
- **Queue wait:** 

## Results
- **Energy:** 
- **Convergence iterations:** 
- **Run log JSON:** `data/runs/[molecule]/[run-id].json`
- **Visualization:** [link]

## Notes
```

---

## 7. CI/CD on GitHub Actions

Bare minimum for week 1–2:

- **Lint + format check** (ruff or black) on every PR
- **Unit tests** (pytest) on every PR
- **Smoke test** that imports the package and runs the H₂ Aer pipeline on every PR

Don't run hardware tests in CI — IonQ credits cost money and CI runs constantly. Hardware runs are manual.

---

## 8. Wiring everything together

The hybrid architecture only works if the cross-references are real. Concretely:

- **Every GitHub issue** — set Week, Owner, Type, Priority. Otherwise the views are useless.
- **Every PR** — link the issue it closes (`Closes #42`) so the issue auto-closes on merge.
- **Every architectural decision** — gets an ADR. Write it up the same day, not later.
- **Every meeting** — Notion note, with GitHub issue links for code action items.
- **Every hardware run** — issue + run log JSON + commit. The run log lives forever as part of the gallery dataset.
- **Every reference cited in code or docs** — has a Notion entry. Cross-link by URL from code comments.

If you find yourself maintaining the same info in two places, the architecture is broken — fix it.

---

## 9. First-day checklist

A concrete sequence for the first day of Week 1–2:

1. Create the GitHub repo (`qorbital`) with MIT license, README stub
2. Push the folder structure from section 1 (empty `__init__.py` files OK)
3. Create the GitHub Project, add custom fields (section 2.2), set up the 6 views (section 2.3)
4. Create all 5 milestones (section 3)
5. Create the labels (section 4)
6. Add the issue templates from sections 5 + 6
7. Add the ADR template
8. File the Week 1–2 seed issues (section 3, end), assign to milestone, set Owner
9. Set up GitHub Actions CI for lint + test
10. Set up the Notion hub from the blueprint
11. Hold a 30-min kickoff sync, log it as Notion meeting note #1, capture action items as GitHub issues

Total time: roughly 2–3 hours for both of you in parallel.