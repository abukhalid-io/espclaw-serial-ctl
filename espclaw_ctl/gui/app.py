import queue
import threading
import tkinter as tk
import webbrowser
from tkinter import ttk

import serial

from espclaw_ctl import config_store
from espclaw_ctl.cli import (
    DEFAULT_BAUD,
    find_candidate_ports,
    looks_like_esp_port,
    quote_console_arg,
    reset_device,
)
from espclaw_ctl.gui.theme import Theme
from espclaw_ctl.gui.widgets import Card, LobsterLogo, PillButton, Spinner, StatusDot
from espclaw_ctl.gui.wifi_parse import (
    parse_wifi_scan,
    parse_wifi_scan_failure,
    parse_wifi_set_result,
    parse_wifi_status,
    signal_bars,
)

MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_INTERVAL_MS = 1500


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("ESP-Claw Control")
        self.root.geometry("900x700")
        self.root.minsize(640, 520)
        self.root.configure(bg=Theme.BG)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.ser = None
        self.reader_thread = None
        self.reader_stop = threading.Event()
        self.msg_queue = queue.Queue()

        self._scanning = False
        self._auto_connected = False

        self._last_port = None
        self._disconnect_requested = False
        self._reconnect_attempts = 0
        self._pw_visible = False

        self.wifi_status_buffer = ""
        self.wifi_scan_buffer = ""
        self.wifi_scanning = False
        self.ap_results = []
        self.selected_ap = None
        self.web_ip_filled = False

        self.wifi_set_buffer = ""
        self.wifi_set_pending = None
        self._wifi_set_gen = 0
        self._scan_retries_left = 0

        self._setup_style()
        self._build_scan_view()
        self._build_dashboard_view()

        self.show_scan_view()
        self.start_scanning()
        self.root.after(50, self._poll_queue)

    def run(self):
        self.root.mainloop()

    def _setup_style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Treeview", background=Theme.CARD, fieldbackground=Theme.CARD,
                         foreground=Theme.TEXT, borderwidth=0, rowheight=26, font=Theme.FONT)
        style.configure("Treeview.Heading", background=Theme.BG, foreground=Theme.DIM,
                         font=Theme.FONT_BOLD, borderwidth=0)
        style.map("Treeview", background=[("selected", Theme.ACCENT_SOFT)],
                  foreground=[("selected", Theme.TEXT)])

    # ---------- scan view ----------

    def _build_scan_view(self):
        self.scan_frame = tk.Frame(self.root, bg=Theme.BG)
        wrap = tk.Frame(self.scan_frame, bg=Theme.BG)
        wrap.place(relx=0.5, rely=0.5, anchor="center")

        title_row = tk.Frame(wrap, bg=Theme.BG)
        title_row.pack(pady=(0, 2))
        LobsterLogo(title_row, size=40).pack(side="left", padx=(0, 8))
        tk.Label(title_row, text="ESP-Claw", font=Theme.FONT_TITLE, bg=Theme.BG,
                 fg=Theme.TEXT).pack(side="left")
        tk.Label(wrap, text="Find and connect your device", font=Theme.FONT, bg=Theme.BG,
                 fg=Theme.DIM).pack(pady=(0, 16))

        self.spinner = Spinner(wrap)
        self.spinner.pack(pady=(0, 12))

        self.scan_status_label = tk.Label(wrap, text="Searching for device on USB...", font=Theme.FONT,
                                           bg=Theme.BG, fg=Theme.TEXT)
        self.scan_status_label.pack(pady=(0, 16))

        self.port_list_frame = tk.Frame(wrap, bg=Theme.BG, width=520)
        self.port_list_frame.pack(fill="x", pady=(0, 16))
        self.port_list_frame.pack_propagate(False)

        btn_row = tk.Frame(wrap, bg=Theme.BG)
        btn_row.pack()
        PillButton(btn_row, "Rescan", command=self.start_scanning, width=140,
                   bg=Theme.CARD, fg=Theme.TEXT, outline=True).pack(side="left")

        self.scan_error_label = tk.Label(wrap, text="", font=Theme.FONT, bg=Theme.BG, fg=Theme.RED)
        self.scan_error_label.pack(pady=(10, 0))

        self.scan_hint_label = tk.Label(
            wrap, text="Click a device to connect instantly — last used port/SSID is pre-highlighted.",
            font=Theme.FONT, bg=Theme.BG, fg=Theme.DIM)
        self.scan_hint_label.pack(pady=(4, 0))

    def start_scanning(self):
        self.scan_error_label.configure(text="")
        self.spinner.start()
        self.scan_status_label.configure(text="Searching for device on USB...")
        self._scanning = True
        self._auto_connected = False
        self._scan_tick()

    def _scan_tick(self):
        if not self._scanning:
            return
        matches, all_ports = find_candidate_ports()
        self._render_ports(all_ports)

        if matches and not self._auto_connected:
            self._auto_connected = True
            self._scanning = False
            self.spinner.stop()
            self.scan_status_label.configure(
                text=f"Found ESP-Claw at {matches[0].device} — connecting...")
            self.root.after(500, lambda: self.connect_to(matches[0].device))
            return

        if not all_ports:
            self.scan_status_label.configure(text="No serial ports detected. Plug in ESP-Claw via USB.")
        elif not matches:
            self.scan_status_label.configure(
                text="Port detected, but not ESP-Claw. Pick manually or plug in the right device.")
        else:
            self.scan_status_label.configure(text="")

        self.root.after(900, self._scan_tick)

    def _render_ports(self, ports):
        for child in self.port_list_frame.winfo_children():
            child.destroy()

        last_port = config_store.load().get("last_port")
        for p in ports:
            is_match = looks_like_esp_port(p)
            is_recent = not is_match and p.device == last_port
            self._build_port_row(self.port_list_frame, p, is_match, is_recent)

    def _build_port_row(self, parent, port, is_match, is_recent):
        border_color = Theme.ACCENT if (is_match or is_recent) else Theme.BORDER
        row_bg = Theme.ACCENT_SOFT if is_match else Theme.CARD

        row = tk.Frame(parent, bg=row_bg, highlightbackground=border_color, highlightthickness=1,
                        cursor="hand2")
        row.pack(fill="x", pady=(0, 8))
        inner = tk.Frame(row, bg=row_bg)
        inner.pack(fill="x", padx=14, pady=11)

        icon_bg = Theme.ACCENT if is_match else Theme.BORDER
        icon_fg = "#FFFFFF" if is_match else Theme.DIM
        icon = tk.Label(inner, text="\U0001F50C" if is_match else "\U0001F4E1", font=("Segoe UI", 13),
                         bg=icon_bg, fg=icon_fg, width=2, height=1)
        icon.pack(side="left", padx=(0, 12))

        info = tk.Frame(inner, bg=row_bg)
        info.pack(side="left", fill="x", expand=True)
        primary_row = tk.Frame(info, bg=row_bg)
        primary_row.pack(anchor="w")
        tk.Label(primary_row, text=port.device, font=("Segoe UI", 11, "bold"), bg=row_bg,
                 fg=Theme.TEXT).pack(side="left")
        if is_match:
            tk.Label(primary_row, text=" ESP-CLAW ", font=("Segoe UI", 8, "bold"), bg=Theme.CARD,
                     fg=Theme.ACCENT, highlightbackground=Theme.ACCENT, highlightthickness=1).pack(
                side="left", padx=(8, 0))
        elif is_recent:
            tk.Label(primary_row, text=" last used ", font=("Segoe UI", 8, "bold"), bg=Theme.CARD,
                     fg=Theme.DIM, highlightbackground=Theme.BORDER, highlightthickness=1).pack(
                side="left", padx=(8, 0))

        vidpid = f"{port.vid:04x}:{port.pid:04x}" if port.vid else "-"
        desc = port.description or "Unknown device"
        tk.Label(info, text=f"{vidpid} · {desc}", font=("Consolas", 9), bg=row_bg,
                 fg=Theme.DIM).pack(anchor="w", pady=(2, 0))

        chevron = tk.Label(inner, text="›", font=("Segoe UI", 14), bg=row_bg,
                            fg=Theme.ACCENT if is_match else Theme.DIM)
        chevron.pack(side="right")

        def on_click(_event=None):
            self._scanning = False
            self.connect_to(port.device)

        def on_enter(_event=None):
            row.configure(highlightbackground=Theme.ACCENT)

        def on_leave(_event=None):
            row.configure(highlightbackground=border_color)

        self._bind_recursive(row, "<Button-1>", on_click)
        self._bind_recursive(row, "<Enter>", on_enter)
        self._bind_recursive(row, "<Leave>", on_leave)

    def _bind_recursive(self, widget, event, handler):
        widget.bind(event, handler)
        for child in widget.winfo_children():
            self._bind_recursive(child, event, handler)

    # ---------- dashboard view ----------

    def _build_dashboard_view(self):
        self.dash_frame = tk.Frame(self.root, bg=Theme.BG)
        outer = tk.Frame(self.dash_frame, bg=Theme.BG)
        outer.pack(fill="both", expand=True, padx=24, pady=20)

        hero = Card(outer)
        hero.pack(fill="x", pady=(0, 14))
        hero_row = tk.Frame(hero.body, bg=Theme.CARD)
        hero_row.pack(fill="x")
        left = tk.Frame(hero_row, bg=Theme.CARD)
        left.pack(side="left", fill="x", expand=True)
        title_row = tk.Frame(left, bg=Theme.CARD)
        title_row.pack(anchor="w")
        LobsterLogo(title_row, size=24).pack(side="left", padx=(0, 6))
        tk.Label(title_row, text="ESP-Claw", font=("Segoe UI", 13, "bold"), bg=Theme.CARD,
                 fg=Theme.TEXT).pack(side="left")
        status_row = tk.Frame(left, bg=Theme.CARD)
        status_row.pack(anchor="w", pady=(4, 0))
        self.status_dot = StatusDot(status_row)
        self.status_dot.pack(side="left", padx=(0, 6))
        self.dash_subtitle = tk.Label(status_row, text="", font=Theme.FONT, bg=Theme.CARD, fg=Theme.DIM)
        self.dash_subtitle.pack(side="left")
        PillButton(hero_row, "Disconnect", command=self.disconnect_clicked, width=120, height=34,
                   bg=Theme.CARD, fg=Theme.TEXT, outline=True).pack(side="right")

        stats_row = tk.Frame(outer, bg=Theme.BG)
        stats_row.pack(fill="x", pady=(0, 14))
        wifi_card = Card(stats_row)
        wifi_card.pack(side="left", fill="both", expand=True, padx=(0, 7))
        tk.Label(wifi_card.body, text="\U0001F4F6 WIFI", font=Theme.FONT_BOLD, bg=Theme.CARD,
                 fg=Theme.DIM).pack(anchor="w")
        self.wifi_value_label = tk.Label(wifi_card.body, text="—", font=("Segoe UI", 14, "bold"),
                                          bg=Theme.CARD, fg=Theme.TEXT)
        self.wifi_value_label.pack(anchor="w", pady=(4, 0))

        link_card = Card(stats_row)
        link_card.pack(side="left", fill="both", expand=True, padx=(7, 0))
        tk.Label(link_card.body, text="\U0001F50C SERIAL LINK", font=Theme.FONT_BOLD, bg=Theme.CARD,
                 fg=Theme.DIM).pack(anchor="w")
        self.link_value_label = tk.Label(link_card.body, text="—", font=("Segoe UI", 14, "bold"),
                                          bg=Theme.CARD, fg=Theme.TEXT)
        self.link_value_label.pack(anchor="w", pady=(4, 0))

        tab_row = tk.Frame(outer, bg=Theme.BG)
        tab_row.pack(fill="x")
        self.tab_buttons = {}
        for key, label in (("console", "Console"), ("wifi", "WiFi"), ("web", "Web View")):
            btn = tk.Label(tab_row, text=label, font=Theme.FONT_BOLD, bg=Theme.BG, fg=Theme.DIM,
                           padx=16, pady=8, cursor="hand2")
            btn.pack(side="left")
            btn.bind("<Button-1>", lambda e, k=key: self.show_tab(k))
            self.tab_buttons[key] = btn

        self.panel_container = tk.Frame(outer, bg=Theme.CARD, highlightbackground=Theme.BORDER,
                                         highlightthickness=1)
        self.panel_container.pack(fill="both", expand=True)

        self._build_console_panel()
        self._build_wifi_panel()
        self._build_web_panel()
        self.show_tab("console")

    def _make_soft_btn(self, master, text, command):
        return PillButton(master, text, command=command, width=118, height=32,
                           bg=Theme.ACCENT_SOFT, fg=Theme.ACCENT, font=("Segoe UI", 9, "bold"))

    def _build_console_panel(self):
        self.console_panel = tk.Frame(self.panel_container, bg=Theme.CARD)
        pad = tk.Frame(self.console_panel, bg=Theme.CARD)
        pad.pack(fill="both", expand=True, padx=16, pady=16)

        quick_row = tk.Frame(pad, bg=Theme.CARD)
        quick_row.pack(fill="x", pady=(0, 10))
        self._make_soft_btn(quick_row, "Help", lambda: self.quick("help")).pack(side="left", padx=(0, 8))
        self._make_soft_btn(quick_row, "WiFi Status", lambda: self.quick("wifi --status")).pack(
            side="left", padx=(0, 8))
        self._make_soft_btn(quick_row, "WiFi Scan", lambda: self.quick("wifi --scan")).pack(
            side="left", padx=(0, 8))
        self._make_soft_btn(quick_row, "Reset", self.reset_clicked).pack(side="left")

        text_frame = tk.Frame(pad, bg=Theme.CARD, highlightbackground=Theme.BORDER, highlightthickness=1)
        text_frame.pack(fill="both", expand=True, pady=(0, 10))
        self.console_text = tk.Text(text_frame, wrap="word", font=Theme.FONT_MONO, bg=Theme.CONSOLE_BG,
                                     fg=Theme.CONSOLE_TEXT, insertbackground=Theme.CONSOLE_TEXT,
                                     selectbackground=Theme.CONSOLE_TEXT, selectforeground=Theme.CONSOLE_BG,
                                     borderwidth=0, state="disabled")
        scrollbar = ttk.Scrollbar(text_frame, command=self.console_text.yview)
        self.console_text.configure(yscrollcommand=scrollbar.set)
        self.console_text.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        scrollbar.pack(side="right", fill="y")

        input_row = tk.Frame(pad, bg=Theme.CARD)
        input_row.pack(fill="x")
        self.cmd_entry = tk.Entry(input_row, font=Theme.FONT_MONO, bg=Theme.BG, fg=Theme.TEXT,
                                   relief="flat", highlightbackground=Theme.BORDER, highlightthickness=1)
        self.cmd_entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 8))
        self.cmd_entry.bind("<Return>", lambda e: self.send_clicked())
        PillButton(input_row, "Send", command=self.send_clicked, width=90, height=36).pack(side="left")

    def _build_wifi_panel(self):
        self.wifi_panel = tk.Frame(self.panel_container, bg=Theme.CARD)
        pad = tk.Frame(self.wifi_panel, bg=Theme.CARD)
        pad.pack(fill="both", expand=True, padx=16, pady=16)

        top_row = tk.Frame(pad, bg=Theme.CARD)
        top_row.pack(fill="x", pady=(0, 10))
        self.wifi_scan_btn = PillButton(top_row, "\U0001F50D Scan WiFi", command=self.scan_wifi,
                                         width=140, height=34, bg=Theme.ACCENT_SOFT, fg=Theme.ACCENT,
                                         font=("Segoe UI", 9, "bold"))
        self.wifi_scan_btn.pack(side="left", padx=(0, 10))
        self.wifi_scan_status = tk.Label(top_row, text="", font=Theme.FONT, bg=Theme.CARD, fg=Theme.DIM)
        self.wifi_scan_status.pack(side="left")

        ap_frame = tk.Frame(pad, bg=Theme.CARD, highlightbackground=Theme.BORDER, highlightthickness=1)
        ap_frame.pack(fill="both", expand=True, pady=(0, 10))
        columns = ("ssid", "signal", "security")
        self.ap_tree = ttk.Treeview(ap_frame, columns=columns, show="headings", height=8,
                                     selectmode="browse")
        self.ap_tree.heading("ssid", text="SSID")
        self.ap_tree.heading("signal", text="SIGNAL")
        self.ap_tree.heading("security", text="SECURITY")
        self.ap_tree.column("ssid", width=220)
        self.ap_tree.column("signal", width=90)
        self.ap_tree.column("security", width=120)
        self.ap_tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.ap_tree.bind("<<TreeviewSelect>>", self._on_ap_select)

        self.wifi_form = tk.Frame(pad, bg=Theme.CARD)
        self.wifi_form_title = tk.Label(self.wifi_form, text="", font=Theme.FONT_BOLD, bg=Theme.CARD,
                                         fg=Theme.TEXT)
        self.wifi_form_title.pack(anchor="w", pady=(0, 8))
        form_row = tk.Frame(self.wifi_form, bg=Theme.CARD)
        form_row.pack(fill="x")
        self.wifi_password_entry = tk.Entry(form_row, font=Theme.FONT, bg=Theme.BG, fg=Theme.TEXT,
                                             show="*", relief="flat", highlightbackground=Theme.BORDER,
                                             highlightthickness=1)
        self.wifi_password_entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 8))
        self.wifi_password_entry.bind("<Return>", lambda e: self.connect_wifi())
        self.pw_toggle_btn = tk.Label(form_row, text="Show", font=Theme.FONT, bg=Theme.CARD,
                                       fg=Theme.DIM, cursor="hand2", padx=6)
        self.pw_toggle_btn.pack(side="left", padx=(0, 8))
        self.pw_toggle_btn.bind("<Button-1>", lambda e: self._toggle_password_visibility())
        PillButton(form_row, "Connect", command=self.connect_wifi, width=90, height=36).pack(
            side="left", padx=(0, 8))
        PillButton(form_row, "Cancel", command=self.cancel_wifi_form, width=90, height=36,
                   bg=Theme.CARD, fg=Theme.TEXT, outline=True).pack(side="left")
        self.wifi_connect_status = tk.Label(self.wifi_form, text="", font=Theme.FONT, bg=Theme.CARD,
                                             fg=Theme.DIM)
        self.wifi_connect_status.pack(anchor="w", pady=(6, 0))

    def _build_web_panel(self):
        self.web_panel = tk.Frame(self.panel_container, bg=Theme.CARD)
        pad = tk.Frame(self.web_panel, bg=Theme.CARD)
        pad.pack(fill="both", expand=True, padx=16, pady=16)

        tk.Label(pad, text="Open the ESP-Claw web settings page in your system browser:",
                 font=Theme.FONT, bg=Theme.CARD, fg=Theme.TEXT).pack(anchor="w", pady=(0, 10))

        row = tk.Frame(pad, bg=Theme.CARD)
        row.pack(fill="x")
        self.web_ip_entry = tk.Entry(row, font=Theme.FONT, bg=Theme.BG, fg=Theme.TEXT, relief="flat",
                                      highlightbackground=Theme.BORDER, highlightthickness=1)
        self.web_ip_entry.insert(0, "192.168.4.1")
        self.web_ip_entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 8))
        PillButton(row, "Open in Browser", command=self.open_web_ui, width=160, height=36).pack(side="left")

        tk.Label(pad, text=("Default Access Point IP: 192.168.4.1. Once connected to WiFi, "
                             "the IP fills in automatically from the device's WiFi status."),
                 font=Theme.FONT, bg=Theme.CARD, fg=Theme.DIM, justify="left", wraplength=520).pack(
            anchor="w", pady=(14, 0))

    def open_web_ui(self):
        ip = self.web_ip_entry.get().strip()
        if not ip:
            return
        url = ip if ip.startswith("http") else f"http://{ip}/"
        webbrowser.open(url)

    def show_tab(self, key):
        for k, btn in self.tab_buttons.items():
            btn.configure(fg=Theme.ACCENT if k == key else Theme.DIM)
        self.console_panel.pack_forget()
        self.wifi_panel.pack_forget()
        self.web_panel.pack_forget()
        {"console": self.console_panel, "wifi": self.wifi_panel, "web": self.web_panel}[key].pack(
            fill="both", expand=True)

    def show_scan_view(self):
        self.dash_frame.pack_forget()
        self.scan_frame.pack(fill="both", expand=True)

    def show_dashboard_view(self):
        self.scan_frame.pack_forget()
        self.dash_frame.pack(fill="both", expand=True)

    # ---------- connection ----------

    def connect_to(self, port, baud=DEFAULT_BAUD):
        if self.ser is not None:
            self._close_serial()
        self._disconnect_requested = False
        self._reconnect_attempts = 0
        try:
            self.ser = serial.Serial(port, baud, timeout=0.2)
        except serial.SerialException as e:
            self.scan_error_label.configure(text=f"Failed to open {port}: {e}")
            self.start_scanning()
            return
        self.reader_stop.clear()
        self.reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.reader_thread.start()
        try:
            reset_device(self.ser)
        except (serial.SerialException, OSError) as e:
            self._close_serial()
            self.scan_error_label.configure(text=f"Device disconnected while connecting to {port}: {e}")
            self.start_scanning()
            return

        self._last_port = port
        config_store.save(last_port=port)
        self.dash_subtitle.configure(text=f"Connected · {port} @ {baud}")
        self.link_value_label.configure(text=f"{port.split('/')[-1]} @ {baud}")
        self.wifi_value_label.configure(text="—", fg=Theme.TEXT)
        self._clear_console()
        self.wifi_status_buffer = ""
        self.web_ip_filled = False
        self.show_dashboard_view()
        self.root.after(3000, lambda: self.quick("wifi --status"))

    def disconnect_clicked(self):
        self._disconnect_requested = True
        self._close_serial()
        self.show_scan_view()
        self.start_scanning()

    def _close_serial(self):
        self.reader_stop.set()
        if self.ser is not None:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None

    def _on_close(self):
        self._close_serial()
        self.root.destroy()

    # ---------- serial I/O ----------

    def _read_loop(self):
        while not self.reader_stop.is_set():
            ser = self.ser
            if ser is None:
                return
            try:
                chunk = ser.read(1024)
            except (serial.SerialException, OSError):
                self._close_serial()
                self.msg_queue.put(None)
                return
            if chunk:
                self.msg_queue.put(chunk.decode(errors="replace"))

    def _poll_queue(self):
        try:
            while True:
                item = self.msg_queue.get_nowait()
                if item is None:
                    self._append_console("\n[Connection lost]\n")
                    self.root.after(800, self._handle_unexpected_disconnect)
                else:
                    self._append_console(item)
                    self._on_serial_text(item)
        except queue.Empty:
            pass
        self.root.after(50, self._poll_queue)

    # ---------- reconnect ----------

    def _handle_unexpected_disconnect(self):
        if self._disconnect_requested or not self._last_port:
            self.disconnect_clicked()
            return
        self._reconnect_attempts = 0
        self._attempt_reconnect()

    def _attempt_reconnect(self):
        if self._disconnect_requested:
            return
        self._reconnect_attempts += 1
        port = self._last_port
        self._append_console(
            f"\n[Reconnecting to {port}... attempt {self._reconnect_attempts}/{MAX_RECONNECT_ATTEMPTS}]\n")
        self.dash_subtitle.configure(text=f"Reconnecting to {port}...")
        try:
            self.ser = serial.Serial(port, DEFAULT_BAUD, timeout=0.2)
        except serial.SerialException:
            self.ser = None

        if self.ser is not None:
            self.reader_stop.clear()
            self.reader_thread = threading.Thread(target=self._read_loop, daemon=True)
            self.reader_thread.start()
            self._reconnect_attempts = 0
            self._append_console("[Reconnected]\n")
            self.dash_subtitle.configure(text=f"Connected · {port} @ {DEFAULT_BAUD}")
            self.root.after(1000, lambda: self.quick("wifi --status"))
            return

        if self._reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
            self._append_console("[Reconnect failed, returning to device search]\n")
            self.root.after(500, self.disconnect_clicked)
        else:
            self.root.after(RECONNECT_INTERVAL_MS, self._attempt_reconnect)

    def _write_serial(self, text):
        ser = self.ser
        if ser is None:
            return
        try:
            ser.write(text.encode() + b"\r\n")
        except (serial.SerialException, OSError, TypeError):
            self._close_serial()
            self.msg_queue.put(None)

    def _on_serial_text(self, text):
        self.wifi_status_buffer = (self.wifi_status_buffer + text)[-2000:]
        status = parse_wifi_status(self.wifi_status_buffer)
        if status:
            self._apply_wifi_status(status)

        if self.wifi_scanning:
            self.wifi_scan_buffer += text
            failure = parse_wifi_scan_failure(self.wifi_scan_buffer)
            if failure is not None:
                self._handle_wifi_scan_failure(failure)
                return
            aps = parse_wifi_scan(self.wifi_scan_buffer)
            if aps is not None:
                self.wifi_scanning = False
                self.wifi_scan_btn.set_enabled(True)
                self.ap_results = aps
                self.wifi_scan_status.configure(
                    text=f"{len(aps)} network(s) found." if aps else "No networks found.")
                self._render_ap_list()

        if self.wifi_set_pending is not None:
            self.wifi_set_buffer += text
            result = parse_wifi_set_result(self.wifi_set_buffer)
            if result is not None:
                self._handle_wifi_set_result(result)

    def _apply_wifi_status(self, kv):
        connected = kv.get("sta_connected")
        if connected == "1":
            self.wifi_value_label.configure(text=kv.get("saved_ssid", "?"), fg=Theme.GREEN)
            ip = kv.get("sta_ip")
            if ip:
                self.dash_subtitle.configure(text=f"Connected · IP {ip}")
                if not self.web_ip_filled:
                    self.web_ip_entry.delete(0, "end")
                    self.web_ip_entry.insert(0, ip)
                    self.web_ip_filled = True
        elif connected == "0":
            self.wifi_value_label.configure(text="Disconnected", fg=Theme.RED)

    # ---------- console panel actions ----------

    def _append_console(self, text):
        self.console_text.configure(state="normal")
        self.console_text.insert("end", text)
        self.console_text.see("end")
        self.console_text.configure(state="disabled")

    def _clear_console(self):
        self.console_text.configure(state="normal")
        self.console_text.delete("1.0", "end")
        self.console_text.configure(state="disabled")

    def quick(self, cmd):
        self._append_console(f"\n> {cmd}\n")
        self._write_serial(cmd)

    def reset_clicked(self):
        self._append_console("\n[Resetting device]\n")
        ser = self.ser
        if ser is not None:
            try:
                reset_device(ser)
            except (serial.SerialException, OSError, TypeError):
                self._close_serial()
                self.msg_queue.put(None)

    def send_clicked(self):
        text = self.cmd_entry.get()
        if not text:
            return
        self.cmd_entry.delete(0, "end")
        self.quick(text)

    # ---------- wifi panel actions ----------

    def scan_wifi(self):
        self.ap_results = []
        self.selected_ap = None
        self.wifi_scan_buffer = ""
        self.wifi_scanning = True
        # Scanning switches the radio to STA+AP mode too, so it can hit the
        # same ESP_ERR_WIFI_STATE busy race as wifi --set --apply whenever
        # the device's own background STA reconnect loop is mid-attempt.
        self._scan_retries_left = 8
        self.wifi_form.pack_forget()
        self.wifi_scan_btn.set_enabled(False)
        self.wifi_scan_status.configure(text="Scanning... (~5 seconds)")
        self._render_ap_list()
        self.quick("wifi --scan")
        self.root.after(20000, self._scan_wifi_timeout)

    def _handle_wifi_scan_failure(self, err):
        if err == "ESP_ERR_WIFI_STATE" and self._scan_retries_left > 0:
            self._scan_retries_left -= 1
            self.wifi_scan_buffer = ""
            self.wifi_scan_status.configure(text="Device busy reconnecting, retrying scan...")
            self.root.after(1500, self._retry_scan)
            return
        self.wifi_scanning = False
        self.wifi_scan_btn.set_enabled(True)
        self.wifi_scan_status.configure(text=f"Scan failed ({err}). Try again.")

    def _retry_scan(self):
        if not self.wifi_scanning:
            return
        self.wifi_scan_buffer = ""
        self._write_serial("wifi --scan")

    def _scan_wifi_timeout(self):
        if self.wifi_scanning:
            self.wifi_scanning = False
            self.wifi_scan_btn.set_enabled(True)
            self.wifi_scan_status.configure(
                text="" if self.ap_results else "No networks found, try scanning again.")

    def _render_ap_list(self):
        self.ap_tree.delete(*self.ap_tree.get_children())
        self._ap_by_iid = {}
        for i, ap in enumerate(self.ap_results):
            security = "Open" if ap["auth"] == "open" else f"\U0001F512 {ap['auth']}"
            bars = signal_bars(ap["rssi"])
            iid = f"ap{i}"
            self.ap_tree.insert("", "end", iid=iid, values=(ap["ssid"], f"{ap['rssi']} dBm ({bars}/4)", security))
            self._ap_by_iid[iid] = ap
        # Note: no auto-selecting the last-used SSID here — with open
        # networks now connecting immediately on selection (see
        # _on_ap_select), programmatically pre-selecting a row would
        # silently trigger a reconnect attempt with no user action.

    def _on_ap_select(self, _event):
        sel = self.ap_tree.selection()
        if not sel:
            return
        ap = self._ap_by_iid.get(sel[0])
        if not ap:
            return
        self.selected_ap = ap

        if ap["auth"] == "open":
            # No password needed — connect right away, no popup.
            self.wifi_form.pack_forget()
            self.wifi_password_entry.delete(0, "end")
            self.wifi_scan_status.configure(text=f"Connecting to {ap['ssid']}...")
            self.connect_wifi()
            return

        self.wifi_form_title.configure(text=f"Connect to {ap['ssid']}")
        self.wifi_password_entry.delete(0, "end")
        self._pw_visible = False
        self.wifi_password_entry.configure(show="*")
        self.pw_toggle_btn.configure(text="Show")
        self.wifi_connect_status.configure(text="")
        self.wifi_form.pack(fill="x", pady=(4, 0))

    def cancel_wifi_form(self):
        self.selected_ap = None
        self.wifi_form.pack_forget()
        for iid in self.ap_tree.selection():
            self.ap_tree.selection_remove(iid)

    def _toggle_password_visibility(self):
        self._pw_visible = not self._pw_visible
        self.wifi_password_entry.configure(show="" if self._pw_visible else "*")
        self.pw_toggle_btn.configure(text="Hide" if self._pw_visible else "Show")

    def connect_wifi(self):
        if not self.selected_ap:
            return
        ssid = self.selected_ap["ssid"]
        password = self.wifi_password_entry.get()
        command = (f"wifi --set --ssid {quote_console_arg(ssid)} "
                   f"--password {quote_console_arg(password)} --apply")

        self._wifi_set_gen += 1
        gen = self._wifi_set_gen
        # Device rejects --set --apply with ESP_ERR_WIFI_STATE ("sta is
        # connecting, cannot set config") whenever its own background STA
        # reconnect loop is mid-attempt at that instant. That loop retries
        # roughly every 10s and each attempt fails fast, so most of that
        # window is actually idle — retrying a few times a couple seconds
        # apart reliably lands in that idle gap instead of silently no-op'ing.
        self.wifi_set_pending = {"ssid": ssid, "command": command, "retries_left": 8, "gen": gen}
        self.wifi_set_buffer = ""

        config_store.save(last_ssid=ssid)
        self.wifi_connect_status.configure(text=f"Applying Wi-Fi config for {ssid}...")
        self._append_console(f"\n> wifi --set --ssid {quote_console_arg(ssid)} --password **** --apply\n")
        self._write_serial(command)

    def _retry_wifi_set(self, gen):
        pending = self.wifi_set_pending
        if pending is None or pending["gen"] != gen:
            return
        self.wifi_set_buffer = ""
        self._write_serial(pending["command"])

    def _handle_wifi_set_result(self, result):
        pending = self.wifi_set_pending
        if pending is None:
            return

        if result["ok"]:
            self.wifi_set_pending = None
            self.wifi_connect_status.configure(text=f"Applied — connecting to {pending['ssid']}...")
            self.root.after(4000, lambda: self.quick("wifi --status"))
            return

        err = result["err"] or "unknown_error"
        if err == "ESP_ERR_WIFI_STATE" and pending["retries_left"] > 0:
            pending["retries_left"] -= 1
            gen = pending["gen"]
            # Clear now, not just inside _retry_wifi_set: otherwise any
            # further chatter arriving during the 1.5s wait keeps matching
            # this same stale "ok=0" line and re-triggers this branch on
            # every poll tick, burning through retries in a tight loop.
            self.wifi_set_buffer = ""
            self.wifi_connect_status.configure(text="Device busy reconnecting, retrying...")
            self.root.after(1500, lambda: self._retry_wifi_set(gen))
            return

        self.wifi_set_pending = None
        self.wifi_connect_status.configure(
            text=f"Failed to apply Wi-Fi config ({err}). Try Connect again.")


def main(argv=None):
    App().run()


if __name__ == "__main__":
    main()
