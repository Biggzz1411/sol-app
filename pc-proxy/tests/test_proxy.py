"""Self-test: chains two local proxies (HTTP upstream -> SOCKS5 upstream) and
fetches pages through them over HTTP-proxy CONNECT, plain HTTP and SOCKS5."""
import http.server, os, socket, struct, sys, threading, urllib.request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import locaproxy as lp

log = lambda m, debug=False: print("   ", m)

# Local origin web server for plain-HTTP tests
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = f"hello {self.path}".encode()
        self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass
origin = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=origin.serve_forever, daemon=True).start()
oport = origin.server_address[1]

# A: direct (or via $HTTPS_PROXY if set, to reach the internet from a sandbox)
up_a = lp.Upstream.from_url(os.environ["HTTPS_PROXY"]) if os.environ.get("HTTPS_PROXY") else lp.Upstream("direct")
a = lp.LocalProxyServer(lp.free_port(), up_a, log); a.start()
# B: SOCKS5 upstream pointing at A (A speaks SOCKS5 and HTTP on one port)
b = lp.LocalProxyServer(lp.free_port(), lp.Upstream("socks5", "127.0.0.1", a.server_address[1]), log); b.start()
bport = b.server_address[1]
opener = urllib.request.build_opener(urllib.request.ProxyHandler(
    {"http": f"http://127.0.0.1:{bport}", "https": f"http://127.0.0.1:{bport}"}))

ok = True
def check(name, fn):
    global ok
    try:
        r = fn(); print(f"PASS {name}: {r}")
    except Exception as e:
        ok = False; print(f"FAIL {name}: {e!r}")

# Plain HTTP via B -> SOCKS5 -> A -> direct to local origin (A's upstream may be the sandbox proxy,
# which can't reach 127.0.0.1, so test plain HTTP with a direct-only chain)
c = lp.LocalProxyServer(lp.free_port(), lp.Upstream("direct"), log); c.start()
d = lp.LocalProxyServer(lp.free_port(), lp.Upstream("socks5", "127.0.0.1", c.server_address[1]), log); d.start()
op2 = urllib.request.build_opener(urllib.request.ProxyHandler({"http": f"http://127.0.0.1:{d.server_address[1]}"}))
check("plain HTTP through socks chain", lambda: op2.open(f"http://127.0.0.1:{oport}/x?y=1", timeout=10).read().decode())

def socks_client():
    s = socket.create_connection(("127.0.0.1", d.server_address[1]))
    s.sendall(b"\x05\x01\x00"); assert s.recv(2) == b"\x05\x00"
    host = b"127.0.0.1"
    s.sendall(b"\x05\x01\x00\x03" + bytes([len(host)]) + host + struct.pack(">H", oport))
    assert lp.recv_exact(s, 10)[1] == 0
    s.sendall(b"GET /socks HTTP/1.0\r\nHost: x\r\n\r\n")
    data = b""
    while (chunk := s.recv(4096)): data += chunk
    return data.split(b"\r\n\r\n", 1)[1].decode()
check("SOCKS5 client", socks_client)

check("HTTPS CONNECT through HTTP+SOCKS chain (pypi.org)",
      lambda: f"status {opener.open('https://pypi.org/simple/pip/', timeout=30).status}")
def bad_upstream():
    try:
        lp.Upstream("socks5", "127.0.0.1", 1).connect("example.com", 80, 3)
    except lp.ProxyError as e:
        return f"clean error: {e}"
    raise AssertionError("expected an error")
check("unreachable upstream gives clean error", bad_upstream)
check("URL parsing", lambda: vars(lp.Upstream.from_url("socks5://u:p%40ss@1.2.3.4:1081")))
check("password masking", lambda: lp.mask_url("http://user:secret@h:1"))
for s in (a, b, c, d): s.stop()
print("ALL PASSED" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
