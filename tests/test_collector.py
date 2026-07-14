import unittest

from pulseboard.collector import SystemCollector


class CollectorTests(unittest.TestCase):
    def test_snapshot_has_expected_shape_and_ranges(self):
        collector = SystemCollector()
        snapshot = collector.snapshot()
        for key in ("host", "cpu", "memory", "gpu", "disk", "network", "processes"):
            self.assertIn(key, snapshot)
        self.assertGreaterEqual(snapshot["cpu"]["percent"], 0)
        self.assertLessEqual(snapshot["cpu"]["percent"], 100)
        self.assertGreater(snapshot["memory"]["total"], 0)
        self.assertLessEqual(len(snapshot["processes"]["top_cpu"]), 5)
        self.assertLessEqual(len(snapshot["processes"]["top_memory"]), 5)

    def test_program_rows_are_aggregated(self):
        collector = SystemCollector()
        top_cpu, top_memory, count = collector._programs()
        self.assertGreater(count, 0)
        self.assertTrue(all(row["instances"] >= 1 for row in top_cpu + top_memory))


if __name__ == "__main__":
    unittest.main()

