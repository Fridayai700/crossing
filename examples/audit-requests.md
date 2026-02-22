# Crossing Audit Report: Requests

**Project:** requests (psf/requests)
**Version:** 2.32.x (main branch, Feb 2026)
**Scanned:** 2026-02-22
**Tool:** Crossing Semantic Scanner v0.9

---

## Executive Summary

Requests has **5 semantic boundary crossings** at medium risk or above, including **2 high-risk** findings. For a compact 18-file library with 61 raise sites and 69 handlers, this is a notable crossing density — though lower than Flask's.

The two high-risk findings involve **handler collapse**: `InvalidURL` (7 raise sites, 1 handler) and `TypeError` (3 raise sites, 1 handler). In both cases, a single handler catches exceptions from multiple unrelated error conditions, with no way to distinguish between them programmatically.

**Risk Level:** Medium. The highest-impact finding (`InvalidURL` collapse) affects URL validation — a path that users interact with directly. The `TypeError` collapse is less likely to cause user-facing bugs but represents a fragile error path.

---

## Findings

### HIGH RISK: `InvalidURL` — 7 raise sites, 1 handler

**Files:** `models.py`, `utils.py`, `adapters.py`
**Impact:** Seven different error conditions raise `InvalidURL`:
- Invalid percent-encoding in URL (`utils.py:637`)
- Missing URL scheme (`models.py:437`)
- Missing URL host (`models.py:446`)
- Invalid URL characters (`models.py:456`, `:458`)
- TLS context with non-HTTPS URL (`adapters.py:453`)
- Proxy URL scheme invalid (`adapters.py:616`)

Only one handler exists (`utils.py:663` in `requote_uri`), which catches `InvalidURL` to return the URI unmodified.

**Why this matters:** If a caller catches `InvalidURL`, they cannot distinguish between a fundamentally malformed URL (missing scheme), a URL with encoding issues, and a TLS configuration error. The error message varies, but messages are not a stable API. A developer writing `except InvalidURL: handle_bad_url()` will treat TLS misconfiguration and missing schemes identically.

**Recommendation:** `InvalidURL` is a custom exception. Add an `error_code` or `reason` attribute to distinguish the 7 error conditions programmatically. Alternatively, subclass `InvalidURL` for the distinct categories (encoding, scheme, host, TLS).

### HIGH RISK: `TypeError` — 3 raise sites, 1 handler

**Files:** `cookies.py`, `models.py`, `utils.py`
**Impact:** Three `TypeError` raise sites with different meanings:
- Invalid cookie `morsel_key_type` (`cookies.py:479`) — cookie has wrong key type
- Invalid morsel conversion (`cookies.py:500`) — can't convert morsel to cookie
- Streaming with wrong `decode_unicode` type (`models.py:844`) — non-bool passed to iter_content

The single handler in `get_unicode_from_response` (`utils.py:614`) catches `TypeError` to return `None` — silently swallowing any of these errors if they propagate during response encoding detection.

**Recommendation:** Low priority. The handler is scoped to a deprecated function (`get_unicode_from_response`). The risk is that the deprecated function silently catches `TypeError` from unrelated sources during response processing. Consider removing the deprecated function or narrowing the catch.

### MEDIUM RISK: `ValueError` — 8 raise sites, 10 handlers

**Files:** `utils.py`, `cookies.py`, `sessions.py`, `models.py`, `adapters.py`
**Impact:** `ValueError` is the most broadly used exception in requests — 8 raise sites across 6 different functions, caught by 10 handlers. The semantic contexts range from:
- Invalid key-value pair format (`utils.py:328`)
- Invalid URL scheme for sending (`sessions.py:692`)
- Invalid file encoding parameter (`models.py:149`)
- Invalid hook name (`models.py:213`)
- Missing content-length for non-seekable body (`adapters.py:636`)

**Why this matters:** The 10 handlers include `_check_cryptography` (catching import-related ValueError), `is_valid_cidr` (catching IP parsing errors), and `parse_header_links` (catching URL parsing errors). None of these intend to catch ValueError from file encoding or hook registration. If a call chain crosses these boundaries, the wrong handler swallows the wrong error.

**Recommendation:** For the most critical path (`Session.send` raising ValueError for missing content-length), consider a more specific exception. `ContentLengthError` or similar would prevent accidental catching by the 10 other handlers.

### MEDIUM RISK: `KeyError` — 2 raise sites, 2 handlers

**Files:** `cookies.py`, `sessions.py`
**Impact:** Two `KeyError` raise sites in the cookie jar:
- `_find` — cookie not found by name
- `_find_no_duplicates` — cookie not found or ambiguous (multiple matches)

Two handlers:
- `RequestsCookieJar.get` — returns default value on missing cookie
- `SessionRedirectMixin.rebuild_proxies` — rebuilds proxy config on missing key

**Why this matters:** The proxy handler catches `KeyError` for missing proxy configuration keys. If a cookie operation raises `KeyError` during redirect handling, the proxy handler could interpret it as "no proxy configured" rather than "cookie lookup failed."

**Recommendation:** Low priority. The handlers are well-scoped and the `KeyError` paths are unlikely to cross. No action needed unless proxy-cookie interaction changes.

### MEDIUM RISK: `OSError` — 3 raise sites, 7 handlers

**Files:** `adapters.py`, `help.py`, `utils.py`, `models.py`
**Impact:** Three `OSError` raises in `cert_verify` (SSL certificate file not found, invalid format, key file missing), caught by 7 handlers across the codebase. The handlers are mostly unrelated — checking file sizes, testing IP addresses, rewinding request bodies.

**Recommendation:** Low priority. `OSError` is inherently broad. The handlers are well-scoped to their own `try` blocks and unlikely to catch certificate errors from unrelated paths.

---

## Benchmark Context

| Project | Files | Crossings (med+) | High Risk | Density |
|---|---|---|---|---|
| flask | 24 | 6 | 2 | 0.25 |
| **requests** | **18** | **5** | **2** | **0.28** |
| rich | 100 | 5 | 1 | 0.05 |
| celery | 161 | 12 | 3 | 0.07 |
| httpx | 23 | 3 | 0 | 0.13 |
| fastapi | 47 | 0 | 0 | 0.00 |

Requests has the second-highest crossing density (0.28 crossings per file) behind Flask. Its `InvalidURL` collapse is structurally similar to Flask's `click.BadParameter` collapse — a custom exception with many raise sites and very few handlers.

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
