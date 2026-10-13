"""One repeated phrase cannot prove which component supplied the DOM text."""
import json
import html as html_lib
import os
from types import SimpleNamespace

import pytest

from crawler import _extract_text_blocks
from finding_contract import serialize_span
from models import CodeBlock, Confidence, FileResult, TextBlock, TextSpan
from repo_pairing import content_index, index_for_path, mapping_for, mapping_lines, pair_blocks
from report.model import from_finding_dicts


def page(text="Read the documentation", **context):
    return TextBlock("page", "https://example.test/", "main > p", text, source_context=context)


def span(block):
    return TextSpan(block.block_id, 0, len(block.text), 0.9, Confidence.HIGH, "test", details={"source": "model"})


def write(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_repeated_phrase_keeps_every_component_without_picking_a_file(tmp_path):
    write(tmp_path, "A.tsx", "<p>Read the documentation</p>")
    write(tmp_path, "B.tsx", "<p>Read the documentation</p>")
    block = page()
    assert pair_blocks([block], index_for_path(str(tmp_path))) == 1
    assert block.source_mapping == "ambiguous"
    assert block.source_file == "" and block.source_line is None
    mapping = serialize_span(span(block), block)["mapping"]
    assert {c["file"] for c in mapping["candidates"]} == {str(tmp_path / "A.tsx"), str(tmp_path / "B.tsx")}
    assert not mapping["auto_fix_eligible"]
    assert "source_file" not in serialize_span(span(block), block)


def test_two_occurrences_in_one_source_file_are_also_ambiguous(tmp_path):
    write(tmp_path, "A.tsx", "<p>Read the documentation</p>\n<p>Read the documentation</p>")
    block = page()
    pair_blocks([block], index_for_path(str(tmp_path)))
    assert block.source_mapping == "ambiguous"
    assert {c["line"] for c in block.source_candidates} == {1, 2}


def test_exact_unique_match_retains_source_hash_and_verified_range(tmp_path):
    raw = "<p>Read the documentation</p>"
    path = write(tmp_path, "A.tsx", raw)
    block = page()
    pair_blocks([block], index_for_path(str(tmp_path)))
    assert block.source_mapping == "exact-unique"
    assert block.source_file == str(path) and block.source_line == 1
    mapping = mapping_for(block)
    assert mapping["auto_fix_eligible"] and mapping["requires_hash_revalidation"]
    candidate = mapping["candidates"][0]
    assert raw[candidate["offset"]:candidate["end_offset"]] == block.text
    assert len(candidate["file_hash"]) == len(candidate["text_hash"]) == 64


def test_normalized_match_is_inferred_and_not_an_automatic_target(tmp_path):
    write(tmp_path, "A.tsx", "<p>Read  the documentation</p>")
    block = page()
    pair_blocks([block], index_for_path(str(tmp_path)))
    assert block.source_mapping == "inferred"
    assert block.source_file == "" and block.source_line is None
    assert not mapping_for(block)["auto_fix_eligible"]


def test_unmapped_cms_text_clears_any_previous_source(tmp_path):
    write(tmp_path, "A.tsx", "<p>Read the documentation</p>")
    block = page()
    pair_blocks([block], index_for_path(str(tmp_path)))
    pair_blocks([block], {})
    assert block.source_mapping == "unmapped"
    assert block.source_candidates == [] and block.source_file == "" and block.source_line is None


def test_language_guesses_do_not_hide_a_second_source():
    text = "Read the documentation"
    sources = [CodeBlock(str(i), path, 0, len(text), text, i + 1, language_hint=lang)
               for i, (path, lang) in enumerate([("A.tsx", "en"), ("B.tsx", "uk")])]
    block = page()
    index = content_index([SimpleNamespace(blocks=sources)])
    pair_blocks([block], index)
    assert block.source_mapping == "ambiguous"
    assert len(block.source_candidates) == 2


def test_duplicate_reference_to_the_same_source_occurrence_is_not_ambiguity():
    text = "Read the documentation"
    source = CodeBlock("source", "A.tsx", 0, len(text), text, 1)
    block = page()
    index = content_index([SimpleNamespace(blocks=[source, source])])
    pair_blocks([block], index)
    assert len(block.source_candidates) == 1
    assert block.source_mapping == "exact-unique"
    assert not mapping_for(block)["auto_fix_eligible"]  # no source bytes verified


def test_locale_dom_and_component_context_rank_but_do_not_prove_origin(tmp_path):
    write(tmp_path, "locales/en.json", '{"other": "Read the documentation", "docs": "Read the documentation"}')
    blocks = _extract_text_blocks('<p data-i18n="docs">Read the documentation</p>', "https://example.test/")
    block = blocks[0]
    pair_blocks([block], index_for_path(str(tmp_path)))
    assert block.source_context["locale_key"] == "docs"
    assert block.source_mapping == "ambiguous"
    assert block.source_candidates[0]["context"]["locale_key"] == "docs"
    assert block.source_candidates[0]["context_matches"] == ["locale_key"]
    assert len(block.source_candidates) == 2 and block.source_file == ""
    assert mapping_for(block)["source_map_status"] == "unknown"


def test_observed_component_and_element_context_is_preserved(tmp_path):
    write(tmp_path, "Hero.tsx", "<h1>Read the documentation</h1>")
    block = _extract_text_blocks('<h1 data-component-file="Hero.tsx">Read the documentation</h1>', "https://example.test/")[0]
    pair_blocks([block], index_for_path(str(tmp_path)))
    candidate = block.source_candidates[0]
    assert candidate["context"]["element"] == "h1"
    assert candidate["context"]["component_file"] == "Hero.tsx"
    assert set(candidate["context_matches"]) == {"element", "component_file"}


def test_json_and_report_keep_all_candidates_and_detach_their_data(tmp_path):
    for name in ("A.tsx", "B.tsx"):
        write(tmp_path, name, "<p>Read the documentation</p>")
    block = page()
    pair_blocks([block], index_for_path(str(tmp_path)))
    record = serialize_span(span(block), block)
    restored = json.loads(json.dumps(record))
    finding = from_finding_dicts([restored]).findings[0]
    assert finding.evidence["mapping"] == record["mapping"]
    record["mapping"]["candidates"].clear()
    assert len(block.source_candidates) == len(finding.evidence["mapping"]["candidates"]) == 2


@pytest.mark.parametrize("lang", ["uk", "it", "en"])
def test_gui_and_human_report_show_every_candidate_in_the_selected_language(tmp_path, lang):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QLabel, QPushButton
    from ui.window_parts.findings_panel import FindingsPanelMixin
    from report.template import render_html
    from i18n.translations import t
    app = QApplication.instance() or QApplication([])
    for name in ("A.tsx", "B.tsx"):
        write(tmp_path, name, "<p>Read the documentation</p>")
    block = page()
    pair_blocks([block], index_for_path(str(tmp_path)))
    class Host(FindingsPanelMixin):
        drafts = {}
        _build_ignore_button = staticmethod(lambda *args: QPushButton("ignore"))
    host = Host()
    host.lang = lang
    widget = host._build_detail_widget(span(block), block)
    widget.resize(620, 650)
    widget.show()
    app.processEvents()
    labels = [label.text() for label in widget.findChildren(QLabel)]
    assert t("source_mapping_ambiguous", lang) in labels
    assert all(any(c["file"] in label for label in labels) for c in block.source_candidates)
    model = from_finding_dicts([serialize_span(span(block), block)])
    html = render_html(model, lang)
    assert all(c["file"] in html for c in block.source_candidates)
    assert t("source_mapping_ambiguous", lang) in html_lib.unescape(html)
    widget.close()


def test_fullscan_cli_uses_the_same_candidate_evidence(tmp_path, monkeypatch):
    from cli_impl import fullscan
    for name in ("A.tsx", "B.tsx"):
        write(tmp_path, name, "<p>Read the documentation</p>")
    block = page()
    fake = SimpleNamespace(name="test", analyze_blocks=lambda blocks: [span(b) for b in blocks])
    monkeypatch.setattr(fullscan, "_content_passes", lambda args: [fake])
    monkeypatch.setattr(fullscan, "_cache_for", lambda *args: None)
    records = fullscan._content_findings_from_pages([SimpleNamespace(blocks=[block])],
                                                   SimpleNamespace(repo=str(tmp_path)))
    assert records[0]["mapping"] == mapping_for(block)
    assert len(records[0]["mapping"]["candidates"]) == 2
    assert "source_file" not in records[0]
