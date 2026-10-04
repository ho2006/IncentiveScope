"""Published portfolio links and byte receipts must survive a fresh checkout."""

import hashlib
import importlib.util
import json
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_portfolio", ROOT / "scripts/build_portfolio.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class PortfolioCheck(unittest.TestCase):
    def test_frozen_input_and_reward_receipts_survive_checkout(self):
        ledger = ROOT / "data/evidence/reward-allocations"
        row = next(row for row in json.loads((ledger / "manifest.json").read_text(encoding="utf-8"))["files"] if row["file"] == "epoch_summary.csv")
        self.assertEqual(hashlib.sha256((ledger / row["file"]).read_bytes()).hexdigest(), row["sha256"], row["file"])
        sample = ROOT / "data/sample"
        self.assertEqual(hashlib.sha256((sample / "trades.csv").read_bytes()).hexdigest(), json.loads((sample / "manifest.json").read_text(encoding="utf-8"))["sha256"])
        cuda = json.loads((ROOT / "data/evidence/ml/cuda-smoke.json").read_text(encoding="utf-8"))
        self.assertEqual(hashlib.sha256((ROOT / "scripts/check_cuda.py").read_bytes()).hexdigest(), cuda["probe_sha256"])
        dune = json.loads((ROOT / "data/evidence/dune/execution-status.json").read_text(encoding="utf-8"))
        self.assertEqual(hashlib.sha256((ROOT / dune["probe_sql_path"]).read_bytes()).hexdigest(), dune["probe_sql_sha256"])

    def test_authored_links_rendering_and_published_receipt(self):
        for name in ("README.md", "docs/portfolio-report.md", "docs/reproduction.md", "docs/application.md", "docs/interview.md"):
            source = ROOT / name
            for url in re.findall(r"\]\(([^)]+)\)", source.read_text(encoding="utf-8")):
                if urlsplit(url).scheme or url.startswith("#"):
                    continue
                path = ROOT / url.lstrip("/") if url.startswith("/") else source.parent / url.split("#")[0]
                self.assertTrue(path.exists(), (name, url))
        parsed = []
        class Links(HTMLParser):
            def handle_starttag(self, tag, attrs):
                if tag == "img":
                    parsed.append(dict(attrs)["src"])
        rendered = builder.render_html(list(builder.blocks(builder.SOURCE.read_text(encoding="utf-8"))))
        Links().feed(rendered)
        self.assertEqual(len(parsed), 3)
        for src in parsed:
            self.assertTrue((builder.OUTPUT / src).is_file())
        self.assertEqual(builder.target("data-quality.md"), builder.REPO + "docs/data-quality.md")
        receipt = json.loads((builder.OUTPUT / "manifest.json").read_text(encoding="utf-8"))
        for path, digest in receipt["source_sha256"].items():
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), digest, path)
        for row in receipt["files"]:
            path = builder.OUTPUT / row["file"]
            self.assertEqual(path.stat().st_size, row["bytes"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), row["sha256"])
        self.assertEqual((builder.OUTPUT / "index.html").read_text(encoding="utf-8"), rendered)
