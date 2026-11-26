"""App desktop local: FastAPI + index.html. Rotas nunca quebram: devolvem {"ok": ...} com status 200."""
import argparse
import json
import os
import threading
import webbrowser
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse

BASE = Path(__file__).resolve().parent
try:
    from dotenv import load_dotenv
    load_dotenv(BASE / ".env")
except ImportError:
    pass

app = FastAPI(title="Cognitive Wiki OS")


@app.get("/")
def home():
    return FileResponse(BASE / "index.html", media_type="text/html")


@app.post("/api/collect")
def api_collect():
    try:
        import collector
        conversations = collector.collect()
        by_source = {}
        for conversation in conversations:
            source = conversation.get("source", "desconhecido")
            by_source[source] = by_source.get(source, 0) + 1
        return {"ok": True, "total": len(conversations), "by_source": by_source}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/web-extract/{platform}")
def api_web_extract(platform: str):
    if platform not in ("chatgpt", "claude", "gemini"):
        return {"ok": False, "error": f"plataforma invalida: {platform}"}
    try:
        import collector
        return {"ok": True, "result": collector.run_web_extraction(platform)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/diagnose")
def api_diagnose():
    try:
        import diagnostics
        return {"ok": True, "result": diagnostics.run_cognitive_diagnosis()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/wiki")
def api_wiki():
    try:
        import obsidian
        return {"ok": True, "result": obsidian.sync_conversations_to_obsidian()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/frontier")
def api_frontier():
    try:
        import research
        return {"ok": True, "result": research.expand_frontier()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/email")
def api_email():
    try:
        import integrations
        return {"ok": True, "result": integrations.send_report()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/checkout")
def api_checkout():
    try:
        import integrations
        return {"url": integrations.create_checkout()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/status")
def api_status():
    mock = False
    try:
        diagnostics = json.loads((BASE / "data" / "diagnostics.json").read_text(encoding="utf-8"))
    except Exception:
        mock = True
        try:
            diagnostics = json.loads((BASE / "mock" / "diagnostics.json").read_text(encoding="utf-8"))
        except Exception:
            diagnostics = None
    try:
        conversations = len(json.loads((BASE / "data" / "conversations.json").read_text(encoding="utf-8")))
    except Exception:
        conversations = 0
    vault = Path(os.environ.get("OBSIDIAN_VAULT_PATH") or "~/AIWikiVault").expanduser()
    return {"diagnostics": diagnostics, "mock": mock, "conversations": conversations, "vault": str(vault)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cognitive Wiki OS")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    url = f"http://127.0.0.1:{args.port}"
    print(f"Cognitive Wiki OS em {url}")
    if not args.no_browser:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    uvicorn.run(app, host="127.0.0.1", port=args.port)
