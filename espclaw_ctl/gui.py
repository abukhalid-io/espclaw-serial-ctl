import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import scrolledtext, ttk

import serial

from espclaw_ctl.cli import (
    CH340_VID_PID,
    DEFAULT_BAUD,
    find_candidate_ports,
    reset_device,
)

SCAN_INTERVAL_MS = 1000


class EspClawApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ESP-Claw Serial Control")
        self.geometry("760x560")
        self.minsize(560, 400)

        self.ser = None
        self.out_queue = queue.Queue()
        self.reader_thread = None
        self.reader_stop = threading.Event()

        self.scan_frame = ScanFrame(self, on_connect=self.connect)
        self.console_frame = ConsoleFrame(self, on_disconnect=self.disconnect)

        self.scan_frame.pack(fill="both", expand=True)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.after(100, self.scan_frame.start_scanning)

    def connect(self, port, baud=DEFAULT_BAUD):
        try:
            self.ser = serial.Serial(port, baud, timeout=0.2)
        except serial.SerialException as e:
            self.scan_frame.show_error(f"Gagal buka {port}: {e}")
            return

        self.scan_frame.pack_forget()
        self.console_frame.pack(fill="both", expand=True)
        self.console_frame.attach(port, baud)

        self.reader_stop.clear()
        self.reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.reader_thread.start()

        reset_device(self.ser)
        self._poll_queue()

    def _read_loop(self):
        while not self.reader_stop.is_set():
            try:
                chunk = self.ser.read(1024)
            except (serial.SerialException, OSError):
                self.out_queue.put(None)
                return
            if chunk:
                self.out_queue.put(chunk.decode(errors="replace"))

    def _poll_queue(self):
        try:
            while True:
                item = self.out_queue.get_nowait()
                if item is None:
                    self.console_frame.append_output("\n[Koneksi terputus]\n")
                    self.disconnect()
                    return
                self.console_frame.append_output(item)
        except queue.Empty:
            pass
        if self.ser is not None:
            self.after(80, self._poll_queue)

    def send_command(self, text):
        if self.ser is None:
            return
        try:
            self.ser.write(text.encode() + b"\r\n")
        except (serial.SerialException, OSError) as e:
            self.console_frame.append_output(f"\n[Gagal kirim: {e}]\n")

    def disconnect(self):
        self.reader_stop.set()
        if self.ser is not None:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None
        self.console_frame.pack_forget()
        self.scan_frame.pack(fill="both", expand=True)
        self.scan_frame.start_scanning()

    def on_close(self):
        self.reader_stop.set()
        if self.ser is not None:
            try:
                self.ser.close()
            except Exception:
                pass
        self.destroy()


class ScanFrame(ttk.Frame):
    def __init__(self, master, on_connect):
        super().__init__(master, padding=20)
        self.on_connect = on_connect
        self._scanning = False

        title = ttk.Label(self, text="ESP-Claw Serial Control", font=("", 16, "bold"))
        title.pack(pady=(10, 4))
        subtitle = ttk.Label(self, text="Mencari device ESP32-S3 (ESP-Claw) di USB...")
        subtitle.pack(pady=(0, 16))

        self.status_var = tk.StringVar(value="Scanning...")
        self.status_label = ttk.Label(self, textvariable=self.status_var, foreground="#555")
        self.status_label.pack(pady=(0, 10))

        self.tree = ttk.Treeview(self, columns=("vidpid", "desc"), show="headings", height=6)
        self.tree.heading("vidpid", text="VID:PID")
        self.tree.heading("desc", text="Deskripsi")
        self.tree.column("vidpid", width=110)
        self.tree.column("desc", width=380)
        self.tree.pack(fill="x", pady=(0, 10))

        btn_row = ttk.Frame(self)
        btn_row.pack(fill="x")
        self.connect_btn = ttk.Button(btn_row, text="Hubungkan", command=self._connect_selected, state="disabled")
        self.connect_btn.pack(side="left")
        self.rescan_btn = ttk.Button(btn_row, text="Scan Ulang", command=self.start_scanning)
        self.rescan_btn.pack(side="left", padx=(8, 0))

        self.error_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.error_var, foreground="#b00020").pack(pady=(10, 0))

        self._auto_connected = False

    def start_scanning(self):
        self._auto_connected = False
        self.error_var.set("")
        self.status_var.set("Scanning...")
        self._scanning = True
        self._scan_once()

    def _scan_once(self):
        if not self._scanning:
            return
        matches, all_ports = find_candidate_ports()

        self.tree.delete(*self.tree.get_children())
        for p in all_ports:
            vidpid = f"{p.vid:04x}:{p.pid:04x}" if p.vid else "-"
            is_match = p.vid and (p.vid, p.pid) == CH340_VID_PID
            tag = "match" if is_match else ""
            self.tree.insert("", "end", iid=p.device, values=(vidpid, p.description), tags=(tag,))
        self.tree.tag_configure("match", foreground="#0a7d2c")

        self.connect_btn.config(state="normal" if all_ports else "disabled")

        if matches and not self._auto_connected:
            self._auto_connected = True
            self._scanning = False
            self.status_var.set(f"Ditemukan ESP-Claw di {matches[0].device}, menghubungkan...")
            self.after(400, lambda: self.on_connect(matches[0].device))
            return

        if not all_ports:
            self.status_var.set("Tidak ada serial port terdeteksi. Colok ESP-Claw via USB.")
        elif not matches:
            self.status_var.set("Port terdeteksi tapi bukan ESP-Claw (CH340). Pilih manual atau colok device yang benar.")

        self.after(SCAN_INTERVAL_MS, self._scan_once)

    def _connect_selected(self):
        sel = self.tree.selection()
        if not sel:
            self.error_var.set("Pilih port dari daftar dulu.")
            return
        self._scanning = False
        self.on_connect(sel[0])

    def show_error(self, msg):
        self.error_var.set(msg)
        self.status_var.set("Gagal konek.")
        self.start_scanning()


class ConsoleFrame(ttk.Frame):
    def __init__(self, master, on_disconnect):
        super().__init__(master, padding=10)
        self.master_app = master
        self.on_disconnect = on_disconnect

        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 6))
        self.title_var = tk.StringVar(value="ESP-Claw")
        ttk.Label(header, textvariable=self.title_var, font=("", 12, "bold")).pack(side="left")
        ttk.Button(header, text="Putuskan", command=self._disconnect_clicked).pack(side="right")

        quick_row = ttk.Frame(self)
        quick_row.pack(fill="x", pady=(0, 6))
        for label, cmd in [
            ("help", "help"),
            ("wifi status", "wifi --status"),
            ("wifi scan", "wifi --scan"),
            ("reset", None),
        ]:
            b = ttk.Button(quick_row, text=label, command=lambda c=cmd: self._quick(c))
            b.pack(side="left", padx=(0, 6))

        self.output = scrolledtext.ScrolledText(self, wrap="word", bg="#111", fg="#ddd", insertbackground="#ddd")
        self.output.pack(fill="both", expand=True)
        self.output.configure(state="disabled")

        entry_row = ttk.Frame(self)
        entry_row.pack(fill="x", pady=(6, 0))
        self.entry_var = tk.StringVar()
        entry = ttk.Entry(entry_row, textvariable=self.entry_var)
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<Return>", self._send_clicked)
        ttk.Button(entry_row, text="Kirim", command=self._send_clicked).pack(side="left", padx=(6, 0))
        self._entry_widget = entry

    def attach(self, port, baud):
        self.title_var.set(f"ESP-Claw — {port} @ {baud}")
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")
        self._entry_widget.focus_set()

    def append_output(self, text):
        self.output.configure(state="normal")
        self.output.insert("end", text)
        self.output.see("end")
        self.output.configure(state="disabled")

    def _send_clicked(self, event=None):
        text = self.entry_var.get()
        if not text:
            return
        self.entry_var.set("")
        self.append_output(f"\n> {text}\n")
        self.master_app.send_command(text)

    def _quick(self, cmd):
        if cmd is None:
            self.append_output("\n[Reset device]\n")
            if self.master_app.ser is not None:
                reset_device(self.master_app.ser)
            return
        self.append_output(f"\n> {cmd}\n")
        self.master_app.send_command(cmd)

    def _disconnect_clicked(self):
        self.on_disconnect()


def main(argv=None):
    app = EspClawApp()
    app.mainloop()


if __name__ == "__main__":
    main()
