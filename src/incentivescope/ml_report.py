"""Portable, source-backed figures and narrative for the time-held-out ML study."""

import json
from pathlib import Path

from .common import atomic_text
from .report import escaped, link, number, percent


MODEL_LABELS = {
    "constant": "Training prevalence",
    "recency": "Recent activity ranking",
    "logistic_regression": "Logistic regression",
    "hist_gradient_boosting": "Histogram gradient boosting",
    "pytorch_mlp": "PyTorch MLP · seed 42",
}
COLORS = {"constant": "#65747b", "recency": "#ab7293", "logistic_regression": "#4976a1",
          "hist_gradient_boosting": "#b78331", "pytorch_mlp": "#147d80"}
LIMITATIONS = [
    "This is one historical campaign and one final time holdout; it is not evidence of generalisation across protocols or campaigns.",
    "Training and validation labels occur while rebates are active. The final test label occurs after rebates end; prevalence and behaviour can shift.",
    "Repeated addresses occur at different training cutoffs. The final test separately reports addresses present and absent from parameter training.",
    "Addresses are not people. Keeper senders are not trader accounts; several addresses may belong to one entity.",
    "The label is a positive-size successful opening or increase in [T + 23 days, T + 30 days), not any return within 30 days.",
    "Predictions and permutation importance describe associations. They do not estimate the causal effect of incentives or justify targeting interventions.",
    "Scores are not additionally calibrated. Reliability plots show any probability bias; recency provides ranking scores only.",
    "Indexed coverage starts on 2023-09-20. First observed opening and pre-campaign history are bounded by this extract, not lifetime history.",
    "This event-time backtest uses a later frozen indexer snapshot. Historical point-in-time index availability and subsequent corrections were not audited.",
    "Dune execution and independent cross-source agreement have not been established by this ML study.",
]


def label(name: str) -> str:
    return MODEL_LABELS.get(name, name.replace("_", " "))


def strongest_baseline(results: dict) -> dict:
    return max((row for row in results["models"] if row["name"] != "pytorch_mlp"),
               key=lambda row: row["validation"]["average_precision"] or 0)


def findings(results: dict) -> list[str]:
    primary = next(row for row in results["models"] if row["name"] == "pytorch_mlp")
    baseline = strongest_baseline(results)
    test = primary["test"]
    return [
        f"The final test contains {test['n']:,} addresses and {test['positives']:,} R30 returns ({percent(test['prevalence'])}).",
        f"Primary MLP test AP is {number(test['average_precision'])}; {label(baseline['name'])}, the strongest baseline by validation AP, has test AP {number(baseline['test']['average_precision'])}.",
        f"The MLP top 10% ranking captures {percent(test['top10_recall'])} of returns, with precision {percent(test['top10_precision'])} and lift {number(test['top10_lift'])}× over test prevalence.",
        f"Model selection used validation AP and selected {label(results['selected_model'])}. MLP seed {results['primary_seed']} was designated before final test evaluation; all three seeds are reported.",
    ]


def feature_description(name: str) -> str:
    """Keep the feature dictionary tied to the actual exported column names."""
    descriptions = {
        "days_since_first_observed_opening": "Days from first observed opening to cutoff; extract-bounded history.",
        "days_since_last_opening": "Days from latest observed opening to cutoff.",
        "pre_campaign_opening": "1 if an opening was observed before the earning window, else 0.",
        "market_count_30d": "Distinct markets with openings in the preceding 30 days.",
        "top_market_share_30d": "Largest market's share of opening USD size in the preceding 30 days; zero without openings.",
    }
    if name in descriptions:
        return descriptions[name]
    for prefix, meaning in (("opening_count", "Opening/increase execution count"),
                            ("active_days", "Distinct active UTC days"),
                            ("opening_size_usd", "Sum of opening/increase size, USD"),
                            ("opening_fee_usd", "Net opening position fees after trader discount, USD")):
        if name.startswith(prefix + "_"):
            return f"{meaning}, preceding {name.rsplit('_', 1)[1].rstrip('d')} days; zero if no activity."
    return name.replace("_", " ") + "; measured strictly before the cutoff."


def figures_ml(results: dict, output_dir: Path) -> dict[str, Path]:
    """Standard Matplotlib figures; imports stay optional for the core pipeline."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter

    output_dir.mkdir(parents=True, exist_ok=True)
    models = results["models"]
    primary = next(row for row in models if row["name"] == "pytorch_mlp")
    baseline = strongest_baseline(results)
    test_split = next(row for row in results["split_summary"] if row["split"] == "test")
    test_window = f"Label [{test_split['label_start'][:10]}, {test_split['label_end'][:10]}) UTC · N={primary['test']['n']:,}"
    assets = {}
    style = {"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
             "axes.spines.right": False, "axes.edgecolor": "#ccd9da", "axes.labelcolor": "#172e39",
             "text.color": "#172e39", "xtick.color": "#56717a", "ytick.color": "#56717a",
             "figure.facecolor": "white", "axes.facecolor": "white", "svg.fonttype": "none", "svg.hashsalt": "incentivescope-ml",
             "axes.titleweight": "bold", "axes.titlesize": 12}

    def save(name, fig):
        fig.savefig(output_dir / f"{name}.svg", bbox_inches="tight", metadata={"Date": None})
        fig.savefig(output_dir / f"{name}.png", bbox_inches="tight", dpi=160)
        plt.close(fig)
        assets[name] = output_dir / f"{name}.svg"

    with plt.rc_context(style):
        fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.2), layout="constrained")
        ordered = sorted(models, key=lambda row: row["test"]["average_precision"] or 0)
        names = [label(row["name"]) for row in ordered]
        for ax, field, title in ((axes[0], "average_precision", "Test Average Precision"),
                                (axes[1], "top10_lift", "Test top 10% lift")):
            values = [row["test"][field] or 0 for row in ordered]
            ax.barh(names, values, color=[COLORS.get(row["name"], "#65747b") for row in ordered], height=.6)
            ax.set_xlim(0, max(values + [0.01]) * 1.3)
            ax.set_title(title, loc="left", pad=15)
            ax.set_xlabel("AP (higher is better)" if field == "average_precision" else "× test prevalence")
            ax.grid(axis="x", color="#e8efed", linewidth=.7)
            ax.set_axisbelow(True)
            for index, value in enumerate(values):
                ax.text(value + ax.get_xlim()[1] * .02, index, f"{value:.3f}" if field == "average_precision" else f"{value:.2f}×", va="center")
            if field == "top10_lift":
                ax.axvline(1, color="#172e39", linestyle=":", linewidth=1)
        fig.suptitle(test_window + f" · {primary['test']['positives']:,} returns", x=.02, ha="left", fontsize=11)
        save("model-comparison", fig)

        fig, ax = plt.subplots(figsize=(9.2, 5.4), layout="constrained")
        for row in models:
            curve = row["test"]["pr_curve"]
            if curve["recall"]:
                ax.plot(curve["recall"], curve["precision"], color=COLORS.get(row["name"], "#65747b"),
                        linestyle="--" if row["name"] in {"constant", "recency"} else "-", linewidth=1.8,
                        label=f"{label(row['name'])} · AP {row['test']['average_precision']:.3f}")
        ax.axhline(primary["test"]["prevalence"], color="#172e39", linestyle=":", linewidth=1,
                   label=f"Test prevalence {percent(primary['test']['prevalence'])}")
        ax.set(xlim=(0, 1), ylim=(0, 1), xlabel="Recall · share of all R30 returns", ylabel="Precision · share of ranked addresses returning")
        ax.set_title("Final-test precision–recall curves\n" + test_window, loc="left", pad=15)
        ax.xaxis.set_major_formatter(PercentFormatter(1))
        ax.yaxis.set_major_formatter(PercentFormatter(1))
        ax.grid(color="#e8efed", linewidth=.7)
        ax.legend(loc="upper right", fontsize=9, frameon=False)
        save("precision-recall", fig)

        fig, ax = plt.subplots(figsize=(9.2, 5.4), layout="constrained")
        # A validation-selected comparator avoids choosing a baseline on final-test scores.
        probability_baseline = max((row for row in models if row["name"] != "pytorch_mlp" and row["test"]["reliability"]),
                                   key=lambda row: row["validation"]["average_precision"] or 0)
        for row in [probability_baseline, primary]:
            bins = row["test"]["reliability"]
            if bins:
                ax.plot([cell["mean_probability"] for cell in bins], [cell["observed_rate"] for cell in bins],
                        "o-", color=COLORS.get(row["name"], "#65747b"), linewidth=1.8,
                        markerfacecolor="white" if row["name"] != "pytorch_mlp" else COLORS["pytorch_mlp"],
                        label=label(row["name"]))
                for index, cell in enumerate(bins):
                    ax.annotate(f"n={cell['count']:,}", (cell["mean_probability"], cell["observed_rate"]),
                                xytext=(4, 7 if index % 2 == 0 else -15), textcoords="offset points", fontsize=8,
                                color=COLORS.get(row["name"], "#65747b"))
        ax.plot([0, 1], [0, 1], color="#172e39", linestyle=":", linewidth=1, label="Perfect calibration reference")
        ax.set(xlim=(0, 1), ylim=(0, 1), xlabel="Mean predicted probability in bin", ylabel="Observed R30 return share in bin")
        ax.set_title("Final-test reliability · counts on each occupied bin\n" + test_window, loc="left", pad=15)
        ax.xaxis.set_major_formatter(PercentFormatter(1))
        ax.yaxis.set_major_formatter(PercentFormatter(1))
        ax.grid(color="#e8efed", linewidth=.7)
        ax.legend(loc="upper left", fontsize=9, frameon=False)
        save("reliability", fig)

        fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.2), layout="constrained")
        for run, color in zip(results["mlp_seed_results"], ("#4976a1", "#147d80", "#b78331")):
            history = run["history"]
            epochs = [entry["epoch"] for entry in history]
            for ax, field in ((axes[0], "train_loss"), (axes[1], "validation_ap")):
                ax.plot(epochs, [entry[field] for entry in history], color=color,
                        linestyle="-" if run["seed"] == results["primary_seed"] else "--", label=f"Seed {run['seed']}")
                ax.axvline(run["best_epoch"], color=color, alpha=.35, linewidth=.8, linestyle=":")
        for ax, title, ylabel in ((axes[0], "MLP training loss", "Unweighted BCE loss"),
                                  (axes[1], "MLP validation Average Precision", "AP · early stopping metric")):
            ax.set_title(title, loc="left", pad=15)
            ax.set(xlabel="Epoch", ylabel=ylabel)
            ax.grid(color="#e8efed", linewidth=.7)
            ax.legend(frameon=False, fontsize=9)
        save("training", fig)

        rows = sorted(results["permutation_importance"], key=lambda row: row["ap_drop_mean"])
        fig, ax = plt.subplots(figsize=(9.4, max(5.6, len(rows) * .31)), layout="constrained")
        ax.barh([row["feature"] for row in rows], [row["ap_drop_mean"] for row in rows],
                xerr=[row["ap_drop_std"] for row in rows], color="#147d80", height=.62,
                error_kw={"ecolor": "#172e39", "capsize": 2, "elinewidth": .8})
        ax.axvline(0, color="#172e39", linewidth=.8)
        ax.set_title("Validation permutation importance · primary MLP seed 42", loc="left", pad=15)
        ax.set_xlabel("AP decrease after shuffling · error bars are repeat SD, not confidence intervals")
        ax.grid(axis="x", color="#e8efed", linewidth=.7)
        ax.set_axisbelow(True)
        save("importance", fig)
    return assets


def render_ml(results: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    assets = figures_ml(results, output_dir / "figures")
    data = results["dataset"]
    synthetic = data.get("is_synthetic", False)
    status = "SYNTHETIC MODEL DEMONSTRATION — NOT GMX FINDINGS" if synthetic else "HISTORICAL TIME-HOLDOUT RESEARCH · ONE CAMPAIGN"
    conclusions = findings(results)
    models = results["models"]
    primary = next(row for row in models if row["name"] == "pytorch_mlp")
    test = primary["test"]
    metrics = (("average_precision", "AP"), ("roc_auc", "ROC-AUC"), ("top10_precision", "Top 10% precision"),
               ("top10_recall", "Top 10% recall"), ("top10_lift", "Top 10% lift"), ("brier", "Brier"), ("log_loss", "Log loss"))

    def table(headers, rows, caption=""):
        return '<div class="scroll"><table><caption>' + escaped(caption) + '</caption><thead><tr>' + ''.join(
            '<th scope="col">' + escaped(value) + '</th>' for value in headers) + '</tr></thead><tbody>' + ''.join(
            '<tr>' + ''.join('<td>' + escaped(value) + '</td>' for value in row) + '</tr>' for row in rows) + '</tbody></table></div>'

    comparison_rows = [[label(row["name"]), number(row["validation"]["average_precision"]),
                        f"{row['test']['positives']:,}/{row['test']['n']:,}", f"{row['test']['top10_count']:,}"] + [number(row["test"][field]) for field, _ in metrics] for row in models]
    comparison = table(["Model", "Validation AP", "Test positive / N", "Top 10% ranked N"] + [title for _, title in metrics], comparison_rows,
                       "Top 10% uses ceiling rounding; tied scores use account order, never labels. AP, ROC-AUC and lift: higher is better. Brier and log loss: lower is better. Recency has ranking scores only.")
    splits = table(["Use", "Prediction cutoff T (UTC)", "Label start (inclusive)", "Label end (exclusive)", "Samples", "R30 returns"],
                   [[row["split"], row["as_of"], row["label_start"], row["label_end"], f"{row['n']:,}", f"{row['positive']:,}"] for row in results["split_summary"]],
                   "One address × prediction cutoff. Earlier labels finish before the next evaluation cutoff.")
    subgroup_rows = [[label(row["name"]), group.replace("_", " "), f"{value['positives']:,}/{value['n']:,}",
                      number(value["average_precision"]), number(value["roc_auc"]), number(value["top10_lift"])]
                     for row in models for group, value in row["subgroups"].items()]
    subgroups = table(["Model", "Training membership", "R30 returns / N", "AP", "ROC-AUC", "Top 10% lift"], subgroup_rows,
                      "Seen = participated in at least one parameter-training cutoff. New = absent from parameter training; validation may include these addresses.")
    seeds = table(["MLP seed", "Best epoch", "Validation AP", "Test AP", "Test top 10% lift", "Test Brier"],
                  [[row["seed"], row["best_epoch"], number(row["validation"]["average_precision"]),
                    number(row["test"]["average_precision"]), number(row["test"]["top10_lift"]), number(row["test"]["brier"])] for row in results["mlp_seed_results"]],
                  "Primary seed is fixed at 42. This spread is optimisation variation, not a confidence interval.")
    feature_rows = [[name, feature_description(name), "log1p + training-only standardisation" if name in results["log_features"] else "Training-only standardisation" if "share" in name else "Binary / unscaled"]
                    for name in results["feature_names"]]
    features = table(["Exported feature", "Definition", "Transform"], feature_rows,
                     "All 17 features use only events with timestamp < T. Zero-activity addresses remain eligible.")
    reliability_rows = [[label(row["name"]), number(cell["mean_probability"]), number(cell["observed_rate"]), f"{cell['count']:,}"]
                        for row in models for cell in row["test"]["reliability"] or []]
    reliability_table = table(["Model", "Mean prediction", "Observed share", "Bin N"], reliability_rows,
                              "All occupied bins are retained. Recency is excluded because its scores are not probabilities.")
    shift_rows = [[row["split"], row["as_of"], f"{row['no_opening_30d']:,}/{row['n']:,}",
                   percent(row["no_opening_30d"] / row["n"]) if row["n"] else "N/A", row["returns_among_inactive"],
                   number(row["median_days_since_last_opening"])] for row in results.get("feature_shift", [])]
    shift = table(["Use", "Cutoff UTC", "No opening in last 30 days / N", "Share", "Later returns in inactive group", "Median days since latest opening"], shift_rows,
                  "Observed cohort composition at each cutoff. All eligible inactive addresses stay in the experiment.") if shift_rows else ""
    provenance = {"input": data, **results.get("provenance", {}), "feature_order": results["feature_names"],
                  "preprocessing": results["preprocessing"], "primary_seed": results["primary_seed"],
                  "model_configs": {row["name"]: row["config"] for row in models}}
    panels = "".join('<section class="panel" id="' + name + '"><h2>' + title + '</h2><p class="sub">' + escaped(caption) +
                     '</p><div class="figure"><img src="figures/' + path.name + '" alt="' + escaped(title) +
                     '"></div><p class="downloads"><a href="figures/' + path.name + '">SVG</a><a href="figures/' + path.with_suffix('.png').name + '">PNG</a></p></section>'
                     for name, title, caption, path in (
                         ("comparison", "Does the neural network improve prediction?", "Same final-test addresses and labels for every method. Ordering uses test AP for display; model selection uses validation AP.", assets["model-comparison"]),
                         ("ranking", "Precision and recall", "AP uses the full prediction set. Exported curves may contain bounded display points; this does not change AP.", assets["precision-recall"]),
                         ("probabilities", "How reliable are the probabilities?", "Counts accompany every occupied plotted bin. The strongest probability baseline by validation AP is compared with the primary MLP; all probability-model bins are available below.", assets["reliability"]),
                         ("optimisation", "Training and early stopping", "Solid curves show the primary seed. Dotted vertical lines mark each restored best epoch; final-test metrics never drive early stopping.", assets["training"]),
                         ("explanation", "What does the MLP depend on?", "Ten validation-set shuffles per feature. Repeat SD describes shuffle variation, not sampling uncertainty or a causal effect.", assets["importance"])))
    page = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>IncentiveScope · Predicting R30 participation</title><style>
:root{--ink:#172e39;--muted:#56717a;--teal:#147d80;--line:#d8e2df;--paper:#f7f8f3}*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.6 system-ui,sans-serif}a{color:var(--teal)}
header,main,footer{max-width:1160px;margin:auto;padding:28px}header{padding-top:45px}.brand{font-weight:750;letter-spacing:.1em;font-size:13px}
h1{font-size:clamp(30px,5vw,50px);line-height:1.12;letter-spacing:-.04em}h2{font-size:23px;line-height:1.3}.sub{color:var(--muted);max-width:900px}
.badge{padding:12px 16px;background:#fff5dc;border:1px solid #d8ae64;border-radius:8px;font-weight:700}.panel{background:white;border:1px solid var(--line);border-radius:12px;padding:24px;margin-bottom:20px}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:20px}.stat{background:white;border:1px solid var(--line);border-radius:12px;padding:20px}.stat strong{display:block;font-size:34px;letter-spacing:-.03em}.stat small{color:var(--muted)}
.figure{overflow:auto}.figure img{display:block;width:100%;height:auto;min-width:600px}.scroll{overflow:auto}table{width:100%;border-collapse:collapse;font-size:13px}td,th{padding:10px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}caption{text-align:left;margin-bottom:12px;color:var(--muted)}
code{overflow-wrap:anywhere}pre{white-space:pre-wrap;font-size:12px;background:#edf2ee;padding:16px;border-radius:8px;overflow-wrap:anywhere}.downloads,nav{display:flex;gap:18px;flex-wrap:wrap}details summary{cursor:pointer;font-weight:700}:focus-visible{outline:3px solid #b78331;outline-offset:4px}
footer{color:var(--muted);font-size:12px;border-top:1px solid var(--line)}@media(max-width:760px){header,main,footer{padding:20px}.stats{grid-template-columns:1fr}.panel{padding:18px}}
</style></head><body><header><div class="brand">INCENTIVESCOPE / ML RESEARCH NOTE 002</div>
<h1>Can past trading predict<br>who comes back?</h1><p class="sub">Small PyTorch MLP, traditional baselines and strict time-held-out evaluation of R30 opening participation.</p><div class="badge">$STATUS$</div><p>$CAMPAIGN$</p><nav><a href="../index.html">Campaign research</a><a href="#comparison">Model comparison</a><a href="#methods">Methods and features</a><a href="#evidence">Provenance</a></nav></header>
<main><section class="stats" aria-label="Primary MLP final-test results"><article class="stat">Final-test returns<strong>$RETURNS$</strong><small>$PREVALENCE$ prevalence · fixed denominator</small></article><article class="stat">Primary MLP AP<strong>$AP$</strong><small>Seed 42 · full prediction set</small></article><article class="stat">Top 10% lift<strong>$LIFT$×</strong><small>$RECALL$ of R30 returns captured</small></article></section>
<section class="panel"><h2>What the held-out data shows</h2><ul>$FINDINGS$</ul><p>Training conditions and final-test conditions differ. These predictive associations do not establish the effect of rebates.</p></section>
$PANELS$<section class="panel"><h2>Exact model scores</h2>$COMPARISON$</section><section class="panel"><h2>Addresses seen during parameter training</h2>$SUBGROUPS$</section><section class="panel"><h2>All fixed MLP seeds</h2>$SEEDS$</section>
<section class="panel"><h2>Training-to-test distribution shift</h2><p>Label prevalence is visible in the time-split table. The table below also shows how inactivity changes before each prediction cutoff.</p>$SHIFT$</section>
<section class="panel" id="methods"><h2>Time split and leakage controls</h2>$SPLITS$<p>$TRAINING$ unique addresses contribute training examples. Cutoff dates, addresses and hashes are tracking fields, not predictors. Scalers fit on training examples only; the validation set selects settings and best epochs and is not added back to training.</p><p>MLP architecture: <code>17 → 32 → 16 → 1</code>, ReLU, dropout 0.1, unweighted BCEWithLogitsLoss and AdamW. Learning rate 0.001, weight decay 0.001, batch size 256, maximum 100 epochs and validation-AP patience 10.</p><details><summary>Feature dictionary and transforms</summary>$FEATURES$</details></section>
<section class="panel"><h2>Probability-bin evidence</h2><details><summary>Show all probability models and occupied bins</summary>$RELIABILITY$</details></section>
<section class="panel" id="evidence"><h2>Source and reproducibility</h2><p>$SOURCE$ · coverage <code>$COVERAGE$</code></p><p>Frozen input SHA-256: <code>$HASH$</code></p><details><summary>Recorded versions, code state, transforms and model settings</summary><pre>$PROVENANCE$</pre></details><p class="downloads"><a href="results.json">Results JSON</a><a href="research.md">Research note</a><a href="features.csv.gz">Cutoff feature data</a><a href="predictions.csv.gz">Final-test predictions</a><a href="mlp-seed-42.pt">Primary PyTorch checkpoint</a><a href="artifact-manifest.json">Artifact hashes</a><a href="https://github.com/ho2006/IncentiveScope/blob/main/notebooks/retention-ml.ipynb">Editable notebook</a></p></section>
<section class="panel"><h2>Interpretation limits</h2><ul>$LIMITATIONS$</ul><details><summary>Run notes</summary><ul>$NOTES$</ul></details></section>
</main><footer>IncentiveScope · historical observational prediction · $DEVICE$ reference run; reproducibility is scoped to recorded versions and device.</footer></body></html>'''
    replacements = {"STATUS": escaped(status), "CAMPAIGN": escaped(results["campaign"].get("name", "GMX V2 Arbitrum STIP")),
                    "RETURNS": f"{test['positives']:,} / {test['n']:,}", "PREVALENCE": percent(test["prevalence"]),
                    "AP": number(test["average_precision"]), "LIFT": number(test["top10_lift"]), "RECALL": percent(test["top10_recall"]),
                    "FINDINGS": ''.join('<li>' + escaped(text) + '</li>' for text in conclusions), "PANELS": panels,
                    "COMPARISON": comparison, "SUBGROUPS": subgroups, "SEEDS": seeds, "SPLITS": splits, "SHIFT": shift,
                    "TRAINING": f"{results['training_unique_accounts']:,}", "FEATURES": features, "RELIABILITY": reliability_table,
                    "SOURCE": link(data.get("source_url", ""), "Indexed execution source"),
                    "COVERAGE": escaped(data.get("coverage_start", "") + " → " + data.get("coverage_end", "")),
                    "HASH": escaped(data.get("sha256", "unavailable")), "PROVENANCE": escaped(json.dumps(provenance, indent=2, ensure_ascii=False, allow_nan=False)),
                    "LIMITATIONS": ''.join('<li>' + escaped(text) + '</li>' for text in LIMITATIONS),
                    "NOTES": ''.join('<li>' + escaped(text) + '</li>' for text in results.get("notes", [])),
                    "DEVICE": escaped(results.get("provenance", {}).get("device", "Recorded-device"))}
    for name, contents in replacements.items():
        page = page.replace("$" + name + "$", contents)
    atomic_text(output_dir / "index.html", page)
    markdown = f"# IncentiveScope: predicting R30 participation\n\n{status}\n\n" + '\n\n'.join(conclusions)
    markdown += "\n\n## Model comparison\n\n| Model | Validation AP | Test positives / N | Test AP | Top 10% lift | Brier |\n|---|---:|---:|---:|---:|---:|\n"
    markdown += '\n'.join(f"| {escaped(label(row['name']))} | {number(row['validation']['average_precision'])} | {row['test']['positives']:,}/{row['test']['n']:,} | {number(row['test']['average_precision'])} | {number(row['test']['top10_lift'])} | {number(row['test']['brier'])} |" for row in models)
    markdown += "\n\n## Figures\n\n" + '\n\n'.join(f"![{name.replace('-', ' ')}](figures/{path.name})" for name, path in assets.items())
    markdown += "\n\n## Methods\n\nAt cutoff T, eligible accounts have already opened during [earning start, T). Every feature uses timestamp < T; the label is an opening in [T+23 days, T+30 days). Training-only log1p/scaling, validation-only model selection and early stopping, and a fixed primary MLP seed 42 prevent final-test tuning. Validation examples are never added back to parameter training.\n\n"
    markdown += "| Use | Cutoff UTC | Label start | Label end (exclusive) | Samples | Returns |\n|---|---|---|---|---:|---:|\n" + '\n'.join(
        f"| {escaped(row['split'])} | {row['as_of']} | {row['label_start']} | {row['label_end']} | {row['n']:,} | {row['positive']:,} |" for row in results["split_summary"])
    markdown += "\n\n## Feature dictionary\n\n" + '\n'.join(f"- `{escaped(name)}`: {escaped(feature_description(name))}" for name in results["feature_names"])
    markdown += "\n\n## Source and interpretation limits\n\nFrozen input SHA-256: `" + data.get("sha256", "unavailable") + "`.\n\n" + '\n'.join("- " + text for text in LIMITATIONS)
    markdown += "\n\nFull settings, split-specific metrics, probability bins, seed histories and versions are in [results.json](results.json).\n"
    atomic_text(output_dir / "research.md", markdown)
