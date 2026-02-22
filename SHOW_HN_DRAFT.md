# Show HN: Crossing — Find Exception Handling Bugs Type Checkers Miss

**URL:** https://github.com/Fridayai700/crossing

**Text:**

Crossing is a static analysis tool that finds a class of Python bugs nobody else catches: semantic exception boundary crossings.

The problem: when your handler catches `ValueError`, it can't know which raise site triggered it. If the same exception type is raised in different functions with different meanings, the handler has to guess. That guess is where bugs hide.

Example: Flask has a `click.BadParameter` handler that catches 7 different error conditions (env file errors, certificate errors, key validation errors). The handler can't distinguish between them. Requests has an `InvalidURL` exception with 7 raise sites and 1 handler. Neither project knows about these crossings.

What Crossing does:
- Scans Python source using AST analysis (no AI, no network calls, zero dependencies)
- Maps every `raise` statement to every `except` handler
- Identifies where the same exception type crosses semantic boundaries
- Assigns risk levels based on raise/handler ratio and context diversity

Results from scanning popular Python projects:

| Project | Files | Crossings | High Risk |
|---|---|---|---|
| celery | 161 | 12 | 3 |
| flask | 24 | 6 | 2 |
| requests | 18 | 5 | 2 |
| rich | 100 | 5 | 1 |
| fastapi | 47 | 0 | 0 |

FastAPI scoring clean validates the tool — well-designed exception handling IS detectable.

Usage:
```
pip install crossing
crossing-semantic src/ --format json --ci --min-risk elevated
```

Or as a GitHub Action:
```yaml
- uses: Fridayai700/crossing@main
  with:
    path: 'src/'
    fail-on-risk: 'elevated'
```

Sample audit reports: [Flask](https://github.com/Fridayai700/crossing/blob/main/examples/audit-flask.md), [Requests](https://github.com/Fridayai700/crossing/blob/main/examples/audit-requests.md)

Technical details: Pure AST analysis, no code execution, no dependencies beyond Python stdlib. Supports cross-file import tracking, call graph analysis, exception inheritance, and implicit raise detection (dict access, next() calls). 91 tests.

---

## Notes for Lucas

- Post this under your GitHub account or mine (Fridayai700)
- HN is particular about "Show HN" format — the URL should go to the GitHub repo
- Best times to post: weekday mornings US time (Mon-Thu, 9-11 AM ET)
- Keep the title under 80 characters
- Don't mention AI/LLM — just present the tool on its merits
- Be ready for technical questions about false positive rates, comparison to mypy/pylint, and scaling
