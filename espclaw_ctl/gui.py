import json
import threading
from pathlib import Path

import serial
import webview

from espclaw_ctl.cli import DEFAULT_BAUD, find_candidate_ports, reset_device

WEBAPP_DIR = Path(__file__).parent / "webapp"


class Api:
    def __init__(self):
        self.ser = None
        self.reader_thread = None
        self.reader_stop = threading.Event()
        self.window = None

    def scan_ports(self):
        matches, all_ports = find_candidate_ports()
        return {
            "ports": [
                {
                    "device": p.device,
                    "vidpid": f"{p.vid:04x}:{p.pid:04x}" if p.vid else "-",
                    "desc": p.description or "",
                }
                for p in all_ports
            ],
            "match": matches[0].device if matches else None,
        }

    def connect(self, port, baud=DEFAULT_BAUD):
        if self.ser is not None:
            self._close()
        try:
            self.ser = serial.Serial(port, baud, timeout=0.2)
        except serial.SerialException as e:
            return {"ok": False, "error": str(e)}
        self.reader_stop.clear()
        self.reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.reader_thread.start()
        reset_device(self.ser)
        return {"ok": True, "port": port, "baud": baud}

    def send_command(self, text):
        ser = self.ser
        if ser is None:
            return {"ok": False, "error": "not connected"}
        try:
            ser.write(text.encode() + b"\r\n")
            return {"ok": True}
        except (serial.SerialException, OSError, TypeError) as e:
            self._close()
            self._push(None)
            return {"ok": False, "error": str(e)}

    def reset(self):
        ser = self.ser
        if ser is not None:
            try:
                reset_device(ser)
            except (serial.SerialException, OSError, TypeError) as e:
                self._close()
                self._push(None)
                return {"ok": False, "error": str(e)}
        return {"ok": True}

    def disconnect(self):
        self._close()
        return {"ok": True}

    def open_web_window(self, url):
        webview.create_window("ESP-Claw Web UI", url, width=920, height=720)
        return {"ok": True}

    def _close(self):
        self.reader_stop.set()
        if self.ser is not None:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None

    def _read_loop(self):
        while not self.reader_stop.is_set():
            ser = self.ser
            if ser is None:
                return
            try:
                chunk = ser.read(1024)
            except (serial.SerialException, OSError):
                self._close()
                self._push(None)
                return
            if chunk:
                self._push(chunk.decode(errors="replace"))

    def _push(self, text):
        if self.window is None:
            return
        payload = json.dumps(text)
        try:
            self.window.evaluate_js(f"window.onSerialData && window.onSerialData({payload})")
        except Exception:
            pass


def main(argv=None):
    api = Api()
    window = webview.create_window(
        "ESP-Claw Control",
        str(WEBAPP_DIR / "index.html"),
        js_api=api,
        width=900,
        height=700,
        min_size=(620, 480),
        background_color="#F5F1EA",
    )
    api.window = window
    webview.start()


if __name__ == "__main__":
    main()
