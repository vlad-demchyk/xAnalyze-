"""Checking the page in the states a person actually puts it in.

Everything else in this package looks at one snapshot. But most of what
makes a page unusable only exists in a state: the focus ring that turns out
to be invisible, the menu that opens but cannot be closed with a key, the
dialog that lets focus wander out behind it, the content that only appears
on hover and therefore never appears to a keyboard at all.

This is the largest remaining source of automatable findings that does not
involve a model. It is also the part that genuinely needs a browser: every
check below is "do something, then look", and there is nothing to do to a
static string.

The script runs entirely inside the page, in one pass, and restores what it
touched. It deliberately does **not** click anything: a click can submit a
form, navigate away, or fire an analytics event on a real site. Focus and
keyboard events are safe in a way that clicks are not, so the checks are
built from those.
"""
from __future__ import annotations

import json

from .base import (
    ACCESSIBILITY, MODERATE, SERIOUS, Issue,
)

#: What each check reports, and how badly. Keyboard traps come first because
#: a trapped keyboard user cannot leave the page at all.
STATE_RULES = {
    "keyboard-trap": SERIOUS,
    "focus-not-visible": SERIOUS,
    "focus-order-mismatch": MODERATE,
    "hover-only-content": MODERATE,
    "no-skip-link": MODERATE,
    "focus-outside-viewport": MODERATE,
    "modal-focus-not-contained": SERIOUS,
}

STATE_SCRIPT = """
(function() {
  var FOCUSABLE = 'a[href],button,input,select,textarea,summary,[tabindex]';
  var findings = [];
  var active = document.activeElement;
  var scrollX = window.scrollX, scrollY = window.scrollY;

  function selectorFor(el) {
    var parts = [];
    while (el && el.nodeType === 1 && parts.length < 6) {
      var name = el.tagName.toLowerCase();
      if (el.id) { parts.unshift(name + '#' + el.id); break; }
      var parent = el.parentElement;
      if (parent) {
        var same = Array.prototype.filter.call(parent.children, function(c) {
          return c.tagName === el.tagName;
        });
        if (same.length > 1) name += ':nth-of-type(' + (same.indexOf(el) + 1) + ')';
      }
      parts.unshift(name);
      el = el.parentElement;
    }
    return parts.join(' > ');
  }

  function record(rule, el, extra) {
    var item = {rule: rule, selector: el ? selectorFor(el) : '',
                html: el ? (el.outerHTML || '').slice(0, 200) : '',
                tag: el ? el.tagName.toLowerCase() : ''};
    for (var k in (extra || {})) item[k] = extra[k];
    findings.push(item);
  }

  function visible(el) {
    var style = getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden') return false;
    var rect = el.getBoundingClientRect();
    return rect.width > 0 || rect.height > 0;
  }

  // --- 0. An already-open modal owns focus -------------------------------
  // This observes an existing state only. It does not click an opener or
  // dispatch Escape, because either can submit a form or change a real
  // session. A visible aria-modal dialog with focus still behind it is a
  // concrete failure of the state the visitor is currently in.
  var openModal = Array.prototype.slice.call(
    document.querySelectorAll('[role="dialog"][aria-modal="true"], [role="alertdialog"][aria-modal="true"]')
  ).find(visible);
  if (openModal && (!active || !openModal.contains(active))) {
    record('modal-focus-not-contained', openModal, {});
  }

  var candidates = Array.prototype.slice.call(document.querySelectorAll(FOCUSABLE))
    .filter(function(el) {
      return visible(el) && el.tabIndex >= 0 && !el.disabled;
    })
    .slice(0, 120);   // a bounded pass; huge pages are sampled, not skipped

  // --- 1. Is the focus indicator actually visible? ------------------------
  // A ring that the design removed and never replaced is the single most
  // common keyboard problem, and it is invisible to any static check
  // because `outline: none` usually lives in a stylesheet, not the markup.
  //
  // It is also the check most able to lie, and it did. A document that does
  // not itself have focus never matches `:focus` in Chromium: `el.focus()`
  // sets `activeElement`, no focus rule applies, no computed style changes,
  // and every focusable element on the page reports a missing indicator.
  // Measured on `https://www.gov.uk/` - whose focus state is among the most
  // tested on the web - the pass returned 588 serious findings across ten
  // pages, one for very nearly every element it examined.
  //
  // So the precondition is checked first, and a pass that cannot see focus
  // styles reports *nothing* and says why. A check firing on ~100% of what
  // it looks at is measuring the harness, not the page.
  var canSeeFocus = false;
  if (candidates.length) {
    try { window.focus(); } catch (e) {}
    var probe = candidates[0];
    try { probe.focus({preventScroll: true}); } catch (e) {}
    try {
      canSeeFocus = document.hasFocus() && probe.matches(':focus');
    } catch (e) { canSeeFocus = false; }
  }

  candidates.forEach(function(el) {
    // Off-canvas, not below the fold. The third condition used to be
    // `rect.top > innerHeight + scrollY + 2000`, which is a statement about
    // how long the page is: on `https://www.gov.uk/` it reported 151
    // `govuk-footer__link` elements - the ordinary footer - as focusable
    // content outside the viewport. Content further down a page is reached
    // by scrolling, which is what pages do.
    //
    // What the rule is for is the element parked off-screen with
    // `left: -9999px` and left focusable, so a keyboard lands somewhere the
    // eye cannot follow. That is what a negative edge means.
    var rect = el.getBoundingClientRect();
    if (rect.bottom < 0 || rect.right < 0) {
      record('focus-outside-viewport', el, {});
    }
    if (!canSeeFocus) return;
    var before = getComputedStyle(el);
    var beforeShadow = before.boxShadow, beforeBorder = before.borderColor;
    var beforeOutlineW = before.outlineWidth, beforeOutlineS = before.outlineStyle;
    var beforeBg = before.backgroundColor, beforeColor = before.color;
    try { el.focus({preventScroll: true}); } catch (e) { return; }
    if (document.activeElement !== el) return;
    var after = getComputedStyle(el);
    var gainedOutline = after.outlineStyle !== 'none' &&
                        parseFloat(after.outlineWidth || '0') > 0 &&
                        (after.outlineStyle !== beforeOutlineS ||
                         after.outlineWidth !== beforeOutlineW);
    var gainedShadow = after.boxShadow !== beforeShadow && after.boxShadow !== 'none';
    var gainedBorder = after.borderColor !== beforeBorder;
    // Background and text colour count too, and leaving them out was the
    // second half of the same defect: GOV.UK's indicator is a yellow
    // background (`#fd0`), not a ring, and 83 rules in its stylesheet set
    // `background` on `:focus`. WCAG asks for a visible change, not for an
    // outline specifically.
    var gainedBackground = after.backgroundColor !== beforeBg;
    var gainedColor = after.color !== beforeColor;
    if (!gainedOutline && !gainedShadow && !gainedBorder &&
        !gainedBackground && !gainedColor) {
      record('focus-not-visible', el, {outline: after.outlineStyle});
    }
  });

  // --- 2. Keyboard traps --------------------------------------------------
  // Anything that swallows Tab without moving focus onwards. Checked by
  // dispatching the key and seeing whether the element cancels it — not by
  // actually tabbing, which the page's own handlers would fight over.
  candidates.forEach(function(el) {
    try { el.focus({preventScroll: true}); } catch (e) { return; }
    if (document.activeElement !== el) return;
    var event = new KeyboardEvent('keydown', {key: 'Tab', code: 'Tab',
                                              bubbles: true, cancelable: true});
    var delivered = el.dispatchEvent(event);
    if (!delivered && !el.matches('input,textarea,select,[contenteditable]')) {
      record('keyboard-trap', el, {});
    }
  });

  // --- 3. Does focus order follow reading order? --------------------------
  // Compared against document order rather than pixel position, because a
  // two-column layout legitimately reads down one column first.
  var lastTop = -Infinity, mismatches = 0, firstMismatch = null;
  candidates.forEach(function(el) {
    var top = el.getBoundingClientRect().top + window.scrollY;
    if (top < lastTop - 40) {
      mismatches += 1;
      if (!firstMismatch) firstMismatch = el;
    }
    lastTop = Math.max(lastTop, top);
  });
  if (mismatches > 2 && firstMismatch) {
    record('focus-order-mismatch', firstMismatch, {count: mismatches});
  }

  // --- 4. Content that only exists on hover --------------------------------
  // A submenu that opens on hover and has no focus equivalent is unreachable
  // from a keyboard, and its links are invisible to anyone not using a mouse.
  var hoverOnly = 0, hoverExample = null;
  Array.prototype.slice.call(document.querySelectorAll('[class*="dropdown"],[class*="submenu"],[class*="tooltip"],[class*="popover"]'))
    .slice(0, 40)
    .forEach(function(el) {
      var style = getComputedStyle(el);
      if (style.display !== 'none' && style.visibility !== 'hidden') return;
      var parent = el.parentElement;
      if (!parent) return;
      var opensOnFocus = parent.querySelector(FOCUSABLE) !== null ||
                         parent.getAttribute('aria-expanded') !== null;
      if (!opensOnFocus) {
        hoverOnly += 1;
        if (!hoverExample) hoverExample = el;
      }
    });
  if (hoverExample) record('hover-only-content', hoverExample, {count: hoverOnly});

  // --- 5. Skip link --------------------------------------------------------
  // On a page with a lot of navigation, its absence means every keyboard
  // visit starts by tabbing through the whole menu again.
  var navLinks = document.querySelectorAll('nav a, header a').length;
  if (navLinks > 8) {
    var first = candidates[0];
    var hasSkip = Array.prototype.slice.call(document.querySelectorAll('a[href^="#"]'))
      .slice(0, 5)
      .some(function(a) { return /skip|jump|перейти|content|main|vai/i.test(a.textContent || ''); });
    if (!hasSkip) record('no-skip-link', first, {navLinks: navLinks});
  }

  // Put the page back the way it was found.
  try { if (active && active.focus) active.focus({preventScroll: true}); } catch (e) {}
  window.scrollTo(scrollX, scrollY);

  return JSON.stringify({findings: findings.slice(0, 200),
                         focusableChecked: candidates.length,
                         focusMeasured: canSeeFocus});
})()
"""


def issues_from_states(payload: str, source: str) -> list:
    """State-pass results -> `Issue`s."""
    data = _load(payload)
    if "error" in data:
        return [Issue(rule_id="state-pass", severity=MODERATE,
                      category=ACCESSIBILITY, source=source, engine="browser",
                      details={"engine_error": data["error"]})]

    issues = []
    for finding in data.get("findings", []):
        rule = finding.get("rule", "")
        severity = STATE_RULES.get(rule, MODERATE)
        details = {k: v for k, v in finding.items()
                   if k not in ("rule", "selector", "html")}
        details["engine"] = "state-pass"
        issues.append(Issue(
            rule_id=f"state:{rule}",
            severity=severity,
            category=ACCESSIBILITY,
            selector=finding.get("selector", ""),
            snippet=finding.get("html", ""),
            source=source,
            engine="browser",
            details=details,
        ))
    return issues


def _load(payload) -> dict:
    if isinstance(payload, dict):
        return payload
    if not payload:
        return {}
    try:
        return json.loads(payload)
    except (TypeError, ValueError):
        return {"error": "state pass returned a non-JSON result"}


def state_script() -> str:
    return STATE_SCRIPT
