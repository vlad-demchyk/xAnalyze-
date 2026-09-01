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
    # --- the form journey ---------------------------------------------------
    # A form is the part of a page where a mistake costs the visitor the
    # whole task, and every check here reads the state the page is *in*: the
    # accessible name after scripts have run, the browser's own verdict on
    # what has been typed, the error text that is on screen right now.
    "form-field-unnamed": SERIOUS,
    "form-placeholder-as-label": MODERATE,
    "form-invalid-not-announced": MODERATE,
    "form-error-not-associated": SERIOUS,
}

# A raw string: everything below is JavaScript, and its backslashes belong to
# the browser's regexes (`/\s+/`) and to its own escaping (`\\"`). Read as
# Python escapes they are a `SyntaxWarning` on 3.12+ and an error later, and
# `\s` in a Python string is not `\s` in the regex the browser receives.
STATE_SCRIPT = r"""
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

  // --- 5. The form journey -------------------------------------------------
  // Read-only, like everything else here, and for a sharper reason: this is
  // the one region of a page where *acting* has consequences. Typing into a
  // field fires the page's own handlers - autosave, validation requests,
  // analytics - and submitting is worse still, so nothing below fills,
  // clears, clicks or submits anything. What it does instead is read the
  // live state the browser already maintains:
  //
  //   * the accessible name, computed after scripts have run, which is what
  //     makes this different from the static rule of the same shape - a
  //     field labelled by JavaScript is labelled, and a field the markup
  //     labelled and a script detached is not;
  //   * `el.validity`, the browser's own verdict on what is currently in the
  //     field. The property is read; the method of a similar name is not,
  //     because calling it fires an `invalid` event the page can act on;
  //   * the error text that is on screen at this moment, and whether
  //     anything points a screen reader at it.
  //
  // What is deliberately not here: filling a field to see what a form does
  // with a wrong value. That is the other half of the journey and there is
  // no way to do it on somebody's real page without changing their page.
  var fields = Array.prototype.slice.call(
    document.querySelectorAll('input,select,textarea')
  ).filter(function(el) {
    var type = (el.getAttribute('type') || '').toLowerCase();
    // Hidden inputs have nothing to label, and the three button types are
    // named by their own value rather than by a label.
    if (type === 'hidden' || type === 'submit' || type === 'button' ||
        type === 'reset') return false;
    if (el.disabled) return false;
    if (el.getAttribute('aria-hidden') === 'true') return false;
    return visible(el);
  }).slice(0, 60);

  function labelText(el) {
    var parts = [];
    var wrapping = el.closest ? el.closest('label') : null;
    if (wrapping) parts.push(wrapping.textContent || '');
    var id = el.getAttribute('id');
    if (id) {
      try {
        Array.prototype.forEach.call(
          document.querySelectorAll('label[for="' + id.replace(/"/g, '\\"') + '"]'),
          function(label) { parts.push(label.textContent || ''); });
      } catch (e) { /* an id no selector can express is an id with no label */ }
    }
    return parts.join(' ').replace(/\s+/g, ' ').trim();
  }

  function referencedText(el, attribute) {
    var value = el.getAttribute(attribute) || '';
    var text = '';
    value.split(/\s+/).forEach(function(id) {
      if (!id) return;
      var target = document.getElementById(id);
      if (target) text += ' ' + (target.textContent || '');
    });
    return text.replace(/\s+/g, ' ').trim();
  }

  fields.forEach(function(el) {
    var named = labelText(el) ||
                (el.getAttribute('aria-label') || '').trim() ||
                referencedText(el, 'aria-labelledby') ||
                (el.getAttribute('title') || '').trim();
    var placeholder = (el.getAttribute('placeholder') || '').trim();
    if (!named) {
      // A placeholder is not a label: it is gone the moment somebody types,
      // it is not announced by every screen reader, and it fails contrast
      // far more often than body text does. Reported apart from a field
      // with nothing at all, because the fix is different - one needs a
      // label written, the other needs the words it already has moved.
      record(placeholder ? 'form-placeholder-as-label' : 'form-field-unnamed',
             el, placeholder ? {placeholder: placeholder} : {});
    }

    // The browser's own verdict on what is in the field right now, read as a
    // property. The method that asks the same question fires an `invalid`
    // event on the way out, and hands the page's own code a reason to react.
    var validity = null;
    try { validity = el.validity; } catch (e) { validity = null; }
    if (validity && validity.valid === false &&
        (el.getAttribute('aria-invalid') || '').toLowerCase() !== 'true') {
      record('form-invalid-not-announced', el,
             {reason: validity.valueMissing ? 'value-missing'
                      : (validity.typeMismatch ? 'type-mismatch' : 'constraint')});
    }
  });

  // Error text that is on screen and pointed at by nothing. The static rule
  // asks the mirror-image question - a field marked `aria-invalid` with no
  // description - and neither finds this one: a red sentence under a field,
  // rendered by the page's own validation, that no `aria-describedby` or
  // `aria-errormessage` refers to. A screen reader never reaches it.
  var describedIds = {};
  fields.forEach(function(el) {
    ['aria-describedby', 'aria-errormessage'].forEach(function(attribute) {
      (el.getAttribute(attribute) || '').split(/\s+/).forEach(function(id) {
        if (id) describedIds[id] = true;
      });
    });
  });
  var errorNodes = Array.prototype.slice.call(document.querySelectorAll(
    '[role="alert"],[class*="error"],[class*="invalid"],[id*="error"]'
  )).filter(function(el) {
    if (!visible(el)) return false;
    if (!el.closest || !el.closest('form')) return false;
    var text = (el.textContent || '').trim();
    // A wrapper whose class happens to contain "error" is not a message.
    // Text, and not the whole form's worth of it.
    if (text.length < 3 || text.length > 200) return false;
    return el.querySelectorAll('input,select,textarea').length === 0;
  }).slice(0, 20);
  errorNodes.forEach(function(el) {
    var id = el.getAttribute('id');
    if (id && describedIds[id]) return;
    if (el.getAttribute('role') === 'alert' && !id) return;  // announced live
    record('form-error-not-associated', el,
           {message: (el.textContent || '').trim().slice(0, 80)});
  });

  // --- 6. Skip link --------------------------------------------------------
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
                         fieldsChecked: fields.length,
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
