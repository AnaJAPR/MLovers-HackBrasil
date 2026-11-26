"""App desktop local: FastAPI + index.html. Rotas nunca quebram: devolvem {"ok": ...} com status 200."""
import argparse
import importlib
import json
import os
import socket
import threading
import traceback
import webbrowser
from pathlib import Path

import sys

import uvicorn
from fastapi import FastAPI, Request

# Windows: console/redirecionamento em cp1252 quebra ao imprimir acentos/emoji das conversas.
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
from fastapi.responses import FileResponse, JSONResponse

BASE = Path(__file__).resolve().parent
try:
    from dotenv import load_dotenv
    load_dotenv(BASE / ".env")
except ImportError:
    pass

app = FastAPI(title="Cognitive Wiki OS")


def call(module, func, *args):
    try:
        return {"ok": True, "result": getattr(importlib.import_module(module), func)(*args)}
    except Exception as e:
        traceback.print_exc()
        return {"ok": False, "error": str(e)}


@app.middleware("http")
async def local_only(request: Request, call_next):
    port = request.scope["server"][1]
    if request.headers.get("host") not in (f"127.0.0.1:{port}", f"localhost:{port}"):
        return JSONResponse({"ok": False, "error": "host nao permitido"}, status_code=403)
    origin = request.headers.get("origin")
    if request.method != "GET" and origin and origin not in (f"http://127.0.0.1:{port}", f"http://localhost:{port}"):
        return JSONResponse({"ok": False, "error": "origem nao permitida"}, status_code=403)
    return await call_next(request)


@app.get("/")
def home():
    return FileResponse(BASE / "index.html", media_type="text/html")


@app.post("/api/collect")
def api_collect():
    out = call("collector", "collect")
    if out["ok"]:  # nao manda as conversas inteiras para a UI, so a contagem
        counts = {}
        for conv in out["result"]:
            counts[conv["source"]] = counts.get(conv["source"], 0) + 1
        out["result"] = {"total": len(out["result"]), "by_source": counts}
    return out


@app.post("/api/web-extract/{platform}")
def api_web_extract(platform: str):
    if platform not in ("chatgpt", "claude", "gemini"):
        return {"ok": False, "error": f"plataforma invalida: {platform}"}
    return call("collector", "run_web_extraction", platform, 50, True)  # botao = sob demanda (force)


@app.post("/api/diagnose")
def api_diagnose():
    return call("diagnostics", "run_cognitive_diagnosis")


@app.post("/api/wiki")
def api_wiki():
    return call("obsidian", "sync_conversations_to_obsidian")


@app.post("/api/frontier")
def api_frontier():
    return call("research", "expand_frontier")


@app.post("/api/email")
def api_email():
    return call("integrations", "send_report")


@app.post("/api/checkout")
def api_checkout():
    return call("integrations", "create_checkout")


@app.get("/api/status")
def api_status():
    mock = False
    error = None
    diag_path = BASE / "data" / "diagnostics.json"
    if diag_path.exists():
        try:
            diagnostics = json.loads(diag_path.read_text(encoding="utf-8-sig"))
        except Exception as e:
            diagnostics, error = None, str(e)
    else:
        mock = True
        try:
            diagnostics = json.loads((BASE / "mock" / "diagnostics.json").read_text(encoding="utf-8-sig"))
        except Exception as e:
            diagnostics, error = None, str(e)
    try:
        conversations = json.loads((BASE / "data" / "conversations.json").read_text(encoding="utf-8-sig"))
        conversations = len(conversations) if isinstance(conversations, list) else 0
    except Exception:
        conversations = 0
    frontier_path = BASE / "data" / "frontier_research.json"
    frontier_mock = not frontier_path.exists()
    if frontier_mock:
        frontier_path = BASE / "mock" / "frontier_research.json"
    try:
        frontier = json.loads(frontier_path.read_text(encoding="utf-8-sig"))
        frontier = frontier if isinstance(frontier, list) else []
    except Exception:
        frontier = []
    vault = Path(os.environ.get("OBSIDIAN_VAULT_PATH") or Path.home() / "AIWikiVault").expanduser()
    return {"diagnostics": diagnostics, "mock": mock, "error": error, "conversations": conversations,
            "vault": str(vault), "frontier": frontier, "frontier_mock": frontier_mock}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cognitive Wiki OS")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    url = f"http://127.0.0.1:{args.port}"
    with socket.socket() as sock:
        if sock.connect_ex(("127.0.0.1", args.port)) == 0:
            print(f"ja existe um app rodando em {url}")
            if not args.no_browser:
                webbrowser.open(url)
            raise SystemExit(0)
    print(f"Cognitive Wiki OS em {url}")
    if not args.no_browser:
        timer = threading.Timer(1.0, webbrowser.open, args=(url,))
        timer.daemon = True
        timer.start()
    uvicorn.run(app, host="127.0.0.1", port=args.port)
