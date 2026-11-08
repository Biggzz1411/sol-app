# Handoff: install LocaProxy on Biggzz's PC and connect it to BotChat

You're working on Biggzz's Windows PC. Goal: BotChat's coder bots search, read and download
**from a country Biggzz picks**, while their connections to the AI models stay direct and fast.

## Rules (read first)

- **Never open** BotChat's chat logs (`chats\`), the code the bots wrote, or Story AI's stories
  and pictures.
- **Never show, print, log or commit** the RunPod key or `KCPP_KEY` (`D:\Story AI\app\cloud.json`).
- **Don't restart Story AI** unless Biggzz says to. Don't start the RunPod pod (it costs money).
- Before editing any BotChat file, **back it up** (`file.bak`). Prefer adding new files over editing.
- If you're unsure whether a BotChat file counts as "code the bots wrote", **ask Biggzz** before
  opening it.

## 1. Get LocaProxy

Repo `biggzz1411/sol-app`, branch `claude/pc-proxy-location-1hhhqc`, folder `pc-proxy/`.
Copy that folder to `C:\LocaProxy`. Files:

| File | What it is |
|---|---|
| `locaproxy.py` | The whole app. Python standard library only, with a tkinter window. |
| `Start LocaProxy.bat` | Double-click launcher (uses `pyw`/`pythonw`). |
| `Build EXE.bat` | Optional: builds `dist\LocaProxy.exe` with PyInstaller. |
| `tests/test_proxy.py` | Self-test for the proxy engine. |
| `README.md` | User guide. |

What it does: runs an HTTP **and** SOCKS5 proxy on `127.0.0.1:8080` (one port, both protocols).
Traffic leaves through either **Tor** (exit relays limited to one country; Tor Expert Bundle
auto-downloads to `C:\LocaProxy\data\tor`, sha256-checked) or a saved SOCKS5/HTTP server.
"Route my whole PC" sets the Windows WinINET proxy (HKCU Internet Settings) and restores it on
disconnect/exit/next start. Settings: `C:\LocaProxy\data\settings.json`.

CLI (handy for you): `python locaproxy.py --cli -l tor:de -v`. Use `--list` to see locations.

## 2. Verify LocaProxy (it hasn't run on Windows yet)

It was tested on Linux only: proxy engine, saved-server connect, and the window. **Untested:**
the real Tor download/connect, Windows system-proxy switching, the `.bat` files.

1. Check that `py --version` works, or have Biggzz install Python 3 from python.org (tick "Add to PATH").
2. `cd C:\LocaProxy && py tests\test_proxy.py`. Expect `ALL PASSED`.
3. `py locaproxy.py --cli -l tor:us -v`. Expect it to download Tor, show "Bootstrapped 100%",
   then print "You appear to be in … United States".
   - If the Tor download fails: check `TorManager.download()` against
     https://dist.torproject.org/torbrowser/ (the file name pattern is
     `tor-expert-bundle-windows-x86_64-<ver>.tar.gz`; checksums are in `sha256sums-signed-build.txt`).
   - If the IP check fails but Tor connected: `check_ip()` tries ipwho.is, ipinfo.io, then
     ip-api.com. Some block Tor, so try `tor:de` or `tor:nl`.
4. Window test: double-click `Start LocaProxy.bat`, pick a country, CONNECT. Then confirm in
   Windows Settings > Network > Proxy that "Use a proxy server" shows `127.0.0.1:8080`. DISCONNECT
   and confirm it's back to how it was.
5. Fix anything that breaks, keep the changes small, and commit back to the branch.

## 3. Fix in LocaProxy: never send Tailscale or RunPod through the proxy

`SystemProxy._win_enable()` sets `ProxyOverride` to `<local>;localhost;127.*;10.*;192.168.*`.
Add **`100.*`** (Tailscale, e.g. `100.87.221.65`) and **`*.runpod.net`** (the pod used by
@Coder, Story AI and Heretic). Without these, "Route my whole PC" would push the model
connections through Tor and make them crawl or fail.

Better: add a `"bypass"` list to `DEFAULT_SETTINGS` (default
`["<local>","localhost","127.*","10.*","192.168.*","100.*","*.runpod.net"]`). Use it for
`ProxyOverride` (joined with `;`), and add an "Always go direct" text box in the window.
Do the same for the macOS (`-setproxybypassdomains`) and GNOME (`ignore-hosts`) paths if it's easy.

## 4. Connect BotChat (both @Coder2 and @Coder)

BotChat (`C:\Story AI Models\BotChat`, started with `Start BotChat.cmd`, UI at
http://localhost:3777) runs its tools on the PC: web search, read pages, downloads to
`D:\BotChat Downloads`. So routing **BotChat's outbound web traffic** through LocaProxy covers
**both** bots. That includes @Coder, whose model is on RunPod.

**Do not** route these through the proxy:

- koboldcpp, `localhost:5050` (the @Coder2 model)
- the pod, `*.proxy.runpod.net` (the @Coder model)
- LAN `192.168.12.31` and Tailscale `100.87.221.65` (how Biggzz opens the UI)

Steps:

1. **Find out what BotChat runs on.** Read only `Start BotChat.cmd` and the top-level manifest
   (`package.json` or `requirements.txt`). Don't browse further without asking Biggzz.
2. **Make a new launcher** `Start BotChat (LocaProxy).cmd` next to the original (leave the original
   untouched). It sets the env vars, then does exactly what the original does:
   ```bat
   set HTTP_PROXY=http://127.0.0.1:8080
   set HTTPS_PROXY=http://127.0.0.1:8080
   set NO_PROXY=localhost,127.0.0.1,::1,192.168.12.31,100.87.221.65,.runpod.net,.proxy.runpod.net
   ```
   Runtime gotchas:
   - **Node.js:** built-in `fetch` ignores these vars. Node ≥ 24: also `set NODE_USE_ENV_PROXY=1`.
     Older Node: the fetch code needs undici's `EnvHttpProxyAgent` (`setGlobalDispatcher`). That's a
     code change, so ask Biggzz first. axios honors `HTTP(S)_PROXY` itself.
   - **Python:** `requests`, `httpx` and `urllib` honor the vars. `aiohttp` needs `trust_env=True`.
   - `NO_PROXY` matching differs by library. Use exact hosts and `.domain` suffixes as above, not
     `192.168.*` wildcards.
   - Any headless browser BotChat uses (Playwright/Puppeteer) needs `--proxy-server=http://127.0.0.1:8080`
     or the launch option `proxy: {server: ...}`.
3. **Test** (the pod can stay stopped; @Coder2 is local):
   - Start LocaProxy, connect to e.g. Germany (`tor:de`).
   - Start BotChat with the new launcher.
   - `POST http://localhost:3777/send {"text":"@Coder2 search the web for 'what is my ip' and tell me the country"}`
     (or have it read `https://ipwho.is/`). Watch `GET /events`. The answer should say Germany.
   - Confirm @Coder2 still answers at normal speed (koboldcpp not proxied).
   - Disconnect LocaProxy. BotChat web tools should now fail cleanly (connection refused on 8080),
     which proves they were going through it. Document this in the note below.
   - Don't use `/auto` or approve file changes for testing. Use read-only requests.

## 5. Optional: give the bots the private browser

This was promised as a later feature and isn't built yet. A "Launch private browser" button in LocaProxy
starts Chrome/Edge with a throwaway profile in `C:\LocaProxy\data\browser-profile` and these flags:
`--proxy-server=http://127.0.0.1:8080`,
`--force-webrtc-ip-handling-policy=disable_non_proxied_udp`, `--lang=<country language>`,
geolocation blocked in profile prefs, and `--remote-debugging-port=9222` (localhost only).
Bots can then attach via CDP (`chromium.connectOverCDP("http://127.0.0.1:9222")`).
Also wanted: an optional "match time zone" checkbox (`tzutil /s "<zone>"` on connect, restore on
disconnect) and a "Check for leaks" button (IP country, DNS, time-zone match, as pass/fail).

## When you're done, tell Biggzz in plain words

- Whether LocaProxy works on the PC (Tor connect, window, system proxy on/off).
- How to start BotChat "from another country" (which launcher to double-click).
- Anything that didn't work or needs their OK. Don't paste any keys.
