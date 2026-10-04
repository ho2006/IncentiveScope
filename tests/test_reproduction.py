"""Rehearsal receipts must fail when learned data or analytical results change."""

import csv
import gzip
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/verify_reproduction.py"
spec = importlib.util.spec_from_file_location("verify_reproduction", SCRIPT)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class ReproductionCheck(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="incentivescope-reproduction-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.reference, self.candidate = self.root / "reference", self.root / "candidate"
        self.input = self.root / "trades.csv"
        self.input.write_bytes(b"frozen input\n")
        self.sha = hashlib.sha256(self.input.read_bytes()).hexdigest()
        self.core = {"dataset": {"sha256": self.sha}, "summary": {"cohort_size": 10, "r30": {"n": 2}},
                     "activity": {"position_fee_usd": 100.25}}
        self.ml = {"dataset": {"sha256": self.sha}, "feature_names": ["opening_count_7d"],
                   "models": [{"test": {"average_precision": 0.5}, "config": {"C": 1}}],
                   "mlp_seed_results": [{"seed": 42, "checkpoint": "mlp-seed-42.pt", "best_epoch": 2}],
                   "provenance": {"input_sha256": self.sha, "config_sha256": "config-hash",
                                  "manifest_sha256": "manifest-hash", "source_sha256": {"ml.py": "source-hash"},
                                  "code_commit": "reference-commit", "tracked_worktree_dirty": False,
                                  "executed_at": "earlier", "platform": "same CPU platform",
                                  "python": "3.14.4", "versions": {"torch": "2.14.1+cpu"}, "device": "cpu"}}
        self.populate()

    def populate(self):
        for core, ml in ((self.reference / "reports/gmx-stip", self.reference / "reports/gmx-stip/ml"),
                         (self.candidate / "core", self.candidate / "ml")):
            core.mkdir(parents=True, exist_ok=True)
            ml.mkdir(parents=True, exist_ok=True)
            (core / "results.json").write_text(json.dumps(self.core), encoding="utf-8")
            result = json.loads(json.dumps(self.ml))
            if ml.is_relative_to(self.candidate):
                result["provenance"].update(code_commit="tested-commit", executed_at="later")
            (ml / "results.json").write_text(json.dumps(result), encoding="utf-8")
            (ml / "preprocessing.json").write_text('{"mean": [0.5], "fit_split": "train"}', encoding="utf-8")
            (ml / "mlp-seed-42.pt").write_bytes(b"fixed weights")
            self.csv(core / "wallet_cohorts.csv", ["account", "r30", "campaign_volume_usd"], ["a", "True", "123.25"])
            self.csv(core / "wallet_daily.csv", ["account", "day", "position_fee_usd"], ["a", "2024-01-01", "100.25"])
            self.csv(ml / "features.csv.gz", ["account", "as_of", "label", "opening_count_7d"], ["a", "cutoff", "1", "2"])
            self.csv(ml / "predictions.csv.gz", ["account", "seed", "label", "score"], ["a", "42", "1", "0.5"])
            self.csv(ml / "training_curve.csv", ["seed", "epoch", "train_loss", "validation_ap"], ["42", "1", "0.7", "0.5"])

    @staticmethod
    def csv(path, header, row):
        opened = gzip.open(path, "wt", encoding="utf-8", newline="") if path.suffix == ".gz" else path.open(
            "w", encoding="utf-8", newline="")
        with opened as stream:
            writer = csv.writer(stream)
            writer.writerow(header)
            writer.writerow(row)

    def verify(self, **kwargs):
        return verifier.verify(self.reference, self.candidate, self.input, **kwargs)

    def test_exact_replay_accepts_only_incidental_execution_metadata(self):
        receipt = self.verify()
        self.assertIs(receipt["passed"], True)
        self.assertEqual(receipt["tested_commit"], "tested-commit")
        self.assertEqual(receipt["input_sha256"], self.sha)
        self.assertTrue(all(row["accepted_float_drift_count"] == 0 for row in receipt["checks"]
                            if "accepted_float_drift_count" in row))

    def test_analytical_and_raw_data_mutations_fail(self):
        mutations = {
            "core_count": lambda: self.edit_json("core/results.json", lambda d: d["summary"]["r30"].update(n=3)),
            "ml_metric": lambda: self.edit_json("ml/results.json", lambda d: d["models"][0]["test"].update(average_precision=0.51)),
            "configuration": lambda: self.edit_json("ml/results.json", lambda d: d["models"][0]["config"].update(C=10)),
            "preprocessing": lambda: (self.candidate / "ml/preprocessing.json").write_text('{"mean": [0.6], "fit_split": "train"}'),
            "weights": lambda: (self.candidate / "ml/mlp-seed-42.pt").write_bytes(b"changed weights"),
            "features": lambda: self.csv(self.candidate / "ml/features.csv.gz", ["account", "as_of", "label", "opening_count_7d"], ["a", "cutoff", "1", "3"]),
            "predictions": lambda: self.csv(self.candidate / "ml/predictions.csv.gz", ["account", "seed", "label", "score"], ["a", "42", "1", "0.6"]),
            "epochs": lambda: self.csv(self.candidate / "ml/training_curve.csv", ["seed", "epoch", "train_loss", "validation_ap"], ["42", "2", "0.7", "0.5"]),
            "dependency_version": lambda: self.edit_json("ml/results.json", lambda d: d["provenance"]["versions"].update(torch="changed")),
            "dirty_source": lambda: self.edit_json("ml/results.json", lambda d: d["provenance"].update(tracked_worktree_dirty=True)),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                self.populate()
                mutate()
                receipt = self.verify()
                self.assertIs(receipt["passed"], False)
                self.assertTrue(any(row["difference_count"] for row in receipt["checks"]))

    def edit_json(self, name, mutate):
        path = self.candidate / name
        result = json.loads(path.read_text(encoding="utf-8"))
        mutate(result)
        path.write_text(json.dumps(result), encoding="utf-8")

    def test_core_tolerance_is_opt_in_recorded_and_cannot_hide_ml_changes(self):
        self.edit_json("core/results.json", lambda d: d["activity"].update(position_fee_usd=100.25000000001))
        self.assertIs(self.verify()["passed"], False)
        receipt = self.verify(core_float_tolerance=1e-12)
        self.assertIs(receipt["passed"], True)
        self.assertEqual(receipt["checks"][0]["accepted_float_drift_count"], 1)
        self.assertEqual(receipt["comparison_policy"]["core_float_tolerance"], 1e-12)
        self.edit_json("ml/results.json", lambda d: d["models"][0]["test"].update(average_precision=0.5000000000000001))
        self.assertIs(self.verify(core_float_tolerance=1e-12)["passed"], False)
        self.populate()
        self.edit_json("core/results.json", lambda d: d["summary"]["r30"].update(n=3))
        self.assertIs(self.verify(core_float_tolerance=1e-12)["passed"], False)

    def test_different_downloaded_input_fails(self):
        self.input.write_bytes(b"different input")
        receipt = self.verify()
        self.assertIs(receipt["passed"], False)
        check = next(row for row in receipt["checks"] if row["name"] == "input_checksum")
        self.assertFalse(check["passed"])


if __name__ == "__main__":
    unittest.main()
