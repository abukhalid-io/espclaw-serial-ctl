let scanning = false;
let autoConnected = false;
let wifiBuffer = "";
let webIpFilled = false;
let apiReady = false;

window.addEventListener("pywebviewready", () => {
  apiReady = true;
  startScanning();
});

function startScanning() {
  document.getElementById("scan-error").textContent = "";
  document.getElementById("spinner").classList.remove("done");
  document.getElementById("scan-status").textContent = "Mencari device di USB...";
  scanning = true;
  autoConnected = false;
  scanTick();
}

async function scanTick() {
  if (!scanning || !apiReady) return;
  try {
    const res = await window.pywebview.api.scan_ports();
    renderPorts(res.ports);
    document.getElementById("connect-btn").disabled = res.ports.length === 0;

    if (res.match && !autoConnected) {
      autoConnected = true;
      scanning = false;
      document.getElementById("spinner").classList.add("done");
      document.getElementById("scan-status").textContent = `Ditemukan ESP-Claw di ${res.match} — menghubungkan...`;
      setTimeout(() => connectTo(res.match), 500);
      return;
    }

    document.getElementById("scan-status").textContent = res.ports.length === 0
      ? "Tidak ada serial port terdeteksi. Colok ESP-Claw via USB."
      : (res.match ? "" : "Port terdeteksi, bukan ESP-Claw. Pilih manual atau colok device yang benar.");
  } catch (e) {
    console.error(e);
  }
  if (scanning) setTimeout(scanTick, 900);
}

function renderPorts(ports) {
  const tbody = document.getElementById("port-list");
  tbody.innerHTML = "";
  window._ports = ports;
  ports.forEach((p) => {
    const tr = document.createElement("tr");
    tr.style.cursor = "pointer";
    tr.innerHTML = `<td>${p.device}</td><td>${p.vidpid}</td><td>${p.desc}</td>`;
    tr.onclick = () => {
      document.querySelectorAll("#port-list tr").forEach((r) => (r.style.background = ""));
      tr.style.background = "var(--accent-soft)";
      window._selectedPort = p.device;
    };
    tbody.appendChild(tr);
  });
}

function connectSelected() {
  const port = window._selectedPort || (window._ports && window._ports[0] && window._ports[0].device);
  if (!port) {
    document.getElementById("scan-error").textContent = "Pilih port dari daftar dulu.";
    return;
  }
  scanning = false;
  connectTo(port);
}

async function connectTo(port) {
  const res = await window.pywebview.api.connect(port);
  if (!res.ok) {
    document.getElementById("scan-error").textContent = `Gagal buka ${port}: ${res.error}`;
    startScanning();
    return;
  }
  document.getElementById("scan-view").style.display = "none";
  document.getElementById("dashboard-view").style.display = "flex";
  document.getElementById("dash-subtitle").textContent = `Terhubung · ${res.port} @ ${res.baud}`;
  document.getElementById("link-value").textContent = `${res.port.split("/").pop()} @ ${res.baud}`;
  const wifiEl = document.getElementById("wifi-value");
  wifiEl.textContent = "—";
  wifiEl.className = "stat-value";
  document.getElementById("console-output").textContent = "";
  wifiBuffer = "";
  webIpFilled = false;
  setTimeout(() => quick("wifi --status"), 3000);
}

window.onSerialData = function (text) {
  if (text === null) {
    appendOutput("\n[Koneksi terputus]\n");
    setTimeout(disconnectClicked, 800);
    return;
  }
  appendOutput(text);
  parseWifi(text);
};

function appendOutput(text) {
  const el = document.getElementById("console-output");
  el.textContent += text;
  el.scrollTop = el.scrollHeight;
}

function parseWifi(text) {
  wifiBuffer = (wifiBuffer + text).slice(-2000);
  if (!wifiBuffer.includes("sta_connected")) return;
  const kv = {};
  const re = /(\w+)=(\S+)/g;
  let m;
  while ((m = re.exec(wifiBuffer)) !== null) kv[m[1]] = m[2];

  const wifiEl = document.getElementById("wifi-value");
  if (kv.sta_connected === "1") {
    wifiEl.textContent = kv.saved_ssid || "?";
    wifiEl.className = "stat-value green";
    document.getElementById("dash-subtitle").textContent = `Terhubung · IP ${kv.sta_ip || "?"}`;
    if (!webIpFilled && kv.sta_ip) {
      document.getElementById("web-url-input").value = kv.sta_ip;
      webIpFilled = true;
    }
  } else if (kv.sta_connected === "0") {
    wifiEl.textContent = "Terputus";
    wifiEl.className = "stat-value red";
  }
}

function quick(cmd) {
  if (cmd === null) {
    appendOutput("\n[Reset device]\n");
    window.pywebview.api.reset();
    return;
  }
  appendOutput(`\n> ${cmd}\n`);
  window.pywebview.api.send_command(cmd);
}

function sendClicked() {
  const input = document.getElementById("cmd-input");
  const text = input.value;
  if (!text) return;
  input.value = "";
  quick(text);
}

function disconnectClicked() {
  window.pywebview.api.disconnect();
  document.getElementById("dashboard-view").style.display = "none";
  document.getElementById("scan-view").style.display = "flex";
  startScanning();
}

function showTab(name) {
  document.getElementById("tab-console").classList.toggle("active", name === "console");
  document.getElementById("tab-web").classList.toggle("active", name === "web");
  document.getElementById("panel-console").style.display = name === "console" ? "flex" : "none";
  document.getElementById("panel-web").style.display = name === "web" ? "flex" : "none";
  if (name === "web") loadWebUi();
}

function loadWebUi() {
  const ip = document.getElementById("web-url-input").value.trim();
  if (!ip) return;
  const url = ip.startsWith("http") ? ip : `http://${ip}/`;
  document.getElementById("web-frame").src = url;
}

function openWebWindow() {
  const ip = document.getElementById("web-url-input").value.trim();
  if (!ip) return;
  const url = ip.startsWith("http") ? ip : `http://${ip}/`;
  window.pywebview.api.open_web_window(url);
}
