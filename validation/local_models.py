"""Frozen local Transformers adapters and published logits-based research statistics."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
from time import perf_counter

from lang_detect import guess_language_safe
from .corpus import digest

MODEL_METHODS = ("multilingual-encoder", "fast-detectgpt", "binoculars")
PATHS = {"multilingual-encoder": ("model_path",),
         "fast-detectgpt": ("scoring_model_path", "reference_model_path"),
         "binoculars": ("observer_model_path", "performer_model_path")}
COMMON_SETTINGS = {"max_tokens", "device"}


def validate_model_config(name, config):
    allowed = set(PATHS.get(name, ())) | COMMON_SETTINGS
    if name == "multilingual-encoder":
        allowed |= {"ai_class_index", "languages"}
    if name not in MODEL_METHODS or not isinstance(config, dict) or set(config) - allowed:
        raise ValueError("invalid local-model benchmark configuration")
    for key in PATHS[name]:
        if key in config and (not isinstance(config[key], str) or not config[key]):
            raise ValueError(f"invalid {key}")
    count = config.get("max_tokens", 512)
    if type(count) is not int or not 2 <= count <= 8192:
        raise ValueError("max_tokens must be between 2 and 8192")
    if config.get("device", "cpu") not in ("cpu", "mps", "cuda"):
        raise ValueError("invalid inference device")
    if name == "multilingual-encoder":
        if type(config.get("ai_class_index")) is not int or config["ai_class_index"] < 0:
            raise ValueError("classifier requires explicit ai_class_index")
        if not isinstance(config.get("languages"), str) or not config["languages"]:
            raise ValueError("classifier requires explicit declared language scope")
        if any(not language.strip() for language in config["languages"].split(",")):
            raise ValueError("invalid declared classifier language scope")


def artifact_identity(name, config):
    """Hash local config, tokenizer and safetensors weights; never resolve Hub IDs."""
    validate_model_config(name, config)
    artifacts = {}
    for key in PATHS[name]:
        folder = Path(config[key]) if key in config else None
        if folder is None or not folder.is_dir():
            artifacts[key] = {"status": "unavailable", "reason": "local model directory missing"}
            continue
        files = sorted(p for p in folder.rglob("*") if p.is_file() and
                       (p.suffix in (".json", ".safetensors", ".model") or p.name in ("vocab.txt", "merges.txt")))
        hashes = {}
        for path in files:
            hasher = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    hasher.update(chunk)
            hashes[str(path.relative_to(folder))] = hasher.hexdigest()
        present = "config.json" in hashes and any(p.endswith(".safetensors") for p in hashes) and any(
            p in hashes for p in ("tokenizer.json", "vocab.json", "vocab.txt", "tokenizer.model", "sentencepiece.bpe.model"))
        artifacts[key] = {"status": "frozen" if present else "unavailable", "files": hashes,
                          "sha256": digest(hashes), "reason": "" if present else "config/tokenizer/safetensors missing"}
    return artifacts


def _statistics_logits(logits):
    """Move MPS logits before casting: even a combined device/dtype to() fails."""
    if logits.device.type == "mps":
        logits = logits.cpu()
    return logits.double()


def sampling_discrepancy(reference_logits, scoring_logits, labels):
    """Fast-DetectGPT analytic conditional log-likelihood discrepancy."""
    import torch
    if scoring_logits.ndim != 3 or scoring_logits.shape[0] != 1 or reference_logits.shape != scoring_logits.shape or labels.shape != scoring_logits.shape[:-1]:
        raise ValueError("aligned token positions and vocabulary are required")
    scoring_log_probabilities = _statistics_logits(scoring_logits).log_softmax(-1)
    reference_probabilities = _statistics_logits(reference_logits).to(scoring_log_probabilities.device).softmax(-1)
    labels = labels.to(scoring_log_probabilities.device)
    observed = scoring_log_probabilities.gather(-1, labels.unsqueeze(-1)).squeeze(-1)
    mean = (reference_probabilities * scoring_log_probabilities).sum(-1)
    variance = (reference_probabilities * (scoring_log_probabilities - mean.unsqueeze(-1)).square()).sum()
    if not torch.isfinite(variance) or variance <= torch.finfo(torch.float64).eps * labels.numel():
        raise ValueError("sampling discrepancy has zero/nonfinite variance")
    value = ((observed - mean).sum() / variance.sqrt()).item()
    if not math.isfinite(value):
        raise ValueError("nonfinite sampling discrepancy")
    return value


def binoculars_statistic(observer_logits, performer_logits, input_ids, attention_mask, pad_token_id):
    """Published performer next-token NLL / observer-to-performer cross-entropy."""
    import torch
    if performer_logits.ndim != 3 or performer_logits.shape[0] != 1 or observer_logits.shape != performer_logits.shape or input_ids.shape != performer_logits.shape[:-1] or attention_mask.shape != input_ids.shape:
        raise ValueError("aligned vocabulary and token positions are required")
    log_performer = _statistics_logits(performer_logits).log_softmax(-1)
    input_ids = input_ids.to(log_performer.device)
    attention_mask = attention_mask.to(log_performer.device)
    valid_next = attention_mask[:, 1:].bool()
    valid_cross = input_ids != pad_token_id if pad_token_id is not None else attention_mask.bool()
    if not valid_next.any() or not valid_cross.any():
        raise ValueError("no valid tokens for Binoculars")
    observed_nll = -log_performer[:, :-1].gather(-1, input_ids[:, 1:].unsqueeze(-1)).squeeze(-1)
    numerator = observed_nll[valid_next].mean()
    cross_entropy = -(_statistics_logits(observer_logits).to(log_performer.device).softmax(-1) * log_performer).sum(-1)
    denominator = cross_entropy[valid_cross].mean()
    if not torch.isfinite(denominator) or denominator <= 0:
        raise ValueError("zero/nonfinite Binoculars cross-entropy")
    value = (numerator / denominator).item()
    if not math.isfinite(value):
        raise ValueError("nonfinite Binoculars score")
    return value


def oriented_score(raw, higher_ai=True):
    """Monotonic bounded ranking score, not an AI-authorship probability."""
    if not math.isfinite(raw):
        raise ValueError("nonfinite raw research score")
    value = raw if higher_ai else -raw
    return 1 / (1 + math.exp(-value)) if value >= 0 else math.exp(value) / (1 + math.exp(value))


class LocalModelAdapter:
    def __init__(self, name, config):
        validate_model_config(name, config)
        self.name, self.config = name, dict(config)
        self.artifacts = artifact_identity(name, config)
        self.tokenizers, self.models = {}, {}

    def available(self):
        return all(item["status"] == "frozen" for item in self.artifacts.values())

    def _load(self):
        if self.models:
            return
        from transformers import AutoTokenizer, AutoModelForCausalLM, AutoModelForSequenceClassification
        model_class = AutoModelForSequenceClassification if self.name == "multilingual-encoder" else AutoModelForCausalLM
        tokenizers, models = {}, {}
        for key in PATHS[self.name]:
            path = str(Path(self.config[key]).resolve())
            tokenizers[key] = AutoTokenizer.from_pretrained(path, local_files_only=True, trust_remote_code=False)
            model, loading = model_class.from_pretrained(path, local_files_only=True, trust_remote_code=False,
                                                         use_safetensors=True, output_loading_info=True)
            fields = ("missing_keys", "mismatched_keys", "error_msgs")
            if not isinstance(loading, dict) or any(not isinstance(loading.get(field), (list, tuple, set)) for field in fields):
                raise ValueError("model loading diagnostics unavailable")
            if any(loading[field] for field in fields):
                raise ValueError("missing or mismatched checkpoint weights; random initialization is forbidden")
            models[key] = model.to(self.config.get("device", "cpu")).eval()
        if len(tokenizers) > 1:
            first, second = tokenizers.values()
            if first.get_vocab() != second.get_vocab() or first.all_special_ids != second.all_special_ids:
                raise ValueError("research model tokenizers/vocabularies differ")
        # Reject a checkpoint that changed between hashing and model loading.
        if artifact_identity(self.name, self.config) != self.artifacts:
            raise ValueError("local model artifact changed during loading")
        self.tokenizers, self.models = tokenizers, models

    def score(self, text):
        import torch
        device = self.config.get("device", "cpu")
        if ((device == "mps" and not torch.backends.mps.is_available())
                or (device == "cuda" and not torch.cuda.is_available())):
            return {"status": "abstained", "reason": f"requested {device} device unavailable; no device substitution"}
        self._load()
        encodings = {}
        for key, tokenizer in self.tokenizers.items():
            encoded = tokenizer(text, return_tensors="pt", return_token_type_ids=False, truncation=False)
            count = encoded["input_ids"].shape[-1]
            limit = self.config.get("max_tokens", 512)
            for attribute in ("max_position_embeddings", "n_positions"):
                context = getattr(self.models[key].config, attribute, None)
                if type(context) is int and context > 0:
                    limit = min(limit, context)
            if count < 2 or count > limit:
                return {"status": "abstained", "reason": "outside declared token range; input not truncated"}
            encodings[key] = {k: v.to(self.config.get("device", "cpu")) for k, v in encoded.items()}
        if len(encodings) > 1:
            first, second = encodings.values()
            if not torch.equal(first["input_ids"], second["input_ids"]):
                raise ValueError("research models tokenize this text differently")
        with torch.inference_mode():
            logits = {key: model(**encodings[key]).logits for key, model in self.models.items()}
        if self.name == "multilingual-encoder":
            values = logits["model_path"]
            index = self.config["ai_class_index"]
            if values.ndim != 2 or index >= values.shape[-1] or values.shape[-1] < 2:
                raise ValueError("invalid classifier output/AI label mapping")
            raw = _statistics_logits(values).softmax(-1)[0, index].item()
            score, semantics = raw, "declared AI-class softmax, calibration required"
        elif self.name == "fast-detectgpt":
            labels = encodings["scoring_model_path"]["input_ids"][:, 1:]
            raw = sampling_discrepancy(logits["reference_model_path"][:, :-1], logits["scoring_model_path"][:, :-1], labels)
            score, semantics = oriented_score(raw), "logistic of analytic discrepancy; ranking, not probability"
        else:
            encoded = encodings["observer_model_path"]
            raw = binoculars_statistic(logits["observer_model_path"], logits["performer_model_path"],
                                       encoded["input_ids"], encoded["attention_mask"], self.tokenizers["observer_model_path"].pad_token_id)
            score, semantics = oriented_score(raw, higher_ai=False), "logistic of negative Binoculars ratio; ranking, not probability"
        if not math.isfinite(score):
            raise ValueError("nonfinite local model score")
        inference_device = next(iter(logits.values())).device
        return {"status": "checked", "score": score, "raw_score": raw, "score_semantics": semantics,
                "inference_device": str(inference_device),
                "statistics_device": "cpu" if inference_device.type == "mps" else str(inference_device),
                "statistics_dtype": "float64",
                "token_count": count, "truncated": False, "localization_supported": False, "spans": []}


def score_local_samples(samples, name, config):
    adapter = LocalModelAdapter(name, config)
    languages = {value.strip() for value in config.get("languages", "").split(",")}
    results = []
    for row in samples:
        record = {**row, "status": "abstained", "score": None, "spans": [], "localization_supported": False,
                  "latency_ms": None, "cost_usd": 0.}
        if not adapter.available():
            record["reason"] = "frozen local config/tokenizer/safetensors unavailable"
        elif name == "multilingual-encoder" and guess_language_safe(row["text"]) not in languages | {None}:
            record["reason"] = "outside declared classifier language scope"
        else:
            start = perf_counter()
            try:
                record.update(adapter.score(row["text"]))
            except (ImportError, OSError, TypeError, ValueError, RuntimeError) as exc:
                record.update(status="error", reason=type(exc).__name__)
            record["latency_ms"] = (perf_counter() - start) * 1000
        results.append(record)
    return results
