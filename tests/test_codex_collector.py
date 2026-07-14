import unittest

from pulseboard.codex_collector import parse_usage_snapshot


class CodexCollectorTests(unittest.TestCase):
    def test_parse_usage_snapshot(self):
        result = parse_usage_snapshot(
            {"account": {"planType": "pro"}},
            {
                "rateLimits": {
                    "primary": {"usedPercent": 12, "windowDurationMins": 10080, "resetsAt": 1784616076},
                    "planType": "pro",
                }
            },
            {"summary": {"lifetimeTokens": 5000000000}, "dailyUsageBuckets": [{"startDate": "2026-07-13", "tokens": 1200000000}]},
            {"name": "测试任务"},
            {
                "last": {"total_tokens": 129200},
                "total": {"total_tokens": 18000000},
                "model_context_window": 258400,
            },
        )
        self.assertTrue(result["connected"])
        self.assertEqual(result["quota"]["used_percent"], 12)
        self.assertEqual(result["tokens"]["latest_daily"], 1200000000)
        self.assertEqual(result["context"]["used_percent"], 50)
        self.assertEqual(result["context"]["thread_name"], "测试任务")


if __name__ == "__main__":
    unittest.main()
