"""O "LLM Wiki": le o vault do Obsidian, ingere conversas em notas de conceito (com [[links]]),
escreve as cores do grafo e respeita edicoes/delecoes feitas pelo usuario no Obsidian.
Expoe read_vault() e write_note() para os outros modulos."""
import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

VAULT = Path(os.getenv("OBSIDIAN_VAULT_PATH") or (Path.home() / "AIWikiVault")).expanduser()
DATA = Path(__file__).resolve().parent / "data"
MOCK = Path(__file__).resolve().parent / "mock"
STATE_FILE = ".wiki_state.json"


def _safe_name(title: str) -> str:
    """Nome de arquivo valido no Windows e no Obsidian."""
    name = re.sub(r'[<>:"/\\|?*#^\[\]\x00-\x1f]', "", str(title)).strip().rstrip(". ")[:80].strip()
    if re.match(r"(?i)^(con|prn|aux|nul|com[1-9]|lpt[1-9])$", name.split(".", 1)[0]):
        name = ("Nota " + name)[:80]
    return name


def _parse_note(text: str) -> tuple[dict, str]:
    """Separa frontmatter YAML do corpo. Sem frontmatter valido, devolve o texto inteiro (nada se perde)."""
    raw = text.lstrip("\ufeff")
    lines = raw.splitlines(keepends=True)
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                try:
                    loaded = yaml.safe_load("".join(lines[1:i]))
                except yaml.YAMLError:
                    return {}, raw
                return (loaded, "".join(lines[i + 1:])) if isinstance(loaded, dict) else ({}, raw)
    return {}, raw


def _compose(frontmatter: dict, body: str) -> str:
    body = str(body).strip()
    if not frontmatter:
        return f"{body}\n"
    header = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False).strip()
    return f"---\n{header}\n---\n\n{body}\n"


def read_vault() -> dict:
    """titulo -> {"path", "frontmatter", "body", "links"} para todos os .md do vault (fora de pastas ocultas)."""
    vault = {}
    if not VAULT.exists():
        return vault
    for path in VAULT.rglob("*.md"):
        if any(part.startswith(".") for part in path.relative_to(VAULT).parts):
            continue
        try:
            frontmatter, body = _parse_note(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as error:
            print(f"[obsidian] nao consegui ler {path}: {error}", file=sys.stderr)
            continue
        if path.stem in vault:
            print(f"[obsidian] stem duplicado '{path.stem}': mantendo {vault[path.stem]['path']}, ignorando {path}", file=sys.stderr)
            continue
        links = []
        for raw in re.findall(r"\[\[([^\]]+)\]\]", body):
            target = raw.split("|", 1)[0].replace("\\", "").split("#", 1)[0].rsplit("/", 1)[-1].strip()
            if target.lower().endswith(".md"):
                target = target[:-3].strip()
            if target and target not in links:
                links.append(target)
        vault[path.stem] = {
            "path": str(path), "frontmatter": frontmatter, "body": body, "links": links,
        }
    return vault


def _load_state() -> dict:
    path = VAULT / STATE_FILE
    if not path.exists():
        return {"created": [], "ingested": [], "ignored": []}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"state do vault ilegivel ({path}): {error}. Corrija o JSON ou apague o arquivo para recomecar."
        ) from error
    if not isinstance(loaded, dict):
        raise RuntimeError(f"state do vault corrompido ({path}): esperado um objeto JSON.")
    state = {"created": [], "ingested": [], "ignored": []}
    for key in state:
        if isinstance(loaded.get(key), list):
            state[key] = [str(item) for item in loaded[key]]
    return state


def _save_state(state: dict) -> None:
    VAULT.mkdir(parents=True, exist_ok=True)
    tmp = VAULT / (STATE_FILE + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(VAULT / STATE_FILE)


def _load_json(name: str):
    path = DATA / name
    if not path.exists():
        path = MOCK / name
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        print(f"[obsidian] {path} invalido: {error}", file=sys.stderr)
    return None


def write_note(title: str, body: str, frontmatter: dict) -> str:
    """Cria a nota ou ACRESCENTA conteudo/mescla listas no fim dela. Nunca reescreve texto existente.
    Retorna "created", "appended" ou "ignored" (nota que o usuario deletou ou ilegivel)."""
    state = _load_state()
    name = _safe_name(title)
    if not name:
        return "ignored"
    if any(_safe_name(item).lower() == name.lower() for item in state["ignored"]):
        return "ignored"

    path = VAULT / f"{name}.md"
    if VAULT.exists():
        for candidate in VAULT.rglob("*.md"):
            if candidate.stem.lower() == name.lower() and not any(
                part.startswith(".") for part in candidate.relative_to(VAULT).parts
            ):
                path = candidate
                break

    addition = str(body).strip()
    if not path.exists():
        VAULT.mkdir(parents=True, exist_ok=True)
        path.write_text(_compose(frontmatter or {}, body), encoding="utf-8")
        if name not in state["created"]:
            state["created"].append(name)
            _save_state(state)
        return "created"

    try:
        existing = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        print(f"[obsidian] nao consegui ler {path}: {error}", file=sys.stderr)
        return "ignored"
    existing_fm, existing_body = _parse_note(existing)
    if not existing_fm:
        # sem frontmatter confiavel: so acrescenta ao texto cru, sem reescrever nada
        if addition and not existing.rstrip().endswith(addition):
            path.write_text(existing.rstrip() + "\n\n" + addition + "\n", encoding="utf-8")
        return "appended"

    changed = False
    for key in ("tags", "conversations", "source_urls"):
        new_values = (frontmatter or {}).get(key)
        if isinstance(new_values, str):
            new_values = [new_values] if new_values else []
        current = existing_fm.get(key)
        if isinstance(current, str):
            current = existing_fm[key] = [current] if current else []
        if isinstance(new_values, list) and new_values:
            if current is None:
                existing_fm[key] = list(new_values)
                changed = True
            elif isinstance(current, list):
                for value in new_values:
                    if value not in current:
                        current.append(value)
                        changed = True
    if addition and not existing_body.rstrip().endswith(addition):
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
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            print(f"[obsidian] graph.json invalido, recriando: {error}", file=sys.stderr)
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


def _extract_concepts(conversation: dict, existing: list) -> list:
    """Monta o prompt da conversa, chama o LLM e normaliza os conceitos extraidos."""
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
    concepts = []
    for item in raw_concepts or []:
        if isinstance(item, dict) and str(item.get("title") or "").strip():
            related = item.get("related") if isinstance(item.get("related"), list) else []
            concepts.append({
                "title": str(item["title"]).strip(),
                "summary": str(item.get("summary") or "").strip(),
                "related": [str(r).strip() for r in related if str(r).strip()],
            })
    return concepts


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

    pending = [
        conversation for conversation in conversations
        if isinstance(conversation, dict) and str(conversation.get("id") or "")
        and str(conversation.get("id")) not in state["ingested"]
    ]

    # lotes de 6: extracao no LLM em paralelo; escrita das notas e do state sequencial, na ordem
    with ThreadPoolExecutor(max_workers=6) as pool:
        for start in range(0, len(pending), 6):
            batch = pending[start:start + 6]
            if use_llm:
                futures = [pool.submit(_extract_concepts, conversation, list(existing)) for conversation in batch]
                extracted = []
                for conversation, future in zip(batch, futures):
                    try:
                        extracted.append(future.result())
                    except Exception as error:
                        print(f"[obsidian] LLM falhou em '{conversation.get('title')}': {error}")
                        extracted.append([])
            else:
                extracted = [[] for _ in batch]

            for conversation, concepts in zip(batch, extracted):
                cid = str(conversation.get("id"))
                diagnosis = diagnoses.get(cid) or {}
                heading = str(conversation.get("title") or "Conversa").replace("\n", " ").strip()
                date = str(conversation.get("created_at") or "")[:10] or "sem-data"
                source = str(conversation.get("source") or "desconhecido")
                default_summary = f"- Discutido na conversa: {heading}"

                if not concepts:
                    topics = diagnosis.get("topics") or []
                    if isinstance(topics, str):
                        topics = [topics]
                    topics = [t.strip() for t in topics if isinstance(t, str) and t.strip()]
                    concepts = [
                        {
                            "title": topic.title(),
                            "summary": default_summary,
                            "related": [other.title() for other in topics if other != topic],
                        }
                        for topic in topics
                    ]

                try:
                    severity = int(diagnosis.get("severity") or 0)
                except (TypeError, ValueError):
                    severity = 0
                tags = ["source/prompt"]
                if (diagnosis.get("category") == "blind_delegation" and severity >= 2) or (
                    diagnosis.get("category") == "frustration_loop" and severity >= 3
                ):
                    tags.append("alert/brain-rot")

                seen = set()
                for concept in concepts:
                    title = concept["title"].strip()
                    if not title or title.lower() in seen:
                        continue
                    seen.add(title.lower())
                    summary_text = concept["summary"] or default_summary
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
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingere conversas como notas de conceito no vault Obsidian.")
    parser.add_argument("--no-llm", action="store_true", help="nao usa LLM: usa os topics do diagnostico")
    args = parser.parse_args()
    print(json.dumps(sync_conversations_to_obsidian(use_llm=not args.no_llm), ensure_ascii=False, indent=2))
