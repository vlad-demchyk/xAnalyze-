"""Real local model loading plus mathematical research statistics, without accuracy claims."""
from copy import deepcopy
import itertools
import json
import math

import pytest

torch = pytest.importorskip("torch")

from tests.test_validation_contract import sample, dataset
from validation import adapters, local_models as local, protocol


@pytest.fixture
def tiny_models(tmp_path):
    from tokenizers import Tokenizer
    from tokenizers.models import WordLevel
    from tokenizers.pre_tokenizers import Whitespace
    from transformers import (BertConfig, BertForSequenceClassification,
        GPT2Config, GPT2LMHeadModel, PreTrainedTokenizerFast)
    vocab = {word: i for i, word in enumerate(["[PAD]", "[UNK]", "[BOS]", "[EOS]", "This", "is", "a", "fixture", "text", "."])}
    core = Tokenizer(WordLevel(vocab, unk_token="[UNK]"));core.pre_tokenizer = Whitespace()
    tokenizer = PreTrainedTokenizerFast(tokenizer_object=core, pad_token="[PAD]", unk_token="[UNK]",
                                       bos_token="[BOS]", eos_token="[EOS]")
    paths = {}
    for key, seed in (("scoring", 1), ("reference", 2), ("classifier", 3)):
        path = tmp_path / key;path.mkdir()
        torch.manual_seed(seed)
        if key == "classifier":
            model = BertForSequenceClassification(BertConfig(vocab_size=len(vocab), hidden_size=8,
                num_hidden_layers=1, num_attention_heads=2, intermediate_size=16, max_position_embeddings=32,
                num_labels=2, id2label={0: "human", 1: "model"}, label2id={"human": 0, "model": 1}))
        else:
            model = GPT2LMHeadModel(GPT2Config(vocab_size=len(vocab), n_embd=8, n_layer=1, n_head=2,
                n_positions=32, bos_token_id=2, eos_token_id=3, pad_token_id=0))
        model.save_pretrained(path, safe_serialization=True)
        tokenizer.save_pretrained(path)
        paths[key] = str(path)
    return paths


def config(name, paths):
    if name == "multilingual-encoder":
        return {"model_path": paths["classifier"], "ai_class_index": 1, "languages": "en,it,uk"}
    if name == "fast-detectgpt":
        return {"scoring_model_path": paths["scoring"], "reference_model_path": paths["reference"]}
    return {"observer_model_path": paths["reference"], "performer_model_path": paths["scoring"]}


def test_fast_detectgpt_matches_exact_conditional_sampling_distribution():
    reference = torch.tensor([[[.2, 1.1, -.3], [.7, -.8, .4]]], dtype=torch.float64)
    scoring = torch.tensor([[[1.3, .4, -.2], [-.1, .8, .2]]], dtype=torch.float64)
    labels = torch.tensor([[0, 1]])
    probs = reference.softmax(-1)[0].tolist();logs = scoring.log_softmax(-1)[0].tolist()
    distribution = [(probs[0][a] * probs[1][b], logs[0][a] + logs[1][b]) for a, b in itertools.product(range(3), repeat=2)]
    mean = sum(p * value for p, value in distribution)
    variance = sum(p * (value - mean) ** 2 for p, value in distribution)
    expected = (logs[0][0] + logs[1][1] - mean) / math.sqrt(variance)
    assert local.sampling_discrepancy(reference, scoring, labels) == pytest.approx(expected, abs=1e-12)


def test_binoculars_matches_next_token_nll_over_full_position_cross_entropy():
    observer = torch.tensor([[[1., 0.], [.3, .8], [-.2, .5]]], dtype=torch.float64)
    performer = torch.tensor([[[.4, .2], [.7, -.1], [1.1, .3]]], dtype=torch.float64)
    ids = torch.tensor([[0, 1, 0]]);mask = torch.ones_like(ids)
    probabilities = observer.softmax(-1)[0].tolist();logits = performer.log_softmax(-1)[0].tolist()
    nll = -(logits[0][1] + logits[1][0]) / 2
    entropy = -sum(sum(p * log for p, log in zip(row, lp)) for row, lp in zip(probabilities, logits)) / 3
    assert local.binoculars_statistic(observer, performer, ids, mask, None) == pytest.approx(nll / entropy, abs=1e-12)


def test_degenerate_variance_is_not_fabricated_as_zero_discrepancy():
    with pytest.raises(ValueError, match="variance"):
        local.sampling_discrepancy(torch.zeros(1, 2, 3), torch.zeros(1, 2, 3), torch.zeros(1, 2, dtype=torch.long))


def test_vocabulary_and_token_alignment_are_required():
    with pytest.raises(ValueError, match="aligned"):
        local.sampling_discrepancy(torch.zeros(1, 2, 3), torch.zeros(1, 2, 4), torch.zeros(1, 2, dtype=torch.long))


def test_rank_transform_preserves_opposite_method_directions_without_probability_claims():
    assert local.oriented_score(2) > local.oriented_score(1)
    assert local.oriented_score(2, False) < local.oriented_score(1, False)
    assert local.oriented_score(-1000) == 0 and local.oriented_score(1000) == 1


@pytest.mark.parametrize("name", local.MODEL_METHODS)
def test_frozen_local_checkpoints_really_load_and_infer_without_downloads(tiny_models, name, monkeypatch):
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    settings = config(name, tiny_models)
    identity = adapters.detector_identity(name, settings)
    assert identity["snapshot_verified"]
    result = adapters.score_samples([sample("local", text="This is a fixture text.")], name, settings, [])[0]
    assert result["status"] == "checked" and 0 <= result["score"] <= 1
    assert not result["localization_supported"] and not result["truncated"]
    assert math.isfinite(result["raw_score"])
    assert result["cost_usd"] == 0


def test_weight_or_tokenizer_changes_invalidate_frozen_identity(tiny_models):
    settings=config("multilingual-encoder",tiny_models)
    before=adapters.detector_identity("multilingual-encoder",settings)
    path=__import__('pathlib').Path(tiny_models['classifier'])/'tokenizer_config.json'
    data=json.loads(path.read_text());data['fixture_changed']=True;path.write_text(json.dumps(data))
    after=adapters.detector_identity("multilingual-encoder",settings)
    assert before["fingerprint"] != after["fingerprint"]


def test_long_input_abstains_instead_of_silently_truncating(tiny_models):
    settings={**config("fast-detectgpt",tiny_models),"max_tokens":4}
    result=adapters.score_samples([sample("long",text="This is a fixture text.")],"fast-detectgpt",settings,[])[0]
    assert result["status"] == "abstained" and result["score"] is None


def test_unavailable_checkpoint_never_becomes_a_human_negative():
    result=adapters.score_samples([sample("missing")],"fast-detectgpt",{},[])[0]
    assert result["status"] == "abstained" and result["score"] is None
    assert not adapters.detector_identity("fast-detectgpt",{})["snapshot_verified"]


@pytest.mark.parametrize("name", local.MODEL_METHODS)
def test_real_cli_freeze_and_locked_test_with_owned_tiny_models(tiny_models, tmp_path, monkeypatch, name):
    from scripts.benchmark import main
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("XANALYZE_VALIDATION_LEDGER", str(tmp_path / "ledger"))
    data = tmp_path / "dataset.json";data.write_text(json.dumps(dataset()))
    settings = tmp_path / "config.json";settings.write_text(json.dumps(config(name, tiny_models)))
    frozen = tmp_path / "protocol.json"
    report = tmp_path / "report.json"
    assert main(["freeze", str(data), "--detector", name, "--config", str(settings),
                 "--fixed-threshold", "1", "--output", str(frozen)]) == 0
    assert main(["run", str(data), "--protocol", str(frozen), "--output", str(report)]) == 2
    result = json.loads(report.read_text())
    assert result["protocol"]["detector"]["snapshot_verified"]
    assert all(r["status"] == "checked" for r in result["predictions"])
    assert not result["quality"]["passed"] and result["protocol"]["purpose"] == "fixture"
    assert main(["run", str(data), "--protocol", str(frozen), "--output", str(tmp_path / "again.json")]) == 1


@pytest.mark.parametrize("phase", ["calibration", "test"])
def test_local_artifact_changed_during_scoring_rejects_run_and_keeps_test_consumed(tiny_models, tmp_path, monkeypatch, phase):
    from pathlib import Path
    monkeypatch.setenv("XANALYZE_VALIDATION_LEDGER", str(tmp_path / "ledger"))
    settings = config("multilingual-encoder", tiny_models)
    original = protocol.score_samples
    frozen = protocol.freeze(dataset(), "multilingual-encoder", settings, fixed_threshold=1.) if phase == "test" else None
    def changing(*args, **kwargs):
        results = original(*args, **kwargs)
        path = Path(tiny_models["classifier"]) / "tokenizer_config.json"
        value = json.loads(path.read_text());value["changed_during_run"] = True
        path.write_text(json.dumps(value))
        return results
    monkeypatch.setattr(protocol, "score_samples", changing)
    with pytest.raises(ValueError, match="artifact changed during"):
        if phase == "test":
            protocol.evaluate(dataset(), frozen)
        else:
            protocol.freeze(dataset(), "multilingual-encoder", settings, fixed_threshold=1.)
    if phase == "test":
        with pytest.raises(ValueError, match="already exposed"):
            protocol.freeze(dataset(), "multilingual-encoder", settings, fixed_threshold=1.)
