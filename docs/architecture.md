# Architecture

This document describes the conceptual architecture of the Supervisor, a self-recovering automation manager. The production implementation handles real process control; this public model demonstrates the same decision categories through a lightweight state machine.

## Component overview

```
                    +------------------------+
                    |      CLI / Monitor     |
                    |  Commands / Display    |
                    +-----------+------------+
                                |
                                v
                    +------------------------+
                    |   Supervisor Engine    |
                    |  Main Monitor Loop     |
                    |  (~10s adaptive cycle) |
                    +-----------+------------+
                                |
          +---------------------+---------------------+
          |                     |                     |
          v                     v                     v
  +--------------+    +-----------------+    +------------------+
  |   Scheduler  |    |  Safety Gates   |    | Project Registry |
  |              |    |                 |    |                  |
  | Priority     |    | Network state   |    | Configured       |
  | Capacity     |    | Resource pressure|   | projects with    |
  | Cooldown     |    | Pause/sleep     |    | lifecycle        |
  | Eligibility  |    | Recovery block  |    | contracts        |
  +------+-------+    +--------+--------+    +--------+---------+
         |                     |                      |
         +---------------------+----------------------+
                               |
                               v
                    +------------------------+
                    |  Project Lifecycle     |
                    |  Start / Stop / Run    |
                    |  Recovery / Retry      |
                    +-----------+------------+
                                |
                                v
                    +------------------------+
                    |   Process Manager      |
                    |  Ownership / Identity  |
                    |  Output / Exit Watch   |
                    +-----------+------------+
                                |
                                v
                    +------------------------+
                    |  Observation Layer     |
                    |  Completion Proof      |
                    |  Health Checks         |
                    |  Structured Events     |
                    +-----------+------------+
                                |
                                v
                    +------------------------+
                    |  State Persistence     |
                    |  Recovery / Reconcile  |
                    +------------------------+
```

## Module responsibilities

| Module | Responsibility |
|--------|---------------|
| **Engine** | Central decision loop. Owns the runtime cycle, state persistence, operator commands, and all scheduling/shutdown/recovery decisions. |
| **Project Registry** | Generic project definitions with type-specific lifecycle contracts. Rejects duplicates, missing fields, and unsafe configurations. |
| **Scheduler** | Produces explicit decisions (START, WAIT_CAPACITY, WAIT_COOLDOWN, BLOCKED, PAUSED, REPAIR_REQUIRED, ALREADY_RUNNING, DISABLED). Does not directly launch processes. |
| **Safety Gates** | Observations consumed by the scheduler: network state, resource pressure, pause state, recovery block, battery, user idle time. Health checks report facts; they do not start or stop projects. |
| **Process Manager** | Owns launched child processes. Verifies identity through PID + creation timestamp. Maintains output buffers and exit watches. Never trusts PID files alone. |
| **State Persistence** | Atomic JSON snapshots written each cycle. Crash-safe with backup files. A restart must not make the system forget what happened. |
| **Observation Layer** | Completion verification, health checks, structured event logging. Distinguishes process exit from work completion. |
| **Recovery Manager** | Detects unclean shutdowns, inspects interrupted transactions, reconciles stale ownership, and holds ambiguous projects until verified. |

## State machine

### Project lifecycle states

| State | Meaning |
|-------|---------|
| **READY** | Eligible for scheduling. Not running, not in cooldown, not held. |
| **STARTING** | Launch initiated, within the start grace window. Process identity being confirmed. |
| **RUNNING** | Process confirmed alive with verified identity. Actively executing. |
| **STOPPING** | Graceful stop requested. Awaiting child acknowledgment and exit verification. |
| **STOPPED** | Process confirmed exited. Completion proof verified (or absent). Ready for relaunch. |
| **COOLDOWN** | Temporary failure. Waiting for cooldown timer before retry. |
| **REPAIR_REQUIRED** | Durable failure. Requires operator action or verified fix evidence. Not auto-retried. |
| **PAUSED** | Held by operator or network loss. Resumes when the hold is released. |
| **RECOVERING** | Prior session unclean. Ownership unverified. Held until inspection completes. |

### Legal transitions

```
READY -----------> STARTING, PAUSED
STARTING --------> RUNNING, COOLDOWN, REPAIR_REQUIRED, STOPPED
RUNNING ---------> STOPPING, COOLDOWN, REPAIR_REQUIRED, PAUSED, STOPPED
STOPPING --------> STOPPED, RECOVERING
STOPPED ---------> RECOVERING, READY
COOLDOWN --------> READY, REPAIR_REQUIRED, PAUSED
REPAIR_REQUIRED --> RECOVERING, READY, PAUSED
PAUSED ----------> READY, STOPPED
RECOVERING ------> READY, STOPPED, REPAIR_REQUIRED
```

Key invariant: transitions are validated against this table. No arbitrary state mutation is allowed.

## Recovery after unclean shutdown

```
                    Supervisor crashes
                           |
                           v
                  +------------------+
                  | Next startup     |
                  +--------+---------+
                           |
                           v
                  +------------------+
                  | Load persisted   |
                  | state from disk  |
                  +--------+---------+
                           |
                           v
                  +------------------+
                  | Prior session    |
                  | marker present?  |
                  +---+----------+---+
                      |          |
                    YES         NO
                      |          |
                      v          v
              +------------+  +------------+
              | UNCLEAN    |  | CLEAN      |
              | RECOVERY   |  | START      |
              +-----+------+  +-----+------+
                    |               |
                    v               v
          +------------------+  Normal
          | Inspect all      |  scheduling
          | running projects |  begins
          +--------+---------+
                   |
                   v
          +------------------+
          | For each project:|
          | - Is process     |
          |   still alive?   |
          | - Is ownership   |
          |   ambiguous?     |
          +--------+---------+
                   |
          +--------+--------+
          |                  |
       ALIVE             ABSENT
          |                  |
          v                  v
   Re-adopt process    Clear for
   (RUNNING)           relaunch (STOPPED)
```

## Process ownership

The Supervisor maintains a single-owner model: one manager owns all child processes. The Task Scheduler (or equivalent) starts only the manager; the manager starts everything else.

### Identity verification

Every process match uses two factors:
- **PID**: process identifier
- **Creation timestamp**: Windows process birth marker (equivalent to `GetProcessTimes`)

A live process with a different birth time proves the original exited and the OS reused its PID. The Supervisor never trusts a PID file or stored PID alone.

### Ownership lifecycle

```
Launch initiated
       |
       v
PID + birth marker captured
       |
       v
Process confirmed alive
(identity verified each cycle)
       |
       v
Stop requested
       |
       v
Stop receipt verified
(correlated request ID + PID + birth marker)
       |
       v
Process exit confirmed
(exact identity match)
       |
       v
Ownership released
```

## Stop transactions

Stopping a project is modeled as a multi-phase transaction:

```
REQUESTED
    |
    v
IDENTIFY_OWNER  (find exact process by PID + birth marker)
    |
    v
SIGNAL          (write stop file / send termination signal)
    |
    v
WAIT            (poll for child acknowledgment)
    |
    v
VERIFY_EXIT     (confirm process gone, identity match)
    |
    v
FINALIZE_STATE  (update persisted state, release ownership)
```

Each phase is recorded. If any phase fails, the transaction enters an attention state rather than silently claiming success. The scheduler cannot relaunch a project while its stop transaction is unresolved.

## Scheduling decisions

Each cycle, the scheduler evaluates:

1. **Is automation paused?** Operator hold blocks all starts.
2. **Is the network healthy?** Network degradation blocks new work.
3. **Are safety gates clear?** Resource pressure, battery, recovery state.
4. **Is the project eligible?** Enabled, not running, not in cooldown, not repair-latched.
5. **Does it fit capacity?** Weight-based admission control prevents overload.
6. **Has the attempt budget been exhausted?** Exceeded budget moves to REPAIR_REQUIRED.
7. **Is duplicate ownership prevented?** Already running = skip.

The scheduler produces an explicit decision for every project every cycle. Decisions are recorded as structured events.

## Completion verification

The Supervisor distinguishes two observations:

| Observation | Meaning |
|-------------|---------|
| Process exited | The child process is no longer running |
| Work completed | A fresh, identity-bound artifact confirms success |

Process exit alone is never treated as completion. The Supervisor requires:
1. Fresh child-specific artifact or log evidence
2. Pattern matching against required/success/attention markers
3. Exact process exit with identity verification
4. (For shutdown) A correlated result artifact matching the specific stop request

## Health and degraded mode

Health checks are observations, not actions:

| Signal | Source |
|--------|--------|
| Network availability | DNS/HTTP probes |
| Process health | PID + birth marker inspection |
| Resource pressure | CPU, RAM, battery, process count |
| Supervisor heartbeat | State file update frequency |
| State store health | Atomic write verification |

If monitoring data becomes unavailable, the system enters degraded mode: daily job admission is blocked, but live projects continue. The system prefers safe hold over optimistic start.

## Retry vs repair-required

| Path | Trigger | Resolution |
|------|---------|------------|
| Temporary failure | Network timeout, brief crash | Cooldown timer expires -> READY |
| Repair-required | Auth failure, config error, budget exhaustion | Operator action or verified fix evidence |

Repair-required states are latched: subsequent successes must provide fresh, verified proof to clear them. This prevents retry storms on durable problems.

## Structured logging

Every lifecycle event provides:
- Timestamp
- Severity (INFO, WARN, CRITICAL)
- Component (supervisor, scheduler, process_manager)
- Project name
- Operation (start, stop, transition, recovery)
- Decision (allow, skip, hold, block)
- Reason (human-readable explanation)
- State transition (old_state -> new_state)
- Attempt number
- Correlation ID (where applicable)

The production system writes a machine-readable decision summary each cycle as a full audit trail.

## Design principles

1. **Safety over throughput.** Preventing duplicate or incompatible actions takes priority over starting work quickly.

2. **Fail-closed ambiguity.** When the system cannot determine process state, marker validity, or telemetry reliability, it holds the current safe state. It never guesses.

3. **Evidence-based completion.** Process exit, exit codes, and generic success lines are never trusted alone. Every completion requires fresh, identity-bound proof.

4. **Single-owner process model.** One manager owns all child processes. This eliminates duplicate-launch and split-brain problems.

5. **PID-reuse-safe identity.** Every process match combines PID + creation timestamp. This prevents a new, unrelated process from being mistaken for a managed child.

6. **Archetype-separated lifecycles.** Different project types (live, scheduled, local) share a registry but have separate lifecycle contracts. This prevents one type from inheriting unsafe behavior from another.

7. **Immutable proof artifacts.** Stop receipts, shutdown results, and completion markers are versioned. Mutable state is updated only after proof publication.

8. **Bounded concurrency.** Nothing loops forever. Attempt budgets are finite. Network backoffs escalate through defined levels. Repository publication uses a bounded worker pool.

9. **Recovery is explicit.** After an unclean shutdown, the system does not silently assume health. It inspects, reconciles, and only then resumes.

10. **Observability is structural.** Every decision produces a structured audit trail. Logs are useful for both human debugging and automated diagnosis.
