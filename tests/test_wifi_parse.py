import unittest

from espclaw_ctl.gui.wifi_parse import parse_wifi_scan, parse_wifi_status, signal_bars


class TestParseWifiStatus(unittest.TestCase):
    def test_parses_key_value_pairs(self):
        buffer = "cmd=wifi-status ok=1 sta_connected=1 sta_ip=192.168.1.23 saved_ssid=HomeNet\r\n"
        result = parse_wifi_status(buffer)
        self.assertEqual(result["sta_connected"], "1")
        self.assertEqual(result["sta_ip"], "192.168.1.23")
        self.assertEqual(result["saved_ssid"], "HomeNet")

    def test_returns_none_when_marker_missing(self):
        self.assertIsNone(parse_wifi_status("some unrelated console output\n"))


class TestParseWifiScan(unittest.TestCase):
    SCAN_BUFFER = (
        "ap idx=0 rssi=-40 ch=6 auth=wpa2 ssid=HomeNet\r\n"
        "ap idx=1 rssi=-70 ch=11 auth=open ssid=CafeWifi\r\n"
        "ap idx=2 rssi=-55 ch=6 auth=wpa2 ssid=HomeNet\r\n"  # duplicate SSID, weaker signal
        "cmd=scan ok=1 count=3\r\n"
    )

    def test_returns_none_before_scan_completes(self):
        self.assertIsNone(parse_wifi_scan("ap idx=0 rssi=-40 ch=6 auth=wpa2 ssid=HomeNet\r\n"))

    def test_dedupes_by_strongest_signal_and_sorts_desc(self):
        aps = parse_wifi_scan(self.SCAN_BUFFER)
        self.assertEqual([a["ssid"] for a in aps], ["HomeNet", "CafeWifi"])
        self.assertEqual(aps[0]["rssi"], -40)  # kept the stronger of the two HomeNet entries

    def test_skips_blank_ssid(self):
        buffer = "ap idx=0 rssi=-40 ch=6 auth=open ssid=\r\ncmd=scan ok=1 count=1\r\n"
        self.assertEqual(parse_wifi_scan(buffer), [])


class TestSignalBars(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual(signal_bars(-40), 4)
        self.assertEqual(signal_bars(-60), 3)
        self.assertEqual(signal_bars(-70), 2)
        self.assertEqual(signal_bars(-90), 1)


if __name__ == "__main__":
    unittest.main()
