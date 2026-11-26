"""Notas verdes do grafo: conceitos na fronteira do que o usuario ja sabe.
Le o vault, escolhe os conceitos centrais, pede ao LLM topicos vizinhos que faltam,
pesquisa fontes reais no Firecrawl e escreve a nota verde so com base nelas."""
import argparse
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from firecrawl import Firecrawl

import llm
import obsidian

load_dotenv(Path(__file__).resolve().parent / ".env")
DATA = Path(__file__).resolve().parent / "data"


def expand_frontier(n: int = 3) -> list:
    """Pesquisa n conceitos vizinhos do grafo, cria as notas verdes e grava data/frontier_research.json."""
    DATA.mkdir(parents=True, exist_ok=True)
    out = DATA / "frontier_research.json"
    vault = obsidian.read_vault()
    if not vault:
        print("[research] vault vazio: nada para expandir")
        out.write_text("[]\n", encoding="utf-8")
        return []

    canonical = {title.lower(): title for title in vault}
    degree, blind = {title: 0 for title in vault}, []
    for title, note in vault.items():
        for link in note["links"]:
            target = canonical.get(link.lower())
            if target and target != title:
                degree[title] += 1   # link de saida
                degree[target] += 1  # backlink
        tags = (note["frontmatter"] or {}).get("tags") or []
        tags = [tags] if isinstance(tags, str) else tags if isinstance(tags, list) else []
        if any(str(tag).lstrip("#") == "alert/brain-rot" for tag in tags):
            blind.append(title)
    central = [
        title for title, _ in sorted(degree.items(), key=lambda item: (-item[1], item[0]))
        if str((vault[title]["frontmatter"] or {}).get("source") or "") != "firecrawl"
    ][:8]

    central_block = "\n".join(
        f"- {title} (grau {degree[title]}): {' '.join(str(vault[title]['body']).split())[:300]}"
        for title in central
    ) or "(vault sem conceitos centrais)"
    titles = sorted(canonical.values())

    prompt = f"""Voce mantem um wiki pessoal em grafo e quer sugerir os proximos conceitos que o usuario deveria estudar.

Conceitos centrais que o usuario ja discutiu:
{central_block}

Pontos cegos (onde ele delegou demais a IA): {', '.join(blind) or '(nenhum)'}
Todos os titulos que JA existem no vault: {json.dumps(titles, ensure_ascii=False)}

Proponha {n} topicos de FRONTEIRA: conceitos adjacentes que ainda NAO existem no vault, especificos e acionaveis (nada generico). Nao repita nem apenas renomeie um titulo existente. "why": 1-2 frases sobre por que importa para o que o usuario constroi, citando os conceitos dele. "search_query" curta, em ingles se tecnico. "related": apenas titulos EXATOS da lista acima.

Responda APENAS com JSON: {{"topics": [{{"topic": "...", "why": "...", "search_query": "...", "related": ["Titulo Existente"]}}]}}"""

    try:
        answer = llm.ask_json(prompt)
    except Exception as error:
        print(f"[research] LLM indisponivel, nenhum topico proposto: {error}", file=sys.stderr)
        answer = {}
    proposals = answer.get("topics") if isinstance(answer, dict) else answer
    proposals = proposals if isinstance(proposals, list) else []
    # notas que o usuario deletou no Obsidian nunca voltam (e nao gastam Firecrawl)
    try:
        ignored = obsidian._load_state()["ignored"]
    except RuntimeError as error:
        raise RuntimeError(f"[research] state do vault indisponivel, nada foi expandido: {error}") from error
    seen = set(canonical) | {t.lower() for t in ignored}
    topics = []
    for item in proposals:
        if len(topics) >= n or not isinstance(item, dict):
            continue
        topic = str(item.get("topic") or "").strip()
        if not topic or topic.lower() in seen:
            continue
        raw_related = item.get("related") if isinstance(item.get("related"), list) else []
        related = list(dict.fromkeys(
            canonical[raw.strip().lower()] for raw in raw_related
            if isinstance(raw, str) and raw.strip().lower() in canonical
        ))
        seen.add(topic.lower())
        topics.append({
            "topic": topic,
            "why": str(item.get("why") or "").strip(),
            "search_query": str(item.get("search_query") or topic).strip(),
            "related": related,
        })
    if len(topics) < n:
        print(f"[research] {len(topics)} topico(s) valido(s) de {n} pedido(s)")

    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        print("[research] FIRECRAWL_API_KEY ausente: sem fonte real, nenhuma nota verde sera criada")
    results = []
    for proposal in topics:
        topic = proposal["topic"]
        entry = {"topic": topic, "why": proposal["why"], "note_title": topic, "sources": []}
        try:
            docs = []
            if api_key:
                response = Firecrawl(api_key=api_key).search(
                    proposal["search_query"], limit=3,
                    scrape_options={"formats": ["markdown"], "only_main_content": True},
                )
                for item in getattr(response, "web", None) or []:
                    meta = getattr(item, "metadata", None)
                    url = getattr(item, "url", None) or (meta and (meta.url or meta.source_url))
                    title = getattr(item, "title", None) or (meta and meta.title) or url
                    markdown = getattr(item, "markdown", None)
                    if url and markdown:
                        docs.append({"title": str(title), "url": str(url), "markdown": str(markdown)})
                docs = docs[:3]
                if not docs:
                    print(f"[research] '{topic}': Firecrawl nao trouxe texto, nota nao criada")
            if docs:
                blocks = "\n\n".join(
                    f"[{i}] {doc['title']} — {doc['url']}\n{doc['markdown'][:3000]}"
                    for i, doc in enumerate(docs, 1)
                )
                answer = llm.ask_json(f"""Escreva uma nota de wiki tecnica usando SOMENTE as fontes abaixo.
Topico: {topic}
Por que importa: {proposal['why']}

Fontes:
{blocks}

Nota em markdown de 6 a 12 linhas, citando cada afirmacao com [1], [2] ou [3]. Use so as fontes, sem conhecimento externo; se um ponto nao estiver nelas, omita.

Responda APENAS com JSON: {{"summary_md": "...", "key_points": ["..."]}}""")
                summary = str(answer.get("summary_md") or "").strip() if isinstance(answer, dict) else ""
                if not summary and isinstance(answer, dict) and isinstance(answer.get("key_points"), list):
                    summary = "\n".join(f"- {point}" for point in answer["key_points"] if str(point).strip())
                # citacao valida = marcador [n] com n dentro das fontes realmente recebidas
                summary = re.sub(
                    r"\[(\d+)\]",
                    lambda match: match.group(0) if 1 <= int(match.group(1)) <= len(docs) else "",
                    summary,
                )
                if not summary:
                    print(f"[research] '{topic}': resumo vazio, nota nao criada")
                elif not any(1 <= int(match) <= len(docs) for match in re.findall(r"\[(\d+)\]", summary)):
                    print(f"[research] '{topic}': resumo sem citacao valida das fontes, nota nao criada")
                else:
                    body = (
                        f"## Por que isso importa para voce\n{proposal['why']}\n\n"
                        f"## Resumo\n{summary}\n\n"
                        f"## Conecta com\n{' '.join(f'[[{r}]]' for r in proposal['related']) or '(sem conexoes identificadas)'}\n\n"
                        f"## Fontes\n"
                        + "\n".join(f"{i}. [{doc['title']}]({doc['url']})" for i, doc in enumerate(docs, 1))
                    )
                    status = obsidian.write_note(topic, body, {
                        "type": "concept", "source": "firecrawl", "tags": ["source/firecrawl"],
                        "source_urls": [doc["url"] for doc in docs],
                    })
                    entry["sources"] = [{"title": doc["title"], "url": doc["url"]} for doc in docs]
                    print(f"[research] nota verde '{topic}' {status}")
        except Exception as error:
            print(f"[research] falhou em '{topic}': {error}", file=sys.stderr)
        results.append(entry)

    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pesquisa conceitos de fronteira e cria notas verdes no vault.")
    parser.add_argument("--n", type=int, default=3, help="quantos topicos pesquisar (padrao: 3)")
    args = parser.parse_args()
    print(json.dumps(expand_frontier(args.n), ensure_ascii=False, indent=2))
