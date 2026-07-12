# Architecture

This public repository models the control plane of a resilient automation
manager without containing any production adapters.

```text
health signals -> safety gates -> priority queue -> job state machine
      |                |               |                 |
      +------ structured decision and recovery events ---+
```

## Design boundaries

- **Observation is separate from action.** Health checks produce facts; policy
  decides whether an action is allowed.
- **Starts are capacity-aware.** A weighted queue prevents a restart storm
  after a machine or network recovery.
- **Failure types are explicit.** Temporary failures enter cooldown; durable
  failures require attention; neither is silently called a success.
- **Completion needs proof.** A process exit alone is not modeled as completed.
- **Recovery is conservative.** Work resumes only after the recovery signal is
  explicitly verified.

The production system that inspired this demonstration adds operating-system
process hosting, interactive terminal panes, persistent state, and integration
adapters. Those details are intentionally excluded from this public version.
