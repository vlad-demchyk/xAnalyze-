"""Writes approved replacements directly back into source files.

Unlike web mode (where nothing is ever published back to the live site),
repo mode edits files that live on your own disk — usually under version
control. Three safety nets are built in:

1. Every file about to be modified gets a `.bak` copy next to it first.
   Only the *first* backup taken for a given file is kept, so re-running
   never overwrites your one clean copy with an already-edited version.
2. Every write re-checks that the text at the recorded offset still
   matches what was scanned, and refuses that edit if the file changed
   underneath it.
3. Overlapping edits inside one file are rejected rather than applied,
   since splicing two overlapping ranges would corrupt the result.

IMPORTANT — replacements are SPAN-scoped, not block-scoped. A detector
usually flags a block sentence by sentence, so a block like
"Sentence A. Sentence B. Sentence C." produces three spans. Editing only
sentence B must replace *only* sentence B's characters in the file and
leave A and C untouched. That's why a plan carries absolute file offsets
for the span (block.start + span.start) rather than the block's own
range — replacing the whole block with one sentence's rewrite would
silently delete the other sentences from the user's source file.
"""
from __future__ import annotations

import os

import backups
from dataclasses import dataclass, field

from models import CodeBlock, TextSpan


@dataclass
class ReplacementPlan:
    """One edit: replace file_path[abs_start:abs_end] (which must currently
    equal original_text) with new_text."""
    file_path: str
    abs_start: int
    abs_end: int
    original_text: str
    new_text: str
    block_id: str = ""
    # Deleting the matched text is a legitimate correction for an invisible
    # character, but an empty box in the UI usually means "not filled in".
    # Only plans that opt in here may replace text with nothing.
    allow_empty: bool = False


@dataclass
class ApplyResult:
    files_changed: list[str] = field(default_factory=list)
    passages_applied: int = 0
    passages_skipped_stale: list[str] = field(default_factory=list)
    passages_skipped_overlap: list[str] = field(default_factory=list)
    passages_skipped_no_text: int = 0
    errors: list[str] = field(default_factory=list)


def _drop_overlaps(plans: list[ReplacementPlan], result: ApplyResult) -> list[ReplacementPlan]:
    """Keep plans that don't overlap each other. Earliest-start wins; any
    later plan that intersects an already-kept range is reported and
    dropped instead of silently corrupting the file."""
    kept: list[ReplacementPlan] = []
    for plan in sorted(plans, key=lambda p: (p.abs_start, p.abs_end)):
        if any(plan.abs_start < k.abs_end and k.abs_start < plan.abs_end for k in kept):
            result.passages_skipped_overlap.append(plan.block_id)
            continue
        kept.append(plan)
    return kept


def apply_replacements(plans: list[ReplacementPlan]) -> ApplyResult:
    result = ApplyResult()
    by_file: dict[str, list[ReplacementPlan]] = {}
    for plan in plans:
        is_empty = not plan.new_text
        if plan.new_text == plan.original_text or (is_empty and not plan.allow_empty):
            result.passages_skipped_no_text += 1
            continue
        by_file.setdefault(plan.file_path, []).append(plan)

    for file_path, file_plans in by_file.items():
        try:
            with open(file_path, "r", encoding="utf-8") as fh:
                original_content = fh.read()
        except OSError as exc:
            result.errors.append(f"{file_path}: {exc}")
            continue

        file_plans = _drop_overlaps(file_plans, result)
        if not file_plans:
            continue

        # Highest offset first, so earlier offsets stay valid as we splice
        # in replacements whose length differs from the original.
        content = original_content
        applied_here = 0
        for plan in sorted(file_plans, key=lambda p: p.abs_start, reverse=True):
            if content[plan.abs_start:plan.abs_end] != plan.original_text:
                result.passages_skipped_stale.append(plan.block_id)
                continue
            content = content[:plan.abs_start] + plan.new_text + content[plan.abs_end:]
            applied_here += 1

        if not applied_here:
            continue

        try:
            # One implementation of "keep the first copy", shared with the
            # audit's own writer. Two safety nets with the same rule in them
            # is how one of them eventually stops matching the other.
            backups.take(file_path, original_content)
        except OSError as exc:
            result.errors.append(f"{file_path}: could not write backup ({exc}), skipping this file")
            continue

        try:
            with open(file_path, "w", encoding="utf-8") as fh:
                fh.write(content)
            result.files_changed.append(file_path)
            result.passages_applied += applied_here
        except OSError as exc:
            result.errors.append(f"{file_path}: {exc}")

    return result


def build_plans(blocks_by_id: dict[str, CodeBlock], spans: list[TextSpan],
                 drafts: dict[tuple, str]) -> list[ReplacementPlan]:
    """Build one plan per flagged span that has a saved draft.

    A block may legitimately contribute several plans (one per flagged
    sentence); each is scoped to its own character range so untouched
    sentences in the same block survive the write.
    """
    plans: list[ReplacementPlan] = []
    seen_keys: set[tuple] = set()
    for span in spans:
        block = blocks_by_id.get(span.block_id)
        if block is None:
            continue
        key = (block.block_id, span.start, span.end)
        if key in seen_keys:
            continue
        draft = drafts.get(key)
        if draft is None:
            continue
        seen_keys.add(key)
        plans.append(
            ReplacementPlan(
                file_path=block.file_path,
                abs_start=block.start + span.start,
                abs_end=block.start + span.end,
                original_text=block.text[span.start:span.end],
                new_text=draft,
                block_id=block.block_id,
                # An empty draft is honoured only when the detector itself
                # asked for a deletion (an invisible character), never when
                # the user simply left the box blank.
                allow_empty=(span.replacement == "" and draft == ""),
            )
        )
    return plans
