"""O "LLM Wiki": le o vault do Obsidian, ingere conversas em notas de conceito (com [[links]]),
escreve as cores do grafo e respeita edicoes/delecoes feitas pelo usuario no Obsidian.
Expoe read_vault() e write_note() para os outros modulos."""
import argparse
import json
import os
import re
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

VAULT = Path(os.getenv("OBSIDIAN_VAULT_PATH") or (Path.home() / "AIWikiVault")).expanduser()
DATA = Path(__file__).resolve().parent / "data"
MOCK = Path(__file__).resolve().parent / "mock"
STATE_FILE = ".wiki_state.json"
MERGE_LISTS = ("tags", "conversations", "source_urls")


def _safe_name(title: str) -> str:
    """Nome de arquivo valido no Windows e no Obsidian."""
    return re.sub(r'[<>:"/\\|?*#^\[\]]', "", str(title)).strip().rstrip(". ")[:80].strip()


def _parse_note(text: str) -> tuple[dict, str]:
    """Separa frontmatter YAML do corpo. Tolerante: sem frontmatter (ou YAML quebrado) -> {}."""
    text = text.lstrip("\ufeff")
    lines = text.splitlines(keepends=True)
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                try:
                    loaded = yaml.safe_load("".join(lines[1:i]))
                except yaml.YAMLError:
                    loaded = None
                return (loaded if isinstance(loaded, dict) else {}), "".join(lines[i + 1:])
    return {}, text


def _compose(frontmatter: dict, body: str) -> str:
    body = str(body).strip()
    if not frontmatter:
        return f"{body}\n"
    header = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False).strip()
    return f"---\n{header}\n---\n\n{body}\n"


def read_vault() -> dict:
    """titulo -> {"path", "frontmatter", "body", "links"} para todos os .md do vault (fora de .obsidian)."""
    vault = {}
    if not VAULT.exists():
        return vault
    for path in VAULT.rglob("*.md"):
        if ".obsidian" in path.parts:
            continue
        try:
            frontmatter, body = _parse_note(path.read_text(encoding="utf-8"))
        except OSError as error:
            print(f"[obsidian] nao consegui ler {path}: {error}")
            continue
        links = []
        for raw in re.findall(r"\[\[([^\]]+)\]\]", body):
            target = raw.split("|", 1)[0].split("#", 1)[0].strip()
            if target and target not in links:
                links.append(target)
        vault[path.stem] = {
            "path": str(path), "frontmatter": frontmatter, "body": body, "links": links,
        }
    return vault


def _load_state() -> dict:
    state = {"created": [], "ingested": [], "ignored": []}
    path = VAULT / STATE_FILE
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            print(f"[obsidian] state invalido, recomecando: {error}")
            loaded = {}
        if isinstance(loaded, dict):
            for key in state:
                if isinstance(loaded.get(key), list):
                    state[key] = [str(item) for item in loaded[key]]
    return state


def _save_state(state: dict) -> None:
    VAULT.mkdir(parents=True, exist_ok=True)
    (VAULT / STATE_FILE).write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _load_json(name: str):
    for folder in (DATA, MOCK):
        path = folder / name
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                print(f"[obsidian] {path} invalido: {error}")
    return None


def write_note(title: str, body: str, frontmatter: dict) -> str:
    """Cria a nota ou ACRESCENTA conteudo/mescla listas no fim dela. Nunca reescreve texto existente.
    Retorna "created", "appended" ou "ignored" (nota que o usuario deletou)."""
    state = _load_state()
    name = _safe_name(title)
    if not name:
        return "ignored"
    if any(_safe_name(item).lower() == name.lower() for item in state["ignored"]):
        return "ignored"

    path = VAULT / f"{name}.md"
    if not path.exists():
        VAULT.mkdir(parents=True, exist_ok=True)
        path.write_text(_compose(frontmatter or {}, body), encoding="utf-8")
        if name not in state["created"]:
            state["created"].append(name)
            _save_state(state)
        return "created"

    existing = path.read_text(encoding="utf-8")
    existing_fm, existing_body = _parse_note(existing)
    changed = False
    for key in MERGE_LISTS:
        new_values = (frontmatter or {}).get(key)
        if not isinstance(new_values, list) or not new_values:
            continue
        current = existing_fm.get(key)
        if current is None:
            existing_fm[key] = list(new_values)
            changed = True
        elif isinstance(current, list):
            for value in new_values:
                if value not in current:
                    current.append(value)
                    changed = True
    addition = str(body).strip()
    if addition and addition not in existing_body.strip():
        existing_body = existing_body.rstrip("\n") + "\n\n" + addition
        changed = True
    if changed:
        path.write_text(_compose(existing_fm, existing_body), encoding="utf-8")
    return "appended"


def ensure_graph_colors() -> None:
    """Cria/atualiza .obsidian/graph.json preservando as outras chaves. Ordem das cores importa."""
    graph_path = VAULT / ".obsidian" / "graph.json"
    graph = {}
    if graph_path.exists():
        try:
            loaded = json.loads(graph_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                graph = loaded
        except (OSError, json.JSONDecodeError) as error:
            print(f"[obsidian] graph.json invalido, recriando: {error}")
    graph["colorGroups"] = [
        {"query": f"tag:{tag}", "color": {"a": 1, "rgb": int(color, 16)}}
        for tag, color in (
            ("#alert/brain-rot", "ef4444"),
            ("#source/firecrawl", "22c55e"),
            ("#source/prompt", "3b82f6"),
        )
    ]
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    graph_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")


def sync_conversations_to_obsidian(use_llm: bool = True) -> dict:
    """Ingere as conversas ainda nao ingeridas como notas de conceito no vault."""
    state = _load_state()
    removed = [name for name in state["created"] if not (VAULT / f"{name}.md").exists()]
    for name in removed:
        state["created"].remove(name)
        if name not in state["ignored"]:
            state["ignored"].append(name)
            print(f"[obsidian] nota '{name}' sumiu do vault: usuario deletou, sera ignorada")
    if removed:
        _save_state(state)

    conversations = _load_json("conversations.json")
    diagnostics = _load_json("diagnostics.json")
    if not isinstance(conversations, list):
        print("[obsidian] nenhuma conversa encontrada em data/ nem mock/")
        conversations = []
    raw_diagnoses = diagnostics.get("conversation_diagnoses", []) if isinstance(diagnostics, dict) else diagnostics
    diagnoses = {
        str(item.get("conversation_id")): item
        for item in raw_diagnoses or [] if isinstance(item, dict)
    }
    existing = list(read_vault())
    summary = {"new_conversations": 0, "created": 0, "appended": 0, "ignored": 0, "vault": str(VAULT)}

    for conversation in conversations:
        if not isinstance(conversation, dict):
            continue
        cid = str(conversation.get("id") or "")
        if not cid or cid in state["ingested"]:
            continue
        diagnosis = diagnoses.get(cid) or {}
        concepts = []
        if use_llm:
            try:
                import llm
                blocks, total = [], 0
                for message in conversation.get("messages") or []:
                    role = message.get("role")
                    text = str(message.get("content") or "")[:1500 if role == "user" else 500]
                    block = f"{'USUARIO' if role == 'user' else 'IA'}: {text}\n"
                    if total + len(block) > 8000:
                        break
                    blocks.append(block)
                    total += len(block)
                prompt = f"""Voce mantem uma wiki de conceitos em Obsidian (estilo LLM Wiki) a partir das conversas do usuario.

Conceitos que ja existem no vault (reutilize EXATAMENTE estes titulos quando o assunto for o mesmo, para nao duplicar notas):
{', '.join(existing[:200]) or '(vault vazio)'}

Conversa:
{''.join(blocks)}

Extraia de 1 a 5 conceitos TECNICOS e ESPECIFICOS realmente discutidos nesta conversa (nada generico como "Programacao" ou "Estudo"). No summary, escreva de 2 a 5 bullets em markdown sobre o que o usuario discutiu, aprendeu ou decidiu sobre esse conceito. Em related, liste titulos de conceitos relacionados.

Responda APENAS com JSON: {{"concepts": [{{"title": "Nome Do Conceito", "summary": "- bullet 1\\n- bullet 2", "related": ["Outro Conceito"]}}]}}"""
                answer = llm.ask_json(prompt)
                raw_concepts = answer.get("concepts") if isinstance(answer, dict) else answer
                for item in raw_concepts or []:
                    if isinstance(item, dict) and str(item.get("title") or "").strip():
                        related = item.get("related") if isinstance(item.get("related"), list) else []
                        concepts.append({
                            "title": str(item["title"]).strip(),
                            "summary": str(item.get("summary") or "").strip(),
                            "related": [str(r).strip() for r in related if str(r).strip()],
                        })
            except Exception as error:
                print(f"[obsidian] LLM falhou em '{conversation.get('title')}': {error}")

        if not concepts:
            topics = [str(t).strip() for t in diagnosis.get("topics") or [] if str(t).strip()]
            concepts = [
                {
                    "title": topic.title(),
                    "summary": f"- Discutido na conversa: {conversation.get('title') or 'sem titulo'}",
                    "related": [other.title() for other in topics if other != topic],
                }
                for topic in topics
            ]

        try:
            severity = int(diagnosis.get("severity") or 0)
        except (TypeError, ValueError):
            severity = 0
        tags = ["source/prompt"]
        if diagnosis.get("category") in ("blind_delegation", "frustration_loop") and severity >= 3:
            tags.append("alert/brain-rot")

        heading = str(conversation.get("title") or "Conversa").replace("\n", " ").strip()
        date = str(conversation.get("created_at") or "")[:10] or "sem-data"
        source = str(conversation.get("source") or "desconhecido")
        seen = set()
        for concept in concepts:
            title = concept["title"].strip()
            if not title or title.lower() in seen:
                continue
            seen.add(title.lower())
            summary_text = concept["summary"] or f"- Discutido na conversa: {heading}"
            related = [r for r in concept["related"] if r.lower() != title.lower()]
            body = f"\n## {heading} ({date}, {source})\n{summary_text}\n"
            if related:
                body += "\nRelacionados: " + " ".join(f"[[{r}]]" for r in related) + "\n"
            result = write_note(title, body, {
                "type": "concept", "source": "prompt", "tags": list(tags), "conversations": [cid],
            })
            summary[result] += 1
            if title not in existing:
                existing.append(title)

        state = _load_state()
        if cid not in state["ingested"]:
            state["ingested"].append(cid)
            _save_state(state)
        summary["new_conversations"] += 1
        print(f"[obsidian] conversa '{heading}' ingerida ({len(seen)} conceito(s))")

    ensure_graph_colors()
    _save_state(_load_state())
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingere conversas como notas de conceito no vault Obsidian.")
    parser.add_argument("--no-llm", action="store_true", help="nao usa LLM: usa os topics do diagnostico")
    args = parser.parse_args()
    print(json.dumps(sync_conversations_to_obsidian(use_llm=not args.no_llm), ensure_ascii=False, indent=2))
