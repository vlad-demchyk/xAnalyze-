"""A test module must fail as a skip, never as a collection error.

Measured 2026-09-02 on CI (ubuntu-latest, Python 3.14): PySide6 installs
fine, `libEGL.so.1` does not, and `from PySide6.QtWidgets import ...` raises.
Two of the 104 test modules did that at import time, so pytest reported

    collected 2562 items / 2 errors
    !!!!! Interrupted: 2 errors during collection !!!!!

and **none** of the 2562 ran. A collection error is not one red test; it
stops the suite. The skip that both files were designed around never got the
chance to fire.

Two shapes caused it, and this checks for both:

1. `tests/test_window_profile.py` imported Qt with no guard at all.
2. `tests/test_cli_offer_dialog.py` guarded the import correctly and then
   read `QMessageBox.ButtonRole` in a **class body** - which runs at import
   time, exactly like the import it was protecting itself from.

The second is the interesting one: the guard was there and looked right. So
the rule below is about *use*, not about the guard - a name that may be
`None` must not be reached through at module level.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent

#: Installed by `requirements.txt` and still unimportable on a machine with
#: no GL/EGL libraries, which is what a CI container is. Any module that
#: needs it has to survive its absence.
_OPTIONAL = ("PySide6",)


def _test_modules():
    return sorted(HERE.glob("test_*.py"))


def _module_level_nodes(tree: ast.Module):
    """Everything that executes when the module is imported, unprotected.

    Class bodies are included - that is the whole point - and function
    bodies are not, because they run when a test runs, by which time the
    skip has already been decided.

    A `try` block's own body is excluded too, and so is its `else`: code
    there is covered by the very handler that binds the `None`, so

        try:
            from audit.driver import available
            _CAN_PRINT = bool(available()[0])
        except Exception:
            _CAN_PRINT = False

    is correct however `available` fails. `except` and `finally` clauses are
    *not* excluded: those run precisely when the import did not.
    """
    stack = list(tree.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        yield node
        if isinstance(node, ast.Try):
            children = [*node.handlers, *node.finalbody]
        else:
            children = list(ast.iter_child_nodes(node))
        stack.extend(children)


class NoTestModuleFailsAtImport(unittest.TestCase):

    def test_an_optional_import_is_guarded(self):
        offenders = []
        for path in _test_modules():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in tree.body:  # top level only: a `try` is not `body`
                module = ""
                if isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                elif isinstance(node, ast.Import):
                    module = ",".join(alias.name for alias in node.names)
                if any(name in module for name in _OPTIONAL):
                    offenders.append(
                        f"{path.name}:{node.lineno} imports {module} with no "
                        f"try/except - a machine without it cannot collect "
                        f"this file, and pytest stops the whole suite")
        self.assertEqual(offenders, [], "\n" + "\n".join(offenders))

    def test_a_guarded_name_is_not_reached_through_at_import_time(self):
        """`X = None` in the `except` only helps if nobody says `X.thing`.

        Attribute access and calls are the two ways a `None` placeholder
        blows up while the module is still being imported. Comparing it
        (`X is None`) or handing it to `getattr` is exactly what the guard is
        for, so those stay legal.
        """
        offenders = []
        for path in _test_modules():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            guarded = set()
            for node in tree.body:
                if not isinstance(node, ast.Try):
                    continue
                for inner in ast.walk(node):
                    if isinstance(inner, (ast.Import, ast.ImportFrom)):
                        for alias in inner.names:
                            guarded.add(alias.asname
                                        or alias.name.split(".")[0])
            if not guarded:
                continue
            for node in _module_level_nodes(tree):
                if isinstance(node, ast.Attribute):
                    target, how = node.value, f".{node.attr}"
                elif isinstance(node, ast.Call):
                    target, how = node.func, "(...)"
                else:
                    continue
                if isinstance(target, ast.Name) and target.id in guarded:
                    offenders.append(
                        f"{path.name}:{node.lineno} reads "
                        f"{target.id}{how} at import time, but {target.id} "
                        f"is only bound if a guarded import succeeded")
        self.assertEqual(offenders, [], "\n" + "\n".join(sorted(set(offenders))))


if __name__ == "__main__":
    unittest.main()
