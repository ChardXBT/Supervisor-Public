# Self-Recovering Automation

Self-Recovering Automation is a public reference implementation of a control
plane for long-running and scheduled software. It demonstrates how one manager
can decide what should run, prevent duplicate starts, isolate failures, pause
work during unsafe conditions, and recover without guessing that an interrupted
job succeeded.

The repository is intentionally integration-free. It models the orchestration
and recovery behavior with synthetic workflows so the design can be studied and
run without accounts, credentials, background services, or external actions.

## Monitor-only view

The image below is a real capture of the included Windows terminal monitor. It
was opened in monitor-only mode, contained only synthetic idle workflows, and
was captured at the window boundary so no user path or account information is
visible.

![Monitor-only terminal](assets/monitor-only.png)

Run the same screen locally:

```bash
python monitor.py
```

Render one frame without opening a persistent monitor:

```bash
python monitor.py --once
```

## The problem it solves

A script can be reliable in isolation and still fail as part of a larger
system. Common failure modes include:

- several due jobs starting together after a reboot;
- a process exiting without producing valid completion evidence;
- a temporary network outage being mistaken for a permanent failure;
- a stale process identifier being mistaken for a live process;
- a failed job preventing unrelated jobs from running;
- an automatic restart fighting a user who intentionally stopped the system;
- recovery beginning before saved state is known to be consistent.

The manager addresses these as state transitions rather than scattered retry
loops. Observation, policy, and action remain separate, making every decision
explainable and testable.

## System model

```text
health observations ──> safety policy ──> capacity-aware priority queue
        │                      │                       │
        │                      v                       v
        └────────────> recovery state machine ──> job lifecycle
                               │                       │
                               └──── structured decisions ────┘
```

### 1. Observation layer

The public demo treats health inputs as facts, not commands. A production
adapter could report process liveness, connectivity, machine load, completion
artifacts, or operator state. The policy layer decides what those facts permit.

### 2. Safety policy

Global conditions can block all new work, while job-specific failures affect
only one workflow. The distinction prevents one broken integration from
shutting down an otherwise healthy automation platform.

### 3. Weighted priority queue

Each workflow has a priority and resource weight. The scheduler selects only
jobs that fit remaining capacity, preventing the classic recovery storm where
every overdue task starts at once.

### 4. Explicit lifecycle states

```text
READY ──> RUNNING ──> COMPLETE
  ▲           │
  │           ├──> PAUSED ───────────────┐
  │           ├──> COOLDOWN ─────────────┤
  │           └──> ATTENTION             │
  └──────────────────────────────────────┘
```

- `PAUSED` preserves work across a global safety event.
- `COOLDOWN` represents a retryable failure with delayed eligibility.
- `ATTENTION` represents a durable condition that must not self-clear.
- `COMPLETE` requires explicit proof; process exit alone is insufficient.

## Reliability invariants

| Invariant | Why it matters |
| --- | --- |
| One identity, one active instance | Prevents duplicate work after races or restarts |
| Completion requires proof | An empty or interrupted run cannot look successful |
| Failure scope is explicit | One workflow failure does not stop unrelated work |
| Recovery is gated | Work resumes only after the recovery condition is verified |
| Priority is capacity-aware | Important work wins without overloading the host |
| Durable failures remain visible | The manager never loops forever on a known-broken job |
| Monitor-only cannot act | Diagnostics cannot accidentally launch or modify workflows |

## Deterministic failure demonstration

`demo.py` runs the state machine through a reproducible sequence:

1. schedule work by priority and capacity;
2. simulate a connectivity loss;
3. checkpoint active workflows;
4. verify recovery;
5. resume eligible work;
6. accept completion only after explicit proof.

```bash
python demo.py --dry-run
```

The demonstration never starts an operating-system process or contacts an
external service.

## Testing strategy

The test suite covers behavior, not just individual functions:

- capacity limits prevent start storms;
- disconnects pause work without marking it complete;
- cooldowns require explicit release;
- durable failures are not retried automatically;
- monitor output remains fixed-width and identity-free;
- monitor-only language clearly states that launches and writes are blocked.

```bash
python -m unittest discover -s tests -v
```

The same commands run in GitHub Actions on every push and pull request.

## Repository layout

```text
.
├── assets/monitor-only.png
├── docs/architecture.md
├── scripts/capture_monitor.ps1
├── src/self_recovering_automation/
│   ├── engine.py       # Priority, capacity, failure, and recovery decisions
│   ├── model.py        # Typed workflow states and events
│   ├── monitor.py      # Stable monitor-only screen model
│   └── cli.py          # Deterministic recovery demonstration
├── tests/
├── demo.py
├── monitor.py
└── pyproject.toml
```

## Public boundary

This repository demonstrates control-plane architecture, not production
integrations. It contains no service adapters, credentials, user identifiers,
machine-specific configuration, or private operational rules. The production
system that inspired it adds persistent state, interactive terminal hosting,
and integration contracts behind the same safety boundaries.

See [the architecture notes](docs/architecture.md) for a compact design map.
