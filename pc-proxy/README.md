# LocaProxy: be anywhere in the world, from your PC

Pick a country, press **Connect**, and websites see you in that country.
Press **Disconnect** and everything goes back to normal.

## Setup (Windows, about 2 minutes)

1. Install **Python 3** from <https://www.python.org/downloads/>.
   During setup, tick **"Add python.exe to PATH"**.
2. Put this `pc-proxy` folder anywhere, for example on your Desktop.
3. Double-click **`Start LocaProxy.bat`**.

That's it. Choose a location from the list and click **CONNECT**.
The first time you use a free location, LocaProxy downloads Tor
(about 20 MB, from torproject.org, checked against its official checksum).

> Want a single `.exe` with no Python needed? Double-click **`Build EXE.bat`** once,
> and you get `dist\LocaProxy.exe` that you can copy anywhere or pin to the taskbar.

**macOS / Linux:** run `./start.sh`. You need Python 3 with tkinter, and on Linux
either install `tor` (`sudo apt install tor`) or let the app download it.

## How it works

LocaProxy runs a small proxy on your PC at `127.0.0.1:8080`. Your traffic has to
come out of a computer in the country you chose, so you have two options:

| Option | Cost | Speed | How |
|---|---|---|---|
| **Free (Tor)** | Free | Slow to medium | Uses only Tor exit relays in the country you picked. Built in, no account needed. |
| **★ My servers** | Whatever your provider charges | Fast | Any SOCKS5 or HTTP proxy in any country, from a proxy provider or your own cloud server. |

### Adding your own server

Click **My proxy servers…**, give it a name (for example `Tokyo, Japan`), and paste the
address in one of these formats:

```
socks5://username:password@203.0.113.5:1080
http://username:password@198.51.100.7:3128
socks5://203.0.113.5:1080            (no login)
```

It then shows up at the top of the location list with a ★.

## Settings

- **Route my whole PC through it** (on by default): turns on your system proxy while
  connected, so Chrome, Edge, Firefox (with "use system proxy settings"), Windows Store
  apps and most other programs go through it. It's switched back off when you disconnect
  or close the app, and restored on the next start if the app ever crashed.
- **Connect automatically when I open LocaProxy**: opens straight into your last location.
- **Local proxy port**: change it from 8080 if something else already uses that port.
- **Switching location while connected** reconnects automatically.

If you turn off the whole-PC option, point a single app at `127.0.0.1:8080`.
It works as both an **HTTP** and a **SOCKS5** proxy.

## Good to know

- **Some apps ignore the system proxy**, such as many online games, torrent clients and
  anything using UDP. Use their own proxy setting (SOCKS5 `127.0.0.1:8080`), or use a full
  VPN for those.
- **Tor countries:** some countries have few or no Tor exits. If one doesn't work, the app
  says so; pick a nearby country or "Anywhere". Some sites (streaming, banking) block Tor;
  your own servers work better for those.
- With Tor and SOCKS5 servers, website names are looked up at the far end, so your DNS
  doesn't reveal your real location.
- Settings are stored in `data/settings.json` next to the app.

## Command line (optional)

```
python locaproxy.py --list                 # show all locations
python locaproxy.py --cli -l tor:de        # connect to Germany, no window
python locaproxy.py --cli --proxy socks5://user:pass@host:1080 --system-proxy
```

Self-test: `python tests/test_proxy.py`
