"""Tests for report.py — audit report generation."""

import json
from report import generate_report, _classify_overall_risk, _describe_impact, _generate_recommendation


def _minimal_scan_data(crossings=None, files=10, raises=20, handlers=15):
    """Create minimal scan data for testing."""
    return {
        "root": "/test/project",
        "summary": {
            "files_scanned": files,
            "parse_errors": 0,
            "total_raises": raises,
            "explicit_raises": raises,
            "implicit_raises": 0,
            "total_handlers": handlers,
            "total_crossings": len(crossings or []),
            "polymorphic_crossings": 0,
            "risky_crossings": sum(
                1 for c in (crossings or [])
                if c.get("risk_level") in ("medium", "high", "elevated")
            ),
            "total_information_loss_bits": 0.0,
            "mean_collapse_ratio": 0.0,
        },
        "crossings": crossings or [],
    }


def test_empty_report():
    """Report with zero crossings produces clean output."""
    data = _minimal_scan_data()
    report = generate_report(data, "TestProject")
    assert "# Crossing Audit Report: TestProject" in report
    assert "zero semantic boundary crossings" in report
    assert "Benchmark Context" in report
    assert "Methodology" in report


def test_low_risk_only():
    """Report with only low-risk crossings says no action needed."""
    crossings = [
        {
            "exception_type": "ValueError",
            "risk_level": "low",
            "description": "Single raise site",
            "is_polymorphic": False,
            "raise_sites": [{"file": "/test/a.py", "line": 10, "exception_type": "ValueError",
                            "function": "foo", "implicit": False, "context": "in foo", "message": None}],
            "handler_sites": [],
            "information_theory": {"semantic_entropy_bits": 0, "handler_discrimination_bits": 0,
                                   "information_loss_bits": 0, "collapse_ratio": 0},
        }
    ]
    data = _minimal_scan_data(crossings)
    report = generate_report(data, "TestProject")
    assert "low risk" in report
    assert "No action required" in report


def test_high_risk_finding():
    """Report with high-risk crossing produces detailed finding."""
    crossings = [
        {
            "exception_type": "KeyError",
            "risk_level": "high",
            "description": "3 raise sites, 1 handler — meaning collapse likely.",
            "is_polymorphic": True,
            "raise_sites": [
                {"file": "/test/a.py", "line": 10, "exception_type": "KeyError",
                 "function": "foo", "implicit": False, "context": "in foo", "message": "key1"},
                {"file": "/test/a.py", "line": 20, "exception_type": "KeyError",
                 "function": "bar", "implicit": False, "context": "in bar", "message": "key2"},
                {"file": "/test/b.py", "line": 5, "exception_type": "KeyError",
                 "function": "baz", "implicit": False, "context": "in baz", "message": None},
            ],
            "handler_sites": [
                {"file": "/test/a.py", "line": 30, "exception_type": "KeyError",
                 "function": "main", "re_raises": False, "returns_value": True,
                 "assigns_default": False, "direct_raises_in_scope": 0},
            ],
            "information_theory": {"semantic_entropy_bits": 1.58, "handler_discrimination_bits": 0,
                                   "information_loss_bits": 1.58, "collapse_ratio": 1.0},
        }
    ]
    data = _minimal_scan_data(crossings)
    report = generate_report(data, "TestProject")
    assert "HIGH RISK" in report
    assert "`KeyError`" in report
    assert "3 raise sites" in report
    assert "1 handler" in report
    assert "Recommendation" in report


def test_benchmark_table_present():
    """Report includes benchmark comparison table."""
    data = _minimal_scan_data()
    report = generate_report(data, "TestProject")
    assert "| Project | Files | Crossings |" in report
    assert "flask" in report
    assert "pytest" in report


def test_classify_overall_risk():
    """Risk classification logic."""
    assert _classify_overall_risk([]) == "Low"
    assert _classify_overall_risk([{"risk_level": "medium"}]) == "Low-Medium"
    assert _classify_overall_risk(
        [{"risk_level": "medium"}] * 3
    ) == "Medium"
    assert _classify_overall_risk(
        [{"risk_level": "high"}]
    ) == "Medium-High"
    assert _classify_overall_risk(
        [{"risk_level": "high"}] * 3
    ) == "High"


def test_project_name_in_bold_row():
    """Current project appears bold in benchmark table."""
    data = _minimal_scan_data()
    report = generate_report(data, "MyLib")
    assert "**MyLib**" in report


def test_repo_in_header():
    """Repo identifier appears in header when provided."""
    data = _minimal_scan_data()
    report = generate_report(data, "MyLib", repo="org/mylib")
    assert "org/mylib" in report


def test_singular_crossing():
    """Grammar: '1 crossing' not '1 crossings'."""
    crossings = [
        {
            "exception_type": "ValueError",
            "risk_level": "medium",
            "description": "test",
            "is_polymorphic": True,
            "raise_sites": [
                {"file": "/test/a.py", "line": 10, "exception_type": "ValueError",
                 "function": "foo", "implicit": False, "context": "in foo", "message": None},
                {"file": "/test/a.py", "line": 20, "exception_type": "ValueError",
                 "function": "bar", "implicit": False, "context": "in bar", "message": None},
            ],
            "handler_sites": [
                {"file": "/test/a.py", "line": 30, "exception_type": "ValueError",
                 "function": "main", "re_raises": False, "returns_value": False,
                 "assigns_default": True, "direct_raises_in_scope": 0},
            ],
            "information_theory": {"semantic_entropy_bits": 1.0, "handler_discrimination_bits": 0,
                                   "information_loss_bits": 1.0, "collapse_ratio": 1.0},
        }
    ]
    data = _minimal_scan_data(crossings)
    report = generate_report(data, "Test")
    assert "1 semantic boundary crossing" in report
    # should NOT have "1 semantic boundary crossings"
    assert "1 semantic boundary crossings" not in report
