"""The abstract factory: registers detector classes by name and builds
configured instances on demand.

Usage:
    from detectors.factory import DetectorFactory
    from detectors import heuristic, claude_llm_judge, claude_watermark_stub  # noqa: F401 (registers)

    detector = DetectorFactory.create("heuristic")
    spans = detector.analyze_blocks(blocks)

Adding a new backend later (OpenAI, your own backend, a real Claude
watermark endpoint once published) means writing one class that implements
`Detector` and calling `DetectorFactory.register(...)` — nothing else in
the app needs to change.
"""
from __future__ import annotations

from .base import Detector


class DetectorFactory:
    _registry: dict[str, type[Detector]] = {}
    #: Retired names that still resolve, so an old `settings.json`, a CLI
    #: flag in someone's git hook, or a script written against a previous
    #: version keeps working instead of failing with "unknown detector".
    #: Aliases are resolved by `create()` but excluded from `available()`,
    #: so they never appear as separate entries in the UI's dropdown.
    _aliases: dict[str, str] = {}

    @classmethod
    def register(cls, name: str, detector_cls: type[Detector]) -> None:
        cls._registry[name] = detector_cls

    @classmethod
    def register_alias(cls, alias: str, target: str) -> None:
        cls._aliases[alias] = target

    @classmethod
    def resolve(cls, name: str) -> str:
        """Follow an alias to the name that is actually registered."""
        seen = set()
        while name in cls._aliases and name not in seen:
            seen.add(name)
            name = cls._aliases[name]
        return name

    @classmethod
    def available(cls) -> list[str]:
        return sorted(cls._registry.keys())

    @classmethod
    def create(cls, name: str, **config) -> Detector:
        resolved = cls.resolve(name)
        if resolved not in cls._registry:
            raise KeyError(
                f"Unknown detector '{name}'. Available: {', '.join(cls.available()) or '(none registered)'}"
            )
        return cls._registry[resolved](**config)
