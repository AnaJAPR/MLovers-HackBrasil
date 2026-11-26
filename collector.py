"""Coleta conversas dos logs locais (Claude Code, Codex) e dos exports em data/imports/
(ChatGPT, Claude.ai, Gemini) para data/conversations.json no contrato do AGENTS.md.
Nao usa rede nem LLM."""
import argparse
import hashlib
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
IMPORTS = DATA / "imports"
SYSTEM_REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)


def _iso(value):
    """Epoch ou string ISO -> string ISO 8601. Valor irreconhecivel volta como veio."""
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
    if isinstance(value, str):
        text = value.strip()
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).isoformat()
        except ValueError:
            return text
    return ""


def _text(content):
    """Extrai so o texto de content (string ou lista de blocos/partes)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                text = block
            elif isinstance(block, dict):
                text = block.get("text") or ""
            else:
                text = ""
            if text.strip():
                parts.append(text)
        return "\n".join(parts)
    return ""


def _session(source, session_id, title, messages, created_at=""):
    """Monta o dict do contrato, juntando falas consecutivas do mesmo role."""
    merged = []
    for msg in messages:
        if merged and merged[-1]["role"] == msg["role"]:
            merged[-1]["content"] += "\n\n" + msg["content"]
        else:
            merged.append(dict(msg))
    if not merged or not any(m["role"] == "user" for m in merged):
        return None
    title = " ".join(str(title or "").split())
    if not title:
        first = next(m["content"] for m in merged if m["role"] == "user")
        title = " ".join(first.split())[:60]
    return {
        "id": hashlib.sha1(f"{source}:{session_id}".encode("utf-8")).hexdigest()[:16],
        "source": source,
        "title": title,
        "created_at": merged[0]["timestamp"] if merged[0]["timestamp"] else _iso(created_at),
        "messages": merged,
    }


def _read_claude_code():
    out = []
    for path in sorted((Path.home() / ".claude" / "projects").glob("**/*.jsonl")):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            print(f"[claude_code] {path.name}: ilegivel ({exc}), pulando")
            continue
        session_id, title, messages = path.stem, "", []
        for line in lines:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            if isinstance(obj.get("aiTitle"), str) and obj["aiTitle"].strip():
                title = obj["aiTitle"].strip()
            if obj.get("type") not in ("user", "assistant") or obj.get("isSidechain"):
                continue
            msg = obj.get("message") if isinstance(obj.get("message"), dict) else {}
            role = msg.get("role")
            if role not in ("user", "assistant"):
                continue
            session_id = obj.get("sessionId") or session_id
            text = _text(msg.get("content"))
            if role == "user":
                text = SYSTEM_REMINDER.sub(" ", text).strip()
                if not text or text.startswith("<") or text.startswith("Caveat:"):
                    continue
            text = text.strip()
            if text:
                messages.append({"role": role, "content": text, "timestamp": obj.get("timestamp") or ""})
        conv = _session("claude_code", session_id, title, messages)
        if conv:
            out.append(conv)
    return out


def _read_codex():
    out = []
    for path in sorted((Path.home() / ".codex" / "sessions").glob("**/*.jsonl")):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            print(f"[codex] {path.name}: ilegivel ({exc}), pulando")
            continue
        session_id, messages, subagent = path.stem, [], False
        for line in lines:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            payload = obj.get("payload") if isinstance(obj.get("payload"), dict) else {}
            if obj.get("type") == "session_meta":
                session_id = payload.get("id") or session_id
                if "subagent" in str(payload.get("source", "")).lower():
                    subagent = True
                    break
            elif (obj.get("type") == "response_item" and payload.get("type") == "message"
                  and payload.get("role") in ("user", "assistant")):
                role = payload["role"]
                text = _text(payload.get("content")).strip()
                if role == "user" and (text.startswith("<") or text.startswith("# AGENTS.md")):
                    continue
                if text:
                    messages.append({"role": role, "content": text,
                                     "timestamp": obj.get("timestamp") or payload.get("timestamp") or ""})
        if subagent:
            continue
        conv = _session("codex", session_id, "", messages)
        if conv:
            out.append(conv)
    return out


def _import_chatgpt(items):
    out = []
    for index, conv in enumerate(items):
        messages = []
        for node in (conv.get("mapping") or {}).values():
            msg = (node or {}).get("message") or {}
            role = (msg.get("author") or {}).get("role")
            if role not in ("user", "assistant"):
                continue
            content = msg.get("content") if isinstance(msg.get("content"), dict) else {}
            text = _text(content.get("parts")).strip()
            if text:
                messages.append({"role": role, "content": text,
                                 "timestamp": _iso(msg.get("create_time"))})
        messages.sort(key=lambda m: (not m["timestamp"], m["timestamp"]))
        conv_id = conv.get("id") or conv.get("conversation_id") or f"{conv.get('title')}:{index}"
        found = _session("chatgpt_web", conv_id, conv.get("title") or "", messages, conv.get("create_time"))
        if found:
            out.append(found)
    return out


def _import_claude(items):
    out = []
    for index, conv in enumerate(items):
        messages = []
        for msg in conv.get("chat_messages") or []:
            role = {"human": "user", "assistant": "assistant"}.get(msg.get("sender"))
            if not role:
                continue
            text = msg.get("text")
            if not isinstance(text, str) or not text.strip():
                text = _text(msg.get("content"))
            if text and text.strip():
                messages.append({"role": role, "content": text.strip(),
                                 "timestamp": _iso(msg.get("created_at"))})
        conv_id = conv.get("uuid") or f"{conv.get('name')}:{index}"
        found = _session("claude_web", conv_id, conv.get("name") or "", messages, conv.get("created_at"))
        if found:
            out.append(found)
    return out


def _import_gemini(items):
    out = []
    for index, item in enumerate(items):
        title = re.sub(r"^(Prompted|Perguntou)\s*:?\s*", "", str(item.get("title") or ""), flags=re.I).strip()
        created = _iso(item.get("time"))
        messages = []
        if title:
            messages.append({"role": "user", "content": title, "timestamp": created})
        reply = []
        for block in item.get("safeHtmlItem") or []:
            if isinstance(block, dict):
                text = block.get("html") or block.get("text") or ""
                reply.append(re.sub(r"<[^>]+>", " ", str(text)).strip())
        reply = "\n".join(part for part in reply if part)
        if reply:
            messages.append({"role": "assistant", "content": reply, "timestamp": created})
        conv_id = item.get("titleUrl") or f"{created}:{title}:{index}"
        found = _session("gemini_web", conv_id, title, messages, created)
        if found:
            out.append(found)
    return out


def _read_imports():
    if not IMPORTS.is_dir():
        return []
    out = []
    for path in sorted(IMPORTS.iterdir()):
        if not path.is_file() or path.suffix.lower() not in (".zip", ".json"):
            continue
        try:
            if path.suffix.lower() == ".zip":
                with zipfile.ZipFile(path) as zf:
                    names = [n for n in zf.namelist() if Path(n).name == "conversations.json"]
                    if not names:
                        print(f"[import] {path.name}: zip sem conversations.json, pulando")
                        continue
                    raw = zf.read(names[0]).decode("utf-8", "replace")
            else:
                raw = path.read_text(encoding="utf-8", errors="replace")
            data = json.loads(raw)
        except Exception as exc:
            print(f"[import] {path.name}: ilegivel ({exc}), pulando")
            continue
        if isinstance(data, dict):
            data = data.get("conversations")
        if not isinstance(data, list) or not data:
            print(f"[import] {path.name}: formato desconhecido, pulando")
            continue
        sample = next((item for item in data if isinstance(item, dict)), {})
        if "mapping" in sample:
            found, label = _import_chatgpt(data), "chatgpt_web"
        elif "chat_messages" in sample:
            found, label = _import_claude(data), "claude_web"
        elif ("safeHtmlItem" in sample or "subtitles" in sample
              or str(sample.get("title", "")).lower().startswith(("prompted", "perguntou"))):
            found, label = _import_gemini(data), "gemini_web"
        else:
            print(f"[import] {path.name}: formato desconhecido, pulando")
            continue
        print(f"[import] {path.name}: {len(found)} conversas ({label})")
        out.extend(found)
    return out


def collect(limit=200):
    """Le logs locais + exports, grava as `limit` conversas mais recentes em data/conversations.json."""
    found = _read_claude_code() + _read_codex() + _read_imports()
    unique = {}
    for conv in found:
        old = unique.get(conv["id"])
        if not old or len(conv["messages"]) > len(old["messages"]):
            unique[conv["id"]] = conv
    convs = sorted(unique.values(), key=lambda c: c.get("created_at") or "", reverse=True)[:limit]
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "conversations.json").write_text(
        json.dumps(convs, indent=2, ensure_ascii=False), encoding="utf-8")
    counts = {}
    for conv in convs:
        counts[conv["source"]] = counts.get(conv["source"], 0) + 1
    resumo = ", ".join(f"{source}={n}" for source, n in sorted(counts.items())) or "nenhuma"
    print(f"[collect] {len(unique)} encontradas, {len(convs)} gravadas ({resumo})")
    return convs


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Coleta conversas locais e exports para data/conversations.json")
    parser.add_argument("--limit", type=int, default=200)
    collect(parser.parse_args().limit)
