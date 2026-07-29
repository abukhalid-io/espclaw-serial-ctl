import argparse
import sys
import threading
import time

import serial
import serial.tools.list_ports

from espclaw_ctl import config_store

DEFAULT_BAUD = 115200

# Known USB-to-serial chip VID:PID pairs seen on ESP32 dev boards.
KNOWN_VID_PID = {
    (0x1A86, 0x7523): "CH340",
    (0x1A86, 0x55D3): "CH9102",  # QinHeng CH34x "USB Single Serial" — ESP-Claw breadboard board
    (0x10C4, 0xEA60): "CP210x",
    (0x0403, 0x6001): "FTDI FT232",
    (0x0403, 0x6015): "FTDI FT231X",
}
# ESP32-S2/S3/C3 built-in native USB-Serial/JTAG — pid varies by chip/mode, match by vendor only.
ESPRESSIF_USB_VID = 0x303A
_DESC_HINTS = ("ch340", "ch9102", "cp210", "ftdi", "usb-serial", "usb serial", "usb jtag", "silicon labs")


def looks_like_esp_port(port):
    """True if a serial.tools.list_ports port-like object looks like an ESP32 USB-serial link."""
    if port.vid is None:
        return False
    if (port.vid, port.pid) in KNOWN_VID_PID:
        return True
    if port.vid == ESPRESSIF_USB_VID:
        return True
    desc = (port.description or "").lower()
    return any(hint in desc for hint in _DESC_HINTS)


def find_candidate_ports():
    ports = list(serial.tools.list_ports.comports())
    matches = [p for p in ports if looks_like_esp_port(p)]
    return matches, ports


def quote_console_arg(value):
    """Quote a value for the ESP-Claw console's double-quoted argument parser."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def resolve_port(explicit_port):
    if explicit_port:
        config_store.save(last_port=explicit_port)
        return explicit_port
    matches, all_ports = find_candidate_ports()
    if len(matches) == 1:
        config_store.save(last_port=matches[0].device)
        return matches[0].device
    if len(matches) > 1:
        print("Found more than one ESP32 device, pick one with --port:", file=sys.stderr)
        for p in matches:
            print(f"  {p.device}  serial={p.serial_number}  {p.description}", file=sys.stderr)
        sys.exit(1)

    last_port = config_store.load().get("last_port")
    if last_port and any(p.device == last_port for p in all_ports):
        print(f"No known VID:PID match, using last used port: {last_port}", file=sys.stderr)
        return last_port

    print("No ESP-Claw device detected.", file=sys.stderr)
    if all_ports:
        print("Available serial ports:", file=sys.stderr)
        for p in all_ports:
            vidpid = f"{p.vid:04x}:{p.pid:04x}" if p.vid else "-"
            print(f"  {p.device}\t{vidpid}\t{p.description}", file=sys.stderr)
    print("Use --port <device> to pick manually, or run 'espclawctl list'.", file=sys.stderr)
    sys.exit(1)


def _port_is_native_usb_jtag(ser):
    """True if the open port is the ESP32's built-in USB-Serial/JTAG peripheral
    (Espressif VID 0x303A) rather than an external USB-UART bridge chip
    (CH340/CP210x/FTDI)."""
    port_name = getattr(ser, "port", None)
    if not port_name:
        return False
    for p in serial.tools.list_ports.comports():
        if p.device == port_name:
            return p.vid == ESPRESSIF_USB_VID
    return False


def _set_rts_native(ser, state):
    ser.setRTS(state)
    # Windows usbser.sys workaround: re-send the current DTR state so the
    # updated RTS state is actually flushed in the same control request.
    ser.setDTR(ser.dtr)


def reset_device(ser, settle=0.5):
    """Hard-reset the ESP32 back into its running app (not the ROM bootloader).

    External USB-UART bridges (CH340/CP210x/FTDI) use the classic DTR/RTS
    dance: hold IO0 (DTR) high while pulsing EN (RTS) low then high, so the
    chip leaves reset straight into the app.

    The native USB-Serial/JTAG peripheral built into ESP32-S2/S3/C3 does NOT
    behave the same way: toggling DTR at all (even setting it to "false"
    first) reliably drops the chip into the ROM download stub ("waiting for
    download") instead of the running app. It only needs an EN pulse via
    RTS, with DTR left completely untouched — mirroring esptool's own
    HardReset(uses_usb=True) strategy for this peripheral.
    """
    if _port_is_native_usb_jtag(ser):
        _set_rts_native(ser, True)   # EN -> LOW, chip in reset
        time.sleep(0.2)
        _set_rts_native(ser, False)  # EN -> HIGH, chip boots the running app
        time.sleep(0.2)
    else:
        ser.setDTR(False)  # IO0=HIGH
        ser.setRTS(True)  # EN=LOW, chip in reset
        time.sleep(0.1)
        ser.setRTS(False)  # EN=HIGH, chip out of reset
        time.sleep(0.1)
        ser.setDTR(False)
    time.sleep(settle)


def read_idle(ser, idle_ms=700, max_total=8.0):
    data = b""
    deadline = time.time() + max_total
    idle_deadline = time.time() + idle_ms / 1000
    while time.time() < deadline and time.time() < idle_deadline:
        chunk = ser.read(1024)
        if chunk:
            data += chunk
            idle_deadline = time.time() + idle_ms / 1000
    return data


def send_command(ser, text, idle_ms=700, max_total=8.0):
    ser.write(b"\r\n")
    time.sleep(0.2)
    ser.reset_input_buffer()
    ser.write(text.encode() + b"\r\n")
    return read_idle(ser, idle_ms=idle_ms, max_total=max_total)


def open_serial(port, baud):
    try:
        return serial.Serial(port, baud, timeout=0.2)
    except serial.SerialException as e:
        print(f"Failed to open {port}: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_list(args):
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("No serial ports detected.")
        return
    for p in ports:
        tag = "  <- likely ESP-Claw" if looks_like_esp_port(p) else ""
        vidpid = f"{p.vid:04x}:{p.pid:04x}" if p.vid else "-"
        print(f"{p.device}\t{vidpid}\t{p.description}{tag}")


def cmd_reset(args):
    port = resolve_port(args.port)
    ser = open_serial(port, args.baud)
    print(f"Resetting {port} ...", file=sys.stderr)
    reset_device(ser)
    data = read_idle(ser, idle_ms=800, max_total=args.timeout)
    ser.close()
    sys.stdout.write(data.decode(errors="replace"))


def cmd_cmd(args):
    port = resolve_port(args.port)
    ser = open_serial(port, args.baud)
    data = send_command(ser, args.command, max_total=args.timeout)
    ser.close()
    sys.stdout.write(data.decode(errors="replace"))


def _run_and_print(args, command, timeout=None, idle_ms=None):
    port = resolve_port(args.port)
    ser = open_serial(port, args.baud)
    kwargs = {"max_total": timeout or args.timeout}
    if idle_ms is not None:
        kwargs["idle_ms"] = idle_ms
    data = send_command(ser, command, **kwargs)
    ser.close()
    sys.stdout.write(data.decode(errors="replace"))


def cmd_wifi_status(args):
    _run_and_print(args, "wifi --status")


def cmd_wifi_scan(args):
    # Scanning switches the radio to STA+AP mode and runs a blocking scan
    # across all channels before printing results — there's a ~2-3s gap
    # with no serial output in the middle of that, longer than the default
    # 700ms idle window, so read_idle() used to give up before the "cmd=scan
    # ok=1 ..." result line ever arrived. Give it more idle headroom.
    _run_and_print(args, "wifi --scan", timeout=max(args.timeout, 8.0), idle_ms=4000)


def cmd_wifi_set(args):
    command = f"wifi --set --ssid {quote_console_arg(args.ssid)} --password {quote_console_arg(args.password)}"
    if not args.save_only:
        command += " --apply"
    # --apply triggers a mode switch + STA connection attempt (DHCP etc.)
    # with the same kind of quiet gap as --scan; --save-only is instant.
    idle_ms = 4000 if not args.save_only else 700
    _run_and_print(args, command, timeout=max(args.timeout, 12.0), idle_ms=idle_ms)
    config_store.save(last_ssid=args.ssid)


def cmd_console(args):
    port = resolve_port(args.port)
    ser = open_serial(port, args.baud)
    print(f"Connected to {port} @ {args.baud} baud. Ctrl+C to quit.", file=sys.stderr)
    if args.reset:
        reset_device(ser)

    stop = threading.Event()

    def reader():
        while not stop.is_set():
            try:
                chunk = ser.read(1024)
            except serial.SerialException:
                break
            if chunk:
                sys.stdout.write(chunk.decode(errors="replace"))
                sys.stdout.flush()

    t = threading.Thread(target=reader, daemon=True)
    t.start()

    try:
        while True:
            line = input()
            ser.write(line.encode() + b"\r\n")
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        stop.set()
        ser.close()
        print("\nDisconnected.", file=sys.stderr)


def build_parser():
    p = argparse.ArgumentParser(
        prog="espclawctl",
        description="Control ESP-Claw (ESP32-S3) over its USB serial console.",
    )
    p.add_argument("--port", help="Serial port, e.g. /dev/ttyACM0 or COM5. Auto-detected if not given.")
    p.add_argument("--baud", type=int, default=DEFAULT_BAUD, help=f"Baud rate (default {DEFAULT_BAUD})")
    p.add_argument("--timeout", type=float, default=8.0, help="Response wait timeout in seconds (default 8)")

    sub = p.add_subparsers(dest="action", required=True)

    sp = sub.add_parser("list", help="List all detected serial ports")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("console", help="Open an interactive terminal to the ESP-Claw console")
    sp.add_argument("--reset", action="store_true", help="Reset the device before entering the console (see boot log)")
    sp.set_defaults(func=cmd_console)

    sp = sub.add_parser("cmd", help="Send a single console command and print the result")
    sp.add_argument("command", help='Console command, e.g. "help" or "wifi --status"')
    sp.set_defaults(func=cmd_cmd)

    sp = sub.add_parser("reset", help="Reset the device and print the boot log")
    sp.set_defaults(func=cmd_reset)

    sp = sub.add_parser("wifi-status", help="Show the device's WiFi status")
    sp.set_defaults(func=cmd_wifi_status)

    sp = sub.add_parser("wifi-scan", help="Scan nearby WiFi access points")
    sp.set_defaults(func=cmd_wifi_scan)

    sp = sub.add_parser("wifi-set", help="Set new WiFi credentials (applies immediately by default)")
    sp.add_argument("--ssid", required=True)
    sp.add_argument("--password", required=True)
    sp.add_argument("--save-only", action="store_true", help="Save without applying/reconnecting immediately")
    sp.set_defaults(func=cmd_wifi_set)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
