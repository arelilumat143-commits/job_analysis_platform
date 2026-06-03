"""
开发用热重载服务器 — 文件改了才刷新，不改不动。
用法: python scripts/dev_server.py
浏览器: http://localhost:8503/playground.html
"""

import http.server
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"

WATCH_SCRIPT = """
<script>
(function() {
    var _mtime = 0;
    setInterval(function() {
        fetch('/__mtime__').then(function(r) {
            return r.text();
        }).then(function(t) {
            var m = parseInt(t);
            if (_mtime && m !== _mtime) location.reload();
            _mtime = m;
        });
    }, 800);
})();
</script>
</body>
"""


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/__mtime__":
            mtime = int(os.path.getmtime(WEB_DIR / "playground.html"))
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(str(mtime).encode())
            return

        path = self.path.split("?")[0] or "/playground.html"
        fp = WEB_DIR / path.lstrip("/")
        if not fp.is_file():
            self.send_error(404)
            return

        body = fp.read_bytes()
        if fp.suffix == ".html":
            body = body.replace(b"</body>", WATCH_SCRIPT.encode() + b"</body>")

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(f"[dev] {args[0]}")


if __name__ == "__main__":
    os.chdir(WEB_DIR)
    srv = http.server.HTTPServer(("0.0.0.0", 8503), Handler)
    print("热重载服务器 http://localhost:8503/playground.html")
    print("修改代码后浏览器自动刷新，不修改不动")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.server_close()
