import json
import threading
import unittest
import urllib.request

from pulseboard.server import PulseBoardHandler, ReusableThreadingHTTPServer


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ReusableThreadingHTTPServer(("127.0.0.1", 0), PulseBoardHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_health_endpoint(self):
        with urllib.request.urlopen(self.base + "/api/health", timeout=5) as response:
            self.assertEqual(json.load(response)["status"], "ok")

    def test_dashboard_and_metrics(self):
        with urllib.request.urlopen(self.base + "/", timeout=5) as response:
            body = response.read().decode("utf-8")
            self.assertIn("PulseBoard", body)
            self.assertIn("数据仅在本机", body)
        with urllib.request.urlopen(self.base + "/api/metrics", timeout=10) as response:
            payload = json.load(response)
            self.assertIn("cpu", payload)
            self.assertIn("top_cpu", payload["processes"])


if __name__ == "__main__":
    unittest.main()

