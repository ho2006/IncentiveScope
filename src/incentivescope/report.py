"""Portable HTML/SVG evidence, generated from the same reviewed metric output."""

import html
import json
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from .common import atomic_text, instant


def escaped(value) -> str:
    return html.escape(str(value), quote=True)


def percent(value) -> str:
    return "N/A" if value is None else f"{value:.1%}"


def metric(value: dict | None) -> str:
    if value is None:
        return "N/A — unavailable"
    return f"{percent(value['rate'])} ({value['n']:,}/{value['N']:,} addresses)"


def number(value) -> str:
    if value is None:
        return "N/A"
    return f"{value:,}" if isinstance(value, int) else f"{value:,.2f}" if abs(value) >= 1000 else f"{value:.4g}"


def link(url: str, label: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc or parsed.username or parsed.password:
        return escaped(label)
    return f'<a href="{escaped(url)}" target="_blank" rel="noopener noreferrer">{escaped(label)}</a>'


def svg(title: str, body: str, height: int = 280) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 {height}" role="img" '
            f'aria-label="{escaped(title)}"><title>{escaped(title)}</title>'
            '<style>text{font-family:system-ui,sans-serif;fill:#172e39;font-size:12px} '
            '.muted{fill:#56717a}.axis{stroke:#ccd9da}</style>' + body + '</svg>')


def bars(title: str, entries: list[tuple[str, float | None, str]]) -> str:
    body = '<line x1="285" y1="20" x2="285" y2="260" class="axis"/>'
    for index, (label, rate, count) in enumerate(entries):
        y = 32 + index * 38
        width = 350 * rate if rate is not None else 0
        body += (f'<text x="12" y="{y+16}">{escaped(label)}</text>'
                 f'<rect x="285" y="{y}" width="350" height="22" rx="4" fill="#e8efed"/>'
                 f'<rect x="285" y="{y}" width="{width:.2f}" height="22" rx="4" fill="#147d80"/>'
                 f'<text x="650" y="{y+16}">{percent(rate)} · {escaped(count)}</text>')
    return svg(title, body, max(120, 50 + len(entries) * 38))


def figures(results: dict) -> dict:
    weekly = results["weekly"]
    week_svg = bars("Weekly repeat opening or increase, fixed campaign cohort",
                    [(f"Week {row['week']}", row["rate"], f"{row['n']}/{row['N']}") for row in weekly])
    heatmap = '<text x="10" y="18">Entry week (N) / weeks since campaign end</text>'
    for col, row in enumerate(weekly):
        heatmap += f'<text x="{213+col*68}" y="45">W{row["week"]}</text>'
    for index, row in enumerate(results["heatmap"]):
        y = 57 + index * 30
        heatmap += f'<text x="10" y="{y+18}">{escaped(row["entry_week"])} ({row["size"]})</text>'
        for col, cell in enumerate(row["weekly"]):
            x = 195 + col * 68
            opacity = 0.12 + 0.65 * cell["rate"]
            heatmap += (f'<rect x="{x}" y="{y}" width="64" height="26" rx="3" fill="#147d80" opacity="{opacity}"/>'
                        f'<text x="{x+7}" y="{y+18}">{cell["n"]}/{row["size"]}</text>')
    groups = defaultdict(lambda: [0, 0])
    for row in results["cohorts"]:
        groups[row["kind"]][0] += row["r30_n"]
        groups[row["kind"]][1] += row["size"]
    newold = bars("R30 by observed history, never a count of people",
                  [(name.replace("_", " "), n / N if N else None, f"{n}/{N}") for name, (n, N) in groups.items()])
    robust = bars("Activity definition sensitivity; identical fixed denominator",
                  [(row["label"], row["rate"], f"{row['n']}/{row['N']}") for row in results["robustness"]])
    campaign = results["campaign"]
    lo = instant(campaign["start"])
    hi = instant(results["dataset"]["coverage_end"])
    span = max((hi - lo).total_seconds(), 1)
    items = [("Configured earning window", campaign["start"], campaign["end"])]
    items += [(row["name"], row["start"], row["end"]) for row in campaign["overlaps"]]
    timeline = f'<text x="12" y="20">{escaped(campaign["start"][:10])} → {escaped(results["dataset"]["coverage_end"][:10])} · UTC</text>'
    for index, (name, start, end) in enumerate(items):
        x = 285 + 450 * (instant(start) - lo).total_seconds() / span
        width = 450 * (instant(end) - instant(start)).total_seconds() / span
        y = 40 + index * 42
        timeline += (f'<text x="12" y="{y+16}">{escaped(name)}</text>'
                     f'<rect x="{x:.2f}" y="{y}" width="{width:.2f}" height="22" rx="4" fill="{"#147d80" if index == 0 else "#c58b3c"}"/>')
    return {"timeline": svg("Campaign and overlapping incentives (configured boundaries)", timeline, 75 + len(items) * 42),
            "weekly": week_svg, "heatmap": svg("Entry-week cohort heatmap, counts and fixed denominators", heatmap, max(120, 85 + len(results["heatmap"]) * 30)),
            "history": newold, "robustness": robust}


def render(results: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    assets = figures(results)
    for name, contents in assets.items():
        atomic_text(output_dir / "figures" / f"{name}.svg", contents)
    data, campaign, summary = results["dataset"], results["campaign"], results["summary"]
    status = "SYNTHETIC DEMONSTRATION — NOT GMX FINDINGS" if data["is_synthetic"] else (
        "EXPLORATORY — EARNING BOUNDARIES UNVERIFIED" if data["boundary_status"] != "verified" else "HISTORICAL DESCRIPTIVE RESEARCH")
    cards = ""
    for name, label in (("r30", "Day 24–30 return"), ("cumulative30", "Any return in first 30 days"), ("sustained30", "Two-day participation")):
        value = summary[name]
        window = results.get("measurement_windows", {}).get(name)
        dates = f'<br><small>[{escaped(window["start"][:10])}, {escaped(window["end_exclusive"][:10])}) UTC</small>' if window else ""
        cards += f'<article class="stat"><p>{label}</p><strong>{percent(value["rate"])}</strong><small>{value["n"]:,} / {value["N"]:,} addresses</small>{dates}</article>'
    rows = "".join(f'<tr data-kind="{escaped(row["kind"])}"><td>{escaped(row["entry_week"])}</td><td>{escaped(row["kind"])}</td>'
                   f'<td>{row["size"]}</td><td>{row["r30_n"]}</td><td>{percent(row["r30_rate"])}</td></tr>' for row in results["cohorts"])
    options = '<option value="all">All observed-history groups</option>' + "".join(
        f'<option value="{escaped(kind)}">{escaped(kind.replace("_", " "))}</option>' for kind in sorted({row["kind"] for row in results["cohorts"]}))
    notes = data["notes"] + results["quality"]["notes"]
    limitations = "".join(f'<li>{escaped(note)}</li>' for note in notes)
    concentration = "".join(f'<tr><td>{escaped(row["label"])}</td><td>{row["r30_n"]}/{row["size"]}</td>'
                            f'<td>{percent(row["r30_rate"])}</td></tr>' for row in results["segments"])
    activity = results["activity"]
    intensity = "".join(f'<tr><td>{label}</td><td>{number((activity[label] or {}).get("active_address_days"))}</td>'
                        f'<td>{percent((activity[label] or {}).get("activity_rate"))}</td>'
                        f'<td>{number((activity[label] or {}).get("position_fee_usd"))}</td></tr>' for label in ("pre", "post"))
    source_link = link(data["source_url"], "Open data source")
    findings = "".join(f"<li>{escaped(text)}</li>" for text in results.get("findings", []))
    evidence = "".join(f"<li>{link(row['url'], row['label'])}</li>" for row in results.get("evidence_links", []))
    ml_entry = ('<section class="panel"><h2>Can past trading predict later return?</h2>'
                '<p>Explore the PyTorch retention study: 17 pre-cutoff features, chronological validation, '
                'traditional baselines and one test after rebates ended.</p>'
                '<a href="ml/index.html">Open the ML research page →</a></section>') if (output_dir / "ml/index.html").exists() else ""
    portfolio_entry = ('<p class="downloads"><a href="portfolio/index.html">Read the complete English report</a>'
                       '<a href="portfolio/research.pdf">Download the PDF</a>'
                       '<a href="https://github.com/ho2006/IncentiveScope/blob/main/docs/interview.md">Follow the demo</a></p>') if (output_dir / "portfolio/index.html").exists() else ""
    rewards = results.get("reward_allocations")
    comparison_note = results.get("cross_source", {}).get("message", "Independent source agreement has not been established for this result.")
    reward_note = (f"{rewards['epoch_count']} official epochs: {escaped(rewards['total_amount_arb'])} ARB allocated to "
                   f"{rewards['unique_recipients']:,} recipient addresses. Allocation files are not payment receipts; "
                   "receiver overrides prevent full trader-level attribution. Cost per retained account remains unavailable.") if rewards else "Reward cost: unavailable until address-level earning-epoch allocations can be reconciled."
    payload = json.dumps(results, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
    page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light"><title>IncentiveScope · After the rebates</title>
<style>
:root{--ink:#172e39;--muted:#56717a;--teal:#147d80;--line:#d8e2df;--paper:#f7f8f3}*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.6 system-ui,sans-serif}a{color:var(--teal)}
header,main,footer{max-width:1160px;margin:auto;padding:28px}header{padding-top:50px}.brand{font-weight:750;letter-spacing:.12em;font-size:13px}
h1{font-size:clamp(30px,5vw,52px);line-height:1.12;margin:22px 0 16px;letter-spacing:-.045em}h2{font-size:21px;line-height:1.3}
p{margin:10px 0}.sub{color:var(--muted);max-width:750px}.badge{margin-top:20px;padding:12px 16px;border:1px solid #d8ae64;background:#fff5dc;border-radius:8px;font-weight:700}
.meta{display:flex;gap:22px;flex-wrap:wrap;margin-top:20px;color:var(--muted);font-size:13px}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.stat,.panel{background:#fff;border:1px solid var(--line);border-radius:12px;padding:22px}.stat p{color:var(--muted);margin:0}.stat strong{font-size:38px;display:block;letter-spacing:-.04em}.stat small{color:var(--muted)}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:20px}.panel{margin-bottom:18px;min-width:0}.wide{grid-column:1/-1}
svg{width:100%;height:auto}.figure{overflow:auto}.figure svg{min-width:560px}table{width:100%;border-collapse:collapse;font-size:13px}td,th{text-align:left;padding:10px;border-bottom:1px solid var(--line)}
caption{text-align:left;margin-bottom:12px;color:var(--muted)}select{padding:8px;border:1px solid var(--line);border-radius:6px;background:white;color:var(--ink)}
:focus-visible{outline:3px solid #c58b3c;outline-offset:4px}.downloads{display:flex;gap:18px;flex-wrap:wrap}.method{max-width:850px}.method code{background:#edf2ee;padding:2px 5px}
footer{color:var(--muted);font-size:12px;border-top:1px solid var(--line)}details summary{cursor:pointer;font-weight:700}
@media(max-width:760px){header,main,footer{padding:20px}.stats,.grid{grid-template-columns:1fr}.stat strong{font-size:32px}.wide{grid-column:auto}}
</style></head><body><header><div class="brand">INCENTIVESCOPE / RESEARCH NOTE 001</div>
<h1>After the rebates.<br>Who keeps trading?</h1><p class="sub">Fixed-cohort repeat participation with explicit denominators, transparent boundaries and reproducible SQL.</p>
<div class="badge">$STATUS$</div><p>$CAMPAIGN$</p><div class="meta"><span>$COHORT$ cohort addresses</span><span>UTC coverage: $COVERAGE$</span><span>$SOURCE$</span></div>
$PORTFOLIOENTRY$</header><main><section class="stats" aria-label="Fixed-cohort metrics">$CARDS$</section>
<section class="panel" style="margin-top:20px"><h2>What the evidence says</h2><ul>$FINDINGS$</ul><p>$REWARDS$</p></section>
$MLENTRY$
<div class="grid"><section class="panel wide"><h2>One timeline, overlapping incentives</h2><p class="sub">Earning windows and reward payment dates are different. Configured boundaries are labelled above.</p><div class="figure">$TIMELINE$</div></section>
<section class="panel wide"><h2>Weekly repeat participation</h2><p class="sub">Same campaign addresses in every denominator; execution dates define activity.</p><div class="figure">$WEEKLY$</div></section>
<section class="panel wide"><h2>History changes the interpretation</h2><p class="sub">First observed in this window does not imply a newly acquired person.</p><div class="figure">$HISTORY$</div></section>
<section class="panel wide"><h2>Entry cohorts</h2><div class="figure">$HEATMAP$</div><label for="cohort-filter">Table history group: </label><select id="cohort-filter">$OPTIONS$</select>
<div style="overflow:auto"><table id="cohort-table"><caption>R30 is a return during days 24–30, not any return within 30 days.</caption><thead><tr><th>Entry week</th><th>Observed history</th><th>Fixed N</th><th>R30 n</th><th>R30</th></tr></thead><tbody>$ROWS$</tbody></table></div><p id="filter-status" aria-live="polite"></p></section>
<section class="panel wide"><h2>Does the definition change the result?</h2><div class="figure">$ROBUSTNESS$</div><p>Strict new-order return: $STRICT$. Day 54–60 return: $R60$.</p><p>Open-or-decrease includes decreases whose ADL status may be unknown. Voluntary return is withheld when forced decreases cannot be separated.</p></section></div>
<section class="panel"><h2>Concentration sensitivity</h2><table><caption>Ranking uses campaign-period volume; ceiling rounding excludes at least one address when N is small.</caption><thead><tr><th>Population</th><th>R30 n/N</th><th>R30</th></tr></thead><tbody>$CONCENTRATION$</tbody></table></section>
<section class="panel"><h2>Equal-window participation intensity</h2><p>$MATURE$ mature addresses, with 30 complete UTC days in each window. Zero-activity addresses remain in the denominator.</p><table><caption>Opening/increase only; net position fees after trader discount, before external rewards. Missing fees are N/A.</caption><thead><tr><th>Window</th><th>Active address-days</th><th>Activity share</th><th>Net position fees (USD)</th></tr></thead><tbody>$INTENSITY$</tbody></table><p>Post/pre activity ratio: $ACTIVITYRATIO$ · Fee ratio: $FEERATIO$</p></section>
<section class="panel method"><h2>Evidence and interpretation</h2><p>Account attribution uses the protocol account, not the keeper execution sender. Cancelled orders, zero-size collateral changes, liquidations and ADL do not count as new opening or increase.</p>
<h3>Cross-source validation</h3><p>$COMPARISON$</p>
<p>The cohort is fixed over <code>[start, end)</code>. R30 uses <code>[first complete post day + 23d, +30d)</code>. Every percentage displays its numerator and denominator. Address counts are not people, and differences do not establish causal impact.</p>
<details><summary>Coverage, missing fields and limitations</summary><ul>$NOTES$</ul><p>Input SHA-256: <code>$CHECKSUM$</code></p></details>
<ul>$EVIDENCE$</ul>
<p class="downloads"><a href="results.json" download>Metric JSON</a><a href="research.md">Research note</a><a href="wallet_cohorts.csv" download>Address cohort CSV</a><a href="wallet_daily.csv" download>Address-day CSV</a></p></section>
</main><footer>IncentiveScope · historical observational research · source-based results and synthetic demonstrations are labelled separately.</footer>
<script type="application/json" id="research-data">$DATA$</script><script>
const select=document.getElementById('cohort-filter');select.addEventListener('change',()=>{let visible=0;document.querySelectorAll('#cohort-table tbody tr').forEach(row=>{row.hidden=select.value!=='all'&&row.dataset.kind!==select.value;if(!row.hidden)visible++;});document.getElementById('filter-status').textContent=visible+' cohort rows shown. Overall charts retain the full fixed cohort.';});
</script></body></html>"""
    replacements = {"STATUS": escaped(status), "CAMPAIGN": escaped(campaign["name"]),
                    "COHORT": str(summary["cohort_size"]), "COVERAGE": escaped(data["coverage_start"] + " → " + data["coverage_end"]),
                    "SOURCE": source_link, "CARDS": cards, "OPTIONS": options, "ROWS": rows,
                    "TIMELINE": assets["timeline"], "WEEKLY": assets["weekly"], "HISTORY": assets["history"],
                    "HEATMAP": assets["heatmap"], "ROBUSTNESS": assets["robustness"],
                    "STRICT": escaped(metric(summary["strict_r30"])), "R60": escaped(metric(summary["r60"])),
                    "CONCENTRATION": concentration, "MATURE": str(activity["eligibleN"]), "INTENSITY": intensity,
                    "ACTIVITYRATIO": number(activity["activity_ratio"]), "FEERATIO": number(activity["fee_ratio"]),
                    "FINDINGS": findings or "<li>This labelled example demonstrates metric definitions and data checks.</li>",
                    "REWARDS": reward_note, "EVIDENCE": evidence, "COMPARISON": escaped(comparison_note), "MLENTRY": ml_entry, "PORTFOLIOENTRY": portfolio_entry,
                    "NOTES": limitations, "CHECKSUM": escaped(data["sha256"]), "DATA": payload}
    import re
    page = re.sub(r"\$([A-Z0-9]+)\$", lambda match: replacements[match.group(1)], page)
    atomic_text(output_dir / "index.html", page)
    paragraphs = [f"# IncentiveScope — {campaign['name']}", f"**{status}**", "",
                  "This note measures execution-based repeat participation. It does not estimate causal acquisition or count people.",
                  f"Data coverage: {data['coverage_start']} to {data['coverage_end']} (exclusive), UTC.",
                  f"Configured earning window: [{campaign['start']}, {campaign['end']}). Post anchor: {campaign['post_anchor']}.",
                  f"Source: {data['source_url']}", f"Input SHA-256: `{data['sha256']}`", "",
                  "## Findings", *[f"- {text}" for text in results.get("findings", [])], reward_note,
                  "## Results", f"Fixed campaign cohort: **{summary['cohort_size']} addresses**."]
    paragraphs += [f"- {name}: {metric(summary[name])}." for name in ("r30", "cumulative30", "sustained30", "open_or_decrease30", "voluntary30", "strict_r30", "r60")]
    paragraphs += ["", "Concentration sensitivity:", *[f"- {row['label']}: {percent(row['r30_rate'])} ({row['r30_n']}/{row['size']} addresses)." for row in results["segments"]],
                   f"Mature equal-window cohort: {activity['eligibleN']} addresses. Post/pre activity ratio: {number(activity['activity_ratio'])}; position-fee ratio: {number(activity['fee_ratio'])}. N/A includes zero baselines and unavailable inputs."]
    paragraphs += ["", "## Method and sensitivity",
                   "The campaign cohort includes accounts with a successful positive-size opening/increase during the configured earning window. It includes accounts that never return. R30 counts at least one such execution during post days 24–30. Cumulative30 counts a return anywhere within the first 30 complete days. Sustained30 requires two distinct UTC activity dates in the R30 window.",
                   "Strict return additionally requires an order created after earning ended; it is withheld when creation timestamps are missing for qualifying R30 events. Liquidations, collateral-only changes and cancelled orders are excluded from opening-only metrics. Open-or-decrease30 is a broader candidate measure. Voluntary30 is withheld when ADL decreases cannot be independently separated.",
                   "Entry-week and observed-history groups reveal exposure differences. Top-1% exclusion ranks on campaign-period size only, with a ceiling rule and account tie-break. These are sensitivity checks, not a randomized control group.",
                   "## Limitations", *[f"- {note}" for note in notes],
                   "- Other incentives and market conditions may affect participation after the configured campaign ends.",
                   "- Reward cost is withheld without reconciled address-level allocations. Fees are withheld when missing; no funding or gas is imputed as a position fee.",
                   "", "## Operating implications",
                   "For synthetic data, these are pipeline checks only. For real exploratory data, conclusions remain conditional on earning-boundary verification. For verified historical data, assess sustained participation alongside concentration and fee coverage; observed changes alone do not justify changing incentive budgets. No causal ROI is estimated.",
                   "## Cross-source validation", comparison_note,
                   "## Evidence", *[f"- [{row['label']}]({row['url']})" for row in results.get("evidence_links", [])],
                   "", "## Reproduction", "See the repository README for the exact analyze command. results.json, wallet_cohorts.csv and wallet_daily.csv are generated from one frozen input and its checksum manifest."]
    atomic_text(output_dir / "research.md", "\n\n".join(paragraphs) + "\n")
