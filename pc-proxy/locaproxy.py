#!/usr/bin/env python3
"""
LocaProxy - appear to be anywhere in the world, from your own PC.

Pick a country, click Connect. LocaProxy starts a local proxy on your PC
(127.0.0.1:8080 by default) and sends your traffic out through either:

  * the Tor network, using only exit relays in the country you picked
    (free, and Tor is downloaded automatically on first use), or
  * your own proxy servers (SOCKS5 / HTTP), for example ones you rent from
    a provider or run on a cloud VPS in another country (faster).

It can also switch your whole PC's proxy setting on and off for you, so
browsers and most apps use it with no extra setup.

Only the Python standard library is used. Run it with:
    python locaproxy.py              (window)
    python locaproxy.py --cli -l tor:de   (no window)
"""

from __future__ import annotations

import argparse
import atexit
import base64
import hashlib
import ipaddress
import json
import os
import platform
import queue
import re
import shutil
import socket
import socketserver
import struct
import subprocess
import sys
import tarfile
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

APP_NAME = "LocaProxy"
APP_VERSION = "1.0.0"

if getattr(sys, "frozen", False):  # built with PyInstaller
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
SETTINGS_FILE = DATA_DIR / "settings.json"
IS_WINDOWS = os.name == "nt"

# Countries that usually have Tor exit relays. Countries with few or no exits
# will connect slowly or not at all; the app tells you if that happens.
TOR_COUNTRIES = {
    "any": "Anywhere (fastest)",
    "us": "United States", "ca": "Canada", "mx": "Mexico", "br": "Brazil",
    "ar": "Argentina", "cl": "Chile", "gb": "United Kingdom", "ie": "Ireland",
    "fr": "France", "de": "Germany", "nl": "Netherlands", "be": "Belgium",
    "lu": "Luxembourg", "ch": "Switzerland", "at": "Austria", "it": "Italy",
    "es": "Spain", "pt": "Portugal", "se": "Sweden", "no": "Norway",
    "fi": "Finland", "dk": "Denmark", "is": "Iceland", "pl": "Poland",
    "cz": "Czech Republic", "sk": "Slovakia", "hu": "Hungary", "ro": "Romania",
    "bg": "Bulgaria", "gr": "Greece", "md": "Moldova", "ua": "Ukraine",
    "lt": "Lithuania", "lv": "Latvia", "ee": "Estonia", "rs": "Serbia",
    "hr": "Croatia", "si": "Slovenia", "tr": "Turkey", "il": "Israel",
    "ae": "United Arab Emirates", "in": "India", "sg": "Singapore",
    "hk": "Hong Kong", "jp": "Japan", "kr": "South Korea", "tw": "Taiwan",
    "my": "Malaysia", "th": "Thailand", "vn": "Vietnam", "id": "Indonesia",
    "au": "Australia", "nz": "New Zealand", "za": "South Africa",
}

DEFAULT_SETTINGS = {
    "location": "tor:us",
    "listen_port": 8080,
    "system_proxy": True,
    "auto_connect": False,
    "tor_path": "",
    "custom_proxies": [],   # [{"name": "...", "url": "socks5://user:pass@host:port"}]
    "proxy_backup": None,   # saved system proxy settings, restored on disconnect
}


class ProxyError(Exception):
    pass


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #

def load_settings() -> dict:
    settings = dict(DEFAULT_SETTINGS)
    try:
        settings.update(json.loads(SETTINGS_FILE.read_text("utf-8")))
    except (OSError, ValueError):
        pass
    return settings


def save_settings(settings: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = SETTINGS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(settings, indent=2), "utf-8")
    os.replace(tmp, SETTINGS_FILE)


# --------------------------------------------------------------------------- #
# Upstream: how a connection leaves your PC
# --------------------------------------------------------------------------- #

SOCKS_ERRORS = {
    1: "general failure", 2: "connection not allowed", 3: "network unreachable",
    4: "host unreachable", 5: "connection refused", 6: "TTL expired",
    7: "command not supported", 8: "address type not supported",
}


def recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ProxyError("connection closed unexpectedly")
        buf += chunk
    return buf


def read_http_head(sock: socket.socket, limit: int = 65536) -> tuple[bytes, bytes]:
    """Read until the end of HTTP headers. Returns (head, extra bytes after it)."""
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            raise ProxyError("connection closed while reading headers")
        buf += chunk
        if len(buf) > limit:
            raise ProxyError("headers too large")
    head, _, rest = buf.partition(b"\r\n\r\n")
    return head + b"\r\n\r\n", rest


def host_for_url(host: str) -> str:
    return f"[{host}]" if ":" in host else host


class Upstream:
    """direct | socks5 | http"""

    def __init__(self, kind="direct", host="", port=0, username="", password="", label=""):
        self.kind = kind
        self.host = host
        self.port = int(port or 0)
        self.username = username or ""
        self.password = password or ""
        self.label = label or kind

    @classmethod
    def from_url(cls, url: str, label: str = "") -> "Upstream":
        url = url.strip()
        if "://" not in url:
            url = "socks5://" + url
        parts = urllib.parse.urlsplit(url)
        scheme = parts.scheme.lower()
        if scheme in ("socks5", "socks5h", "socks"):
            kind, default_port = "socks5", 1080
        elif scheme in ("http", "https"):
            kind, default_port = "http", 8080
        else:
            raise ValueError(f"Unsupported proxy type '{scheme}'. Use socks5:// or http://")
        if not parts.hostname:
            raise ValueError("Proxy address is missing a host")
        try:
            port = parts.port or default_port
        except ValueError:
            raise ValueError("Proxy port must be a number") from None
        return cls(kind, parts.hostname, port,
                   urllib.parse.unquote(parts.username or ""),
                   urllib.parse.unquote(parts.password or ""), label)

    def connect(self, host: str, port: int, timeout: float = 30) -> socket.socket:
        if self.kind == "direct":
            sock = socket.create_connection((host, port), timeout)
        elif self.kind == "socks5":
            sock = self._socks5(host, port, timeout)
        elif self.kind == "http":
            sock = self._http_connect(host, port, timeout)
        else:
            raise ProxyError(f"unknown upstream type {self.kind}")
        sock.settimeout(None)
        return sock

    def _socks5(self, host, port, timeout):
        try:
            sock = socket.create_connection((self.host, self.port), timeout)
        except OSError as e:
            raise ProxyError(f"cannot reach proxy {self.host}:{self.port} ({e})") from None
        try:
            methods = [0, 2] if self.username else [0]
            sock.sendall(bytes([5, len(methods), *methods]))
            ver, method = recv_exact(sock, 2)
            if ver != 5:
                raise ProxyError("upstream is not a SOCKS5 proxy")
            if method == 2:
                u, p = self.username.encode(), self.password.encode()
                sock.sendall(bytes([1, len(u)]) + u + bytes([len(p)]) + p)
                if recv_exact(sock, 2)[1] != 0:
                    raise ProxyError("proxy rejected the username/password")
            elif method != 0:
                raise ProxyError("proxy needs a login (add user:pass@ to the URL)")
            try:
                ip = ipaddress.ip_address(host)
                addr = bytes([1 if ip.version == 4 else 4]) + ip.packed
            except ValueError:
                # Send the hostname so DNS is resolved at the far end (no DNS leak).
                try:
                    hb = host.encode("idna")
                except UnicodeError:
                    hb = host.encode()
                addr = bytes([3, len(hb)]) + hb
            sock.sendall(b"\x05\x01\x00" + addr + struct.pack(">H", port))
            rep = recv_exact(sock, 4)
            if rep[1] != 0:
                raise ProxyError(f"proxy could not connect to {host}: "
                                 f"{SOCKS_ERRORS.get(rep[1], rep[1])}")
            atyp = rep[3]
            if atyp == 1:
                recv_exact(sock, 4 + 2)
            elif atyp == 4:
                recv_exact(sock, 16 + 2)
            elif atyp == 3:
                recv_exact(sock, recv_exact(sock, 1)[0] + 2)
            return sock
        except Exception:
            sock.close()
            raise

    def _http_connect(self, host, port, timeout):
        try:
            sock = socket.create_connection((self.host, self.port), timeout)
        except OSError as e:
            raise ProxyError(f"cannot reach proxy {self.host}:{self.port} ({e})") from None
        try:
            target = f"{host_for_url(host)}:{port}"
            req = f"CONNECT {target} HTTP/1.1\r\nHost: {target}\r\n"
            if self.username:
                cred = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
                req += f"Proxy-Authorization: Basic {cred}\r\n"
            sock.sendall((req + "\r\n").encode())
            head, extra = read_http_head(sock)
            status = head.split(b"\r\n", 1)[0].decode("latin-1")
            m = re.match(r"HTTP/\d\.\d\s+(\d+)", status)
            if not m or m.group(1) != "200":
                if m and m.group(1) == "407":
                    raise ProxyError("proxy rejected the username/password")
                raise ProxyError(f"proxy refused: {status}")
            if extra:  # should never happen for CONNECT
                raise ProxyError("unexpected data from proxy")
            return sock
        except Exception:
            sock.close()
            raise


# --------------------------------------------------------------------------- #
# Local proxy server: speaks both HTTP and SOCKS5 on the same port
# --------------------------------------------------------------------------- #

def pipe(a: socket.socket, b: socket.socket) -> None:
    def forward(src, dst):
        try:
            while True:
                data = src.recv(65536)
                if not data:
                    break
                dst.sendall(data)
            try:
                dst.shutdown(socket.SHUT_WR)
            except OSError:
                pass
        except OSError:
            for s in (a, b):
                try:
                    s.close()
                except OSError:
                    pass

    t = threading.Thread(target=forward, args=(b, a), daemon=True)
    t.start()
    forward(a, b)
    t.join()


class ProxyHandler(socketserver.BaseRequestHandler):
    server: "LocalProxyServer"

    def handle(self):
        client = self.request
        self.server.track(client)
        upstream_sock = None
        try:
            client.settimeout(60)
            first = client.recv(1, socket.MSG_PEEK)
            if not first:
                return
            if first == b"\x05":
                upstream_sock = self.handle_socks5(client)
            else:
                upstream_sock = self.handle_http(client)
            if upstream_sock is None:
                return
            self.server.track(upstream_sock)
            client.settimeout(None)
            pipe(client, upstream_sock)
        except (OSError, ProxyError, ValueError) as e:
            self.server.log(f"[conn] {e}", debug=True)
        finally:
            for s in (client, upstream_sock):
                if s is not None:
                    self.server.untrack(s)
                    try:
                        s.close()
                    except OSError:
                        pass

    def open_upstream(self, host, port):
        return self.server.upstream.connect(host, port)

    # ---- SOCKS5 (for apps that support SOCKS, e.g. Firefox, games launchers)
    def handle_socks5(self, client):
        _, nmethods = recv_exact(client, 2)
        methods = recv_exact(client, nmethods)
        if 0 not in methods:
            client.sendall(b"\x05\xff")
            return None
        client.sendall(b"\x05\x00")
        ver, cmd, _, atyp = recv_exact(client, 4)
        if atyp == 1:
            host = socket.inet_ntoa(recv_exact(client, 4))
        elif atyp == 3:
            host = recv_exact(client, recv_exact(client, 1)[0]).decode("ascii", "replace")
        elif atyp == 4:
            host = socket.inet_ntop(socket.AF_INET6, recv_exact(client, 16))
        else:
            client.sendall(b"\x05\x08\x00\x01" + b"\x00" * 6)
            return None
        port = struct.unpack(">H", recv_exact(client, 2))[0]
        if cmd != 1:  # only CONNECT; UDP is not supported
            client.sendall(b"\x05\x07\x00\x01" + b"\x00" * 6)
            return None
        try:
            up = self.open_upstream(host, port)
        except (OSError, ProxyError) as e:
            self.server.log(f"[socks] {host}:{port} failed: {e}", debug=True)
            client.sendall(b"\x05\x05\x00\x01" + b"\x00" * 6)
            return None
        client.sendall(b"\x05\x00\x00\x01" + b"\x00" * 6)
        return up

    # ---- HTTP proxy (what Windows / macOS system proxy settings use)
    def handle_http(self, client):
        head, rest = read_http_head(client)
        lines = head.decode("latin-1").split("\r\n")
        try:
            method, target, version = lines[0].split(" ", 2)
        except ValueError:
            self.http_error(client, 400, "Bad Request")
            return None

        if method.upper() == "CONNECT":
            host, port = split_host_port(target, 443)
            try:
                up = self.open_upstream(host, port)
            except (OSError, ProxyError) as e:
                self.server.log(f"[http] {target} failed: {e}", debug=True)
                self.http_error(client, 502, "Bad Gateway", str(e))
                return None
            client.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
            if rest:
                up.sendall(rest)
            return up

        # Plain http://host/path request
        url = urllib.parse.urlsplit(target)
        if url.scheme.lower() != "http" or not url.hostname:
            self.http_error(client, 400, "Bad Request",
                            f"{APP_NAME} is a proxy. Point your browser's proxy at it.")
            return None
        port = url.port or 80
        path = url.path or "/"
        if url.query:
            path += "?" + url.query
        headers = [h for h in lines[1:] if h and not h.lower().startswith(
            ("proxy-connection:", "proxy-authorization:", "connection:", "keep-alive:"))]
        headers.append("Connection: close")
        new_head = f"{method} {path} {version}\r\n" + "\r\n".join(headers) + "\r\n\r\n"
        try:
            up = self.open_upstream(url.hostname, port)
        except (OSError, ProxyError) as e:
            self.server.log(f"[http] {url.hostname} failed: {e}", debug=True)
            self.http_error(client, 502, "Bad Gateway", str(e))
            return None
        up.sendall(new_head.encode("latin-1") + rest)
        return up

    @staticmethod
    def http_error(client, code, reason, detail=""):
        body = f"{APP_NAME}: {code} {reason}\n{detail}\n".encode()
        client.sendall(
            f"HTTP/1.1 {code} {reason}\r\nContent-Type: text/plain\r\n"
            f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode() + body)


def split_host_port(target: str, default_port: int) -> tuple[str, int]:
    if target.startswith("["):
        host, _, port = target[1:].partition("]")
        port = port.lstrip(":")
    elif target.count(":") == 1:
        host, port = target.split(":")
    else:
        host, port = target, ""
    return host, int(port) if port.isdigit() else default_port


class LocalProxyServer(socketserver.ThreadingTCPServer):
    daemon_threads = True
    # On Windows SO_REUSEADDR lets two programs share a port; never do that there.
    allow_reuse_address = not IS_WINDOWS

    def __init__(self, port: int, upstream: Upstream, log):
        self.upstream = upstream
        self._log = log
        self._socks = set()
        self._lock = threading.Lock()
        super().__init__(("127.0.0.1", port), ProxyHandler)

    def log(self, msg, debug=False):
        self._log(msg, debug)

    def track(self, s):
        with self._lock:
            self._socks.add(s)

    def untrack(self, s):
        with self._lock:
            self._socks.discard(s)

    def close_all_connections(self):
        with self._lock:
            socks, self._socks = list(self._socks), set()
        for s in socks:
            try:
                s.close()
            except OSError:
                pass

    def start(self):
        threading.Thread(target=self.serve_forever, daemon=True).start()

    def stop(self):
        self.shutdown()
        self.server_close()
        self.close_all_connections()


# --------------------------------------------------------------------------- #
# Tor manager (free country-specific exits)
# --------------------------------------------------------------------------- #

def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TorManager:
    DIST = "https://dist.torproject.org/torbrowser/"

    def __init__(self, log):
        self.log = log
        self.proc: subprocess.Popen | None = None
        self.socks_port = 0
        self.tor_dir = DATA_DIR / "tor"

    # -- finding / installing tor ------------------------------------------
    def bundled_binary(self) -> Path:
        name = "tor.exe" if IS_WINDOWS else "tor"
        default = self.tor_dir / "tor" / name
        if not default.is_file() and self.tor_dir.is_dir():
            found = [p for p in self.tor_dir.rglob(name) if p.is_file()]
            if found:
                return found[0]
        return default

    def geoip_dir(self) -> Path | None:
        if self.tor_dir.is_dir():
            for p in self.tor_dir.rglob("geoip"):
                if p.is_file():
                    return p.parent
        return None

    def find(self, custom_path: str = "") -> str | None:
        if custom_path and Path(custom_path).is_file():
            return custom_path
        if self.bundled_binary().is_file():
            return str(self.bundled_binary())
        return shutil.which("tor")

    @staticmethod
    def _bundle_platform() -> str:
        machine = platform.machine().lower()
        if sys.platform == "darwin":
            return "macos-aarch64" if machine in ("arm64", "aarch64") else "macos-x86_64"
        os_name = "windows" if IS_WINDOWS else "linux"
        if machine in ("amd64", "x86_64"):
            return f"{os_name}-x86_64"
        if machine in ("arm64", "aarch64") and not IS_WINDOWS:
            return f"{os_name}-aarch64"
        return f"{os_name}-i686"

    def download(self, progress=lambda msg: None) -> str:
        """Download the official Tor Expert Bundle from torproject.org and verify its hash."""
        progress("Looking up the latest Tor release…")
        listing = http_get(self.DIST).decode("utf-8", "replace")
        versions = set(re.findall(r'href="(\d+(?:\.\d+)+)/"', listing))
        versions = sorted(versions, key=lambda v: tuple(int(x) for x in v.split(".")), reverse=True)
        plat = self._bundle_platform()
        for ver in versions[:6]:
            name = f"tor-expert-bundle-{plat}-{ver}.tar.gz"
            try:
                sums = http_get(f"{self.DIST}{ver}/sha256sums-signed-build.txt").decode()
            except OSError:
                continue
            m = re.search(r"^([0-9a-f]{64})\s+\*?" + re.escape(name) + r"\s*$", sums, re.M)
            if not m:
                continue
            progress(f"Downloading Tor {ver} (~20 MB)…")
            data = http_get(f"{self.DIST}{ver}/{name}", progress=progress)
            if hashlib.sha256(data).hexdigest() != m.group(1):
                raise ProxyError("Tor download failed verification; please try again")
            progress("Installing Tor…")
            self._extract(data)
            binary = self.bundled_binary()
            if not binary.is_file():
                raise ProxyError("Tor download did not contain the tor program")
            if not IS_WINDOWS:
                binary.chmod(0o755)
            self.log(f"Installed Tor {ver} to {self.tor_dir}")
            return str(binary)
        raise ProxyError("Could not find a Tor download for this computer. "
                         "Install Tor yourself and set its path in Settings.")

    def _extract(self, data: bytes) -> None:
        import io
        if self.tor_dir.exists():
            shutil.rmtree(self.tor_dir)
        self.tor_dir.mkdir(parents=True)
        root = self.tor_dir.resolve()
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            for member in tar.getmembers():
                dest = (root / member.name).resolve()
                if root not in dest.parents and dest != root:
                    raise ProxyError("unsafe path in Tor archive")
                if not (member.isfile() or member.isdir()):
                    continue
                if member.isdir():
                    dest.mkdir(parents=True, exist_ok=True)
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with tar.extractfile(member) as src, open(dest, "wb") as out:
                        shutil.copyfileobj(src, out)

    # -- running tor ---------------------------------------------------------
    def start(self, binary: str, country: str, progress=lambda msg: None, timeout=180) -> int:
        self.stop()
        state_dir = DATA_DIR / "tor-state"
        state_dir.mkdir(parents=True, exist_ok=True)
        self.socks_port = free_port()
        lines = [
            f"SocksPort 127.0.0.1:{self.socks_port}",
            f"DataDirectory {state_dir}",
            "Log notice stdout",
            "AvoidDiskWrites 1",
            "ClientOnly 1",
        ]
        geo_dir = self.geoip_dir() if binary.startswith(str(self.tor_dir)) else None
        if geo_dir:
            lines += [f"GeoIPFile {geo_dir / 'geoip'}", f"GeoIPv6File {geo_dir / 'geoip6'}"]
        if country and country != "any":
            lines += [f"ExitNodes {{{country}}}", "StrictNodes 1"]
        torrc = DATA_DIR / "torrc"
        torrc.write_text("\n".join(lines) + "\n", "utf-8")

        env = dict(os.environ)
        bin_dir = str(Path(binary).parent)
        if not IS_WINDOWS and binary.startswith(str(self.tor_dir)):
            key = "DYLD_LIBRARY_PATH" if sys.platform == "darwin" else "LD_LIBRARY_PATH"
            env[key] = bin_dir + os.pathsep + env.get(key, "")
        flags = 0x08000000 if IS_WINDOWS else 0  # CREATE_NO_WINDOW
        self.proc = subprocess.Popen(
            [binary, "-f", str(torrc)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, env=env, creationflags=flags,
            text=True, encoding="utf-8", errors="replace")

        ready = threading.Event()
        proc = self.proc

        def reader():
            for line in proc.stdout:
                line = line.strip()
                self.log(f"[tor] {line}", debug=True)
                m = re.search(r"Bootstrapped (\d+)%", line)
                if m:
                    progress(f"Connecting to Tor… {m.group(1)}%")
                    if m.group(1) == "100":
                        ready.set()
        threading.Thread(target=reader, daemon=True).start()

        deadline = time.time() + timeout
        while not ready.wait(0.25):
            if proc.poll() is not None:
                raise ProxyError("Tor stopped unexpectedly (see log for details)")
            if time.time() > deadline:
                self.stop()
                raise ProxyError("Tor took too long to connect. Your network may block Tor.")
        return self.socks_port

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None


def http_get(url: str, progress=None, timeout=60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        chunks, got, last = [], 0, 0.0
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            chunks.append(chunk)
            got += len(chunk)
            if progress and total and time.time() - last > 0.3:
                last = time.time()
                progress(f"Downloading Tor… {got * 100 // total}%")
        return b"".join(chunks)


# --------------------------------------------------------------------------- #
# System proxy (so the whole PC uses LocaProxy)
# --------------------------------------------------------------------------- #

class SystemProxy:
    """Turns the operating system's proxy setting on/off. Returns a backup to restore."""

    @staticmethod
    def supported() -> bool:
        return IS_WINDOWS or sys.platform == "darwin" or bool(shutil.which("gsettings"))

    @staticmethod
    def enable(port: int) -> dict:
        if IS_WINDOWS:
            return SystemProxy._win_enable(port)
        if sys.platform == "darwin":
            return SystemProxy._mac_enable(port)
        if shutil.which("gsettings"):
            return SystemProxy._gnome_enable(port)
        raise ProxyError("Automatic system proxy is not supported on this OS")

    @staticmethod
    def restore(backup: dict | None) -> None:
        if not backup:
            return
        kind = backup.get("kind")
        if kind == "windows":
            SystemProxy._win_restore(backup)
        elif kind == "macos":
            SystemProxy._mac_restore(backup)
        elif kind == "gnome":
            SystemProxy._gnome_restore(backup)

    # ---- Windows
    WIN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
    WIN_VALUES = ("ProxyEnable", "ProxyServer", "ProxyOverride", "AutoConfigURL")

    @staticmethod
    def _win_refresh():
        import ctypes
        wininet = ctypes.windll.wininet
        wininet.InternetSetOptionW(None, 39, None, 0)  # SETTINGS_CHANGED
        wininet.InternetSetOptionW(None, 37, None, 0)  # REFRESH

    @staticmethod
    def _win_enable(port):
        import winreg
        backup = {"kind": "windows", "values": {}}
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, SystemProxy.WIN_KEY, 0,
                            winreg.KEY_READ | winreg.KEY_WRITE) as key:
            for name in SystemProxy.WIN_VALUES:
                try:
                    val, typ = winreg.QueryValueEx(key, name)
                    backup["values"][name] = [val, typ]
                except FileNotFoundError:
                    backup["values"][name] = None
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, f"127.0.0.1:{port}")
            winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ,
                              "<local>;localhost;127.*;10.*;192.168.*")
            if backup["values"]["AutoConfigURL"] is not None:
                winreg.DeleteValue(key, "AutoConfigURL")  # a PAC script would override us
        SystemProxy._win_refresh()
        return backup

    @staticmethod
    def _win_restore(backup):
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, SystemProxy.WIN_KEY, 0,
                            winreg.KEY_READ | winreg.KEY_WRITE) as key:
            for name, saved in backup.get("values", {}).items():
                if saved is None:
                    if name == "ProxyEnable":
                        winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, 0)
                    else:
                        try:
                            winreg.DeleteValue(key, name)
                        except FileNotFoundError:
                            pass
                else:
                    winreg.SetValueEx(key, name, 0, saved[1], saved[0])
        SystemProxy._win_refresh()

    # ---- macOS
    @staticmethod
    def _mac_services():
        out = subprocess.run(["networksetup", "-listallnetworkservices"],
                             capture_output=True, text=True).stdout.splitlines()
        return [s for s in out[1:] if s and not s.startswith("*")]

    @staticmethod
    def _mac_enable(port):
        services = SystemProxy._mac_services()
        for svc in services:
            for kind in ("webproxy", "securewebproxy"):
                subprocess.run(["networksetup", f"-set{kind}", svc, "127.0.0.1", str(port)],
                               capture_output=True)
        return {"kind": "macos", "services": services}

    @staticmethod
    def _mac_restore(backup):
        for svc in backup.get("services", []):
            for kind in ("webproxystate", "securewebproxystate"):
                subprocess.run(["networksetup", f"-set{kind}", svc, "off"], capture_output=True)

    # ---- Linux (GNOME / most desktop environments that read gsettings)
    GNOME_KEYS = [("org.gnome.system.proxy", "mode"),
                  ("org.gnome.system.proxy.http", "host"), ("org.gnome.system.proxy.http", "port"),
                  ("org.gnome.system.proxy.https", "host"), ("org.gnome.system.proxy.https", "port")]

    @staticmethod
    def _gnome_enable(port):
        backup = {"kind": "gnome", "values": []}
        for schema, key in SystemProxy.GNOME_KEYS:
            val = subprocess.run(["gsettings", "get", schema, key],
                                 capture_output=True, text=True).stdout.strip()
            backup["values"].append([schema, key, val])
        for schema in ("org.gnome.system.proxy.http", "org.gnome.system.proxy.https"):
            subprocess.run(["gsettings", "set", schema, "host", "127.0.0.1"])
            subprocess.run(["gsettings", "set", schema, "port", str(port)])
        subprocess.run(["gsettings", "set", "org.gnome.system.proxy", "mode", "manual"])
        return backup

    @staticmethod
    def _gnome_restore(backup):
        for schema, key, val in backup.get("values", []):
            if val:
                subprocess.run(["gsettings", "set", schema, key, val.strip("'")])


# --------------------------------------------------------------------------- #
# Where am I? (checks the IP address websites see)
# --------------------------------------------------------------------------- #

def check_ip(port: int, timeout=20) -> dict:
    proxy = f"http://127.0.0.1:{port}"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    services = [
        ("https://ipwho.is/", lambda d: (d.get("ip"), d.get("country"), d.get("city"), d.get("country_code"))),
        ("https://ipinfo.io/json", lambda d: (d.get("ip"), d.get("country"), d.get("city"), d.get("country"))),
        ("http://ip-api.com/json/", lambda d: (d.get("query"), d.get("country"), d.get("city"), d.get("countryCode"))),
    ]
    last_err = None
    for url, parse in services:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"})
            with opener.open(req, timeout=timeout) as resp:
                ip, country, city, code = parse(json.loads(resp.read()))
            if ip:
                return {"ip": ip, "country": country or "?", "city": city or "",
                        "code": (code or "").lower()}
        except Exception as e:  # noqa: BLE001 - try the next service
            last_err = e
    raise ProxyError(f"could not reach the internet through the proxy ({last_err})")


# --------------------------------------------------------------------------- #
# Controller: glue used by both the window and the command line
# --------------------------------------------------------------------------- #

class Controller:
    def __init__(self, settings: dict, log):
        self.settings = settings
        self.log = log
        self.tor = TorManager(log)
        self.server: LocalProxyServer | None = None
        self.connected_location = None
        self._lock = threading.Lock()
        # If we crashed last time while the system proxy was on, put it back.
        if settings.get("proxy_backup"):
            try:
                SystemProxy.restore(settings["proxy_backup"])
                self.log("Restored your system proxy settings from last session.")
            except Exception as e:  # noqa: BLE001
                self.log(f"Could not restore old proxy settings: {e}")
            settings["proxy_backup"] = None
            save_settings(settings)
        atexit.register(self.disconnect)

    def locations(self) -> list[tuple[str, str]]:
        items = [(f"tor:{code}", f"{name}  (free, Tor)") for code, name in TOR_COUNTRIES.items()]
        tor_any = items.pop(0)
        items.sort(key=lambda i: i[1])
        custom = [(f"custom:{i}", f"★ {p.get('name') or p.get('url')}  (my server)")
                  for i, p in enumerate(self.settings.get("custom_proxies", []))]
        return custom + [tor_any] + items

    def label_for(self, location: str) -> str:
        return dict(self.locations()).get(location, location)

    def _upstream_for(self, location: str, progress) -> Upstream:
        kind, _, value = location.partition(":")
        if kind == "custom":
            proxies = self.settings.get("custom_proxies", [])
            try:
                entry = proxies[int(value)]
            except (ValueError, IndexError):
                raise ProxyError("That saved server no longer exists") from None
            progress(f"Connecting to {entry.get('name') or entry['url']}…")
            return Upstream.from_url(entry["url"], entry.get("name", ""))
        if kind == "tor":
            if value not in TOR_COUNTRIES:
                raise ProxyError(f"Unknown country code '{value}'")
            binary = self.tor.find(self.settings.get("tor_path", ""))
            if not binary:
                binary = self.tor.download(progress)
            progress("Starting Tor…")
            port = self.tor.start(binary, value, progress)
            return Upstream("socks5", "127.0.0.1", port, label=f"Tor ({TOR_COUNTRIES[value]})")
        if kind == "direct":
            return Upstream("direct")
        raise ProxyError(f"Unknown location '{location}'")

    def connect(self, location: str, progress=lambda m: None) -> dict:
        with self._lock:
            self._disconnect_locked()
            try:
                upstream = self._upstream_for(location, progress)
                port = int(self.settings.get("listen_port", 8080))
                try:
                    self.server = LocalProxyServer(port, upstream, self.log)
                except OSError:
                    raise ProxyError(f"Port {port} is already in use. "
                                     f"Pick a different port in Settings.") from None
                self.server.start()
                self.log(f"Local proxy listening on 127.0.0.1:{port} via {upstream.label}")

                progress("Checking your new location…")
                try:
                    info = check_ip(port)
                except ProxyError as e:
                    hint = (" Tor may have no exits in that country right now; try another one."
                            if location.startswith("tor:") and location != "tor:any" else "")
                    raise ProxyError(f"Connected, but no internet through it: {e}.{hint}") from None

                if self.settings.get("system_proxy") and SystemProxy.supported():
                    backup = SystemProxy.enable(port)
                    self.settings["proxy_backup"] = backup
                    self.log("System proxy turned ON (whole PC now uses LocaProxy).")
                self.connected_location = location
                self.settings["location"] = location
                save_settings(self.settings)
                self.log(f"You now appear to be in: {info['city']} {info['country']} ({info['ip']})")
                return info
            except Exception:
                self._disconnect_locked()
                raise

    def disconnect(self):
        with self._lock:
            self._disconnect_locked()

    def _disconnect_locked(self):
        if self.settings.get("proxy_backup"):
            try:
                SystemProxy.restore(self.settings["proxy_backup"])
                self.log("System proxy restored to how it was.")
            except Exception as e:  # noqa: BLE001
                self.log(f"Could not restore system proxy: {e}")
            self.settings["proxy_backup"] = None
            save_settings(self.settings)
        if self.server:
            self.server.stop()
            self.server = None
        self.tor.stop()
        if self.connected_location:
            self.log("Disconnected.")
        self.connected_location = None


# --------------------------------------------------------------------------- #
# Window (tkinter)
# --------------------------------------------------------------------------- #

def run_gui():
    import tkinter as tk
    from tkinter import messagebox, ttk

    BG, CARD, FG, MUTED = "#0f172a", "#1e293b", "#f1f5f9", "#94a3b8"
    GREEN, RED, BLUE, AMBER = "#22c55e", "#ef4444", "#3b82f6", "#f59e0b"

    settings = load_settings()
    events: queue.Queue = queue.Queue()
    log_lines: list[str] = []

    def log(msg, debug=False):
        events.put(("log", f"{time.strftime('%H:%M:%S')}  {msg}"))

    ctrl = Controller(settings, log)

    root = tk.Tk()
    root.title(f"{APP_NAME}")
    root.configure(bg=BG)
    root.minsize(420, 520)
    root.geometry("440x600")

    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TCombobox", fieldbackground=CARD, background=CARD, foreground=FG,
                    arrowcolor=FG, bordercolor=CARD, padding=8)
    style.map("TCombobox", fieldbackground=[("readonly", CARD)], foreground=[("readonly", FG)],
              selectbackground=[("readonly", CARD)], selectforeground=[("readonly", FG)])
    root.option_add("*TCombobox*Listbox.background", CARD)
    root.option_add("*TCombobox*Listbox.foreground", FG)
    root.option_add("*TCombobox*Listbox.selectBackground", BLUE)
    root.option_add("*TCombobox*Listbox.font", ("Segoe UI", 11))

    def label(parent, text="", size=10, color=FG, bold=False, **kw):
        return tk.Label(parent, text=text, bg=parent["bg"], fg=color,
                        font=("Segoe UI", size, "bold" if bold else "normal"), **kw)

    wrap = tk.Frame(root, bg=BG, padx=22, pady=18)
    wrap.pack(fill="both", expand=True)

    label(wrap, APP_NAME, 22, bold=True).pack(anchor="w")
    label(wrap, "Be anywhere in the world. Pick a place, press Connect.", 10, MUTED).pack(anchor="w", pady=(0, 16))

    # Location picker
    label(wrap, "WHERE DO YOU WANT TO BE?", 9, MUTED, bold=True).pack(anchor="w")
    loc_var = tk.StringVar()
    loc_box = ttk.Combobox(wrap, textvariable=loc_var, state="readonly", font=("Segoe UI", 12))
    loc_box.pack(fill="x", pady=(4, 16))
    loc_ids: list[str] = []

    def refresh_locations(select=None):
        items = ctrl.locations()
        loc_ids[:] = [i for i, _ in items]
        loc_box["values"] = [lbl for _, lbl in items]
        want = select or settings.get("location", "tor:us")
        idx = loc_ids.index(want) if want in loc_ids else loc_ids.index("tor:us")
        loc_box.current(idx)

    refresh_locations()

    # Big connect button
    btn = tk.Button(wrap, text="CONNECT", font=("Segoe UI", 16, "bold"), bg=GREEN, fg="white",
                    activebackground="#16a34a", activeforeground="white", relief="flat",
                    bd=0, cursor="hand2", height=2, highlightthickness=0)
    btn.pack(fill="x")

    # Status card
    card = tk.Frame(wrap, bg=CARD, padx=16, pady=14)
    card.pack(fill="x", pady=16)
    status_row = tk.Frame(card, bg=CARD)
    status_row.pack(anchor="w")
    dot = tk.Canvas(status_row, width=12, height=12, bg=CARD, highlightthickness=0)
    dot_id = dot.create_oval(1, 1, 11, 11, fill=RED, outline="")
    dot.pack(side="left", padx=(0, 8))
    status_lbl = label(status_row, "Not connected", 12, bold=True)
    status_lbl.pack(side="left")
    where_lbl = label(card, "Your real location is visible.", 10, MUTED, justify="left", wraplength=360)
    where_lbl.pack(anchor="w", pady=(6, 0))
    ip_lbl = label(card, "", 10, MUTED)
    ip_lbl.pack(anchor="w")

    # Settings
    label(wrap, "SETTINGS", 9, MUTED, bold=True).pack(anchor="w", pady=(4, 4))
    sys_var = tk.BooleanVar(value=settings.get("system_proxy", True))
    auto_var = tk.BooleanVar(value=settings.get("auto_connect", False))

    def check(text, var):
        return tk.Checkbutton(wrap, text=text, variable=var, bg=BG, fg=FG, selectcolor=CARD,
                              activebackground=BG, activeforeground=FG, font=("Segoe UI", 10),
                              anchor="w", command=persist, highlightthickness=0, bd=0)

    def persist():
        settings["system_proxy"] = sys_var.get()
        settings["auto_connect"] = auto_var.get()
        save_settings(settings)

    check("Route my whole PC through it (browsers & most apps)", sys_var).pack(fill="x")
    check("Connect automatically when I open LocaProxy", auto_var).pack(fill="x")

    port_row = tk.Frame(wrap, bg=BG)
    port_row.pack(fill="x", pady=(6, 0))
    label(port_row, "Local proxy port:", 10).pack(side="left")
    port_var = tk.StringVar(value=str(settings.get("listen_port", 8080)))
    port_entry = tk.Entry(port_row, textvariable=port_var, width=7, bg=CARD, fg=FG,
                          insertbackground=FG, relief="flat", font=("Segoe UI", 10),
                          highlightthickness=0)
    port_entry.pack(side="left", padx=8, ipady=3)

    def save_port(*_):
        try:
            p = int(port_var.get())
            if not 1024 <= p <= 65535:
                raise ValueError
            settings["listen_port"] = p
            save_settings(settings)
        except ValueError:
            port_var.set(str(settings.get("listen_port", 8080)))
    port_entry.bind("<FocusOut>", save_port)
    port_entry.bind("<Return>", save_port)

    btn_row = tk.Frame(wrap, bg=BG)
    btn_row.pack(fill="x", pady=(12, 0))

    def small_button(text, cmd):
        return tk.Button(btn_row, text=text, command=cmd, bg=CARD, fg=FG, relief="flat",
                         activebackground="#334155", activeforeground=FG, cursor="hand2",
                         font=("Segoe UI", 10), padx=10, pady=5, bd=0, highlightthickness=0)

    log_frame = tk.Frame(wrap, bg=BG)
    log_text = tk.Text(log_frame, height=8, bg="#020617", fg=MUTED, relief="flat",
                       font=("Consolas", 9), wrap="word", state="disabled")
    log_text.pack(fill="both", expand=True)

    def toggle_log():
        if log_frame.winfo_ismapped():
            log_frame.pack_forget()
        else:
            log_frame.pack(fill="both", expand=True, pady=(10, 0))

    # ---- Saved servers dialog ----------------------------------------------
    def manage_servers():
        win = tk.Toplevel(root)
        win.title("My proxy servers")
        win.configure(bg=BG, padx=16, pady=14)
        win.transient(root)
        win.grab_set()
        label(win, "Add a proxy server in any country", 12, bold=True).pack(anchor="w")
        label(win, "Paste the address your provider gave you, for example:\n"
                   "socks5://user:pass@203.0.113.5:1080   or   http://198.51.100.7:3128",
              9, MUTED, justify="left").pack(anchor="w", pady=(2, 10))

        lst = tk.Listbox(win, height=6, bg=CARD, fg=FG, relief="flat", selectbackground=BLUE,
                         font=("Segoe UI", 10), activestyle="none")
        lst.pack(fill="x")

        def reload_list():
            lst.delete(0, "end")
            for p in settings["custom_proxies"]:
                lst.insert("end", f"{p.get('name') or '(no name)'}   —   {mask_url(p['url'])}")
        reload_list()

        form = tk.Frame(win, bg=BG)
        form.pack(fill="x", pady=10)
        label(form, "Name (e.g. Tokyo, Japan)").grid(row=0, column=0, sticky="w")
        name_var = tk.StringVar()
        tk.Entry(form, textvariable=name_var, bg=CARD, fg=FG, insertbackground=FG,
                 relief="flat", width=40).grid(row=1, column=0, sticky="we", ipady=4)
        label(form, "Proxy address").grid(row=2, column=0, sticky="w", pady=(8, 0))
        url_var = tk.StringVar()
        tk.Entry(form, textvariable=url_var, bg=CARD, fg=FG, insertbackground=FG,
                 relief="flat", width=40).grid(row=3, column=0, sticky="we", ipady=4)
        form.columnconfigure(0, weight=1)

        def add():
            try:
                Upstream.from_url(url_var.get())
            except ValueError as e:
                messagebox.showerror("Invalid address", str(e), parent=win)
                return
            settings["custom_proxies"].append({"name": name_var.get().strip(),
                                               "url": url_var.get().strip()})
            save_settings(settings)
            name_var.set("")
            url_var.set("")
            reload_list()
            refresh_locations(select=f"custom:{len(settings['custom_proxies']) - 1}")

        def remove():
            sel = lst.curselection()
            if not sel:
                return
            if ctrl.connected_location and ctrl.connected_location.startswith("custom:"):
                messagebox.showinfo("Disconnect first", "Disconnect before removing servers.",
                                    parent=win)
                return
            settings["custom_proxies"].pop(sel[0])
            save_settings(settings)
            reload_list()
            refresh_locations()

        row = tk.Frame(win, bg=BG)
        row.pack(fill="x")
        for text, cmd, color in (("Add", add, BLUE), ("Remove selected", remove, CARD),
                                 ("Done", win.destroy, CARD)):
            tk.Button(row, text=text, command=cmd, bg=color, fg=FG, relief="flat", padx=12,
                      pady=5, cursor="hand2").pack(side="left", padx=(0, 6))

    small_button("My proxy servers…", manage_servers).pack(side="left")
    small_button("Show log", toggle_log).pack(side="left", padx=6)

    # ---- connect / disconnect -----------------------------------------------
    busy = {"on": False}

    def set_state(state, text="", detail="", ip=""):
        colors = {"off": RED, "busy": AMBER, "on": GREEN}
        dot.itemconfig(dot_id, fill=colors[state])
        status_lbl.config(text=text)
        where_lbl.config(text=detail)
        ip_lbl.config(text=ip)
        if state == "on":
            btn.config(text="DISCONNECT", bg=RED, activebackground="#dc2626", state="normal")
        elif state == "busy":
            btn.config(text="CONNECTING…", bg=AMBER, activebackground=AMBER, state="normal")
        else:
            btn.config(text="CONNECT", bg=GREEN, activebackground="#16a34a", state="normal")
        loc_box.config(state="disabled" if state == "busy" else "readonly")

    def do_connect():
        location = loc_ids[loc_box.current()]
        busy["on"] = True
        set_state("busy", "Connecting…", ctrl.label_for(location))

        def work():
            try:
                info = ctrl.connect(location, progress=lambda m: events.put(("progress", m)))
                events.put(("connected", info))
            except Exception as e:  # noqa: BLE001
                events.put(("error", str(e)))
        threading.Thread(target=work, daemon=True).start()

    def do_disconnect():
        def work():
            ctrl.disconnect()
            events.put(("disconnected", None))
        threading.Thread(target=work, daemon=True).start()

    def on_button():
        if busy["on"]:
            return
        if ctrl.connected_location:
            do_disconnect()
        else:
            do_connect()
    btn.config(command=on_button)

    def on_location_change(_):
        # Switching location while connected reconnects automatically.
        if ctrl.connected_location and not busy["on"]:
            do_connect()
    loc_box.bind("<<ComboboxSelected>>", on_location_change)

    def poll():
        try:
            while True:
                kind, payload = events.get_nowait()
                if kind == "log":
                    log_lines.append(payload)
                    log_text.config(state="normal")
                    log_text.insert("end", payload + "\n")
                    log_text.see("end")
                    log_text.config(state="disabled")
                elif kind == "progress":
                    where_lbl.config(text=payload)
                elif kind == "connected":
                    busy["on"] = False
                    place = ", ".join(x for x in (payload["city"], payload["country"]) if x)
                    extra = f"\nProxy: 127.0.0.1:{settings['listen_port']}"
                    if not settings.get("system_proxy"):
                        extra += "  (set this in your app/browser)"
                    set_state("on", "Connected", f"You appear to be in {place}" + extra,
                              f"Public IP: {payload['ip']}")
                elif kind == "error":
                    busy["on"] = False
                    set_state("off", "Not connected", "Your real location is visible.")
                    messagebox.showerror(APP_NAME, payload)
                elif kind == "disconnected":
                    busy["on"] = False
                    set_state("off", "Not connected", "Your real location is visible.")
        except queue.Empty:
            pass
        root.after(120, poll)

    def on_close():
        btn.config(state="disabled", text="Closing…")
        root.update_idletasks()
        ctrl.disconnect()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.after(120, poll)
    if settings.get("auto_connect"):
        root.after(400, do_connect)
    root.mainloop()


def mask_url(url: str) -> str:
    return re.sub(r"(://[^:@/]*:)[^@/]*@", r"\1•••@", url)


# --------------------------------------------------------------------------- #
# Command line
# --------------------------------------------------------------------------- #

def run_cli(args):
    settings = load_settings()
    if args.port:
        settings["listen_port"] = args.port
    if args.no_system_proxy:
        settings["system_proxy"] = False
    if args.system_proxy:
        settings["system_proxy"] = True

    def log(msg, debug=False):
        if debug and not args.verbose:
            return
        print(f"{time.strftime('%H:%M:%S')}  {msg}", flush=True)

    ctrl = Controller(settings, log)
    if args.list:
        for loc_id, lbl in ctrl.locations():
            print(f"{loc_id:<12} {lbl}")
        return 0
    previous_location = settings.get("location", "tor:us")
    location = args.location or previous_location
    try:
        if args.proxy:
            # One-off upstream given on the command line
            settings.setdefault("custom_proxies", [])
            settings["custom_proxies"].append({"name": "command line", "url": args.proxy})
            location = f"custom:{len(settings['custom_proxies']) - 1}"
        info = ctrl.connect(location, progress=lambda m: log(m))
    except ProxyError as e:
        log(f"ERROR: {e}")
        return 1
    finally:
        if args.proxy:
            settings["custom_proxies"].pop()
            settings["location"] = previous_location
            save_settings(settings)
    port = settings["listen_port"]
    print(f"\nConnected. You appear to be in {info['city']} {info['country']} ({info['ip']}).")
    print(f"HTTP + SOCKS5 proxy: 127.0.0.1:{port}   Press Ctrl+C to stop.\n", flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        ctrl.disconnect()
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=f"{APP_NAME}: appear to be anywhere in the world.")
    p.add_argument("--cli", action="store_true", help="run without a window")
    p.add_argument("-l", "--location", help="e.g. tor:us, tor:jp, tor:any, custom:0")
    p.add_argument("--proxy", help="use this upstream proxy URL once (socks5://… or http://…)")
    p.add_argument("--list", action="store_true", help="list available locations")
    p.add_argument("-p", "--port", type=int, help="local proxy port (default 8080)")
    p.add_argument("--system-proxy", action="store_true", help="also set the OS proxy")
    p.add_argument("--no-system-proxy", action="store_true", help="don't touch the OS proxy")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)

    if args.cli or args.list or args.location or args.proxy:
        # In CLI mode, only touch the OS proxy if asked.
        if not args.system_proxy:
            args.no_system_proxy = True
        return run_cli(args)
    try:
        run_gui()
    except ImportError:
        print("The window needs tkinter (included with the python.org installer). "
              "Use --cli to run without a window.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
