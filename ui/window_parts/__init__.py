"""MainWindow decomposed into concern-scoped mixins.

`ui.main_window` stays the facade: it composes the mixins, owns the
constructor and the shared widget attributes every part reaches through
`self`. One concern per module - audit findings, flagged text findings,
bulk rewrite actions, account control - so each stays readable on its own.
"""
