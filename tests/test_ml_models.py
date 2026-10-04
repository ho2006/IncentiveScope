"""Optional checks for leakage controls, metrics and saved PyTorch inference."""

import copy
import csv
import gzip
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HAS_ML = all(importlib.util.find_spec(name) is not None for name in ("numpy", "sklearn", "torch"))


@unittest.skipUnless(HAS_ML, "Install the optional ml dependencies")
class ModelCheck(unittest.TestCase):
    def setUp(self):
        from incentivescope.ml_data import FEATURE_NAMES, LOG_FEATURES
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.output = Path(self.directory.name)
        self.data = {"feature_names": list(FEATURE_NAMES), "log_features": list(LOG_FEATURES), "rows": []}
        for split, count in (("train", 64), ("validation", 16), ("test", 16)):
            for index in range(count):
                row = {name: float(index % 9 + 1) for name in FEATURE_NAMES}
                row.update(account=f"0x{index:040x}" if split != "test" or index < 8 else f"0x{index + 100:040x}",
                           as_of={"train": "2024-01-17", "validation": "2024-02-21", "test": "2024-03-27"}[split],
                           split=split, label=index % 2, pre_campaign_opening=index % 2,
                           top_market_share_30d=(index % 4) / 4, days_since_last_opening=float(index))
                self.data["rows"].append(row)

    def test_train_only_scaling_and_feature_whitelist(self):
        import numpy as np
        from incentivescope.ml_models import prepare_features
        parts, fit = prepare_features(self.data)
        changed = copy.deepcopy(self.data)
        for row in changed["rows"]:
            if row["split"] != "train":
                row["opening_size_usd_30d"] = 1e15
        changed_parts, changed_fit = prepare_features(changed)
        self.assertEqual(fit, changed_fit)
        np.testing.assert_array_equal(parts["train"]["x"], changed_parts["train"]["x"])
        binary = self.data["feature_names"].index("pre_campaign_opening")
        np.testing.assert_array_equal(parts["train"]["x"][:, binary], [i % 2 for i in range(64)])
        changed["feature_names"].append("future_r30_label")
        with self.assertRaisesRegex(ValueError, "whitelist"):
            prepare_features(changed)
        changed = copy.deepcopy(self.data)
        changed["rows"][0]["opening_fee_usd_7d"] = float("nan")
        with self.assertRaisesRegex(ValueError, "finite"):
            prepare_features(changed)

    def test_exact_ap_ties_probabilities_and_degenerate_subgroups(self):
        import numpy as np
        from sklearn.metrics import average_precision_score
        from incentivescope.ml_models import evaluate
        result = evaluate([0, 1, 0, 1], [0.5] * 4, ["d", "c", "b", "a"])
        self.assertEqual(result["top10_count"], 1)
        self.assertEqual(result["top10_precision"], 1)
        self.assertEqual(result["average_precision"], 0.5)
        self.assertEqual(result["reliability"], [{"mean_probability": 0.5, "observed_rate": 0.5, "count": 4}])
        rng = np.random.default_rng(42)
        y, score = rng.integers(0, 2, 2000), rng.random(2000)
        exact = evaluate(y, score, [str(i) for i in range(2000)])
        self.assertEqual(exact["average_precision"], float(average_precision_score(y, score)))
        self.assertTrue(exact["pr_curve"]["sampled"])
        self.assertLessEqual(len(exact["pr_curve"]["precision"]), 500)
        self.assertEqual(sum(bin_["count"] for bin_ in exact["reliability"]), 2000)
        self.assertIsNone(evaluate([0, 0], [0.1, 0.2], ["a", "b"])["roc_auc"])
        self.assertIsNone(evaluate([0, 0], [0.1, 0.2], ["a", "b"])["average_precision"])
        self.assertIsNone(evaluate([], [], [])["prevalence"])
        ranking = evaluate([0, 1], [-10, -1], ["a", "b"], probability=False)
        self.assertEqual(ranking["average_precision"], 1)
        self.assertIsNone(ranking["brier"])
        with self.assertRaisesRegex(ValueError, "probability"):
            evaluate([0, 1], [-10, -1], ["a", "b"])
        with self.assertRaisesRegex(ValueError, "labels"):
            evaluate([0, 1.5], [0.1, 0.9], ["a", "b"])

    def test_cpu_training_checkpoint_reload_and_determinism(self):
        import numpy as np
        import torch
        from incentivescope.ml_models import _predict, load_checkpoint, prepare_features, run_models
        result = run_models(self.data, self.output, _max_epochs=2, _patience=2, _permutation_repeats=1)
        self.assertEqual(len(result["models"]), 5)
        self.assertEqual([row["seed"] for row in result["mlp_seed_results"]], [17, 42, 73])
        self.assertEqual(result["primary_seed"], 42)
        self.assertEqual(result["permutation_importance_split"], "validation")
        self.assertEqual(result["training_unique_accounts"], 64)
        expected = max(result["models"][2:], key=lambda row: row["validation"]["average_precision"])
        self.assertEqual(result["selected_model"], expected["name"])
        with gzip.open(self.output / "predictions.csv.gz", "rt", encoding="utf-8", newline="") as stream:
            saved = list(csv.DictReader(stream))
        self.assertEqual(len(saved), 7 * 16)
        self.assertEqual({row["split"] for row in saved}, {"test"})
        self.assertEqual(sum(row["seen_in_training"] == "1" for row in saved), 7 * 8)
        scores = [float(row["score"]) for row in saved if row["model"] == "pytorch_mlp" and row["seed"] == "42"]
        parts, _ = prepare_features(self.data)
        model = load_checkpoint(self.output / "mlp-seed-42.pt")
        np.testing.assert_array_equal(_predict(model, parts["test"]["x"], "cpu"), np.asarray(scores, dtype=np.float32))
        np.testing.assert_array_equal(_predict(model, parts["test"]["x"], "cpu"), _predict(model, parts["test"]["x"], "cpu"))
        self.assertTrue(all(torch.isfinite(value).all() for value in model.state_dict().values()))
        self.assertEqual(json.loads((self.output / "preprocessing.json").read_text())["fit_row_count"], 64)
        repeated = self.output / "repeated"
        again = run_models(self.data, repeated, _max_epochs=2, _patience=2, _permutation_repeats=1)
        self.assertEqual(result, again)
        self.assertEqual((self.output / "predictions.csv.gz").read_bytes(), (repeated / "predictions.csv.gz").read_bytes())
        changed = copy.deepcopy(self.data)
        for row in changed["rows"]:
            if row["split"] == "test":
                row["label"] = 1 - row["label"]
                row["opening_size_usd_30d"] += 1000
                row["days_since_last_opening"] += 50
        future_output = self.output / "changed-test"
        future = run_models(changed, future_output, _max_epochs=2, _patience=2, _permutation_repeats=1)
        self.assertEqual(result["preprocessing"], future["preprocessing"])
        self.assertEqual((self.output / "preprocessing.json").read_bytes(),
                         (future_output / "preprocessing.json").read_bytes())
        self.assertEqual(result["selected_model"], future["selected_model"])
        for original, changed_model in zip(result["models"], future["models"]):
            self.assertEqual(original["config"], changed_model["config"])
            self.assertEqual(original["validation"], changed_model["validation"])
        for original, changed_seed in zip(result["mlp_seed_results"], future["mlp_seed_results"]):
            self.assertEqual(original["history"], changed_seed["history"])
            self.assertEqual(original["validation"], changed_seed["validation"])
            original_weights = load_checkpoint(self.output / original["checkpoint"]).state_dict()
            future_weights = load_checkpoint(future_output / changed_seed["checkpoint"]).state_dict()
            for name in original_weights:
                torch.testing.assert_close(original_weights[name], future_weights[name], rtol=0, atol=0)
        self.assertTrue(any(original["test"] != changed_model["test"]
                            for original, changed_model in zip(result["models"], future["models"])))


if __name__ == "__main__":
    unittest.main()
