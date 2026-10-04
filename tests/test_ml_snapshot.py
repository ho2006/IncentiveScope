"""Audit the published ML receipt without raw events or ML dependencies."""

import csv
import gzip
import hashlib
import json
import math
import sys
import unittest
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/gmx-stip/ml"
FEATURES = [f"{name}_{days}d" for days in (7, 30, 60)
            for name in ("opening_count", "active_days", "opening_size_usd", "opening_fee_usd")] + [
                "days_since_first_observed_opening", "days_since_last_opening", "pre_campaign_opening",
                "market_count_30d", "top_market_share_30d"]
REFERENCES = [
    ("train", "2023-11-22T00:00:00Z", 2197, 560),
    ("train", "2023-12-06T00:00:00Z", 4457, 907),
    ("train", "2023-12-20T00:00:00Z", 6255, 997),
    ("train", "2024-01-03T00:00:00Z", 8095, 830),
    ("train", "2024-01-17T00:00:00Z", 11363, 1221),
    ("validation", "2024-02-21T00:00:00Z", 16634, 1598),
    ("test", "2024-03-27T00:00:00Z", 22145, 954),
]
RUNS = {("constant", ""), ("recency", ""), ("logistic_regression", ""),
        ("hist_gradient_boosting", ""), *(('pytorch_mlp', str(seed)) for seed in (17, 42, 73))}


def independent_metrics(rows, probability):
    """AP steps over tied scores; top-decile ties use address order."""
    count = len(rows)
    positives = sum(row["label"] for row in rows)
    scores = defaultdict(lambda: [0, 0])
    for row in rows:
        scores[row["score"]][0] += 1
        scores[row["score"]][1] += row["label"]
    cumulative_count = cumulative_positive = 0
    contributions = []
    for score in sorted(scores, reverse=True):
        group_count, group_positive = scores[score]
        cumulative_count += group_count
        cumulative_positive += group_positive
        if positives:
            contributions.append(group_positive / positives * cumulative_positive / cumulative_count)
    top_count = math.ceil(count * 0.1)
    ranked = sorted(rows, key=lambda row: (-row["score"], row["account"]))
    hits = sum(row["label"] for row in ranked[:top_count])
    result = {
        "n": count, "positives": positives, "prevalence": positives / count if count else None,
        "average_precision": math.fsum(contributions) if positives else None,
        "top10_count": top_count, "top10_precision": hits / top_count if top_count else None,
        "top10_recall": hits / positives if positives else None,
        "top10_lift": (hits / top_count) / (positives / count) if positives and top_count else None,
        "brier": None, "log_loss": None,
    }
    if probability and count:
        result["brier"] = math.fsum((row["score"] - row["label"]) ** 2 for row in rows) / count
        losses = []
        for row in rows:
            score = min(1 - sys.float_info.epsilon, max(sys.float_info.epsilon, row["score"]))
            losses.append(-math.log(score if row["label"] else 1 - score))
        result["log_loss"] = math.fsum(losses) / count
    return result


class MLPublicationCheck(unittest.TestCase):
    @unittest.skipUnless((REPORT / "results.json").exists(), "ML publication is not yet generated")
    def test_frozen_publication_receipt_and_independent_metrics(self):
        result = json.loads((REPORT / "results.json").read_text(encoding="utf-8"))
        receipt = json.loads((REPORT / "artifact-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["schema_version"], 1)
        self.assertIs(receipt["complete"], True)
        declared_files = set()
        for item in receipt["files"]:
            path = REPORT / item["file"]
            self.assertTrue(path.resolve().is_relative_to(REPORT.resolve()))
            self.assertNotIn(item["file"], declared_files)
            declared_files.add(item["file"])
            self.assertEqual(path.stat().st_size, item["bytes"], item["file"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["file"])
        actual_files = {path.relative_to(REPORT).as_posix() for path in REPORT.rglob("*")
                        if path.is_file() and path.name != "artifact-manifest.json"}
        self.assertEqual(declared_files, actual_files)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["feature_names"], FEATURES)
        self.assertEqual(result["log_features"], [name for name in FEATURES
                                                 if name not in {"pre_campaign_opening", "top_market_share_30d"}])
        frozen_sha = "76e4992debf0bf2e60328221c94c840aa97c2c7545550085bcd3e83d09fe61a3"
        self.assertEqual(result["dataset"]["sha256"], frozen_sha)
        self.assertEqual(result["provenance"]["input_sha256"], frozen_sha)
        self.assertEqual(result["primary_seed"], 42)
        self.assertEqual(result["training_unique_accounts"], 11363)
        self.assertEqual(len(result["split_summary"]), 7)
        expected = {}
        for summary, (split, date, count, positive) in zip(result["split_summary"], REFERENCES):
            expected[date] = (split, count, positive)
            self.assertEqual((summary["split"], summary["as_of"], summary["n"], summary["positive"]),
                             (split, date, count, positive))
            time = datetime.fromisoformat(date.replace("Z", "+00:00"))
            self.assertEqual(summary["label_start"], (time + timedelta(days=23)).isoformat().replace("+00:00", "Z"))
            self.assertEqual(summary["label_end"], (time + timedelta(days=30)).isoformat().replace("+00:00", "Z"))
            self.assertEqual(summary["unique_accounts"], count)
        feature_counts, positive_counts = Counter(), Counter()
        sample_keys, training_accounts, test_labels = set(), set(), {}
        inactive_count = inactive_positive = 0
        with gzip.open(REPORT / "features.csv.gz", "rt", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            self.assertEqual(reader.fieldnames, ["account", "as_of", "split", "label", *FEATURES])
            for row in reader:
                key = (row["as_of"], row["account"])
                self.assertNotIn(key, sample_keys)
                sample_keys.add(key)
                self.assertIn(row["as_of"], expected)
                self.assertEqual(row["split"], expected[row["as_of"]][0])
                label = int(row["label"])
                self.assertIn(label, (0, 1))
                feature_counts[row["as_of"]] += 1
                positive_counts[row["as_of"]] += label
                if row["split"] == "train":
                    training_accounts.add(row["account"])
                elif row["split"] == "test":
                    test_labels[row["account"]] = label
                    if float(row["opening_count_30d"]) == 0:
                        inactive_count += 1
                        inactive_positive += label
        self.assertEqual(len(sample_keys), 71146)
        for date, (_, count, positive) in expected.items():
            self.assertEqual((feature_counts[date], positive_counts[date]), (count, positive))
        self.assertEqual(len(training_accounts), 11363)
        self.assertEqual((inactive_count, inactive_positive), (13561, 148))
        self.assertEqual(sum(account in training_accounts for account in test_labels), 11363)
        predictions = defaultdict(list)
        prediction_keys = set()
        with gzip.open(REPORT / "predictions.csv.gz", "rt", encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                run = (row["model"], row["seed"])
                self.assertIn(run, RUNS)
                self.assertIn(row["account"], test_labels)
                self.assertEqual(row["as_of"], REFERENCES[-1][1])
                self.assertEqual(row["split"], "test")
                self.assertEqual(int(row["label"]), test_labels[row["account"]])
                self.assertEqual(int(row["seen_in_training"]), int(row["account"] in training_accounts))
                key = (*run, row["account"])
                self.assertNotIn(key, prediction_keys)
                prediction_keys.add(key)
                score = float(row["score"])
                self.assertTrue(math.isfinite(score))
                if row["model"] != "recency":
                    self.assertTrue(0 <= score <= 1)
                predictions[run].append({"account": row["account"], "label": int(row["label"]), "score": score})
        self.assertEqual(set(predictions), RUNS)
        self.assertEqual(len(prediction_keys), 155015)
        records = {(row["name"], str(row["seed"]) if row["seed"] is not None else ""): row
                   for row in result["models"]}
        self.assertEqual(set(records), RUNS - {("pytorch_mlp", "17"), ("pytorch_mlp", "73")})
        self.assertEqual([row["seed"] for row in result["mlp_seed_results"]], [17, 42, 73])
        for seed in result["mlp_seed_results"]:
            run = ("pytorch_mlp", str(seed["seed"]))
            if run in records:
                self.assertEqual(records[run]["test"], seed["test"])
                self.assertEqual(records[run]["subgroups"], seed["subgroups"])
            records[run] = seed
        for run, rows in predictions.items():
            self.assertEqual(len(rows), 22145)
            actual = independent_metrics(rows, probability=run[0] != "recency")
            for name, value in actual.items():
                published = records[run]["test"][name]
                if value is None:
                    self.assertIsNone(published, (run, name))
                else:
                    self.assertAlmostEqual(value, published, delta=1e-12, msg=f"{run} {name}")
            for name, membership in (("seen_in_training", True), ("new_to_training", False)):
                subset = [row for row in rows if (row["account"] in training_accounts) == membership]
                actual = independent_metrics(subset, probability=run[0] != "recency")
                for metric, value in actual.items():
                    published = records[run]["subgroups"][name][metric]
                    if value is None:
                        self.assertIsNone(published, (run, name, metric))
                    else:
                        self.assertAlmostEqual(value, published, delta=1e-12, msg=f"{run} {name} {metric}")


if __name__ == "__main__":
    unittest.main()
