# -*- coding: utf-8 -*-
"""
元宝搜索 · 信源体检器（本地界面）
================================

双击 启动.bat（或命令行 python app.py），浏览器会自动打开搜索界面。
key 在 config.py 里，不需要环境变量。
"""

import argparse
import json
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

try:
    import config  # noqa: E402
except ImportError:
    print("\n找不到 config.py。\n请把 config.example.py 复制一份，改名为 config.py，再填入你的 key。\n")
    raise SystemExit(2)
import core    # noqa: E402

UI_FILE = HERE / "ui.html"


def _json(obj, code=200):
    return code, json.dumps(obj, ensure_ascii=False).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "SourceLens/1.0"

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        u = urlparse(self.path)

        if u.path in ("/", "/index.html"):
            if not UI_FILE.exists():
                self._send(500, "缺少 ui.html", "text/plain; charset=utf-8")
                return
            self._send(200, UI_FILE.read_bytes(), "text/html; charset=utf-8")
            return

        if u.path == "/favicon.ico":
            self._send(204, b"")
            return

        if u.path == "/api/search":
            self._handle_search(u)
            return

        self._send(404, "not found", "text/plain; charset=utf-8")

    def _handle_search(self, u):
        qs = parse_qs(u.query)
        q = (qs.get("q") or [""])[0].strip()
        if not q:
            self._send(*_json({"error": "请输入要查的问题"}, 400))
            return

        key = (config.WSA_API_KEY or "").strip()
        if not key or "你的key" in key:
            self._send(*_json({"error": "还没有填 key。打开 config.py，把 WSA_API_KEY 换成你的服务密钥，保存后重新启动。"}, 400))
            return

        try:
            cnt = int((qs.get("cnt") or [config.DEFAULT_CNT])[0])
            mode = int((qs.get("mode") or [config.DEFAULT_MODE])[0])
        except ValueError:
            self._send(*_json({"error": "参数不对"}, 400))
            return
        cnt = min(max(cnt, 10), 50)
        mode = mode if mode in (0, 1, 2) else 2
        fresh = (qs.get("fresh") or [config.DEFAULT_FRESHNESS])[0]

        t0 = time.time()
        try:
            payload = core.search(q, key, cnt=cnt, mode=mode, freshness=fresh)
            docs, meta = core.parse_pages(payload)
            if not docs:
                self._send(*_json({"error": f"接口没返回结果。Msg={meta.get('msg') or '（无）'}", "meta": meta}, 200))
                return
            rep = core.analyze(q, docs)
            rep["meta"] = meta
            rep["query"] = q
            rep["params"] = {"cnt": cnt, "mode": mode, "freshness": fresh}
            rep["elapsed"] = round(time.time() - t0, 2)
            self._send(*_json(rep))
        except Exception as e:  # 网络、额度、参数错误都走这里
            self._send(*_json({"error": str(e)}, 500))

    def log_message(self, fmt, *args):
        print(f"[{time.strftime('%H:%M:%S')}] {fmt % args}")


def serve(port, host, open_browser):
    httpd = None
    last = None
    for p in range(port, port + 12):
        try:
            httpd = ThreadingHTTPServer((host, p), Handler)
            port = p
            break
        except OSError as e:
            last = e
    if httpd is None:
        raise SystemExit(f"端口被占用，最后一个错误：{last}")

    url = f"http://{host}:{port}"
    print("=" * 52)
    print("  元宝搜索 · 信源体检器")
    print(f"  地址：{url}")
    print("  关闭这个窗口即停止服务")
    print("=" * 52)

    if open_browser:
        threading.Timer(0.7, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        httpd.server_close()


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="元宝搜索 · 信源体检器")
    ap.add_argument("--port", type=int, default=getattr(config, "DEFAULT_PORT", 8765))
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args(argv)
    serve(a.port, a.host, not a.no_browser)


if __name__ == "__main__":
    main()
