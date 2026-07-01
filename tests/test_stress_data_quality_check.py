"""Stress, property, and fuzz tests for data-quality-check. Seed: 20260701."""
from __future__ import annotations
import importlib.util, sys, tempfile, time, unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from random import Random

ROOT = Path(__file__).resolve().parents[1]

def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m

dq = load("data_quality_check", "2_Trailwise_Methodology/data-quality-check/scripts/data_quality_check.py")
SEED = 20260701

SCHEMA = {
    "columns": {
        "invoice_id": {"type": "string", "required": True},
        "amount": {"type": "decimal", "required": True},
        "qty": {"type": "integer"},
        "due_date": {"type": "date", "required": True},
    },
    "unique_keys": ["invoice_id"],
}

def write_csv(rows, header="invoice_id,amount,qty,due_date"):
    d = tempfile.mkdtemp()
    p = Path(d) / "input.csv"
    with p.open("w", encoding="utf-8") as f:
        f.write(header + "\n")
        for r in rows:
            f.write(r + "\n")
    return p

class DataQualityLoadTests(unittest.TestCase):
    def test_50k_valid_rows(self):
        rng = Random(SEED)
        rows = [f"INV-{i},{rng.randint(100, 9999)}.{rng.randint(0,99):02d},{rng.randint(1,50)},2026-07-01" for i in range(50_000)]
        p = write_csv(rows)
        start = time.perf_counter()
        result = dq.check_csv(p, SCHEMA)
        elapsed = time.perf_counter() - start
        self.assertTrue(result["valid"])
        self.assertEqual(result["rows"], 50_000)
        self.assertLess(elapsed, 5.0, f"50K rows took {elapsed:.3f}s")

    def test_50k_with_errors(self):
        rng = Random(SEED + 1)
        rows = []
        for i in range(50_000):
            if i % 100 == 0:
                rows.append(f"INV-{i-100},bad,0,not-a-date")  # dup + invalid decimal + invalid date
            else:
                rows.append(f"INV-{i},{rng.randint(100, 9999)}.{rng.randint(0,99):02d},{rng.randint(1,50)},2026-07-01")
        p = write_csv(rows)
        result = dq.check_csv(p, SCHEMA)
        self.assertFalse(result["valid"])
        self.assertGreater(result["error_count"], 0)

class DataQualityPropertyTests(unittest.TestCase):
    def test_valid_file_returns_hash(self):
        p = write_csv(["INV-1,100.00,5,2026-01-01"])
        result = dq.check_csv(p, SCHEMA)
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["sha256"]), 64)

    def test_blank_required_flagged(self):
        p = write_csv(["INV-1,,5,2026-01-01"])
        result = dq.check_csv(p, SCHEMA)
        self.assertFalse(result["valid"])
        codes = {e["code"] for e in result["errors"]}
        self.assertIn("blank_required", codes)

    def test_duplicate_key_flagged(self):
        p = write_csv(["INV-1,100.00,5,2026-01-01", "INV-1,200.00,3,2026-01-02"])
        result = dq.check_csv(p, SCHEMA)
        self.assertIn("duplicate_key", {e["code"] for e in result["errors"]})

    def test_invalid_decimal_flagged(self):
        p = write_csv(["INV-1,abc,5,2026-01-01"])
        result = dq.check_csv(p, SCHEMA)
        self.assertIn("invalid_type", {e["code"] for e in result["errors"]})

    def test_invalid_date_flagged(self):
        p = write_csv(["INV-1,100.00,5,01/07/2026"])
        result = dq.check_csv(p, SCHEMA)
        self.assertIn("invalid_type", {e["code"] for e in result["errors"]})

    def test_invalid_integer_flagged(self):
        p = write_csv(["INV-1,100.00,notint,2026-01-01"])
        result = dq.check_csv(p, SCHEMA)
        self.assertIn("invalid_type", {e["code"] for e in result["errors"]})

    def test_nonfinite_decimal_rejected(self):
        p = write_csv(["INV-1,Infinity,5,2026-01-01"])
        result = dq.check_csv(p, SCHEMA)
        self.assertIn("invalid_type", {e["code"] for e in result["errors"]})

    def test_nan_decimal_rejected(self):
        p = write_csv(["INV-1,NaN,5,2026-01-01"])
        result = dq.check_csv(p, SCHEMA)
        self.assertIn("invalid_type", {e["code"] for e in result["errors"]})

    def test_missing_column_flagged(self):
        p = write_csv(["INV-1,100.00,5"], header="invoice_id,amount,qty")
        result = dq.check_csv(p, SCHEMA)
        self.assertIn("missing_column", {e["code"] for e in result["errors"]})

    def test_unexpected_column_flagged(self):
        p = write_csv(["INV-1,100.00,5,2026-01-01,extra"], header="invoice_id,amount,qty,due_date,extra")
        result = dq.check_csv(p, SCHEMA)
        self.assertIn("unexpected_column", {e["code"] for e in result["errors"]})

    def test_optional_blank_ok(self):
        p = write_csv(["INV-1,100.00,,2026-01-01"])
        result = dq.check_csv(p, SCHEMA)
        self.assertTrue(result["valid"])

    def test_empty_file(self):
        p = write_csv([], header="invoice_id,amount,qty,due_date")
        result = dq.check_csv(p, SCHEMA)
        self.assertEqual(result["rows"], 0)
        self.assertTrue(result["valid"])

    def test_sha256_deterministic(self):
        p = write_csv(["INV-1,100.00,5,2026-01-01"])
        r1 = dq.check_csv(p, SCHEMA)
        r2 = dq.check_csv(p, SCHEMA)
        self.assertEqual(r1["sha256"], r2["sha256"])

    def test_empty_schema_rejected(self):
        p = write_csv(["INV-1,100.00,5,2026-01-01"])
        with self.assertRaises(ValueError):
            dq.check_csv(p, {"columns": {}})

    def test_unknown_unique_key_rejected(self):
        p = write_csv(["INV-1,100.00,5,2026-01-01"])
        with self.assertRaises(ValueError):
            dq.check_csv(p, {"columns": {"invoice_id": {"type": "string"}}, "unique_keys": ["nonexistent"]})

    def test_unsupported_type_treated_as_invalid(self):
        """P2: unsupported type 'float' is not rejected at schema level —
        instead rows with that column are flagged as invalid_type."""
        p = write_csv(["INV-1,100.00,5,2026-01-01"])
        result = dq.check_csv(p, {"columns": {"invoice_id": {"type": "float"}}})
        self.assertFalse(result["valid"])
        self.assertIn("invalid_type", {e["code"] for e in result["errors"]})

    def test_casefold_duplicate_key(self):
        """Duplicate keys should be case-insensitive."""
        p = write_csv(["inv-1,100.00,5,2026-01-01", "INV-1,200.00,3,2026-01-02"])
        result = dq.check_csv(p, SCHEMA)
        self.assertIn("duplicate_key", {e["code"] for e in result["errors"]})

    def test_bom_handling(self):
        """UTF-8 BOM should not break column matching."""
        d = tempfile.mkdtemp()
        p = Path(d) / "bom.csv"
        p.write_bytes(b"\xef\xbb\xbfinvoice_id,amount,qty,due_date\nINV-1,100.00,5,2026-01-01\n")
        result = dq.check_csv(p, SCHEMA)
        self.assertTrue(result["valid"])

class DataQualityFuzzTests(unittest.TestCase):
    def test_fuzz_1k_valid_rows(self):
        rng = Random(SEED + 50)
        for _ in range(1_000):
            rows = [f"INV-{rng.randint(1,10**9)},{rng.randint(1,9999)}.{rng.randint(0,99):02d},{rng.randint(0,100)},2026-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}"]
            p = write_csv(rows)
            result = dq.check_csv(p, SCHEMA)
            self.assertTrue(result["valid"])

    def test_fuzz_1k_invalid_decimals(self):
        rng = Random(SEED + 60)
        for _ in range(1_000):
            bad_val = rng.choice(["abc", "", "  ", "---", "1.2.3", "null", "undefined"])
            p = write_csv([f"INV-1,{bad_val},5,2026-01-01"])
            result = dq.check_csv(p, SCHEMA)
            if bad_val.strip():
                self.assertIn("invalid_type", {e["code"] for e in result["errors"]})

if __name__ == "__main__":
    unittest.main()
