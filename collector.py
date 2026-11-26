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
# prefixos de blocos gerados pelo harness (nao sao fala humana)
NOISE = ("<system-reminder", "<command-", "<local-command", "<task-notification", "<ide_",
         "<environment_context", "<user_instructions", "<permissions", "Caveat:", "# AGENTS.md")


def _iso(value):
    """Epoch (s ou ms) ou string ISO -> ISO 8601 em UTC; irreconhecivel -> ''."""
    try:
        if isinstance(value, (int, float)):
            if value != value:  # NaN
                return ""
            if value > 1e11:  # epoch em milissegundos
                value /= 1000
            return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
        if isinstance(value, str) and value.strip():
            stamp = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            if not stamp.tzinfo:
                stamp = stamp.replace(tzinfo=timezone.utc)
            return stamp.astimezone(timezone.utc).isoformat()
    except (ValueError, OverflowError, OSError):
        pass
    return ""


def _text(content, noise=False):
    """Texto de content (string ou lista de blocos). noise=True descarta blocos de harness."""
    parts = []
    for block in content if isinstance(content, list) else [content]:
        text = block if isinstance(block, str) else block.get("text") if isinstance(block, dict) else None
        if isinstance(text, str):
            text = (SYSTEM_REMINDER.sub(" ", text) if noise else text).strip()
            if text and not (noise and text.startswith(NOISE)):
                parts.append(text)
    return "\n".join(parts)


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
        session_id, title, messages, sdk = path.stem, "", [], False
        try:
            with path.open(encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(obj, dict):
                        continue
                    if str(obj.get("entrypoint") or "").lower().startswith("sdk"):
                        sdk = True  # chamada automatizada (ex: llm.py), nao conversa humana
                        break
                    if isinstance(obj.get("aiTitle"), str) and obj["aiTitle"].strip():
                        title = obj["aiTitle"].strip()
                    if obj.get("type") not in ("user", "assistant") or obj.get("isSidechain"):
                        continue
                    msg = obj.get("message") if isinstance(obj.get("message"), dict) else {}
                    role = msg.get("role")
                    if role not in ("user", "assistant"):
                        continue
                    session_id = obj.get("sessionId") or session_id
                    text = _text(msg.get("content"), noise=role == "user")
                    if text:
                        messages.append({"role": role, "content": text,
                                         "timestamp": _iso(obj.get("timestamp"))})
        except OSError as exc:
            print(f"[claude_code] {path.name}: ilegivel ({exc}), pulando")
            continue
        if sdk:
            continue
        conv = _session("claude_code", session_id, title, messages)
        if conv:
            out.append(conv)
    return out


def _read_codex():
    out = []
    for path in sorted((Path.home() / ".codex" / "sessions").glob("**/*.jsonl")):
        session_id, messages, subagent = path.stem, [], False
        try:
            with path.open(encoding="utf-8", errors="replace") as fh:
                for line in fh:
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
                        text = _text(payload.get("content"), noise=role == "user")
                        if text:
                            messages.append({"role": role, "content": text,
                                             "timestamp": _iso(obj.get("timestamp") or payload.get("timestamp") or "")})
        except OSError as exc:
            print(f"[codex] {path.name}: ilegivel ({exc}), pulando")
            continue
        if subagent:
            continue
        conv = _session("codex", session_id, "", messages)
        if conv:
            out.append(conv)
    return out


def _import_chatgpt(items):
    out = []
    for index, conv in enumerate(items):
        if not isinstance(conv, dict):
            continue
        try:
            mapping = conv.get("mapping") if isinstance(conv.get("mapping"), dict) else {}
            nodes = list(mapping.values())
            if conv.get("current_node"):  # so o ramo ativo; respostas regeneradas abandonadas ficam de fora
                nodes, node_id = [], conv["current_node"]
                while node_id:
                    node = mapping.get(node_id)
                    if not isinstance(node, dict):
                        break
                    nodes.append(node)
                    node_id = node.get("parent")
                nodes.reverse()
            messages = []
            for node in nodes:
                msg = node.get("message") if isinstance(node, dict) else None
                if not isinstance(msg, dict):
                    continue
                role = (msg.get("author") or {}).get("role")
                if role not in ("user", "assistant"):
                    continue
                content = msg.get("content") if isinstance(msg.get("content"), dict) else {}
                text = _text(content.get("parts"))
                if text:
                    messages.append({"role": role, "content": text,
                                     "timestamp": _iso(msg.get("create_time"))})
            if not conv.get("current_node"):
                messages.sort(key=lambda m: (not m["timestamp"], m["timestamp"]))
            conv_id = conv.get("id") or conv.get("conversation_id") or f"{conv.get('title')}:{index}"
            found = _session("chatgpt_web", conv_id, conv.get("title") or "", messages, conv.get("create_time"))
        except Exception as exc:
            print(f"[chatgpt_web] item {index}: {exc}, pulando")
            continue
        if found:
            out.append(found)
    return out


def _import_claude(items):
    out = []
    for index, conv in enumerate(items):
        if not isinstance(conv, dict):
            continue
        try:
            messages = []
            for msg in conv.get("chat_messages") or []:
                if not isinstance(msg, dict):
                    continue
                role = {"human": "user", "assistant": "assistant"}.get(msg.get("sender"))
                if not role:
                    continue
                text = msg.get("text")
                if not isinstance(text, str) or not text.strip():
                    text = _text(msg.get("content"))
                if text.strip():
                    messages.append({"role": role, "content": text.strip(),
                                     "timestamp": _iso(msg.get("created_at"))})
            conv_id = conv.get("uuid") or f"{conv.get('name')}:{index}"
            found = _session("claude_web", conv_id, conv.get("name") or "", messages, conv.get("created_at"))
        except Exception as exc:
            print(f"[claude_web] item {index}: {exc}, pulando")
            continue
        if found:
            out.append(found)
    return out


def _import_gemini(items):
    out = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        try:
            title = re.sub(r"^(Prompted|Perguntou)\s*:?\s*", "", str(item.get("title") or ""), flags=re.I).strip()
            created = _iso(item.get("time"))
            messages = []
            if title:
                messages.append({"role": "user", "content": title, "timestamp": created})
            reply = []
            for block in item.get("safeHtmlItem") or []:
                if isinstance(block, dict):
                    text = block.get("html") or block.get("text") or ""
                    if isinstance(text, str):
                        reply.append(re.sub(r"<[^>]+>", " ", text).strip())
            reply = "\n".join(part for part in reply if part)
            if reply:
                messages.append({"role": "assistant", "content": reply, "timestamp": created})
            # cada atividade e um par pergunta/resposta: time+indice evita deduplicar turnos
            conv_id = f"{item.get('titleUrl') or ''}:{item.get('time') or ''}:{index}"
            found = _session("gemini_web", conv_id, title, messages, created)
        except Exception as exc:
            print(f"[gemini_web] item {index}: {exc}, pulando")
            continue
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
                    raws = [zf.read(name).decode("utf-8-sig", "replace") for name in zf.namelist()
                            if re.fullmatch(r"(conversations(-\d+)?|myactivity)\.json",
                                            name.replace("\\", "/").rsplit("/", 1)[-1].lower())]
            else:
                raws = [path.read_text(encoding="utf-8-sig", errors="replace")]
        except Exception as exc:
            print(f"[import] {path.name}: ilegivel ({exc}), pulando")
            continue
        if not raws:
            print(f"[import] {path.name}: nenhum conversations.json/myactivity.json, pulando")
            continue
        for raw in raws:
            try:
                data = json.loads(raw)
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
            except Exception as exc:
                print(f"[import] {path.name}: falha ao importar ({exc}), pulando")
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
    tmp = DATA / "conversations.json.tmp"
    tmp.write_text(json.dumps(convs, indent=2, ensure_ascii=False), encoding="utf-8", errors="replace")
    tmp.replace(DATA / "conversations.json")
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
