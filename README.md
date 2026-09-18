# Supervisor Public

A sanitized architectural model of a self-recovering automation supervisor.

This repository publicly represents the architecture, state flow, recovery philosophy, and engineering decisions behind a private production supervisor that coordinates multiple long-running automation projects. It is not the production system itself.

## What the Supervisor does

The Supervisor is not one automation script. It is a manager that decides what should run, tracks project state, starts and stops projects, prevents duplicate ownership, detects failures, distinguishes recoverable errors from states requiring intervention, enforces cooldowns, verifies completion, and maintains consistent state after unexpected shutdowns.

The production implementation handles real process ownership, interactive terminal sessions, marketplace compatibility, authentication lifecycle detection, network-aware scheduling, and repository publication barriers. This public model communicates the same architectural concepts through a lightweight, deterministic state machine.

## Architecture

```
                  +---------------------+
                  |    Supervisor UI    |
                  |  CLI / Monitor      |
                  +----------+----------+
                             |
                             v
                  +---------------------+
                  |  Supervisor Engine  |
                  |  State + Decisions  |
                  +----------+----------+
                             |
               +-------------+-------------+
               v             v             v
          Scheduler     Safety Gates   Project Registry
               |             |             |
               +-------------+-------------+
                             |
                             v
                  +---------------------+
                  | Project Lifecycle   |
                  | Start / Stop / Run  |
                  | Recovery / Retry    |
                  +----------+----------+
                             |
                             v
                  +---------------------+
                  | Managed Projects    |
                  | Workers / Syncs     |
                  +----------+----------+
                             |
                             v
                  +---------------------+
                  | Observation + State |
                  | Health / Events /   |
                  | Completion Proof    |
                  +----------+----------+
                             |
                             v
                  +---------------------+
                  | Recovery / Reconcile|
                  +---------------------+
```

Every cycle, the engine:

1. Validates configuration, cooldowns, and safety gates
2. Inspects process ownership (PID + creation-time identity in production)
3. Evaluates network, resource, and pause state
4. Selects the highest-priority eligible project that fits capacity
5. Observes results through completion evidence, not just process exit
6. Persists state atomically for crash recovery

## Lifecycle

Projects move through explicit states with validated transitions:

```
READY
  |
  v
STARTING -----> COOLDOWN (temporary failure)
  |                |
  v                v
RUNNING         READY (after cooldown)
  |
  +--> STOPPING --> STOPPED
  |
  +--> COOLDOWN --> READY
  |
  +--> REPAIR_REQUIRED (durable failure; requires operator action)
  |
  +--> PAUSED (network loss or operator hold)
```

Key design principle: **a failed state never auto-resolves downward in severity.** Repair-required projects remain visible until real fix evidence or an explicit operator acknowledgment returns them to the eligible queue.

## Recovery philosophy

The important design principle is not simply "if something crashes, restart it."

The Supervisor first determines what state the system is actually in, verifies ownership and process identity where necessary, and only then decides whether recovery is safe. After an unexpected shutdown:

1. Load persisted state
2. Determine whether the previous session ended cleanly
3. Inspect persisted process ownership records
4. Reconcile against current OS processes
5. Detect stale or ambiguous ownership
6. Recover safe projects
7. Hold unsafe or ambiguous projects
8. Only then enter normal scheduling

This prevents the system from blindly relaunching a process that may still be running, or losing in-flight work from an interrupted shutdown.

## Process ownership

The Supervisor must know which process belongs to which managed project. A PID alone is not enough.

The production implementation verifies process identity through PID plus Windows creation timestamp (birth marker). A live process with a different birth time proves the original exited and the operating system reused its PID. The Supervisor never trusts a PID file or Task Scheduler state without independent verification.

This prevents duplicate launches, misattributed exits, and stale state from corrupting the system.

## Completion verification

Process exit is not proof that work succeeded.

The Supervisor distinguishes two observations:

- **Process exited**: the child process is no longer running
- **Work completed**: a fresh, identity-bound, timestamp-correlated artifact confirms the operation succeeded

A stale completion marker, partial output, or exit code zero from an unknown run is never accepted as proof. Every completion requires verified evidence from the specific run that was launched.

## Stop transactions

Stopping a project is not a single operation. It is a transaction with phases:

```
REQUESTED -> SIGNAL -> WAIT -> VERIFY_EXIT -> FINALIZE_STATE
```

Each phase is recorded. If the child does not exit within the timeout, the Supervisor holds the failure rather than silently claiming success. The scheduler cannot relaunch a project while its stop transaction is unresolved.

## Retry vs repair-required

The Supervisor separates temporary failures from failures requiring intervention.

**Temporary failure** (retry with cooldown):
```
RUNNING -> COOLDOWN -> READY
```

**Repair-required failure** (latched until explicit action):
```
RUNNING -> REPAIR_REQUIRED
```

A repair-required project does not automatically restart because the next scheduler cycle occurs. It requires fresh verified evidence or an explicit operator acknowledgment before returning to the eligible queue. This prevents retry storms on durable problems.

## Authentication state

The production Supervisor detects authentication state through read-only verification (not login attempts). The detection flow:

```
DETECT -> DECISION -> AUTH REQUEST -> RESULT -> RECONCILIATION
```

Only a confirmed logged-out state triggers automatic re-authentication. Transient, human, or unknown states are never auto-triggered. The child process owns the attempt budget and cooldown logic.

This public model represents the concept without any real authentication implementation.

## Remote control

The production Supervisor exposes a loopback HTTP gateway for remote commands (start, stop, force-rerun, status). Commands are serialized through a control request queue with correlation IDs for audit trails. The gateway is bound to localhost and authenticated through the operating system's identity.

This public model demonstrates the CLI interface. The remote control architecture is documented but not implemented.

## Observability

Every decision produces structured information: timestamp, severity, component, project, operation, event, decision, reason, state transition, and attempt number.

The production system writes a machine-readable decision summary each cycle, maintains atomic state snapshots, and preserves per-run archives with timestamps and exit codes. Logs use semantic event names (not arbitrary strings) so they are useful for both human debugging and automated diagnosis.

## Failure isolation

One project failing should not corrupt the state of unrelated projects. Each project maintains independent state, cooldown timers, attempt counters, and repair-latch conditions. A failure in one project does not prevent other eligible projects from being scheduled.

## Running the demo

```bash
# Run the demonstration scenario
python demo.py

# Or with the installed entry point
supervisor-demo

# View the monitor display (single frame)
python monitor.py --once

# View the monitor display (refreshing loop)
python monitor.py
```

The demo exercises scheduling, network recovery, failure handling, repair-required state, graceful stop, and unclean-shutdown recovery. No processes are spawned and no external state is modified.

## Running the tests

```bash
python -m unittest discover -s tests -v
```

## Project layout

```
src/supervisor_public/
  __init__.py       Package exports
  model.py          Project states, events, transition rules
  engine.py         Supervisor engine (state machine + decisions)
  cli.py            Demo scenario runner
  monitor.py        Terminal monitor display

tests/
  test_engine.py    Engine state transitions and recovery
  test_monitor.py   Monitor safety invariants
  test_public_copy.py  Documentation quality checks

docs/
  architecture.md   Detailed architecture documentation
```

## Public vs private

This repository is a sanitized public architectural model. It communicates the same major concepts, state flows, and engineering decisions as the production Supervisor while containing no private infrastructure, project names, credentials, URLs, business logic, or other sensitive information.

The production implementation adds: real process hosting with PID-reuse-safe identity, interactive terminal sessions, multi-phase stop transactions with SHA-256 evidence digests, unclean-session recovery with orphan detection, marketplace compatibility enforcement, network-aware scheduling with escalating backoff, authentication lifecycle detection, repository publication barriers, and a Textual-based terminal UI.

The engineering in this repository is real. The example projects are generic.

## License

MIT
