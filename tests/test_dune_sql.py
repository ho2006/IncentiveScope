"""Fixture checks for SQL logic; these do not execute Dune or verify its tables."""

import unittest
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
EMITTER = bytes.fromhex("c8ee91a54287db53897056e12d9819156d3822fb")


class DuneSqlCheck(unittest.TestCase):
    def test_date_grid_swaps_join_grain_and_missing_creation(self):
        connection = duckdb.connect()
        self.addCleanup(connection.close)
        connection.execute("CREATE SCHEMA gmx_v2_arbitrum")
        # Dune's date sequence is the only dialect substitution in this fixture.
        connection.execute("CREATE MACRO sequence(a, b) AS generate_series(a, b, INTERVAL '1 day')")
        for table in ("position_increase", "position_decrease"):
            connection.execute(f"""CREATE TABLE gmx_v2_arbitrum.{table} (
                block_date DATE, block_time TIMESTAMP, tx_hash BLOB, "index" BIGINT,
                account BLOB, order_key BLOB, order_type VARCHAR,
                size_delta_usd DOUBLE, contract_address BLOB)""")
        connection.execute("""CREATE TABLE gmx_v2_arbitrum.order_executed (
            block_date DATE, block_time TIMESTAMP, tx_hash BLOB, "index" BIGINT,
            "key" BLOB, account BLOB, secondary_order_type INTEGER, contract_address BLOB)""")
        connection.execute("""CREATE TABLE gmx_v2_arbitrum.order_created (
            block_date DATE, block_time TIMESTAMP, "key" BLOB, account BLOB,
            order_type VARCHAR, contract_address BLOB)""")

        def event(key, account, executed, created, order_type="MarketIncrease", size=10):
            key, account = key.encode(), account.encode()
            day = executed[:10]
            connection.execute("INSERT INTO gmx_v2_arbitrum.order_executed VALUES (?, ?, ?, 11, ?, ?, 0, ?)",
                               [day, executed, key, key, account, EMITTER])
            if order_type != "MarketSwap":
                table = "position_increase" if order_type in {"MarketIncrease", "LimitIncrease"} else "position_decrease"
                connection.execute(f"INSERT INTO gmx_v2_arbitrum.{table} VALUES (?, ?, ?, 10, ?, ?, ?, ?, ?)",
                                   [day, executed, key, account, key, order_type, size, EMITTER])
            connection.execute("INSERT INTO gmx_v2_arbitrum.order_created VALUES (?, ?, ?, ?, ?, ?)",
                               [created[:10], created, key, account, order_type, EMITTER])

        def query(filename):
            cursor = connection.execute((ROOT / "sql" / filename).read_text(encoding="utf-8"))
            fields = [item[0] for item in cursor.description]
            return [dict(zip(fields, row)) for row in cursor.fetchall()]

        event("a-entry", "a", "2023-11-20 10:00:00", "2023-09-01 10:00:00")
        event("b-entry", "b", "2023-11-20 10:00:01", "2023-11-20 09:00:00")
        event("a-return1", "a", "2024-04-19 10:00:00", "2024-03-26 10:00:00")
        event("a-return2", "a", "2024-04-20 10:00:00", "2024-04-20 09:00:00")
        event("a-r60", "a", "2024-05-19 10:00:00", "2024-05-19 09:00:00")
        event("swap", "a", "2024-04-19 11:00:00", "2024-04-19 09:00:00", "MarketSwap")
        event("collateral", "a", "2024-04-19 12:00:00", "2024-04-19 09:00:00", size=0)
        event("liquidation", "a", "2024-04-19 13:00:00", "2024-04-19 09:00:00", "Liquidation", size=0)
        daily = query("dune_gmx_stip_daily_audit.sql")
        self.assertEqual(len(daily), 252)
        self.assertEqual(daily[0]["rows"], 0)
        april19 = next(row for row in daily if str(row["day"])[:10] == "2024-04-19")
        self.assertEqual((april19["rows"], april19["execution_rows"], april19["out_of_scope_execution_rows"]), (3, 4, 1))
        self.assertEqual((april19["increase"], april19["collateral"], april19["liquidation"], april19["zero_size"]), (1, 1, 1, 2))
        self.assertEqual(sum(row["created_missing"] for row in daily), 0)
        metrics = query("dune_gmx_stip_retention.sql")
        self.assertEqual({(row["metric"], row["numerator"], row["denominator"], row["rate"]) for row in metrics},
                         {(metric, 1, 2, 0.5) for metric in ("r30", "cumulative30", "sustained30", "strict_r30", "r60")})

        connection.execute("""INSERT INTO gmx_v2_arbitrum.position_increase
            SELECT * FROM gmx_v2_arbitrum.position_increase WHERE order_key = ?""", [b"a-return1"])
        april19 = next(row for row in query("dune_gmx_stip_daily_audit.sql") if str(row["day"])[:10] == "2024-04-19")
        self.assertEqual((april19["duplicate_position_events"], april19["execution_join_extra_rows"]), (1, 1))
        connection.execute("DELETE FROM gmx_v2_arbitrum.position_increase WHERE order_key = ?", [b"a-return2"])
        april20 = next(row for row in query("dune_gmx_stip_daily_audit.sql") if str(row["day"])[:10] == "2024-04-20")
        self.assertEqual(april20["unmatched_execution_rows"], 1)
        connection.execute("DELETE FROM gmx_v2_arbitrum.order_created WHERE \"key\" = ?", [b"a-return1"])
        metrics = query("dune_gmx_stip_retention.sql")
        strict = next(row for row in metrics if row["metric"] == "strict_r30")
        self.assertIsNone(strict["numerator"])
        self.assertIsNone(strict["rate"])
        self.assertGreater(strict["strict_unknown_events"], 0)
        for account in (b"a", b"conflicting"):
            connection.execute("INSERT INTO gmx_v2_arbitrum.order_created VALUES ('2024-04-19', '2024-04-19 09:00:00', ?, ?, 'MarketIncrease', ?)",
                               [b"a-return1", account, EMITTER])
        strict = next(row for row in query("dune_gmx_stip_retention.sql") if row["metric"] == "strict_r30")
        self.assertIsNone(strict["numerator"])
        self.assertGreater(strict["strict_unknown_events"], 0)
