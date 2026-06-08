#!/usr/bin/env python3
"""📡 持仓清单轻量后端（端口18790，零依赖）
   纯标准库实现，无需 uvicorn/fastapi。"""
import json, os, sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WATCH_CONFIG = os.path.join(WORKSPACE, "config", "stocks.json")
TEMPLATE_CONFIG = os.path.join(WORKSPACE, "scripts", "template-stocks.json")

def _get_sector(code):
    if code.startswith("688"): return "科技/半导体"
    if code.startswith("300"): return "创业板/科技"
    if code.startswith("60"):  return "主板"
    if code.startswith(("000","002","001","003")): return "深市主板"
    if code.startswith("8"):   return "北交所"
    return "其他"

def _load():
    with open(WATCH_CONFIG) as f:
        return json.load(f)

def _save(data):
    with open(WATCH_CONFIG, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    with open(TEMPLATE_CONFIG, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

class Handler(BaseHTTPRequestHandler):
    def _json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
    
    def do_OPTIONS(self):
        self._json({"ok": True})
    
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/watchlist":
            data = _load()
            self._json({"codes": [s["code"] for s in data["watchlist"]],
                        "stocks": data["watchlist"]})
        else:
            self._json({"error": "not found"}, 404)
    
    def do_POST(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        if parsed.path == "/watchlist/add":
            code = (qs.get("code") or [""])[0]
            name = (qs.get("name") or [""])[0]
            if not code or not name:
                return self._json({"error": "missing code/name"}, 400)
            data = _load()
            if any(s["code"] == code for s in data["watchlist"]):
                return self._json({"status": "exists", "message": "已在持仓中"})
            sector = qs.get("sector", [_get_sector(code)])[0]
            data["watchlist"].append({"code": code, "name": name, "sector": sector})
            data["version"] = "2026-06-07"
            _save(data)
            self._json({"status": "ok", "message": f"{name} 已加入持仓", "total": len(data["watchlist"])})
        else:
            self._json({"error": "not found"}, 404)
    
    def do_DELETE(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        if parsed.path == "/watchlist/remove":
            code = (qs.get("code") or [""])[0]
            if not code:
                return self._json({"error": "missing code"}, 400)
            data = _load()
            before = len(data["watchlist"])
            data["watchlist"] = [s for s in data["watchlist"] if s["code"] != code]
            data["version"] = "2026-06-07"
            _save(data)
            self._json({"status": "ok", "message": "已移除", "total": len(data["watchlist"])})
        else:
            self._json({"error": "not found"}, 404)
    
    def log_message(self, format, *args):
        sys.stderr.write("[Watchlist API] %s\n" % (format % args))

if __name__ == "__main__":
    port = 18790
    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"📡 Watchlist API running on http://127.0.0.1:{port}")
    server.serve_forever()
