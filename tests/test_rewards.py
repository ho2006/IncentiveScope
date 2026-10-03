"""Checks for exact reward amounts, source identity and ambiguous recipients."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from incentivescope.rewards import (COMMIT, EPOCHS, TOKEN, cached_source, fetch_rewards,
                                   normalize_distribution, unique_object, units)

RECIPIENT = "0x" + "aB" * 20


def distribution(epoch=EPOCHS[0]):
    return {"token": TOKEN, "distributionTypeId": 1003, "id": f"{epoch}_1003",
            "amounts": {RECIPIENT: "123456789012345678901234567890123456789"}}


class RewardChecks(unittest.TestCase):
    def test_exact_units_and_unknown_attribution(self):
        allocations, overrides = normalize_distribution(distribution(), EPOCHS[0])
        self.assertIsNone(overrides)
        self.assertEqual(list(allocations), [RECIPIENT.lower()])
        self.assertEqual(units(allocations[RECIPIENT.lower()]), "123456789012345678901.234567890123456789")
        self.assertEqual(units(-1), "-0.000000000000000001")

    def test_rejects_ambiguous_or_invalid_input(self):
        mutations = [lambda p: p.update(token="0x" + "0" * 40),
                     lambda p: p.update(distributionTypeId="1003"),
                     lambda p: p.update(id="2023-11-22_1003"),
                     lambda p: p["amounts"].update({RECIPIENT.lower(): "1"}),
                     lambda p: p.update(amounts={"not-an-address": "1"})]
        mutations += [lambda p, value=value: p.update(amounts={RECIPIENT: value})
                      for value in [-1, 1, "-1", "1.0", "1e18", "NaN", "01", " 1"]]
        for mutate in mutations:
            payload = distribution()
            mutate(payload)
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                normalize_distribution(payload, EPOCHS[0])
        with self.assertRaises(ValueError):
            json.loads('{"amounts":{},"amounts":{}}', object_pairs_hook=unique_object)

    def test_records_many_to_one_overrides_without_inventing_amounts(self):
        payload = distribution()
        payload["appliedOverrides"] = {"0x" + "1" * 40: RECIPIENT, "0x" + "2" * 40: RECIPIENT}
        allocations, overrides = normalize_distribution(payload, EPOCHS[0])
        self.assertEqual(len(allocations), 1)
        self.assertEqual(len(overrides), 2)
        self.assertEqual(set(overrides.values()), {RECIPIENT.lower()})

    def test_cached_source_must_match_pinned_git_blob(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "raw/epoch_2023-11-15/file.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b'{}')
            path = "scripts/incentives/distributions/epoch_2023-11-15/file.json"
            with self.assertRaisesRegex(ValueError, "checksum"):
                cached_source(Path(directory), path, {path: "0" * 40})

    def test_complete_ledger_and_batch_total_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tree, downloads = [], {}
            for epoch in EPOCHS:
                prefix = f"scripts/incentives/distributions/epoch_{epoch}/stipTradingIncentives"
                for suffix, payload in [("_distribution.json", distribution(epoch)),
                                        ("_transactionData.json", {"totalAmount": next(iter(distribution()["amounts"].values()))})]:
                    path = prefix + suffix
                    raw = json.dumps(payload).encode()
                    sha = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
                    tree.append({"path": path, "sha": sha, "type": "blob"})
                    downloads[path] = raw
            (root / "source-tree.json").write_text(json.dumps({"sha": COMMIT, "truncated": False, "tree": tree}))
            with patch("incentivescope.rewards.download", side_effect=lambda url: downloads[url.split(COMMIT + "/")[1]]):
                manifest = fetch_rewards(root)
            self.assertEqual(manifest["epoch_count"], 19)
            self.assertEqual(manifest["recipient_epoch_rows"], 19)
            self.assertEqual(manifest["epoch_end_exclusive"], "2024-03-27")
            for output in manifest["files"]:
                self.assertEqual(hashlib.sha256((root / output["file"]).read_bytes()).hexdigest(), output["sha256"])
            original = cached_source

            def incorrect_total(*args):
                payload, receipt = original(*args)
                if "_transactionData.json" in args[1]:
                    payload["totalAmount"] = "0"
                return payload, receipt

            with patch("incentivescope.rewards.cached_source", side_effect=incorrect_total):
                with self.assertRaisesRegex(ValueError, "differs"):
                    fetch_rewards(root)


if __name__ == "__main__":
    unittest.main()
