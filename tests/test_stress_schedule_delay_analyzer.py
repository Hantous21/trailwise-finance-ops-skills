"""Stress, property, and fuzz tests for schedule-delay-analyzer. Seed: 20260701."""
from __future__ import annotations
import importlib.util, sys, time, unittest
from dataclasses import replace
from pathlib import Path
from random import Random

ROOT = Path(__file__).resolve().parents[1]

def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m

sched = load("schedule_delay_analyzer", "6_Contractor_Operations/schedule-delay-analyzer/scripts/schedule_delay_analyzer.py")
Activity = sched.Activity
SEED = 20260701

class ScheduleLoadTests(unittest.TestCase):
    def test_10k_chain(self):
        """Deep: 10K activities in a single chain."""
        acts = [Activity("A0", 1)]
        for i in range(1, 10_000):
            acts.append(Activity(f"A{i}", 1, (f"A{i-1}",)))
        start = time.perf_counter()
        result = sched.analyze(acts)
        elapsed = time.perf_counter() - start
        self.assertEqual(result["project_duration_days"], 10_000)
        self.assertLess(elapsed, 5.0, f"10K chain took {elapsed:.3f}s")

    def test_10k_parallel(self):
        """Wide: 10K activities all parallel from one predecessor."""
        acts = [Activity("START", 0)] + [Activity(f"P{i}", 1, ("START",)) for i in range(10_000)]
        start = time.perf_counter()
        result = sched.analyze(acts)
        elapsed = time.perf_counter() - start
        self.assertEqual(result["project_duration_days"], 1)
        self.assertLess(elapsed, 5.0, f"10K wide took {elapsed:.3f}s")

    def test_10k_dag(self):
        """Mixed DAG: random but acyclic."""
        rng = Random(SEED)
        ids = [f"A{i}" for i in range(10_000)]
        acts = [Activity(ids[0], rng.randint(0, 5))]
        for i in range(1, 10_000):
            n_preds = min(rng.randint(0, 3), i)
            preds = tuple(rng.sample(ids[:i], n_preds)) if n_preds else ()
            acts.append(Activity(ids[i], rng.randint(0, 10), preds))
        start = time.perf_counter()
        result = sched.analyze(acts)
        elapsed = time.perf_counter() - start
        self.assertGreater(result["project_duration_days"], 0)
        self.assertLess(elapsed, 5.0, f"10K DAG took {elapsed:.3f}s")

    def test_empty_schedule_rejected(self):
        with self.assertRaises(ValueError):
            sched.analyze([])

class SchedulePropertyTests(unittest.TestCase):
    def test_cycle_rejected(self):
        acts = [Activity("A", 1, ("B",)), Activity("B", 1, ("A",))]
        with self.assertRaisesRegex(ValueError, "cycle"):
            sched.analyze(acts)

    def test_missing_predecessor_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing predecessor"):
            sched.analyze([Activity("A", 1, ("MISSING",))])

    def test_duplicate_ids_rejected(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            sched.analyze([Activity("A", 1), Activity("A", 2)])

    def test_self_dependency_rejected(self):
        with self.assertRaises(ValueError):
            Activity("A", 1, ("A",))

    def test_duplicate_predecessors_rejected(self):
        with self.assertRaises(ValueError):
            Activity("A", 1, ("B", "B"))

    def test_negative_duration_rejected(self):
        with self.assertRaises(ValueError):
            Activity("A", -1)

    def test_zero_duration_milestone(self):
        result = sched.analyze([Activity("M", 0)])
        self.assertEqual(result["project_duration_days"], 0)
        self.assertIn("M", result["critical_path"])

    def test_empty_id_rejected(self):
        with self.assertRaises(ValueError):
            Activity("", 1)
        with self.assertRaises(ValueError):
            Activity("  ", 1)

    def test_nonnegative_float(self):
        acts = [Activity("A", 3), Activity("B", 5, ("A",)), Activity("C", 2, ("A",))]
        result = sched.analyze(acts)
        for row in result["activities"]:
            self.assertGreaterEqual(row["total_float"], 0)

    def test_cpm_ordering_independence(self):
        acts = [Activity("A", 3), Activity("B", 5, ("A",)), Activity("C", 2, ("A",))]
        r1 = sched.analyze(acts)
        r2 = sched.analyze(list(reversed(acts)))
        self.assertEqual(r1["project_duration_days"], r2["project_duration_days"])
        self.assertEqual(set(r1["critical_path"]), set(r2["critical_path"]))

    def test_critical_path_correct(self):
        acts = [Activity("A", 3), Activity("B", 5, ("A",)), Activity("C", 2, ("A",))]
        result = sched.analyze(acts)
        self.assertEqual(result["project_duration_days"], 8)
        self.assertEqual(result["critical_path"], ["A", "B"])

    def test_delay_absorbs_float_before_impact(self):
        acts = [Activity("A", 3), Activity("B", 5, ("A",)), Activity("C", 2, ("A",))]
        # C has 3 days float. Delay C by 4 → 3 absorbed, 1 project impact
        result = sched.simulate_delay(acts, "C", 4)
        self.assertEqual(result["absorbed_by_float_days"], 3)
        self.assertEqual(result["project_impact_days"], 1)

    def test_delay_on_critical_path_full_impact(self):
        acts = [Activity("A", 3), Activity("B", 5, ("A",))]
        result = sched.simulate_delay(acts, "B", 2)
        self.assertEqual(result["project_impact_days"], 2)
        self.assertEqual(result["absorbed_by_float_days"], 0)

    def test_zero_delay_no_impact(self):
        acts = [Activity("A", 3), Activity("B", 5, ("A",))]
        result = sched.simulate_delay(acts, "A", 0)
        self.assertEqual(result["project_impact_days"], 0)

    def test_negative_delay_rejected(self):
        acts = [Activity("A", 1)]
        with self.assertRaises(ValueError):
            sched.simulate_delay(acts, "A", -1)

    def test_unknown_activity_rejected(self):
        acts = [Activity("A", 1)]
        with self.assertRaises(ValueError):
            sched.simulate_delay(acts, "Z", 1)

    def test_delay_never_decreases_duration(self):
        acts = [Activity("A", 3), Activity("B", 5, ("A",)), Activity("C", 2, ("A",))]
        baseline = sched.analyze(acts)["project_duration_days"]
        rng = Random(SEED + 70)
        for _ in range(100):
            target = rng.choice(["A", "B", "C"])
            delay = rng.randint(0, 10)
            result = sched.simulate_delay(acts, target, delay)
            self.assertGreaterEqual(result["adjusted_duration_days"], baseline)

    def test_float_plus_impact_equals_delay(self):
        """absorbed_by_float + project_impact == input_delay (invariant)."""
        acts = [Activity("A", 3), Activity("B", 5, ("A",)), Activity("C", 2, ("A",))]
        rng = Random(SEED + 80)
        for _ in range(100):
            target = rng.choice(["A", "B", "C"])
            delay = rng.randint(0, 10)
            result = sched.simulate_delay(acts, target, delay)
            self.assertEqual(result["absorbed_by_float_days"] + result["project_impact_days"], delay)

class ScheduleFuzzTests(unittest.TestCase):
    def test_fuzz_1k_random_schedules(self):
        rng = Random(SEED + 100)
        for i in range(1_000):
            n = rng.randint(1, 20)
            ids = [f"S{i}_{j}" for j in range(n)]
            acts = []
            for j in range(n):
                n_preds = min(rng.randint(0, 2), j)
                preds = tuple(rng.sample(ids[:j], n_preds)) if n_preds else ()
                acts.append(Activity(ids[j], rng.randint(0, 5), preds))
            result = sched.analyze(acts)
            for row in result["activities"]:
                self.assertGreaterEqual(row["total_float"], 0)

    def test_fuzz_1k_delays(self):
        rng = Random(SEED + 200)
        acts = [Activity("A", 3), Activity("B", 5, ("A",)), Activity("C", 2, ("A",))]
        baseline = sched.analyze(acts)["project_duration_days"]
        for _ in range(1_000):
            target = rng.choice(["A", "B", "C"])
            delay = rng.randint(0, 15)
            result = sched.simulate_delay(acts, target, delay)
            self.assertGreaterEqual(result["adjusted_duration_days"], baseline)
            self.assertEqual(result["absorbed_by_float_days"] + result["project_impact_days"], delay)

if __name__ == "__main__":
    unittest.main()
