import re

_STATUS_KV_RE = re.compile(r"(\w+)=(\S+)")
_SCAN_DONE_RE = re.compile(r"cmd=scan ok=(\d) count=(\d+)")
_AP_RE = re.compile(r"ap idx=\d+ rssi=(-?\d+) ch=(\d+) auth=(\S+) ssid=(.+)")
_SET_RESULT_RE = re.compile(r"cmd=set ok=(\d)(?:\s+err=(\S+))?")
_SCAN_FAILED_RE = re.compile(r"cmd=scan ok=0(?:\s+err=(\S+))?")


def parse_wifi_set_result(buffer):
    """Parse the device's response to 'wifi --set ... --apply'.

    Returns None until a 'cmd=set ok=...' line has been seen, then a dict
    {"ok": bool, "err": str or None}. The device can reject this command
    with err=ESP_ERR_WIFI_STATE ("sta is connecting, cannot set config")
    when its own background STA reconnect loop happens to be mid-attempt —
    a transient, retryable condition, not a real failure.
    """
    m = _SET_RESULT_RE.search(buffer)
    if not m:
        return None
    return {"ok": m.group(1) == "1", "err": m.group(2)}


def parse_wifi_status(buffer):
    if "sta_connected" not in buffer:
        return None
    return dict(_STATUS_KV_RE.findall(buffer))


def parse_wifi_scan_failure(buffer):
    """True if the device explicitly rejected 'wifi --scan' (ok=0).

    Scanning switches the radio to STA+AP mode, which the device can reject
    with err=ESP_ERR_WIFI_STATE ("sta is connecting, cannot set config")
    whenever its own background STA reconnect loop is mid-attempt — the
    same transient race as the 'wifi --set --apply' busy case. Returns the
    err code (or 'unknown_error') once seen, else None.
    """
    m = _SCAN_FAILED_RE.search(buffer)
    if not m:
        return None
    return m.group(1) or "unknown_error"


def parse_wifi_scan(buffer):
    if not _SCAN_DONE_RE.search(buffer):
        return None
    found = {}
    for m in _AP_RE.finditer(buffer):
        rssi = int(m.group(1))
        ch = m.group(2)
        auth = m.group(3)
        ssid = m.group(4).strip().rstrip("\r")
        if not ssid:
            continue
        existing = found.get(ssid)
        if existing is None or rssi > existing["rssi"]:
            found[ssid] = {"ssid": ssid, "rssi": rssi, "ch": ch, "auth": auth}
    return sorted(found.values(), key=lambda ap: -ap["rssi"])


def signal_bars(rssi):
    if rssi >= -55:
        return 4
    if rssi >= -67:
        return 3
    if rssi >= -75:
        return 2
    return 1
