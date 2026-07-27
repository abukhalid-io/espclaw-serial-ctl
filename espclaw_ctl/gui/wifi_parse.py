import re

_STATUS_KV_RE = re.compile(r"(\w+)=(\S+)")
_SCAN_DONE_RE = re.compile(r"cmd=scan ok=(\d) count=(\d+)")
_AP_RE = re.compile(r"ap idx=\d+ rssi=(-?\d+) ch=(\d+) auth=(\S+) ssid=(.+)")


def parse_wifi_status(buffer):
    if "sta_connected" not in buffer:
        return None
    return dict(_STATUS_KV_RE.findall(buffer))


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
