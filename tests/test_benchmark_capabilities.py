"""Availability checks must neither run inference nor invent authorship evidence."""
import json

import pytest

from scripts.benchmark import main
from validation import capabilities
from validation.adapters import inference_policy


def test_capabilities_are_passive_and_keep_watermark_outside_classification(monkeypatch):
    monkeypatch.setattr("requests.Session", lambda: pytest.fail("network session created"))
    result = capabilities.method_capabilities()
    assert result["network_calls"] == result["model_loads"] == 0
    assert len(result["classification_methods"]) == 15
    assert all(item["name"] != "claude-official-watermark" for item in result["classification_methods"])
    mark = result["provenance_signals"][0]
    assert mark["channel"] == "provenance" and mark["authorship_score"] is None
    assert mark["availability"] == "private-preview" and not mark["adapter_implemented"]


def test_configured_credentials_do_not_establish_vendor_snapshot_or_preview_access(monkeypatch):
    monkeypatch.setenv("GPTZERO_API_KEY", "secret-fixture")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "another-secret")
    report = capabilities.method_capabilities("gptzero", {"request_version": "frozen-version"})
    item = report["classification_methods"][0]
    assert item["credential_configured"] and not item["snapshot_verified"]
    assert "secret-fixture" not in json.dumps(report)
    mark = capabilities.method_capabilities("claude-official-watermark")["provenance_signals"][0]
    assert not mark["adapter_implemented"] and mark["blockers"]


def test_experimental_prerequisites_report_actual_runtime_without_scores(monkeypatch):
    monkeypatch.setattr(capabilities, "_runtime", lambda: {"dependencies": {"en-core-web-sm": None}, "cuda_available": False})
    for name in ("adadetectgpt", "prossd"):
        item = capabilities.method_capabilities(name)["classification_methods"][0]
        assert item["status"] == "research-only" and not item["adapter_implemented"]
        assert len(item["blockers"]) == 2 and "score" not in item
        assert len(item["revision"]) == 40
        with pytest.raises(ValueError, match="no classification benchmark adapter"):
            inference_policy([], name, {}, False)


def test_capability_cli_writes_once_and_validates_configuration(tmp_path, capsys):
    target = tmp_path / "capabilities.json"
    assert main(["capabilities", "--detector", "prossd", "--output", str(target)]) == 0
    result = json.loads(target.read_text())
    assert result["classification_methods"][0]["name"] == "prossd"
    original = target.read_bytes()
    assert main(["capabilities", "--output", str(target)]) == 1
    assert target.read_bytes() == original
    assert main(["capabilities", "--detector", "unknown"]) == 1
    config = tmp_path / "config.json"
    config.write_text('{}')
    assert main(["capabilities", "--config", str(config)]) == 1
    assert "requires --detector" in capsys.readouterr().err


def test_watermark_fails_before_crawl_even_with_credentials_and_url():
    from detectors.base import DetectorUnavailable
    from detectors.claude_watermark_stub import ClaudeOfficialWatermarkDetector
    with pytest.raises(DetectorUnavailable, match="private preview"):
        ClaudeOfficialWatermarkDetector(api_key="fixture", base_url="https://example.invalid")
