# Crossing Audit Report: Celery

**Project:** celery (celery/celery)
**Version:** 5.5.x (main branch, Feb 2026)
**Scanned:** 2026-02-22
**Tool:** Crossing Semantic Scanner v0.9

---

## Executive Summary

Celery has **64 semantic boundary crossings**, with **27 at elevated or high risk** — the highest count of any project scanned to date. For a 413-file distributed task framework with 631 raise sites and 788 handlers, the sheer scale of exception surface area creates many opportunities for semantic collapse.

The three most critical production findings involve **handler collapse** in the worker lifecycle: `WorkerTerminate` (3 raise sites, 1 handler), bare `Exception` (119 raise sites, 126 handlers), and `KeyError` (50 raise sites, 140 handlers). The `WorkerTerminate` finding is the most structurally interesting — three different shutdown pathways funnel into a single handler that cannot distinguish between them.

**Risk Level:** High. The combination of a massive exception surface area, heavy use of bare `Exception` catches, and critical worker lifecycle crossings makes Celery the most crossing-dense production codebase scanned.

---

## Findings

### HIGH RISK: `WorkerTerminate` — 3 raise sites, 1 handler

**Files:** `apps/worker.py`, `worker/state.py`, `worker/consumer/consumer.py`
**Impact:** Three different shutdown pathways raise `WorkerTerminate`:
- `on_hard_shutdown` (`apps/worker.py:335`) — signal handler for SIGTERM/SIGQUIT
- `maybe_shutdown` (`worker/state.py:91`) — state-based shutdown check
- `Consumer.start` (`worker/consumer/consumer.py:363`) — consumer loop shutdown

Only one handler exists: `WorkController.start` (`worker/worker.py:204`).

**Why this matters:** The handler cannot distinguish between a signal-triggered shutdown, a state-check shutdown, and a consumer-initiated shutdown. In a distributed system, these have different implications: a signal shutdown may mean the node is being drained (tasks should be requeued), a state shutdown may mean a critical error was detected, and a consumer shutdown may mean the broker connection died. The handler treats all three identically.

**Recommendation:** Add a `reason` attribute to `WorkerTerminate` (e.g., `WorkerTerminate(reason="signal")`, `WorkerTerminate(reason="state_check")`, `WorkerTerminate(reason="consumer")`). This allows the handler — and any monitoring/logging downstream — to distinguish shutdown pathways without changing the control flow.

### HIGH RISK: Bare `Exception` — 119 raise sites, 126 handlers

**Files:** Throughout the codebase (93 different functions/methods)
**Impact:** Bare `except Exception` handlers appear 126 times across the codebase. 119 of these handlers have no direct `Exception` raises in their try body — they catch from called functions only. This means almost every handler is a cross-function crossing where the handler cannot know what it's catching.

Key locations:
- `Blueprint.send_all` (`bootsteps.py:149`) — catches any exception during bootstep execution
- `Scheduler.apply_entry` (`beat.py:283`) — catches any exception during beat task scheduling
- `trace_task` (`app/trace.py`) — catches any exception during task execution

**Why this matters:** In a task framework, bare `Exception` handlers are sometimes intentional (tasks can raise anything, and the framework must be resilient). But 119 sites catching without distinguishing means that novel failure modes — OOM, serialization errors, broker disconnects — all route through the same error handling path. When celery "swallows" an exception, it's often one of these handlers.

**Recommendation:** This is partially architectural — a task framework must catch broadly. The actionable improvement is structured logging at catch sites: log `type(exc).__name__` and `exc.args` at every bare `except Exception` handler, so that when a task silently fails, the exception type is always visible in logs.

### HIGH RISK: `KeyError` — 50 raise sites, 140 handlers

**Files:** Throughout the codebase (48 different functions/methods)
**Impact:** `KeyError` is the most heavily handled exception in celery — 140 handlers for 50 raise sites. 127 handlers have no direct `KeyError` raises in their try body. Key raise sites include:
- `Blueprint._finalize_steps` (`bootsteps.py:249`) — missing bootstep dependency
- `parse_uid` / `parse_gid` (`platforms.py:446/463`) — unknown system user/group
- `crontab_parser._expand_number` (via call chain) — invalid crontab spec

Key handlers include:
- `Signature.freeze` (`canvas.py:501`) — catches during task chain construction
- `ResultSet.remove` (`result.py:596`) — catches during result cleanup
- 135 more handlers across the codebase

**Why this matters:** `KeyError` is Celery's most polymorphic exception. A missing crontab field, a missing bootstep, and a missing system user all raise `KeyError`. Many handlers catch `KeyError` with fallback behavior (return default, skip step), meaning a novel `KeyError` from an unexpected source is silently swallowed and treated as "key not found — use default." This is the classic semantic crossing pattern.

**Recommendation:** For the most critical paths (bootstep resolution, user/group parsing), use custom exceptions. `BootstepNotFound` and `InvalidUserSpec` would prevent accidental catching by the 140 `KeyError` handlers.

### MEDIUM RISK: `RuntimeError` — 38 raise sites, 11 handlers

**Files:** `canvas.py`, `_state.py`, `result.py`, `platforms.py`, and 26 others
**Impact:** 38 `RuntimeError` raise sites with 11 handlers. All 11 handlers have no direct raises in their try body. Key semantic contexts:
- `get_current_app` (`_state.py:110`) — no app configured
- `assert_will_not_block` (`result.py:38`) — calling `.get()` inside a task
- `_chord.freeze` (`canvas.py:2097`) — chord misconfiguration
- `detached` (`platforms.py:413`) — daemonization failures

The `Proxy` class in `local.py` has 4 handlers that catch `RuntimeError` from `__dict__`, `__repr__`, `__bool__`, and `__dir__` — these are well-scoped. But the broader pattern of 38 different error conditions sharing one exception type creates risk at the framework boundary.

**Recommendation:** The "no app configured" and "will block" RuntimeErrors are the most user-facing. Consider `AppNotConfigured` and `SynchronousCallError` subclasses — these are errors users need to handle differently.

### MEDIUM RISK: `ValueError` — 66 raise sites, 34 handlers

**Files:** `schedules.py`, `canvas.py`, `app/amqp.py`, and 51 others
**Impact:** 66 `ValueError` raise sites across 54 functions. The crontab parser alone has 5 raise sites with different meanings (out of range, invalid expression, unparseable number). Other contexts include invalid serializer names, bad task signatures, and configuration errors.

32 handlers have no direct raises — they catch `ValueError` from called functions. The `crontab_parser._expand_number` handler at `schedules.py:303` demonstrates good practice: it catches `ValueError` from `int()` conversion and re-raises with a more specific message.

**Recommendation:** Low priority. The crontab parser handles `ValueError` well. The broader codebase could benefit from `ConfigurationError` for config-related raises, but the handler density (34) is manageable.

### MEDIUM RISK: `SystemExit` — 5 raise sites, 7 handlers

**Files:** `platforms.py`, `apps/beat.py`, `events/snapshot.py`
**Impact:** `SystemExit` raised in 5 contexts: PID lock failure, beat sync failure, event camera shutdown, and two test helpers. `WorkController.start` (`worker/worker.py:209`) is the critical handler — it catches `SystemExit` as part of the worker shutdown sequence.

**Why this matters:** `SystemExit` from a PID lock failure (another celery instance already running) and `SystemExit` from a beat sync error have very different operational meanings. The worker handler's response to each should differ — one is "exit cleanly, another instance is running" and the other is "exit with error, schedule state is corrupt."

**Recommendation:** Low priority if the handler just exits. Higher priority if it logs or takes cleanup action — in that case, passing an exit code (`SystemExit(1)` vs `SystemExit(0)`) would distinguish the pathways.

---

## Celery-Specific Patterns

### The Task Framework Problem

Celery's exception architecture reveals a fundamental tension in task frameworks: the framework MUST catch broadly (tasks can raise anything), but broad catching creates semantic crossings by definition. The `trace_task` function in `app/trace.py` is the canonical example — it handles `Retry`, `Ignore`, `Reject`, `MemoryError`, `Exception`, and `BaseException` in a carefully ordered chain. This is correct architecture, but it means every new exception type that a task might raise needs to be explicitly handled or it falls through to the bare `except Exception` handler.

### The Worker Lifecycle

The `WorkerTerminate` → `WorkerShutdown` → `SystemExit` hierarchy shows intentional design — these are control flow exceptions, not error exceptions. But the single handler for each means that the REASON for shutdown is lost at the boundary. In production, "why did the worker stop?" is often the critical question.

### Test Code vs Production Code

Of the 64 crossings, approximately 15 are test-only (raise sites in test files, handlers in test files). The `DatabaseError` high-risk finding is entirely test code. The production crossing count is closer to 49, still the highest of any scanned project.

---

## Benchmark Context

| Project | Files | Crossings (all) | High Risk | Density |
|---|---|---|---|---|
| **celery** | **413** | **64** | **4** | **0.15** |
| flask | 24 | 6 | 2 | 0.25 |
| requests | 18 | 5 | 2 | 0.28 |
| rich | 100 | 5 | 1 | 0.05 |
| astroid | 96 | 5 | 0 | 0.05 |
| httpx | 23 | 3 | 0 | 0.13 |
| fastapi | 47 | 0 | 0 | 0.00 |

Celery has the highest absolute crossing count (64) and second-highest high-risk count (4, tied with Flask+Requests combined). Its crossing density (0.15) is moderate — lower than Flask or Requests — because its codebase is much larger. The density reflects architectural necessity: a distributed task framework handles more exception types than a web framework or HTTP client.

---

## Methodology

Crossing performs static AST analysis on Python source files. It maps every `raise` statement to every `except` handler that could catch it, then identifies **semantic boundary crossings** — places where the same exception type is raised with different meanings in different contexts. No code is executed; no network calls are made; no dependencies are required.

Risk levels:
- **Low:** Single raise site or uniform semantics
- **Medium:** Multiple raise sites in different functions — handler may not distinguish
- **Elevated:** Many divergent raise sites — high chance of incorrect handling
- **High:** Handler collapse — many raise sites, very few handlers, ambiguous behavior

---

*Report generated by [Crossing](https://fridayops.xyz/crossing/) v0.9*
*Scan performed by Friday (friday@fridayops.xyz)*
