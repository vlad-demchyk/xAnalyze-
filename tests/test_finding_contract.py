"""Public exports preserve the evidence the GUI's live models already hold."""
import json
from argparse import Namespace
from dataclasses import asdict
from types import SimpleNamespace

import pytest

from audit.base import Issue
from audit.coverage import build_coverage, content_digest
from audit.engine import AccessibilityResult, DocumentReport, analyze_document, analyze_files
from audit.repo_facts import Arrival
from cli_impl import checkpoint
from cli_impl.fullscan import _build_combined, _issues_at_floor, _markdown_briefing_input
from finding_contract import deserialize_finding, serialize_finding, serialize_issue, serialize_span
from models import CodeBlock, Confidence, FileResult, TextBlock, TextSpan
from report.model import from_accessibility, from_finding_dicts


def evidence_issue():
    return Issue("image-alt", "serious", selector="img:nth-of-type(2)", line=18,
                 snippet='<img data-long="' + "a" * 350 + '">',
                 details={"agreement": 2, "also_found_by": ["axe"],
                          "arrived": Arrival("abcd", "fix: image", "author", "2026-10-12")},
                 fix_snippet="<img alt='" + "b" * 300 + "'>", confidence="advisory",
                 source="src/page.html", owner="wordpress", engine="axe")


def test_fullscan_preserves_all_live_issue_facts_and_unabridged_snippets():
    issue = evidence_issue()
    payload = _build_combined(Namespace(), "src", False, "en", None, [], [issue])
    record = json.loads(json.dumps(payload))["audit"]["issues"][0]
    for name, value in asdict(issue).items():
        assert record[name] == value
    assert record["rule"] == issue.rule_id  # version 0 consumer remains valid
    assert record["location"] == {"source": issue.source, "line": 18, "selector": issue.selector}
    assert record["evidence_status"] == "advisory"
    assert record["range"] is None  # no invented character coordinates
    assert payload["schema_version"] == 1


def test_json_round_trip_restores_nested_blame_for_gui_attribute_access():
    issue = evidence_issue()
    back = deserialize_finding(json.loads(json.dumps(serialize_issue(issue))))
    assert back == issue
    assert back.details["arrived"].summary == "fix: image"


def test_json_report_and_gui_model_share_detached_evidence(tmp_path, monkeypatch):
    from cli_impl.reports import _write_report
    import cli_impl.reports as reports
    monkeypatch.setattr(reports, "_read_history", lambda *args: [])
    monkeypatch.setattr(reports, "_write_history", lambda *args: None)
    issue = evidence_issue()
    result = AccessibilityResult("src", mode="repo", documents=[DocumentReport(issue.source, [issue])])
    expected = serialize_issue(issue)
    model = from_accessibility(result, "en")
    payload = _write_report(result, Namespace(report=str(tmp_path / "report.json")), "en")
    assert payload["findings"] == [expected]
    assert model.findings[0].evidence == expected
    row = serialize_finding(model.findings[0])
    assert serialize_finding(deserialize_finding(json.loads(json.dumps(row)))) == row
    model.findings[0].evidence["details"]["also_found_by"].append("fake")
    assert issue.details["also_found_by"] == ["axe"]


@pytest.mark.parametrize("confidence,status", [("exact", "observed"), ("advisory", "advisory"),
                                               ("needs-browser", "unknown")])
def test_certainty_has_an_explicit_evidence_status(confidence, status):
    assert serialize_issue(Issue("r", "minor", confidence=confidence))["evidence_status"] == status


def test_rule_errors_are_not_observed_facts():
    assert serialize_issue(Issue("r", "minor", details={"rule_error": "crash"}))["evidence_status"] == "error"


def test_legacy_issue_and_unknown_additive_fields_are_readable():
    issue = deserialize_finding({"rule": "image-alt", "severity": "serious", "future_field": 42})
    assert issue.rule_id == "image-alt"
    assert issue.engine == "static"


def test_an_unsupported_schema_is_not_silently_reinterpreted():
    with pytest.raises(ValueError, match="schema version"):
        deserialize_finding({"schema_version": 99})


@pytest.mark.parametrize("local", [False, True])
def test_text_spans_keep_precise_scores_details_and_named_coordinates(local):
    text = "x" * 400 + "\u00a0z"
    block = (CodeBlock("b", "src/page.html", 80, 80 + len(text), text, 14)
             if local else TextBlock("b", "https://example.test/", "main > p", text))
    span = TextSpan("b", 2, 402, 0.812345, Confidence.HIGH, "offline",
                    explanation="signal", replacement="replacement", details={"source": "style", "signals": [1, 2]})
    record = serialize_span(span, block)
    assert record["text"] == text[2:402]
    assert record["score"] == span.score
    assert record["details"] == span.details
    assert record["location"]["source"] == (block.file_path if local else block.page_url)
    assert record["range"]["coordinate_system"] == ("source-text" if local else "block-text")
    assert record["range"]["start"] == (82 if local else 2)
    assert deserialize_finding(json.loads(json.dumps(record))) == span
    briefing = _markdown_briefing_input(False, [], [record])
    assert briefing == [record]
    assert from_finding_dicts(briefing).findings[0].evidence == record


def test_a_view_does_not_destroy_unresolved_evidence():
    issue = Issue("contrast", "serious", confidence="needs-browser", source="page.html")
    result = AccessibilityResult("page.html", mode="file", documents=[DocumentReport("page.html", [issue])])
    coverage = build_coverage(result, Namespace(no_browser=True))
    assert _issues_at_floor(result, "exact") == []
    assert result.issues() == [issue]
    assert coverage["unknown"][0]["rule"] == "contrast"
    assert coverage["status"] == "incomplete"


def test_static_coverage_includes_clean_skipped_unknown_and_failed_rules():
    def fail(*_):
        raise RuntimeError("check failed")
    rules = [SimpleNamespace(id="clean", check=lambda *_: []),
             SimpleNamespace(id="web", page_level=True, check=lambda *_: []),
             SimpleNamespace(id="pending", check=lambda *_: [Issue("pending", "minor", confidence="needs-browser")]),
             SimpleNamespace(id="failed", check=fail)]
    document = analyze_document("<p>copy</p>", "component.jsx", rules, document_kind="fragment")
    checks = {row["rule"]: row["status"] for row in document.checks}
    assert checks == {"clean": "checked", "web": "skipped", "pending": "unknown", "failed": "error"}
    assert document.content_hash == content_digest("<p>copy</p>")


def test_repo_coverage_keeps_clean_documents_the_finding_list_omits():
    file = FileResult("clean.html", raw_text="<p>copy</p>")
    result = analyze_files([file], "src", rules=[SimpleNamespace(id="clean", check=lambda *_: [])],
                           media=False, repo_facts=False)
    assert not any(d.source == "clean.html" for d in result.documents)
    coverage = build_coverage(result, Namespace(no_browser=True))
    record = next(d for d in coverage["documents"] if d["source"] == "clean.html")
    assert record["checks"] == [{"rule": "clean", "engine": "static", "status": "checked"}]


def test_checkpoints_keep_kind_errors_hashes_and_scan_read_evidence(tmp_path):
    from audit.authwall import Wall, WallReport
    from audit.media import MediaFetchScan
    issue = evidence_issue()
    result = AccessibilityResult("src", mode="repo", documents=[DocumentReport(issue.source, [issue], kind="email")],
        browser_errors=[{"engine": "axe", "error": "timeout"}],
        browser_coverage=[{"engine": "axe", "status": "error"}],
        auth=WallReport([Wall("https://example.test/login", "password-form")], pages_read=1),
        media=MediaFetchScan(found=12, checked=2, skipped_budget=10),
        markup_by_source={issue.source: "<p>copy</p>"})
    result.coverage = build_coverage(result, Namespace(no_browser=True))
    checkpoint.save_audit(tmp_path, result)
    restored = checkpoint.load_audit(tmp_path)
    assert restored.documents[0].kind == "email"
    assert restored.issues()[0] == issue
    assert restored.browser_errors == result.browser_errors
    assert restored.browser_coverage == result.browser_coverage
    assert restored.coverage == result.coverage
    assert restored.auth.whole_site
    assert restored.media.unchecked == 10
    scan = {"findings": [], "counts": {}, "read": [{"truncated": True, "limit": 20}],
            "content_hashes": {"src/file.txt": content_digest("text")}, "errors": [{"engine": "judge"}]}
    checkpoint.save_scan(tmp_path, [], {}, scan_result=scan)
    restored_scan = checkpoint.load_scan_result(tmp_path)
    assert {k: restored_scan[k] for k in scan} == scan
    assert build_coverage(restored, scan=restored_scan)["status"] == "incomplete"


def test_coverage_versions_and_hashes_describe_shipped_engines():
    coverage = build_coverage(AccessibilityResult("src", mode="repo"))
    assert coverage["status"] == "unknown"
    assert coverage["engines"]["axe"]["version"] == "4.10.3"
    assert len(coverage["engines"]["axe"]["artifact_sha256"]) == 64
    assert coverage["mapping_confidence"] == "unknown"


def test_an_unavailable_requested_judge_does_not_look_like_a_clean_run(monkeypatch):
    from cli_impl import fullscan
    args = Namespace(detector="ai", no_browser=True)
    monkeypatch.setattr(fullscan.DetectorFactory, "create", lambda *a, **k: SimpleNamespace(name="offline"))
    monkeypatch.setattr("cli_impl.scanning._create_detector",
                        lambda *a: (_ for _ in ()).throw(RuntimeError("judge unavailable")))
    monkeypatch.setattr(fullscan, "_judge_distinct", lambda *a: {})
    fullscan._content_findings_from_pages([], args)
    coverage = build_coverage(AccessibilityResult("src", mode="repo"), args)
    assert coverage["status"] == "incomplete"
    assert coverage["content"][0]["status"] == "error"
    assert "judge unavailable" in coverage["errors"][0]["reason"]


@pytest.mark.parametrize("lang,title", [("en", "Check coverage"), ("uk", "Покриття перевірки"),
                                       ("it", "Copertura dei controlli")])
def test_human_exports_show_the_same_coverage_without_losing_uncertainty(lang, title):
    from report.template import render_html
    from cli_impl.reports import _report_markdown
    result = AccessibilityResult("page.html", mode="file", documents=[DocumentReport("page.html", [
        Issue("contrast", "minor", confidence="needs-browser")])])
    result.coverage = build_coverage(result, Namespace(no_browser=True))
    assert title in render_html(from_accessibility(result, lang), lang)
    payload = {"coverage": result.coverage, "root": "page.html", "mode": "file", "generated": "today",
               "summary": {"counts": {}, "documents": 1, "total": 0, "distinct_problems": 0,
                           "rules_triggered": 0, "documents_with_findings": 0},
               "problems": [], "by_rule": [], "history": [], "files": []}
    assert title in _report_markdown(payload, lang)
