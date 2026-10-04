import importlib.util
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree

from incentivescope.ml_report import render_ml


@unittest.skipUnless(importlib.util.find_spec("matplotlib"), "Install optional ml dependencies for scientific report rendering")
class MLReportCheck(unittest.TestCase):
    def test_saved_evidence_figures_and_safe_honest_comparison(self):
        def metrics(ap, n=10, positives=2, probability=True):
            return {"n": n, "positives": positives, "prevalence": positives / n,
                    "average_precision": ap, "roc_auc": .7, "top10_precision": .5,
                    "top10_recall": .25, "top10_lift": 2.5, "top10_count": 1,
                    "brier": .18 if probability else None, "log_loss": .6 if probability else None,
                    "pr_curve": {"precision": [.2, .5, 1], "recall": [1, .5, 0], "thresholds": [.1, .8]},
                    "reliability": [{"mean_probability": .1, "observed_rate": .2, "count": n}] if probability else []}

        models = []
        for name, validation_ap, test_ap in (("constant", .2, .2), ("recency", .3, .3),
                                              ("logistic_regression", .4, .35),
                                              ("hist_gradient_boosting", .5, .44), ("pytorch_mlp", .45, .3)):
            models.append({"name": name, "config": {}, "validation": metrics(validation_ap), "test": metrics(test_ap, probability=name != "recency"),
                           "subgroups": {"seen_in_training": metrics(test_ap, n=6, positives=1),
                                         "new_to_training": metrics(test_ap, n=4, positives=1)}})
        feature_names = [f"{prefix}_{days}d" for days in (7, 30, 60)
                         for prefix in ("opening_count", "active_days", "opening_size_usd", "opening_fee_usd")]
        feature_names += ["days_since_first_observed_opening", "days_since_last_opening", "pre_campaign_opening",
                          "market_count_30d", "top_market_share_30d"]
        result = {
            "dataset": {"is_synthetic": True, "sha256": "a" * 64, "coverage_start": "2023-09-20T00:00:00Z",
                        "coverage_end": "2024-05-29T00:00:00Z", "source_url": "javascript:alert(1)"},
            "campaign": {"name": '</script><script>alert("unsafe")</script>'}, "models": models,
            "split_summary": [{"split": "test", "as_of": "2024-03-27T00:00:00Z", "label_start": "2024-04-19T00:00:00Z",
                               "label_end": "2024-04-26T00:00:00Z", "n": 10, "positive": 2, "unique_accounts": 10}],
            "feature_names": feature_names, "log_features": feature_names[:14] + ["market_count_30d"],
            "training_unique_accounts": 6, "selected_model": "hist_gradient_boosting", "primary_seed": 42,
            "preprocessing": {"fit_split": "train"}, "provenance": {"code_commit": "b" * 40},
            "mlp_seed_results": [{"seed": seed, "best_epoch": 2, "checkpoint": f"mlp-seed-{seed}.pt",
                                  "validation": metrics(.45), "test": metrics(.3),
                                  "history": [{"epoch": 1, "train_loss": .6, "validation_ap": .3},
                                              {"epoch": 2, "train_loss": .5, "validation_ap": .45}]} for seed in (17, 42, 73)],
            "permutation_importance": [{"feature": name, "ap_drop_mean": .01, "ap_drop_std": .003, "repeats": 10} for name in feature_names],
            "notes": ['<script>alert("note")</script>'],
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_ml(result, output)
            page = (output / "index.html").read_text(encoding="utf-8")
            note = (output / "research.md").read_text(encoding="utf-8")
            self.assertIn("SYNTHETIC MODEL DEMONSTRATION", page)
            self.assertIn("2 / 10", page)
            self.assertIn("Primary MLP test AP is 0.3", page)
            self.assertIn("strongest baseline by validation AP, has test AP 0.44", page)
            self.assertIn("not sampling uncertainty", page)
            self.assertIn("2024-04-19T00:00:00Z", page)
            self.assertIn("2024-04-26T00:00:00Z", page)
            self.assertIn("Dune execution and independent cross-source agreement have not been established", page)
            self.assertNotIn('<script>alert("unsafe")', page)
            self.assertNotIn('<script>alert("note")', page)
            self.assertNotIn('href="javascript:', page)
            self.assertIn("&lt;script&gt;alert", page)
            self.assertIn("Primary MLP test AP is 0.3", note)
            svgs = list((output / "figures").glob("*.svg"))
            self.assertEqual(len(svgs), 5)
            self.assertEqual(len(list((output / "figures").glob("*.png"))), 5)
            for path in svgs:
                ElementTree.parse(path)
                self.assertGreater(path.with_suffix(".png").stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
