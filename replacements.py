"""Every pending change in one list, before any of it is written (artboard 3l).

A run can produce three kinds of change, and until now each of them had its
own button and its own moment of truth: the character pass filled drafts in
place, the model rewrote flagged passages, the audit wrote markup back to
disk. Three buttons, three confirmations, and no surface that answered the
question somebody actually has before writing to their repository: *what
exactly is about to change.*

The three are not one kind of thing, which is why the list names the source
of every row rather than presenting one undifferentiated pile:

- **mechanical** - the correction is derived, not composed. An invisible
  character has one right removal; a `<button>` with no accessible name has
  one right attribute. Nobody has to read these to know they are right, so
  they are the rows that come pre-selected.
- **draft** - a model wrote the replacement. It is a suggestion about
  somebody's prose and it can be wrong in ways that still read fluently, so
  it is never selected until a person selects it.
- **decision** - there is no replacement, only the shape of one. `alt=""` on
  a photograph is valid markup and a lie; writing it unattended would make
  the next audit call the page clean. These rows can never be selected here:
  the reason is shown in place of the text that does not exist yet.

The list carries the plan each row would be written by, so nothing is
recomputed at write time - a row is written by exactly the plan that was
shown, or it is not written at all.
"""
from __future__ import annotations

import datetime as _datetime
import os
from dataclasses import dataclass, field

import unicode_rules

#: Where a row's replacement came from. Also the order the counts are read in.
MECHANICAL = "mechanical"
DRAFT = "draft"
DECISION = "decision"
SOURCES = (MECHANICAL, DRAFT, DECISION)

#: Which writer a selected row goes to. Prose lives at character offsets in a
#: file and is written by `file_writer`; markup is an element located in the
#: source and is written by `audit.fixer`. The two cannot be merged: one
#: knows about spans of a block, the other about tags on a line.
TEXT = "text"
MARKUP = "markup"


@dataclass
class Replacement:
    """One row: where it is, what it says now, what it would say."""

    where: str
    before: str
    after: str
    source: str
    writer: str
    plan: object = None
    #: Only for `DECISION`: what has to be decided, shown where the
    #: replacement would otherwise be.
    reason: str = ""
    selected: bool = False
    #: Sort key, so a mixed list still reads as a walk through the files.
    path: str = ""
    line: int = 0

    @property
    def writable(self) -> bool:
        """Can this row be written at all, by anyone, right now?

        A decision has nothing to write; a row whose replacement equals what
        is already there would be a no-op, and offering it as a change would
        inflate the count the button promises.
        """
        return (self.source != DECISION and self.plan is not None
                and self.after != self.before)


def counts(items) -> dict:
    """How many rows of each source, for the header line."""
    return {source: sum(1 for i in items if i.source == source)
            for source in SOURCES}


def selected(items) -> list:
    return [i for i in items if i.selected and i.writable]


def default_filename(when=None) -> str:
    """The name the export is offered under: one list, dated by its run."""
    when = when or _datetime.date.today()
    return f"replacements-{when:%Y-%m-%d}.md"


def short_path(path: str, root: str | None = None) -> str:
    """A path short enough for a column and still unambiguous."""
    if not path:
        return ""
    if root:
        try:
            relative = os.path.relpath(path, root)
        except ValueError:
            relative = path
        if not relative.startswith(".."):
            return relative
    return os.path.basename(path)


def _where(path: str, root: str | None, line: int | None, detail: str) -> str:
    head = short_path(path, root)
    if line:
        head = f"{head}:{line}"
    return f"{head} · {detail}" if detail else head


# --------------------------------------------------------------- collecting

def from_text_result(result, drafts: dict | None = None,
                     root: str | None = None) -> list:
    """Rows for the prose passes: character fixes and model drafts.

    A character finding carries its own correction, so it is a row whether or
    not anybody pressed *Fix characters* first - that button fills the same
    drafts this list would write, and a preview that only showed changes
    already staged would show nothing on a fresh run.
    """
    from models import CodeBlock, Confidence
    from file_writer import ReplacementPlan

    if result is None:
        return []
    drafts = drafts or {}
    blocks = {b.block_id: b for b in result.blocks()}
    rows: list = []
    seen: set = set()
    for span in result.spans:
        if span.confidence == Confidence.LOW:
            continue
        block = blocks.get(span.block_id)
        if not isinstance(block, CodeBlock):
            continue  # a crawled page has no file to write back to
        key = (block.block_id, span.start, span.end)
        if key in seen:
            continue
        original = block.text[span.start:span.end]
        if span.replacement is not None and span.replacement != original:
            after, source = span.replacement, MECHANICAL
        elif key in drafts:
            after, source = drafts[key], DRAFT
        else:
            continue
        seen.add(key)
        rows.append(Replacement(
            where=_where(block.file_path, root, block.line_number, ""),
            before=unicode_rules.visible(original),
            after=unicode_rules.visible(after),
            source=source,
            writer=TEXT,
            plan=ReplacementPlan(
                file_path=block.file_path,
                abs_start=block.start + span.start,
                abs_end=block.start + span.end,
                original_text=original,
                new_text=after,
                block_id=block.block_id,
                allow_empty=(span.replacement == "" and after == ""),
            ),
            selected=(source == MECHANICAL),
            path=block.file_path,
            line=block.line_number or 0,
        ))
    return rows


def from_audit_result(audit_result, root: str | None = None) -> tuple:
    """Rows for the audit pass, plus what could not be planned at all.

    Returns `(rows, skipped)`. The skipped list is handed back rather than
    swallowed: a finding that never became an edit is the one thing a review
    list must not make look handled.
    """
    from audit import fix_ai, fixer

    if audit_result is None:
        return [], []
    ready, pending, skipped = fixer.plan_fixes(audit_result.documents)
    page_text = audit_result.documents[0].source if audit_result.documents else ""
    filled, pending = fix_ai.fill_locally(pending, page_text)
    ready += filled

    rows = []
    for plan in ready:
        rows.append(_audit_row(plan, MECHANICAL, root))
    for plan in pending:
        rows.append(_audit_row(plan, DECISION, root))
    return rows, skipped


def _audit_row(plan, source: str, root: str | None) -> Replacement:
    return Replacement(
        where=_where(plan.path, root, plan.line, plan.rule_id),
        before=plan.original,
        after=plan.replacement,
        source=source,
        writer=MARKUP,
        plan=plan,
        reason=plan.needs_input,
        selected=(source == MECHANICAL),
        path=plan.path,
        line=plan.line or 0,
    )


def collect(result=None, drafts: dict | None = None, audit_result=None,
            root: str | None = None) -> tuple:
    """Every pending change of a run, in file order, plus what was skipped."""
    rows = from_text_result(result, drafts, root)
    audit_rows, skipped = from_audit_result(audit_result, root)
    rows += audit_rows
    rows.sort(key=lambda r: (r.path, r.line))
    return rows, skipped


def fill_decisions(items, provider, page_text: str = "",
                   language: str = "en") -> int:
    """Ask a model for the values the decisions are missing.

    A decision the model answers becomes a **draft**, not a mechanical row,
    and stays unticked. That is the honest reading of what happened: nobody
    read the picture, a model wrote a sentence about it, and the whole point
    of the middle category is that such a sentence is reviewed before it is
    written. `fix_ai.describe` already refuses to invent - it answers SKIP
    when the page does not say - and those rows simply stay decisions.
    """
    from audit import fix_ai

    pending = [i for i in items if i.source == DECISION and i.writer == MARKUP]
    if not pending:
        return 0
    filled, _left = fix_ai.describe([i.plan for i in pending], page_text,
                                    provider, language)
    by_key = {(p.path, p.start, p.end, p.rule_id): p for p in filled}
    answered = 0
    for item in pending:
        plan = by_key.get((item.plan.path, item.plan.start, item.plan.end,
                           item.plan.rule_id))
        if plan is None:
            continue
        item.plan = plan
        item.after = plan.replacement
        item.source = DRAFT
        item.reason = ""
        item.selected = False
        answered += 1
    return answered


# ------------------------------------------------------------------ writing

@dataclass
class WriteOutcome:
    """What one press of *Write selected* actually did."""

    written: int = 0
    files_changed: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    errors: list = field(default_factory=list)


def write(items) -> WriteOutcome:
    """Write the selected rows through the writer each of them belongs to."""
    from audit import fixer
    from file_writer import apply_replacements

    chosen = selected(items)
    outcome = WriteOutcome()
    text_plans = [i.plan for i in chosen if i.writer == TEXT]
    markup_plans = [i.plan for i in chosen if i.writer == MARKUP]

    if text_plans:
        result = apply_replacements(text_plans)
        outcome.written += result.passages_applied
        outcome.files_changed += result.files_changed
        outcome.skipped += [f"{b}: stale" for b in result.passages_skipped_stale]
        outcome.skipped += [f"{b}: overlaps another edit"
                            for b in result.passages_skipped_overlap]
        outcome.errors += result.errors
    if markup_plans:
        result = fixer.apply_fixes(markup_plans)
        outcome.written += len(result.applied)
        outcome.files_changed += [p for p in result.files_changed
                                  if p not in outcome.files_changed]
        outcome.skipped += [f"{s.rule_id}: {s.reason}" for s in result.skipped]
        outcome.errors += result.errors
    return outcome


# ---------------------------------------------------------------- exporting

def render_markdown(items, when=None, root: str | None = None) -> str:
    """The list as a file: the same rows, readable without the application.

    Written for the person who has to take it somewhere else - a review, a
    ticket, a colleague's screen - so every row says its source, and the rows
    that are not going to be written say why in the place of the text.
    """
    when = when or _datetime.date.today()
    totals = counts(items)
    lines = [
        "# Replacement list",
        "",
        f"{when:%Y-%m-%d} · {totals[MECHANICAL]} mechanical · "
        f"{totals[DRAFT]} model drafts · {totals[DECISION]} need a decision",
        "",
    ]
    if root:
        lines += [f"Paths are relative to `{root}`.", ""]
    current = ""
    for item in items:
        head = short_path(item.path, root) or item.where
        if head != current:
            current = head
            lines += [f"## {head}", ""]
        lines.append(f"### {item.where} — {item.source}")
        lines += ["", "```", item.before, "```", ""]
        if item.source == DECISION:
            lines += [f"Needs a decision: {item.reason or 'no replacement yet'}",
                      "", "```", item.after, "```", ""]
        else:
            lines += ["```", item.after, "```", ""]
    return "\n".join(lines)
