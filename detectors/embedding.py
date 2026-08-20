"""Embedding-based AI text detector.

Uses sentence-transformers to compute embeddings and compare with reference
AI/human texts from the corpus. Complementary to the heuristic detector.

Approach:
1. Compute embeddings for AI texts in corpus (reference)
2. For new text, compute embedding
3. Compare with reference using cosine similarity
4. High similarity to AI texts → likely AI-generated

This detector is language-agnostic and works without explicit word lists.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from models import TextBlock, TextSpan, Confidence, score_to_confidence
from .base import Detector
from .factory import DetectorFactory

# Default model - small, fast, good quality
DEFAULT_MODEL = "all-MiniLM-L6-v2"

# Path to corpus relative to project root
CORPUS_PATH = Path(__file__).resolve().parent.parent / "corpus" / "labelled.jsonl"


class EmbeddingDetector(Detector):
    """Embedding-based AI text detector."""

    name = "embedding"
    display_name = "Embedding — semantic similarity to known AI texts"
    supported_languages = ("uk", "it", "en")

    def __init__(self, model_name: str = DEFAULT_MODEL,
                 corpus_path: str | None = None,
                 threshold: float = 0.60, **config):
        super().__init__(**config)
        self.model_name = model_name
        self.corpus_path = Path(corpus_path) if corpus_path else CORPUS_PATH
        self.threshold = threshold
        self._model = None
        self._reference_embeddings = None
        self._reference_labels = None
        self._reference_texts = None

    def _load_model(self):
        """Lazy-load the sentence-transformers model."""
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        except ImportError as exc:
            from .base import DetectorUnavailable
            raise DetectorUnavailable(
                "The 'sentence-transformers' package is not installed. "
                "Run: pip install sentence-transformers"
            ) from exc

    def _load_corpus(self):
        """Load reference corpus and compute embeddings."""
        if self._reference_embeddings is not None:
            return

        self._load_model()

        texts = []
        labels = []
        if self.corpus_path.exists():
            with open(self.corpus_path) as f:
                for line in f:
                    if line.strip():
                        row = json.loads(line)
                        texts.append(row["text"])
                        labels.append(row["label"])

        if not texts:
            from .base import DetectorUnavailable
            raise DetectorUnavailable(
                f"Corpus not found or empty: {self.corpus_path}"
            )

        self._reference_texts = texts
        self._reference_labels = labels
        self._reference_embeddings = self._model.encode(texts)

    def analyze_block(self, block: TextBlock) -> list[TextSpan]:
        """Analyze a single text block."""
        self._load_corpus()
        self._load_model()

        text = block.text
        if not text.strip():
            return []

        # Skip short texts - embeddings are unreliable for single words
        # or very short phrases. Minimum 5 words for meaningful analysis.
        word_count = len(text.split())
        if word_count < 5:
            return []

        # Compute embedding for input text
        text_embedding = self._model.encode([text])

        # Compute similarities with all reference texts
        similarities = self._model.similarity(text_embedding, self._reference_embeddings)[0]

        # Find most similar AI and human texts
        ai_sims = [float(s) for s, l in zip(similarities, self._reference_labels) if l == "model"]
        human_sims = [float(s) for s, l in zip(similarities, self._reference_labels) if l == "human"]

        ai_max = max(ai_sims) if ai_sims else 0.0
        human_max = max(human_sims) if human_sims else 0.0

        # Score: how much more similar to AI than to human
        score_raw = ai_max - human_max

        # Normalize to 0..1
        score = max(0.0, min(1.0, (score_raw + 1.0) / 2.0))

        # Skip if below threshold
        if score < self.threshold:
            return []

        # Find the most similar AI text for explanation
        ai_idx = np.argmax([float(s) for s, l in zip(similarities, self._reference_labels) if l == "model"])
        ai_texts = [t for t, l in zip(self._reference_texts, self._reference_labels) if l == "model"]
        similar_text = ai_texts[ai_idx][:80] if ai_idx < len(ai_texts) else ""

        details = {
            "source": "embedding",
            "ai_similarity": round(ai_max, 3),
            "human_similarity": round(human_max, 3),
            "model": self.model_name,
            "similar_to": similar_text,
        }

        explanation = (
            f"ai_similarity={ai_max:.3f}, human_similarity={human_max:.3f}"
            f" (similar to: {similar_text}...)"
        )

        return [
            TextSpan(
                block_id=block.block_id,
                start=0,
                end=len(text),
                score=score,
                confidence=score_to_confidence(score),
                detector_name=self.name,
                explanation=explanation,
                details=details,
            )
        ]


DetectorFactory.register(EmbeddingDetector.name, EmbeddingDetector)
