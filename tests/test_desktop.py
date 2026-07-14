import unittest

from pulseboard.desktop import CYAN, ORANGE, RED, format_bytes, format_compact_number, format_uptime, pressure_color


class DesktopHelperTests(unittest.TestCase):
    def test_format_bytes(self):
        self.assertEqual(format_bytes(0), "0.0 B")
        self.assertEqual(format_bytes(1024), "1.0 KB")
        self.assertEqual(format_bytes(5 * 1024**3), "5.0 GB")
        self.assertEqual(format_bytes(None), "—")

    def test_format_uptime(self):
        self.assertEqual(format_uptime(3600), "1小时 0分")
        self.assertEqual(format_uptime(90000), "1天 1小时")

    def test_format_compact_number(self):
        self.assertEqual(format_compact_number(1_270_000_000), "1.27B")
        self.assertEqual(format_compact_number(258_400), "258.4K")
        self.assertEqual(format_compact_number(None), "—")

    def test_pressure_colors(self):
        self.assertEqual(pressure_color(20, CYAN), CYAN)
        self.assertEqual(pressure_color(75, CYAN), ORANGE)
        self.assertEqual(pressure_color(90, CYAN), RED)


if __name__ == "__main__":
    unittest.main()
