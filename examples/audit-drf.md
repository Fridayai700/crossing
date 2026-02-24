# Crossing Audit Report: rest_framework

**Project:** rest_framework
**Scanned:** 2026-02-24
**Tool:** Crossing Semantic Scanner v0.9

---

## Executive Summary

rest_framework has **24 semantic boundary crossings**, including **1 high-risk** findings. For a 74-file codebase with 136 raise sites and 120 handlers, this gives a crossing density of 0.32 per file.

**Risk Level:** Medium-High.

---

## Scan Summary

| Metric | Value |
|--------|-------|
| Files scanned | 74 |
| Raise sites | 136 |
| Exception handlers | 120 |
| Total crossings | 24 |
| High risk | 1 |
| Elevated risk | 0 |
| Medium risk | 4 |
| Low risk | 19 |
| Mean collapse ratio | 19% |

---

## Findings

### HIGH RISK: `AssertionError` — 5 raise sites, 1 handler

**Files:** `fields.py`, `filters.py`, `response.py`, `serializers.py`
**Impact:** `AssertionError` is raised at 5 sites across 3 files (fields.py, response.py, serializers.py), in 5 different functions. A single handler in `OrderingFilter.get_default_valid_fields` assigns a default. With 5 raise sites funneling through one handler, semantic disambiguation is impossible. Information collapse: 100% of semantic information is lost (2.3 bits destroyed).

**Raise sites:**
- `response.py:38` raise `AssertionError` in `Response.__init__` — if isinstance(data, Serializer) → raise in __init__
- `serializers.py:247` raise `AssertionError` in `BaseSerializer.data` — if hasattr(self, 'initial_data') and not hasattr(self, '_validated_data') → raise in data
- `serializers.py:262` raise `AssertionError` in `BaseSerializer.errors` — if not hasattr(self, '_errors') → raise in errors
- `serializers.py:269` raise `AssertionError` in `BaseSerializer.validated_data` — if not hasattr(self, '_validated_data') → raise in validated_data
- `fields.py:599` raise `AssertionError` in `Field.fail` — in fail

**Handlers:**
- `filters.py:258` — except `AssertionError` in `OrderingFilter.get_default_valid_fields` (assigns default)

**Information theory:** 2.3 bits entropy, 2.3 bits lost, 100% collapse

**Recommendation:** Narrow the handler scope: isolate the specific call that may raise `AssertionError` inside the try block, so unrelated `AssertionError` exceptions from other code paths aren't caught.

### MEDIUM RISK: `TypeError` — 10 raise sites, 3 handlers

**Files:** `decorators.py`, `relations.py`, `schemas/coreapi.py`, `serializers.py`, `viewsets.py`
**Impact:** `TypeError` is raised at 10 sites across 4 files (decorators.py, relations.py, serializers.py, viewsets.py), in 6 different functions. 3 handlers (3 re-raise, 3 assign default).

**Raise sites:**
- `decorators.py:154` raise `TypeError` in `action` — if 'name' in kwargs and 'suffix' in kwargs → raise in action (`"`name` and `suffix` are mutually exclusive arguments.`)
- `viewsets.py:84` raise `TypeError` in `ViewSetMixin.as_view` — if not actions → raise in as_view (`"The `actions` argument must be provided when calling `.as_vi...`)
- `viewsets.py:91` raise `TypeError` in `ViewSetMixin.as_view` — if key in cls.http_method_names → raise in as_view
- `viewsets.py:95` raise `TypeError` in `ViewSetMixin.as_view` — if not hasattr(cls, key) → raise in as_view
- `viewsets.py:100` raise `TypeError` in `ViewSetMixin.as_view` — if 'name' in initkwargs and 'suffix' in initkwargs → raise in as_view
- `relations.py:258` raise `TypeError` in `PrimaryKeyRelatedField.to_internal_value` — if isinstance(data, bool) → raise in to_internal_value
- `serializers.py:1010` raise `TypeError` in `ModelSerializer.create` — in create
- `serializers.py:1135` raise `TypeError` in `ModelSerializer.get_field_names` — if fields and fields != ALL_FIELDS and not isinstance(fields, (list, tuple)) → raise in get_field_names
- ... and 2 more

**Handlers:**
- `relations.py:317` — except `TypeError` in `HyperlinkedRelatedField.get_object` (re-raises)
- `serializers.py:992` — except `TypeError` in `ModelSerializer.create` (re-raises)
- `schemas/coreapi.py:92` — except `TypeError` in `insert_into` (re-raises)

**Information theory:** 2.6 bits entropy, 0.0 bits lost, 0% collapse

**Recommendation:** `TypeError` is a broad built-in type carrying 10 different meanings here. Consider defining project-specific exception subclasses, or narrowing handler try-blocks to minimize the catch surface.

### MEDIUM RISK: `ValueError` — 9 raise sites, 4 handlers

**Files:** `fields.py`, `pagination.py`, `parsers.py`, `relations.py`, `schemas/coreapi.py`, `schemas/openapi.py`, `serializers.py`, `templatetags/rest_framework.py`, `test.py`, `utils/encoders.py`, `utils/json.py`
**Impact:** `ValueError` is raised at 9 sites across 8 files (coreapi.py, encoders.py, fields.py, json.py, openapi.py, pagination.py, serializers.py, test.py), in 9 different functions. 4 handlers (2 re-raise, 1 return, 1 assign default).

**Raise sites:**
- `pagination.py:32` raise `ValueError` in `_positive_int` — if ret < 0 or (ret == 0 and strict) → raise in _positive_int
- `test.py:114` raise `ValueError` in `RequestsClient.request` — if not url.startswith('http') → raise in request
- `serializers.py:1067` raise `ValueError` in `ModelSerializer.get_fields` — if model_meta.is_abstract_model(self.Meta.model) → raise in get_fields (`"Cannot use ModelSerializer with Abstract Models.`)
- `fields.py:114` raise `ValueError` in `get_attribute` — in get_attribute
- `fields.py:831` raise `ValueError` in `UUIDField.__init__` — if self.uuid_format not in self.valid_formats → raise in __init__
- `utils/encoders.py:38` raise `ValueError` in `JSONEncoder.default` — if timezone and timezone.is_aware(obj) → raise in default (`"JSON can't represent timezone-aware times.`)
- `utils/json.py:13` raise `ValueError` in `strict_constant` — in strict_constant
- `schemas/coreapi.py:98` raise `ValueError` in `insert_into` — in insert_into
- ... and 1 more

**Handlers:**
- `parsers.py:67` — except `ValueError` in `JSONParser.parse` (re-raises)
- `relations.py:314` — except `ValueError` in `HyperlinkedRelatedField.get_object` (re-raises)
- `fields.py:846` — except `ValueError` in `UUIDField.to_internal_value` (handles)
- `templatetags/rest_framework.py:314` — except `ValueError` in `smart_urlquote_wrapper` (returns)

**Information theory:** 3.2 bits entropy, 1.6 bits lost, 50% collapse

**Recommendation:** `ValueError` is a broad built-in type carrying 9 different meanings here. Consider defining project-specific exception subclasses, or narrowing handler try-blocks to minimize the catch surface.

### MEDIUM RISK: `AttributeError` — 2 raise sites, 10 handlers

**Files:** `exceptions.py`, `fields.py`, `relations.py`, `request.py`, `settings.py`, `test.py`
**Impact:** `AttributeError` is raised at 2 sites across 2 files (request.py, settings.py), in 2 different functions. 10 handlers (2 re-raise, 4 return, 3 assign default). Information collapse: 80% of semantic information is lost (0.8 bits destroyed).

**Raise sites:**
- `request.py:424` raise `AttributeError` in `Request.__getattr__` — in __getattr__
- `settings.py:216` raise `AttributeError` in `APISettings.__getattr__` — if attr not in self.defaults → raise in __getattr__

**Handlers:**
- `exceptions.py:80` — except `AttributeError` in `ErrorDetail.__eq__` (returns)
- `relations.py:340` — except `AttributeError` in `HyperlinkedRelatedField.to_internal_value` (handles)
- `relations.py:361` — except `AttributeError` in `HyperlinkedRelatedField.to_internal_value` (assigns default)
- `test.py:163` — except `AttributeError` in `APIRequestFactory._encode_data` (handles)
- `request.py:75` — except `AttributeError` in `wrap_attributeerrors` (re-raises)
- ... and 5 more

**Information theory:** 1.0 bits entropy, 0.8 bits lost, 80% collapse

**Recommendation:** Multiple handlers exist, which may provide adequate discrimination. Verify that each handler's try-block scope only exposes the expected raise sites.

### MEDIUM RISK: `Exception` — 34 raise sites, 8 handlers

**Files:** `fields.py`, `pagination.py`, `parsers.py`, `relations.py`, `renderers.py`, `request.py`, `schemas/coreapi.py`, `schemas/openapi.py`, `serializers.py`, `utils/breadcrumbs.py`, `validators.py`, `views.py`
**Impact:** `Exception` is raised at 34 sites across 7 files (fields.py, openapi.py, pagination.py, parsers.py, relations.py, serializers.py, validators.py), in 28 different functions. 8 handlers (3 re-raise, 1 return, 5 assign default). Information collapse: 62% of semantic information is lost (3.0 bits destroyed).

**Raise sites:**
- `schemas/openapi.py:176` raise `Exception` in `AutoSchema.get_component_name` — if component_name == "" → raise in get_component_name
- `fields.py:75` raise `Exception` in `is_simple_callable` — if inspect.isbuiltin(obj) → raise in is_simple_callable (`"Built-in function signatures are not inspectable. Wrap the f...`)
- `pagination.py:216` raise `Exception` in `PageNumberPagination.paginate_queryset` — in paginate_queryset
- `pagination.py:867` raise `Exception` in `CursorPagination.decode_cursor` — in decode_cursor
- `validators.py:87` raise `Exception` in `UniqueValidator.__call__` — if qs_exists(queryset) → raise in __call__
- `validators.py:136` raise `Exception` in `UniqueTogetherValidator.enforce_required_fields` — if missing_items → raise in enforce_required_fields
- `validators.py:196` raise `Exception` in `UniqueTogetherValidator.__call__` — if checked_values and None not in checked_values and qs_exists_with_condition(queryset, self.condition, condition_kwargs) → raise in __call__
- `validators.py:226` raise `Exception` in `ProhibitSurrogateCharactersValidator.__call__` — if 0xD800 <= ord(ch) <= 0xDFFF) → raise in __call__
- ... and 26 more

**Handlers:**
- `views.py:317` — except `Exception` in `APIView.perform_content_negotiation` (re-raises)
- `views.py:514` — except `Exception` in `APIView.dispatch` (assigns default)
- `renderers.py:202` — except `Exception` in `TemplateHTMLRenderer.get_exception_template` (returns)
- `request.py:360` — except `Exception` in `Request._parse` (re-raises)
- `fields.py:1165` — except `Exception` in `DateTimeField.enforce_timezone` (re-raises)
- ... and 3 more

**Information theory:** 4.8 bits entropy, 3.0 bits lost, 62% collapse

**Recommendation:** Multiple handlers exist, which may provide adequate discrimination. Verify that each handler's try-block scope only exposes the expected raise sites.

---

## Benchmark Context

| Project | Files | Crossings | Elevated+ | Density |
|---------|-------|-----------|-----------|---------|
| **rest_framework** | **74** | **24** | **1** | **0.32** |
| click | 17 | 11 | 4 | 0.65 |
| requests | 18 | 5 | 2 | 0.28 |
| hypothesis | 103 | 29 | 7 | 0.28 |
| invoke | 47 | 12 | 3 | 0.26 |
| flask | 24 | 6 | 2 | 0.25 |
| tqdm | 31 | 7 | 3 | 0.23 |
| scrapy | 113 | 23 | 8 | 0.20 |
| uvicorn | 40 | 7 | 3 | 0.18 |
| colorama | 7 | 1 | 0 | 0.14 |
| httpx | 23 | 3 | 0 | 0.13 |
| pytest | 71 | 9 | 9 | 0.13 |
| celery | 161 | 12 | 3 | 0.07 |
| rich | 100 | 5 | 1 | 0.05 |
| fastapi | 47 | 0 | 0 | 0.00 |

rest_framework's crossing density (0.32) is significantly above the benchmark average (0.20).

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
*Scan performed 2026-02-24*
