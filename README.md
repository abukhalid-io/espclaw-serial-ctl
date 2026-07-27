# espclaw-serial-ctl

Control your **ESP-Claw** (ESP32-S3) device over a USB cable, from any computer you move to — no need to set it up again every time. Auto-detect supports the common USB-serial chips found on ESP32 boards (CH340/CH9102, CP210x, FTDI) as well as the native USB-Serial/JTAG built into ESP32-S2/S3/C3.

Two ways to use it:
- **GUI** (recommended): opens its own window, automatically scans & connects to ESP-Claw, then shows its console.
- **CLI**: for scripting/automation from a terminal.

## Installation

```bash
git clone https://github.com/abukhalid-io/espclaw-serial-ctl.git
cd espclaw-serial-ctl
pip install -r requirements.txt
```

Or install as commands (`espclawctl` / `espclawctl-gui`) on PATH:

```bash
pip install -e .
```

**Requirement**: Python 3.8+. The GUI uses **Tkinter** (lightweight, bundled with Python) — usually already present on Windows/Mac, on Linux you may need `sudo apt install python3-tk`. No extra system dependencies.

## Using the GUI

```bash
python -m espclaw_ctl.gui
# or, once `pip install -e .` has been run:
espclawctl-gui
```

GUI flow:
1. The window opens and automatically **scans USB** for an ESP-Claw device (CH340/CH9102, CP210x, FTDI, or native USB-Serial/JTAG).
2. Once found, it automatically **connects** and opens the dashboard: WiFi status and serial link cards.
3. **Console** tab — send manual commands, watch live serial output (like `console` in the CLI).
4. **WiFi** tab — scan nearby access points, click one, enter the password (if not an open network — there's a **Show/Hide** button to review what you typed), then **Connect** — sends `wifi --set --ssid ... --password ... --apply` to the device automatically.
5. **Web View** tab — a device IP field (defaults to `192.168.4.1`, auto-filled once the device connects to WiFi) with a button to open ESP-Claw's own web settings page in your system browser.
6. If no device is auto-detected, every available serial port is still listed so you can pick one manually — the last-used port and SSID are automatically pre-selected.
7. If the serial connection drops unexpectedly (device bumped, USB glitch), the GUI automatically retries reconnecting to the same port a few times before falling back to the device search screen.

### Creating a desktop shortcut

**Linux:**

```bash
./install_desktop_shortcut.sh
```

This creates an icon on the Desktop and registers the app in the app launcher, so you can just double-click to open it.

**Windows:**

Double-click `install_desktop_shortcut.bat` (or run `powershell -ExecutionPolicy Bypass -File install_desktop_shortcut.ps1`).

This creates an `ESP-Claw Serial Control.lnk` shortcut on the Desktop that launches the GUI via `pythonw` (no console window popping up behind it).

## Using the CLI

```bash
# List all serial ports, flag the ones that are likely ESP-Claw
python -m espclaw_ctl.cli list

# Interactive console right away (like minicom/screen)
python -m espclaw_ctl.cli console --reset

# Send a single command and see the result
python -m espclaw_ctl.cli cmd "help"

# WiFi status & scan
python -m espclaw_ctl.cli wifi-status
python -m espclaw_ctl.cli wifi-scan

# Reset the device, view the boot log
python -m espclaw_ctl.cli reset

# Set new WiFi credentials (replace <ssid> and <password> with your network's)
python -m espclaw_ctl.cli wifi-set --ssid "<ssid>" --password "<password>"
```

The port is auto-detected via known USB-serial chip VID:PID pairs (CH340/CH9102, CP210x, FTDI, native Espressif USB) plus a fallback match on the port description. If more than one matching serial device is found, or auto-detect fails, use `--port /dev/ttyACM0` (Linux/Mac) or `--port COM5` (Windows) to pick manually. If auto-detect fails and no `--port` is given, the CLI tries the last successfully used port (see the saved configuration section) before giving up.

## Saved configuration

For convenience when moving between computers, the CLI and GUI store the **last serial port** and **last WiFi SSID** used in `~/.espclaw_ctl/config.json`. This is only used for pre-selecting/falling back so you don't have to hunt for them manually every time you open the app.

## Security notes

This tool **never stores any credentials** (WiFi password, API keys, etc.) — only the port name and SSID (not secret) in `~/.espclaw_ctl/config.json` as described above. The WiFi SSID/password are always passed as runtime CLI arguments and never written to a file in this repo.

## Testing

```bash
python -m unittest discover -s tests -v
```

Current test coverage: parsing the device's WiFi status/scan output (`wifi_parse.py`), USB-serial chip VID:PID/description detection, console argument escaping, and config store round-trips.
