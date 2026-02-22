# Crossing Audit Report: Django

**Project:** django (django/django)
**Version:** 5.2.x (main branch, Feb 2026)
**Scanned:** 2026-02-22
**Tool:** Crossing Semantic Scanner v0.9

---

## Executive Summary

Django has **80 semantic boundary crossings**, with **6 at high risk** — the most crossings of any project scanned to date. For a 902-file web framework with 2,003 raise sites and 1,224 handlers, the exception surface area is enormous, and three exception types account for 79% of all raises.

The dominant pattern is **volume-based collapse**: `ValueError` (486 raises across 335 functions), bare `Exception` (860 raises across 512 functions), and `TypeError` (236 raises across 189 functions) each have so many raise sites that handlers catching them cannot meaningfully distinguish the cause. The most extreme example: a single `Command.handle` handler in `dumpdata` can reach 65 different `Exception` raise sites across 7 functions.

**Risk Level:** High. Django's scale means that its most-used exception types have become semantically overloaded — the same type carries hundreds of different meanings, and handlers operate on ambiguous signals.

---

## Findings

### HIGH RISK: Bare `Exception` — 860 raise sites, 126 handlers

**Files:** 512 different functions across the entire codebase
**Impact:** The broadest semantic crossing in any project scanned. All 126 handlers catch `Exception` from called functions only — none have direct `Exception` raises in their try body. This means every handler is a cross-function crossing operating blind.

Key handler hotspots:
- `Command.handle` in `dumpdata` — can reach **65 raise sites** across 7 functions via call chain
- `Deserializer._handle_object` (XML, Python, YAML) — can reach 4 raise sites across 2 functions
- `FlatpageFallbackMiddleware.process_response` — can reach 3 raise sites across 2 functions

**Why this matters:** Bare `except Exception` is sometimes defensible in a web framework (request handlers shouldn't crash the server). But 860 raise sites funneled through 126 handlers means that any novel failure — a new database backend error, a third-party middleware bug, a template syntax issue — routes through the same catch-all path. When Django silently returns a 500, the root cause is often buried under one of these handlers. The `dumpdata` handler is the worst case: 65 possible failure meanings collapsed into one code path.

**Recommendation:** The highest-value fix targets the serialization pipeline. `Deserializer.__init__` and `_handle_object` in `pyyaml.py` both catch bare `Exception` and re-raise as `DeserializationError`. These should catch specific exceptions (yaml.YAMLError, LookupError, ValueError) instead of `Exception`, so that truly unexpected errors (MemoryError, SystemError) propagate rather than being wrapped.

### HIGH RISK: `ValueError` — 486 raise sites, 92 handlers

**Files:** 335 different functions across the codebase
**Impact:** The most frequently raised named exception. 89 of 92 handlers catch `ValueError` from called functions only. This means almost every handler is catching a semantically overloaded signal: "invalid form input," "bad URL configuration," "wrong field type," "unparseable date," and hundreds of other meanings arrive as the same exception type.

Key raise clusters:
- **Forms/validation:** `Field.clean()`, `MultiValueField.compress()`, custom validators — "user input is wrong"
- **ORM fields:** `IntegerField.get_prep_value()`, `DateField.to_python()` — "data doesn't match the column type"
- **URL routing:** `URLValidator.__call__()` — "URL is malformed"
- **Template engine:** `Variable.__init__()` — "template variable syntax error"

**Why this matters:** A handler catching `ValueError` in a view has no way to distinguish between "the user typed a bad email" and "the database returned an unparseable date" without inspecting the message string. These are fundamentally different failures — one is expected user error, the other is a data corruption signal — but the type system collapses them.

**Recommendation:** Django already has `ValidationError` for form/model validation. The remaining `ValueError` raises in ORM internals (field type coercion, query construction) should use domain-specific subclasses. Even `class FieldCoercionError(ValueError): pass` would allow handlers to distinguish "field can't convert this value" from "something else went wrong."

### HIGH RISK: `TypeError` — 236 raise sites, 42 handlers

**Files:** 189 different functions across the codebase
**Impact:** Similar to `ValueError` but for type mismatches. 41 of 42 handlers catch from called functions only. Key sources include:
- **ORM lookups:** `get_lookup()`, `resolve_expression()` — wrong type passed to query builder
- **Template rendering:** `Variable._resolve_lookup()` — callable vs. non-callable confusion
- **Serialization:** `Serializer.serialize()` — wrong argument types

**Why this matters:** `TypeError` in Python typically means "you called something wrong." But Django's internal APIs use it for both programming errors (wrong argument type to an API) and runtime conditions (user-provided data that doesn't match expected types). Handlers can't distinguish between "developer mistake" and "runtime data problem."

**Recommendation:** Lower priority than `ValueError` — most `TypeError` catches are defensive and appropriate. The template engine's `TypeError` catches in `Variable._resolve_lookup` deserve attention: they silently swallow type errors during variable resolution, which can mask bugs in template tags.

### HIGH RISK: `ImportError` — 7 raise sites, 58 handlers

**Files:** 5 explicit raise functions, but 58 handlers across the codebase
**Impact:** The inverted ratio is the story. Django has 58 `except ImportError` handlers for only 7 explicit `ImportError` raises. Most handlers catch `ImportError` from `import` statements or `importlib` calls — the real raise surface is Python's import machinery, not Django's explicit raises.

Key handler patterns:
- **Optional dependency guards:** `try: import yaml` / `except ImportError` — 30+ instances
- **GIS backend detection:** `load_geos()`, `load_gdal()` — spatial libraries may not be installed
- **Cache/session backend loading:** `CacheHandler.create_connection()` — pluggable backends

**Why this matters:** This is actually good defensive coding — Django correctly treats importability as uncertain for optional dependencies. But the pattern reveals architectural coupling: 58 places where Django's behavior changes based on what's installed, with no centralized way to know which optional features are active.

**Recommendation:** No immediate fix needed. This is a Django design pattern (pluggable backends), not a bug. A centralized `django.optional_features` registry that checks imports once at startup would reduce the 58 scattered handlers but isn't critical.

### HIGH RISK: `base.DeserializationError` — 4 raise sites, 1 handler

**Files:** `core/serializers/xml_serializer.py`, `core/serializers/python.py`
**Impact:** Four different deserialization failure modes collapse into a single handler:
- XML node structure error (`xml_serializer.py:268`)
- Model not found by natural key (`xml_serializer.py:431`)
- Model app_label mismatch (`xml_serializer.py:438`)
- Python deserializer model lookup failure (`python.py:219`)

The single handler in `python.py:137` just re-raises.

**Why this matters:** When `loaddata` fails on a fixture, the `DeserializationError` tells you *that* deserialization failed but not *why* in a machine-parseable way. "Malformed XML" vs. "model not in registry" vs. "app_label doesn't match" are different problems requiring different fixes. A fixture migration issue (model renamed) looks identical to a corrupt fixture file.

**Recommendation:** Add a `kind` attribute to `DeserializationError`: `DeserializationError(kind="model_not_found", ...)` vs. `DeserializationError(kind="invalid_structure", ...)`. This preserves the single exception type but lets tooling (and humans reading tracebacks) distinguish the cause without parsing the message string.

### HIGH RISK: `FileExistsError` — 3 raise sites, 5 handlers

**Files:** `core/files/move.py`, `core/files/storage/memory.py`, `core/files/storage/filesystem.py`
**Impact:** Three semantically different file-exists conditions:
- `file_move_safe()` — atomic file move failed because target exists
- `InMemoryStorage._resolve()` — in-memory file path collision
- `FileSystemStorage._save()` — on-disk file name collision during upload

The handler in `FileSystemStorage._save` can reach 2 raise sites via call chain (its own raise and the one from `file_move_safe`). One handler re-raises the exception; another silently handles it by generating a new filename.

**Why this matters:** The `_save` handler catches `FileExistsError` from `file_move_safe` (which means the atomic rename failed — a filesystem-level race condition) and treats it the same as a name collision (which means the naming strategy needs to generate a new name). These are different failure modes: one is a transient race condition that might succeed on retry, the other is a deterministic naming conflict.

**Recommendation:** The `FileSystemStorage._save` handler at line 133 should distinguish between its own re-raise (line 86-87, name collision) and the `file_move_safe` raise (line 37, race condition). Wrapping the `file_move_safe` call in its own try/except would separate the two cases.

---

## Medium-Risk Findings (Selected)

### `NotImplementedError` — 148 raise sites, 11 handlers (13.5:1 ratio)

The highest ratio of any exception type. 148 abstract method stubs raise `NotImplementedError`, but only 11 handlers exist. Most handlers make control-flow decisions based on catching it — conflating "abstract base class not overridden" with "optional feature not available." This is a known Django pattern for backend-specific features (e.g., `inspectdb` catching `NotImplementedError` to skip unsupported column types).

### `KeyError` — 16 raise sites, 111 handlers (0.14:1 inverted ratio)

Similar to `ImportError`, the inverted ratio tells the story. 111 handlers for 16 explicit raises — most handlers catch `KeyError` from dict access, not from explicit raises. Django is extremely defensive about dictionary lookups throughout its codebase.

### `AttributeError` — 34 raise sites, 79 handlers

79 handlers catch `AttributeError` from called functions. The template engine accounts for many of these (variable resolution via `getattr` chains), but ORM field access and serializer introspection also contribute.

### `LookupError` — 12 raise sites, 39 handlers

Django uses `LookupError` for app/model registry lookups (`Apps.get_app_config()`, `AppConfig.get_model()`). 39 handlers is proportionate to the number of places that need to resolve app references, but the pattern means that "app not installed" and "model not registered" produce the same exception type.

### `ValidationError` — 24 raise sites, 9 handlers

Django's domain-specific validation exception. 24 raise sites across form fields, model fields, and validators, with 9 handlers mostly in management commands (`createsuperuser`). The handlers are well-scoped — this is how exception specialization *should* look.

---

## Django-Specific Patterns

### The Framework Tax

Django's 2,003 raise sites reflect the cost of being a full-stack framework. Every layer — ORM, templates, forms, URL routing, middleware, management commands, serialization — has its own exception vocabulary, but Python's exception hierarchy forces them to share types. `ValueError` means something different in every layer, but `except ValueError` catches all of them.

### Serialization as Crossing Hotspot

The `core/serializers/` package appears in 4 of the 6 high-risk findings. XML, JSON, YAML, and Python serializers all funnel errors through `DeserializationError` and bare `Exception` catches. This is where Django's boundary crossing problem is most concentrated — and most consequential, because `loaddata` failures during migrations are notoriously hard to debug.

### The ImportError Defense Pattern

58 `ImportError` handlers reveal Django's plugin architecture: spatial backends, cache backends, session backends, template engines, and dozens of optional features are all loaded dynamically. This is sound architecture — but it means Django's runtime behavior depends on which packages are installed, with the dependency graph distributed across 58 scattered try/except blocks.

### Inverted Ratios

Both `KeyError` (16:111) and `ImportError` (7:58) have more handlers than raise sites. This is unusual — most projects have far more raises than handlers. Django's inverted ratios reflect a framework that expects things to go wrong and catches preemptively, rather than a codebase that raises and hopes for the best.

---

## Comparison

| Project | Files | Raises | Handlers | Crossings | High Risk |
|---|---|---|---|---|---|
| **Django** | **902** | **2,003** | **1,224** | **80** | **6** |
| Celery | 413 | 631 | 788 | 64 | 4 |
| Flask | 24 | 87 | 34 | 6 | 2 |
| Requests | 18 | 87 | 29 | 5 | 2 |

Django has the most crossings in absolute terms but the lowest crossing density (0.089 per file, vs. Celery's 0.155). Its scale produces volume-based collapse rather than the concentrated structural crossings seen in smaller projects.

---

*Generated by [Crossing](https://github.com/Fridayai700/crossing) Semantic Scanner v0.9*
