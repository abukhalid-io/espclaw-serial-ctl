import argparse
import sys
import threading
import time

import serial
import serial.tools.list_ports

DEFAULT_BAUD = 115200
# QinHeng CH34x "USB Single Serial" — the USB-serial chip on the ESP-Claw board.
CH340_VID_PID = (0x1A86, 0x55D3)


def find_candidate_ports():
    ports = list(serial.tools.list_ports.comports())
    matches = [p for p in ports if (p.vid, p.pid) == CH340_VID_PID]
    return matches, ports


def resolve_port(explicit_port):
    if explicit_port:
        return explicit_port
    matches, all_ports = find_candidate_ports()
    if len(matches) == 1:
        return matches[0].device
    if len(matches) > 1:
        print("Ditemukan lebih dari satu device CH340, pilih salah satu dengan --port:", file=sys.stderr)
        for p in matches:
            print(f"  {p.device}  serial={p.serial_number}  {p.description}", file=sys.stderr)
        sys.exit(1)
    print("Tidak ada device ESP-Claw (CH340) yang terdeteksi.", file=sys.stderr)
    if all_ports:
        print("Serial port yang tersedia:", file=sys.stderr)
        for p in all_ports:
            vidpid = f"{p.vid:04x}:{p.pid:04x}" if p.vid else "-"
            print(f"  {p.device}\t{vidpid}\t{p.description}", file=sys.stderr)
    print("Gunakan --port <device> untuk pilih manual, atau jalankan 'espclawctl list'.", file=sys.stderr)
    sys.exit(1)


def reset_device(ser, settle=0.5):
    ser.setDTR(False)
    ser.setRTS(True)
    time.sleep(0.1)
    ser.setRTS(False)
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
        print(f"Gagal buka {port}: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_list(args):
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("Tidak ada serial port terdeteksi.")
        return
    for p in ports:
        tag = "  <- kemungkinan ESP-Claw" if p.vid and (p.vid, p.pid) == CH340_VID_PID else ""
        vidpid = f"{p.vid:04x}:{p.pid:04x}" if p.vid else "-"
        print(f"{p.device}\t{vidpid}\t{p.description}{tag}")


def cmd_reset(args):
    port = resolve_port(args.port)
    ser = open_serial(port, args.baud)
    print(f"Reset {port} ...", file=sys.stderr)
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


def _run_and_print(args, command, timeout=None):
    port = resolve_port(args.port)
    ser = open_serial(port, args.baud)
    data = send_command(ser, command, max_total=timeout or args.timeout)
    ser.close()
    sys.stdout.write(data.decode(errors="replace"))


def cmd_wifi_status(args):
    _run_and_print(args, "wifi --status")


def cmd_wifi_scan(args):
    _run_and_print(args, "wifi --scan", timeout=max(args.timeout, 8.0))


def cmd_wifi_set(args):
    command = f'wifi --set --ssid "{args.ssid}" --password "{args.password}"'
    if not args.save_only:
        command += " --apply"
    _run_and_print(args, command, timeout=max(args.timeout, 12.0))


def cmd_console(args):
    port = resolve_port(args.port)
    ser = open_serial(port, args.baud)
    print(f"Terhubung ke {port} @ {args.baud} baud. Ctrl+C untuk keluar.", file=sys.stderr)
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
        print("\nTerputus.", file=sys.stderr)


def build_parser():
    p = argparse.ArgumentParser(
        prog="espclawctl",
        description="Kontrol ESP-Claw (ESP32-S3) via console USB serial-nya.",
    )
    p.add_argument("--port", help="Serial port, misal /dev/ttyACM0 atau COM5. Auto-detect kalau tidak diisi.")
    p.add_argument("--baud", type=int, default=DEFAULT_BAUD, help=f"Baud rate (default {DEFAULT_BAUD})")
    p.add_argument("--timeout", type=float, default=8.0, help="Batas waktu tunggu respons dalam detik (default 8)")

    sub = p.add_subparsers(dest="action", required=True)

    sp = sub.add_parser("list", help="List semua serial port yang terdeteksi")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("console", help="Buka terminal interaktif ke console ESP-Claw")
    sp.add_argument("--reset", action="store_true", help="Reset device dulu sebelum masuk console (lihat boot log)")
    sp.set_defaults(func=cmd_console)

    sp = sub.add_parser("cmd", help="Kirim satu command console dan tampilkan hasilnya")
    sp.add_argument("command", help='Command console, misal: "help" atau "wifi --status"')
    sp.set_defaults(func=cmd_cmd)

    sp = sub.add_parser("reset", help="Reset device dan tampilkan boot log")
    sp.set_defaults(func=cmd_reset)

    sp = sub.add_parser("wifi-status", help="Tampilkan status WiFi device")
    sp.set_defaults(func=cmd_wifi_status)

    sp = sub.add_parser("wifi-scan", help="Scan AP WiFi terdekat")
    sp.set_defaults(func=cmd_wifi_scan)

    sp = sub.add_parser("wifi-set", help="Set kredensial WiFi baru (default langsung apply)")
    sp.add_argument("--ssid", required=True)
    sp.add_argument("--password", required=True)
    sp.add_argument("--save-only", action="store_true", help="Simpan tanpa langsung apply/reconnect")
    sp.set_defaults(func=cmd_wifi_set)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
