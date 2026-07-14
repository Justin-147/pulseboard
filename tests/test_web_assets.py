import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
WEB = ROOT / "pulseboard" / "web"


class WebAssetTests(unittest.TestCase):
    def test_referenced_assets_exist(self):
        html = (WEB / "index.html").read_text(encoding="utf-8")
        for asset in ("styles.css", "app.js"):
            self.assertIn(f'/{asset}', html)
            self.assertTrue((WEB / asset).is_file())

    def test_required_dashboard_regions_and_no_external_assets(self):
        html = (WEB / "index.html").read_text(encoding="utf-8")
        script = (WEB / "app.js").read_text(encoding="utf-8")
        for element_id in ("cpuValue", "gpuValue", "memoryValue", "diskValue", "topCpu", "topMemory", "mainChart"):
            self.assertIn(f'id="{element_id}"', html)
        for script_hook in ('setMetric("cpu"', 'setMetric("gpu"', 'renderPrograms("topCpu"', 'renderPrograms("topMemory"', '$("mainChart")'):
            self.assertIn(script_hook, script)
        self.assertNotIn("https://", html)
        self.assertNotIn("http://", html)


if __name__ == "__main__":
    unittest.main()
