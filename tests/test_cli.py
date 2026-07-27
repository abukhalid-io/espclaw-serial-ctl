import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from espclaw_ctl import config_store
from espclaw_ctl.cli import looks_like_esp_port, quote_console_arg


def fake_port(vid=None, pid=None, description=""):
    return SimpleNamespace(vid=vid, pid=pid, description=description)


class TestLooksLikeEspPort(unittest.TestCase):
    def test_known_ch340_vid_pid_matches(self):
        self.assertTrue(looks_like_esp_port(fake_port(0x1A86, 0x55D3, "USB Single Serial")))

    def test_known_cp210x_vid_pid_matches(self):
        self.assertTrue(looks_like_esp_port(fake_port(0x10C4, 0xEA60, "CP2102 USB to UART Bridge")))

    def test_espressif_native_usb_vid_matches_any_pid(self):
        self.assertTrue(looks_like_esp_port(fake_port(0x303A, 0x1001, "USB JTAG/serial debug unit")))

    def test_unknown_vid_pid_falls_back_to_description_hint(self):
        self.assertTrue(looks_like_esp_port(fake_port(0x9999, 0x0001, "Some CH340 clone")))

    def test_unrelated_device_does_not_match(self):
        self.assertFalse(looks_like_esp_port(fake_port(0x046D, 0xC52B, "Logitech USB Receiver")))

    def test_no_vid_does_not_match(self):
        self.assertFalse(looks_like_esp_port(fake_port(None, None, "Bluetooth link")))


class TestQuoteConsoleArg(unittest.TestCase):
    def test_wraps_in_quotes(self):
        self.assertEqual(quote_console_arg("hello"), '"hello"')

    def test_escapes_double_quotes(self):
        self.assertEqual(quote_console_arg('a"b'), '"a\\"b"')

    def test_escapes_backslash(self):
        self.assertEqual(quote_console_arg("a\\b"), '"a\\\\b"')

    def test_combined_backslash_and_quote(self):
        self.assertEqual(quote_console_arg('pass\\"word'), '"pass\\\\\\"word"')


class TestConfigStore(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        fake_dir = Path(self._tmpdir.name) / ".espclaw_ctl"
        patcher_dir = mock.patch.object(config_store, "CONFIG_DIR", fake_dir)
        patcher_path = mock.patch.object(config_store, "CONFIG_PATH", fake_dir / "config.json")
        patcher_dir.start()
        patcher_path.start()
        self.addCleanup(patcher_dir.stop)
        self.addCleanup(patcher_path.stop)

    def test_load_missing_file_returns_empty_dict(self):
        self.assertEqual(config_store.load(), {})

    def test_save_then_load_roundtrip(self):
        config_store.save(last_port="COM5")
        self.assertEqual(config_store.load(), {"last_port": "COM5"})

    def test_save_merges_with_existing_keys(self):
        config_store.save(last_port="COM5")
        config_store.save(last_ssid="HomeNet")
        self.assertEqual(config_store.load(), {"last_port": "COM5", "last_ssid": "HomeNet"})


if __name__ == "__main__":
    unittest.main()
