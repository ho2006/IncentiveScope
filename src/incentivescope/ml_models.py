"""Optional CPU-first models for the fixed, chronological retention experiment."""

import csv
import gzip
import io
import math
import os
import random
from pathlib import Path

import numpy as np
import torch
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score, brier_score_loss, log_loss, precision_recall_curve,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
from torch import nn

from .common import write_json

SEEDS = (17, 42, 73)
PRIMARY_SEED = 42


def prepare_features(data: dict) -> tuple[dict, dict]:
    """Fit log/scaling parameters on training rows only, with an exact whitelist."""
    from .ml_data import FEATURE_NAMES, LOG_FEATURES

    names = tuple(data["feature_names"])
    logs = tuple(data["log_features"])
    if names != FEATURE_NAMES or logs != LOG_FEATURES:
        raise ValueError("Feature whitelist/order differs from the fixed 17-feature contract")
    rows = data["rows"]
    if not rows:
        raise ValueError("ML dataset is empty")
    values = np.asarray([[row[name] for name in names] for row in rows], dtype=np.float64)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("Features must be finite, nonnegative values")
    binary = names.index("pre_campaign_opening")
    if not np.isin(values[:, binary], [0, 1]).all():
        raise ValueError("pre_campaign_opening must be binary")
    if (values[:, names.index("top_market_share_30d")] > 1).any():
        raise ValueError("top_market_share_30d must be between zero and one")
    log_indices = [names.index(name) for name in logs]
    continuous = [i for i in range(len(names)) if i != binary]
    values[:, log_indices] = np.log1p(values[:, log_indices])
    masks = {split: np.asarray([row["split"] == split for row in rows])
             for split in ("train", "validation", "test")}
    if not all(mask.any() for mask in masks.values()) or sum(mask.sum() for mask in masks.values()) != len(rows):
        raise ValueError("Dataset must contain only nonempty train, validation and test splits")
    labels = np.asarray([row["label"] for row in rows], dtype=np.float64)
    if not np.isin(labels, [0, 1]).all():
        raise ValueError("Retention labels must be binary")
    if len(np.unique(labels[masks["train"]])) != 2 or len(np.unique(labels[masks["validation"]])) != 2:
        raise ValueError("Training and validation need both label classes for selection")
    scaler = StandardScaler().fit(values[masks["train"]][:, continuous])
    values[:, continuous] = scaler.transform(values[:, continuous])
    parts = {
        split: {"x": values[mask].astype(np.float32), "y": labels[mask].astype(np.int64),
                "rows": [row for row, keep in zip(rows, mask) if keep]}
        for split, mask in masks.items()
    }
    preprocessing = {
        "feature_names": list(names), "log_features": list(logs),
        "standardized_features": [names[i] for i in continuous],
        "mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist(),
        "variance": scaler.var_.tolist(), "fit_split": "train",
        "fit_row_count": int(masks["train"].sum()), "output_dtype": "float32",
    }
    return parts, preprocessing


def evaluate(y, scores, accounts, probability: bool = True) -> dict:
    """Full-score metrics; only PR chart points are thinned for portable reports."""
    labels, scores = np.asarray(y, dtype=np.float64), np.asarray(scores, dtype=np.float64)
    if not np.isin(labels, [0, 1]).all():
        raise ValueError("Invalid labels or probability range")
    y = labels.astype(np.int64)
    if len(y) != len(scores) or len(accounts) != len(y) or not np.isfinite(scores).all():
        raise ValueError("Prediction lengths must agree and scores must be finite")
    if probability and ((scores < 0).any() or (scores > 1).any()):
        raise ValueError("Invalid labels or probability range")
    n, positives = len(y), int(y.sum())
    metric = {"n": n, "positives": positives, "prevalence": positives / n if n else None,
              "average_precision": None, "roc_auc": None, "top10_precision": None,
              "top10_recall": None, "top10_lift": None, "top10_count": 0,
              "brier": None, "log_loss": None, "reliability": [],
              "pr_curve": {"precision": [], "recall": [], "thresholds": [], "sampled": False,
                           "full_point_count": 0}}
    if not n:
        return metric
    count = math.ceil(n * 0.1)
    # Equal scores use public account order, never the observed label.
    order = np.lexsort((np.asarray(accounts, dtype=str), -scores))
    hits = int(y[order[:count]].sum())
    metric.update(top10_count=count, top10_precision=hits / count,
                  top10_recall=hits / positives if positives else None,
                  top10_lift=(hits / count) / (positives / n) if positives else None)
    if positives:
        metric["average_precision"] = float(average_precision_score(y, scores))
        precision, recall, thresholds = precision_recall_curve(y, scores)
        indices = np.unique(np.linspace(0, len(precision) - 1, min(500, len(precision)), dtype=int))
        # Each threshold belongs to the same precision/recall point; last point has no threshold.
        metric["pr_curve"] = {
            "precision": precision[indices].tolist(), "recall": recall[indices].tolist(),
            "thresholds": [float(thresholds[i]) if i < len(thresholds) else None for i in indices],
            "sampled": len(indices) < len(precision), "full_point_count": len(precision),
        }
    if 0 < positives < n:
        metric["roc_auc"] = float(roc_auc_score(y, scores))
    if probability:
        metric["brier"] = float(brier_score_loss(y, scores))
        metric["log_loss"] = float(log_loss(y, scores, labels=[0, 1]))
        edges = np.unique(np.quantile(scores, np.linspace(0, 1, 11)))
        bins = np.searchsorted(edges[1:-1], scores, side="right")
        metric["reliability"] = [
            {"mean_probability": float(scores[bins == i].mean()),
             "observed_rate": float(y[bins == i].mean()), "count": int((bins == i).sum())}
            for i in np.unique(bins)
        ]
    return metric


class MLP(nn.Module):
    def __init__(self, features: int = 17):
        super().__init__()
        self.layers = nn.Sequential(nn.Linear(features, 32), nn.ReLU(), nn.Dropout(0.1),
                                    nn.Linear(32, 16), nn.ReLU(), nn.Dropout(0.1), nn.Linear(16, 1))

    def forward(self, values):
        return self.layers(values).squeeze(-1)


def _predict(model: MLP, values: np.ndarray, device: str) -> np.ndarray:
    model.eval()
    with torch.no_grad():
        return torch.sigmoid(model(torch.as_tensor(values, dtype=torch.float32, device=device))).cpu().numpy()


def load_checkpoint(path: Path, device: str = "cpu") -> MLP:
    """Load tensor/primitives-only checkpoints without arbitrary pickle objects."""
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    from .ml_data import FEATURE_NAMES
    if checkpoint["feature_names"] != list(FEATURE_NAMES):
        raise ValueError("Checkpoint feature order does not match the research contract")
    model = MLP(len(FEATURE_NAMES)).to(device)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    return model


def _train_mlp(parts: dict, seed: int, output: Path, device: str, max_epochs: int, patience: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if device == "cuda":
        torch.cuda.manual_seed_all(seed)
    model = MLP(parts["train"]["x"].shape[1]).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=0.001)
    loss_fn = nn.BCEWithLogitsLoss()
    generator = torch.Generator().manual_seed(seed)
    dataset = torch.utils.data.TensorDataset(torch.as_tensor(parts["train"]["x"]),
                                             torch.as_tensor(parts["train"]["y"], dtype=torch.float32))
    loader = torch.utils.data.DataLoader(dataset, batch_size=256, shuffle=True,
                                        generator=generator, num_workers=0)
    best_ap, best_epoch, best_state, history = -1.0, 0, None, []
    for epoch in range(1, max_epochs + 1):
        model.train()
        total_loss = 0.0
        for x, y in loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = loss_fn(model(x), y)
            if not torch.isfinite(loss):
                raise ValueError("Non-finite MLP training loss")
            loss.backward()
            if any(parameter.grad is not None and not torch.isfinite(parameter.grad).all()
                   for parameter in model.parameters()):
                raise ValueError("Non-finite MLP gradient")
            optimizer.step()
            total_loss += float(loss.detach().cpu()) * len(y)
        ap = float(average_precision_score(parts["validation"]["y"],
                                          _predict(model, parts["validation"]["x"], device)))
        history.append({"epoch": epoch, "train_loss": total_loss / len(dataset), "validation_ap": ap})
        if ap > best_ap:
            best_ap, best_epoch = ap, epoch
            best_state = {name: tensor.detach().cpu().clone() for name, tensor in model.state_dict().items()}
        if epoch - best_epoch >= patience:
            break
    path = output / f"mlp-seed-{seed}.pt"
    torch.save({"state_dict": best_state, "feature_names": list(parts["feature_names"]),
                "seed": seed, "architecture": [17, 32, 16, 1], "best_epoch": best_epoch}, path)
    # Evaluation always uses the saved best weights, including its public reload route.
    return load_checkpoint(path, device), history, best_epoch, path.name


@threadpool_limits.wrap(limits=1)
def run_models(data: dict, output_dir: Path, device: str = "cpu", *,
               _max_epochs: int = 100, _patience: int = 10, _permutation_repeats: int = 10) -> dict:
    """Fit fixed candidates, select on validation AP, then evaluate the held-out test."""
    if device == "cuda":
        os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    if device not in ("cpu", "cuda") or (device == "cuda" and not torch.cuda.is_available()):
        raise ValueError("Requested device is unavailable; choose cpu or an available cuda device")
    if min(_max_epochs, _patience, _permutation_repeats) < 1:
        raise ValueError("Training epochs, patience and permutation repeats must be positive")
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    if device == "cuda":
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    parts, preprocessing = prepare_features(data)
    parts["feature_names"] = data["feature_names"]
    write_json(output_dir / "preprocessing.json", preprocessing)
    train, val, test = (parts[name] for name in ("train", "validation", "test"))
    train_accounts = {row["account"] for row in train["rows"]}
    accounts = {split: [row["account"] for row in parts[split]["rows"]]
                for split in ("validation", "test")}
    seen = np.asarray([account in train_accounts for account in accounts["test"]])
    models, predictions, seed_results = [], [], []

    def record(name, scores, config, probability=True, seed=None):
        metric = {"name": name, "config": config, "seed": seed,
                  "validation": evaluate(val["y"], scores["validation"], accounts["validation"], probability),
                  "test": evaluate(test["y"], scores["test"], accounts["test"], probability),
                  "subgroups": {}}
        for group, mask in (("seen_in_training", seen), ("new_to_training", ~seen)):
            metric["subgroups"][group] = evaluate(test["y"][mask], scores["test"][mask],
                                                 np.asarray(accounts["test"])[mask], probability)
        for row, score, was_seen in zip(test["rows"], scores["test"], seen):
            predictions.append({"account": row["account"], "as_of": row["as_of"], "model": name,
                                "seed": seed if seed is not None else "", "label": int(row["label"]),
                                "score": float(score), "split": "test", "seen_in_training": int(was_seen)})
        return metric

    prevalence = float(train["y"].mean())
    models.append(record("constant", {split: np.full(len(parts[split]["y"]), prevalence)
                                      for split in ("validation", "test")}, {"train_prevalence": prevalence}))
    models.append(record("recency", {split: -np.asarray([row["days_since_last_opening"]
                                                         for row in parts[split]["rows"]], dtype=float)
                                     for split in ("validation", "test")},
                         {"score": "negative days_since_last_opening", "ranking_only": True}, False))
    candidates = []
    for c in (0.1, 1.0, 10.0):
        candidate = LogisticRegression(C=c, l1_ratio=0, max_iter=1000, random_state=PRIMARY_SEED)
        candidate.fit(train["x"], train["y"])
        ap = float(average_precision_score(val["y"], candidate.predict_proba(val["x"])[:, 1]))
        candidates.append((ap, c, candidate))
    best = max(candidates, key=lambda candidate: candidate[0])
    models.append(record("logistic_regression", {split: best[2].predict_proba(parts[split]["x"])[:, 1]
                                                 for split in ("validation", "test")},
                         {"C": best[1], "penalty": "l2", "max_iter": 1000,
                          "validation_candidates": [{"C": c, "average_precision": ap} for ap, c, _ in candidates]}))
    candidates = []
    for iterations in (100, 200):
        candidate = HistGradientBoostingClassifier(max_leaf_nodes=7, learning_rate=0.05,
                                                   max_iter=iterations, early_stopping=False,
                                                   random_state=PRIMARY_SEED)
        candidate.fit(train["x"], train["y"])
        ap = float(average_precision_score(val["y"], candidate.predict_proba(val["x"])[:, 1]))
        candidates.append((ap, iterations, candidate))
    best = max(candidates, key=lambda candidate: candidate[0])
    models.append(record("hist_gradient_boosting", {split: best[2].predict_proba(parts[split]["x"])[:, 1]
                                                    for split in ("validation", "test")},
                         {"max_leaf_nodes": 7, "learning_rate": 0.05, "max_iter": best[1],
                          "early_stopping": False, "random_state": PRIMARY_SEED,
                          "validation_candidates": [{"max_iter": iterations, "average_precision": ap}
                                                    for ap, iterations, _ in candidates]}))
    primary_model = None
    mlp_config = {"architecture": [17, 32, 16, 1], "activation": "ReLU", "dropout": 0.1,
                  "optimizer": "AdamW", "learning_rate": 0.001, "weight_decay": 0.001,
                  "loss": "unweighted BCEWithLogitsLoss", "batch_size": 256,
                  "max_epochs": _max_epochs, "patience": _patience}
    for seed in SEEDS:
        model, history, best_epoch, checkpoint = _train_mlp(parts, seed, output_dir, device,
                                                          _max_epochs, _patience)
        scores = {split: _predict(model, parts[split]["x"], device) for split in ("validation", "test")}
        metrics = record("pytorch_mlp", scores, mlp_config, seed=seed)
        seed_results.append({"seed": seed, "history": history, "checkpoint": checkpoint,
                             "best_epoch": best_epoch, "validation": metrics["validation"],
                             "test": metrics["test"], "subgroups": metrics["subgroups"]})
        if seed == PRIMARY_SEED:
            primary_model = model
            models.append(metrics)
    selected = max(models[2:], key=lambda model: model["validation"]["average_precision"])
    rng = np.random.default_rng(PRIMARY_SEED)
    baseline_ap = next(model["validation"]["average_precision"] for model in models if model["name"] == "pytorch_mlp")
    importance = []
    for index, feature in enumerate(data["feature_names"]):
        drops = []
        for _ in range(_permutation_repeats):
            permuted = val["x"].copy()
            permuted[:, index] = permuted[rng.permutation(len(permuted)), index]
            drops.append(baseline_ap - float(average_precision_score(val["y"], _predict(primary_model, permuted, device))))
        importance.append({"feature": feature, "ap_drop_mean": float(np.mean(drops)),
                           "ap_drop_std": float(np.std(drops)), "repeats": _permutation_repeats})
    fields = ("account", "as_of", "model", "seed", "label", "score", "split", "seen_in_training")
    with (output_dir / "predictions.csv.gz").open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
                writer.writeheader()
                writer.writerows(predictions)
    with (output_dir / "training_curve.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("seed", "epoch", "train_loss", "validation_ap"), lineterminator="\n")
        writer.writeheader()
        writer.writerows({"seed": result["seed"], **epoch} for result in seed_results for epoch in result["history"])
    return {"models": models, "mlp_seed_results": seed_results, "primary_seed": PRIMARY_SEED,
            "selected_model": selected["name"], "selection_metric": "validation average_precision",
            "feature_names": data["feature_names"], "log_features": data["log_features"],
            "preprocessing": preprocessing, "training_unique_accounts": len(train_accounts),
            "fit_counts": {split: len(parts[split]["y"]) for split in ("train", "validation", "test")},
            "permutation_importance": importance, "permutation_importance_model": "pytorch_mlp",
            "permutation_importance_seed": PRIMARY_SEED, "permutation_importance_split": "validation",
            "device": device, "cpu_threads": 1, "deterministic_algorithms": True,
            "notes": ["No validation refit, class reweighting, oversampling or probability calibration.",
                      "All three MLP seeds are reported; seed 42 was fixed as primary before test evaluation.",
                      "Top 10% uses ceil(n * 0.1), with descending score and ascending account for ties.",
                      "AP uses all scores; PR charts retain at most 500 points per curve.",
                      "Permutation importance measures validation predictive association, not causal effects.",
                      "Exact reproducibility applies to the same CPU software environment, not across devices/versions."]}
