# espclaw-serial-ctl

Kontrol device **ESP-Claw** (ESP32-S3, chip USB-serial CH340) lewat kabel USB, dari komputer manapun kamu pindah — tanpa perlu setup ulang tiap kali.

Ada dua cara pakai:
- **GUI** (rekomendasi): buka window sendiri, otomatis scan & konek ke ESP-Claw, lalu tampilkan console-nya.
- **CLI**: untuk scripting/automation dari terminal.

## Instalasi

```bash
git clone https://github.com/abukhalid-io/espclaw-serial-ctl.git
cd espclaw-serial-ctl
pip install -r requirements.txt
```

Atau install sebagai command (`espclawctl` / `espclawctl-gui`) di PATH:

```bash
pip install -e .        # cuma CLI
pip install -e .[gui]   # CLI + GUI (pywebview)
```

**Requirement**: Python 3.8+. GUI-nya pakai [pywebview](https://pywebview.flowrl.com/) (webview native, bukan browser terpisah), jadi butuh dependency sistem tambahan:

- **Linux**: `sudo apt install python3-gi gir1.2-webkit2-4.1` (WebKitGTK + PyGObject — biasanya sudah ada di banyak distro desktop).
- **Windows**: pakai WebView2 (Microsoft Edge runtime), biasanya sudah terpasang bawaan Windows 10/11.
- **Mac**: pakai WKWebView bawaan macOS, tidak perlu instalasi tambahan.

`pywebview` sendiri terpasang otomatis lewat `pip install -r requirements.txt` / `pip install -e .[gui]`.

## Pakai GUI

```bash
python -m espclaw_ctl.gui
# atau, kalau sudah `pip install -e .`:
espclawctl-gui
```

GUI-nya berupa window native (pakai pywebview), bukan buka di browser.

Alur GUI:
1. Window terbuka, otomatis **scan USB** mencari device ESP-Claw (CH340).
2. Begitu ketemu, otomatis **konek** dan masuk ke dashboard: kartu status WiFi & serial link.
3. Tab **Console** — kirim command manual, lihat live output serial (mirip `console` di CLI).
4. Tab **Tampilan Web** — menampilkan halaman web settings ESP-Claw asli (yang di-serve device di port 80) langsung di dalam app lewat iframe, dengan kolom IP manual (default `192.168.4.1`) dan tombol untuk buka di window terpisah.
5. Kalau device tidak terdeteksi, semua serial port yang ada tetap ditampilkan supaya bisa pilih manual.

### Bikin shortcut desktop (Linux)

```bash
./install_desktop_shortcut.sh
```

Ini akan bikin ikon di Desktop dan mendaftarkan aplikasi di app launcher, jadi tinggal klik dua kali untuk buka.

## Pakai CLI

```bash
# List semua serial port, tandai yang kemungkinan ESP-Claw
python -m espclaw_ctl.cli list

# Console interaktif langsung (mirip minicom/screen)
python -m espclaw_ctl.cli console --reset

# Kirim satu command dan lihat hasilnya
python -m espclaw_ctl.cli cmd "help"

# Status & scan WiFi
python -m espclaw_ctl.cli wifi-status
python -m espclaw_ctl.cli wifi-scan

# Reset device, lihat boot log
python -m espclaw_ctl.cli reset

# Set WiFi baru (ganti <ssid> dan <password> sesuai jaringan kamu)
python -m espclaw_ctl.cli wifi-set --ssid "<ssid>" --password "<password>"
```

Port di-auto-detect lewat VID:PID CH340 (`1a86:55d3`). Kalau ada lebih dari satu device serial yang cocok, atau auto-detect gagal, pakai `--port /dev/ttyACM0` (Linux/Mac) atau `--port COM5` (Windows) secara manual.

## Catatan keamanan

Tool ini **tidak menyimpan kredensial apapun** (WiFi password, API key, dsb). SSID/password WiFi selalu jadi argumen CLI runtime dan tidak pernah ditulis ke file di repo ini.
