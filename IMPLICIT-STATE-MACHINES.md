# Implicit State Machine Audit — Supervisor Public

Scope: all tracked source files (`git ls-files`), excluding tests-as-fixtures and
docs. The repository is small (~500 lines of package source).

**Headline:** the core project lifecycle is an *explicit* state machine —
`ProjectState` enum (`src/supervisor_public/model.py:16`) plus a validated
`LEGAL_TRANSITIONS` table (`model.py:37`) enforced by
`SupervisorEngine._transition()` (`src/supervisor_public/engine.py:54-72`).
That is the correct pattern and is **not** a finding. The implicit machines
below live *around* it: supervisor-level run modes encoded as loose booleans,
and an attempt-budget lifecycle encoded as a magic counter with no writer.

Context note: `model.py:3-6` and `docs/architecture.md:98-118` state that the
*production* (private) Supervisor models project state as "a conjunction of
orthogonal flags" — ~14 documented fields (`pids`, `cooldown_until`,
`restart_hold_until`, `restart_hold_indefinite`, `shutdown_requested`,
`shutdown_verified`, `shutdown_failure_latched`, ...). That upstream
flag-conjunction machine is exactly the pattern this audit targets, but it is
not present in this repository's code; noted for context only.

## Supervisor run-mode (network × operator-hold) encoded in independent booleans

**States**

- `NORMAL` — scheduling proceeds
- `NETWORK_HOLD` — connectivity lost; new starts held, RUNNING projects parked
- `OPERATOR_HOLD` — automation paused by operator; new starts held
- `NETWORK_HOLD + OPERATOR_HOLD` — both holds active simultaneously

**Encoded as**

Two independent booleans on `SupervisorEngine`, declared at
`src/supervisor_public/engine.py:32-33`:

- `network_ready: bool = True`
- `automation_paused: bool = False`

They are read together only at the scheduling gate
(`engine.py:95-100`) — `if self.automation_paused ... if not
self.network_ready` — so the combined mode exists nowhere as a named value.

A third, related flag hides inside the project enum itself: `PAUSED` is used
for *both* "paused by network loss" (`engine.py:225`) and, per
`docs/architecture.md:82` (`RUNNING --> PAUSED : network loss or operator
hold`), "operator hold". The pause *cause* is never recorded — only the
human-readable `last_reason` string, which the next transition overwrites.

**Invalid combos**

- `automation_paused=True` is **unreachable**: nothing in the package ever
  writes the field (grep-verified — declared at `engine.py:33`, read at
  `engine.py:95`, no setter/API). The OPERATOR_HOLD state is representable but
  cannot be entered; it can only be simulated by mutating the dataclass field
  directly, bypassing any invariant.
- PAUSED-by-operator × `recover_network()`: representable and silently wrong
  (see Risk).
- `network_ready` flipped while `automation_paused` would be set: the two
  holds have no ordering/interaction rule — recovery clears one hold's effects
  regardless of the other.

**Transitions**

- `disconnect()` → `network_ready = False`, `engine.py:221`; parks every
  RUNNING project as PAUSED (`engine.py:224-225`)
- `recover_network()` → `network_ready = True`, `engine.py:233`; releases
  **every** PAUSED project → READY unconditionally (`engine.py:235-237`)
- `automation_paused`: no transition site exists (dead flag)

**Risk**

*Medium.* `recover_network()` unconditionally moves `PAUSED → READY`
(`engine.py:235-237`). Because PAUSED conflates network-pause and
operator-pause, an unrelated network flap-and-recovery silently releases a
project an operator parked — the operator's hold is lost with no record
(`disconnect()` at `engine.py:224` also skips already-PAUSED projects, so the
network hold never even "stacks"). Separately, the dead `automation_paused`
gate gives a false impression that operator pause is implemented; a caller who
sets the field gets pause-on-new-scheduling only, with running work,
resume semantics, and network interplay all undefined.

## Attempt-budget lifecycle encoded as a magic counter with no writer

**States**

- `BUDGET_FRESH` / `BUDGET_PARTIAL` — `attempts < max_attempts`: eligible to start
- `BUDGET_EXHAUSTED` — `attempts >= max_attempts`: forced to REPAIR_REQUIRED

(`attempts` can take values `0..max_attempts` — more representable states than
the two meaningful phases, and every integer in between is a "state" only the
threshold comparison understands.)

**Encoded as**

Two plain ints on `Project` — `attempts: int = 0`, `max_attempts: int = 3`
(`src/supervisor_public/model.py:64-65`) — compared numerically at
`engine.py:114`: `if project.attempts >= project.max_attempts`.

**Invalid combos**

- `attempts < 0` or `attempts > max_attempts`: representable, no invariant.
- `max_attempts` is a mutable per-instance field; `attempts` can be rewound or
  fast-forwarded externally with no validation (tests do exactly this,
  `tests/test_engine.py:59`).
- `attempts=0` with `last_reason` implying prior retries: counter and reason
  string can disagree; nothing keeps them coherent.

**Transitions**

- Exhaustion (READY → REPAIR_REQUIRED): `engine.py:114-116` inside `schedule()`
- Reset on repair acknowledgment: `project.attempts = 0`, `engine.py:178`
- Increment site: **none** — `attempts` is never incremented anywhere in the
  package (verified by grep over `src/`). It is only read (`engine.py:114`),
  reset (`engine.py:178`), echoed into every transition event as telemetry
  (`engine.py:71`), and set directly by tests. The lifecycle's transition
  side does not exist in production code.

**Risk**

*Low–medium.* The exhaustion guard can never fire in real operation, so the
"attempt budget" is a safety check that provides false confidence — the demo
and docs advertise bounded retries (`docs/architecture.md:276`, "Attempt
budgets are finite") while the counter that enforces the bound stays at 0
forever. If increment sites are added later at inconsistent points (per
transition? per failure? per schedule attempt?), the threshold comparison at
`engine.py:114` will start firing with semantics nobody pinned down — and it
currently fires at schedule time from READY, conflating "exhausted" with
"durable failure" into the same REPAIR_REQUIRED bucket the operator-ack
path treats as a latch.

---

## Non-findings (checked, excluded)

- `ProjectState` + `LEGAL_TRANSITIONS` — explicit enum machine, consistently
  validated (`model.py:16-47`, `engine.py:54-72`).
- `Event.level` "INFO"/"WARN" — severity label chosen at one site
  (`engine.py:66`), never used for decisions.
- `fail(repair_required: bool)` (`engine.py:139`) and
  `reconcile_recovering(alive: bool)` (`engine.py:270`) — lone boolean
  parameters selecting between two *explicitly named* enum states; single
  decision sites.
- `monitor.py` hardcoded "IDLE"/status strings — static display text, never
  compared.
- `os.name == "nt"` (`monitor.py:16`), `--dry-run`, `--once` — platform/CLI
  flags, not lifecycle state.
