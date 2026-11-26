r"""Servidor MCP do "LLM Wiki" (vault Obsidian) + diagnostico cognitivo do usuario.

Claude Code (caminhos ABSOLUTOS):
  macOS/Linux: claude mcp add cognitive-wiki -- "/Users/voce/.venv/bin/python" "/Users/voce/projeto/mcp_server.py"
  Windows:     claude mcp add cognitive-wiki -- "C:\Users\voce\.venv\Scripts\python.exe" "C:\Users\voce\projeto\mcp_server.py"
Claude Desktop (macOS: ~/Library/Application Support/Claude/claude_desktop_config.json;
Windows: %APPDATA%\Claude\claude_desktop_config.json). Exemplo macOS:
  {"mcpServers": {"cognitive-wiki": {"command": "/Users/voce/.venv/bin/python", "args": ["/Users/voce/projeto/mcp_server.py"]}}}
No Windows: {"command": "C:\Users\voce\.venv\Scripts\python.exe", "args": ["C:\Users\voce\projeto\mcp_server.py"]}
Rodar: python mcp_server.py (stdio) | python mcp_server.py --http (http://127.0.0.1:8000/mcp)
"""
import difflib
import json
import sys
import unicodedata

from fastmcp import FastMCP

import obsidian

mcp = FastMCP("cognitive-wiki")


def _norm(text) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", str(text)) if not unicodedata.combining(c)).lower()


def _source(node: dict) -> tuple[str, str]:
    fm = node["frontmatter"] or {}
    source = str(fm.get("source") or "human")
    color = {"prompt": "azul", "firecrawl": "verde", "human": "sem cor"}.get(source, "sem cor")
    return source, "vermelho (alerta brain-rot)" if "alert/brain-rot" in [str(t) for t in fm.get("tags") or []] else color


def _find(vault: dict, title: str):
    for name, node in vault.items():
        if _norm(name) == _norm(title).strip():
            return name, node
    return None, None


@mcp.tool
def search_wiki(query: str, limit: int = 8) -> str:
    """Busca por texto (sem diferenciar maiusculas/acentos) no titulo e no corpo do wiki.
    Use quando o usuario citar um conceito ou quiser saber o que ele ja estudou/anotou."""
    q, vault, hits = _norm(query).strip(), obsidian.read_vault(), []
    if not q:
        return "Informe um termo de busca."
    for title, node in vault.items():
        in_title, idx = q in _norm(title), _norm(node["body"]).find(q)
        if in_title or idx >= 0:
            hits.append((in_title, title, node, idx))
    hits.sort(key=lambda h: (not h[0], h[1].lower()))
    if not hits:
        return f"Nenhuma nota para '{query}'. Titulos: {', '.join(sorted(vault)[:8]) or '(vault vazio)'}"
    return "\n".join(
        f"- **{title}** ({_source(node)[0]}) — {' '.join((node['body'][max(0, idx - 80): idx + 120] if idx >= 0 else node['body'][:200]).split())}"
        for _, title, node, idx in hits[:max(1, limit)]
    )


@mcp.tool
def read_node(title: str) -> str:
    """Le uma nota completa (frontmatter resumido + corpo) e seus backlinks. Use depois de
    search_wiki quando precisar do conteudo integral de um conceito."""
    vault = obsidian.read_vault()
    name, node = _find(vault, title)
    if not node:
        close = difflib.get_close_matches(title, list(vault), n=5, cutoff=0.3)
        return f"Nota '{title}' nao encontrada." + (f" Parecidas: {', '.join(close)}." if close else "")
    fm = node["frontmatter"] or {}
    meta = "\n".join(f"- {k}: {', '.join(map(str, v)) if isinstance(v, list) else v}" for k, v in fm.items())
    back = [other for other, item in vault.items() if any(_norm(link) == _norm(name) for link in item["links"])]
    source, color = _source(node)
    return (f"# {name}\n\nFonte: {source} ({color})\n\n## Frontmatter\n{meta or '(vazio)'}\n\n"
            f"## Conteudo\n{node['body'].strip()}\n\n## Backlinks\n" + ("\n".join(f"- [[{b}]]" for b in back) if back else "(nenhum)"))


@mcp.tool
def get_graph_neighbors(title: str) -> str:
    """Mostra links de saida, backlinks e vizinhos de 2 saltos de uma nota, com fonte/cor de cada no
    (azul=prompt, verde=firecrawl, vermelho=alerta brain-rot). Use para navegar entre conceitos."""
    vault = obsidian.read_vault()
    name, node = _find(vault, title)
    if not node:
        close = difflib.get_close_matches(title, list(vault), n=5, cutoff=0.3)
        return f"Nota '{title}' nao encontrada." + (f" Parecidas: {', '.join(close)}." if close else "")
    def describe(item_title: str) -> str:
        real, item = _find(vault, item_title)
        if not item:
            return f"- {item_title} (nota ainda nao criada)"
        source, color = _source(item)
        return f"- {real} ({source}, {color})"
    resolved = {t: {_find(vault, l)[0] for l in n["links"]} - {None} for t, n in vault.items()}
    out, back = node["links"], [o for o, ls in resolved.items() if name in ls]
    near = resolved[name] | set(back)
    second = set().union(*(resolved[t] | {o for o, ls in resolved.items() if t in ls} for t in near)) - near - {name}
    source, color = _source(node)
    return (f"# {name} ({source}, {color})\n\n## Links de saida\n" + ("\n".join(map(describe, out)) or "(nenhum)")
            + "\n\n## Backlinks\n" + ("\n".join(map(describe, back)) or "(nenhum)")
            + "\n\n## Vizinhos de 2 saltos\n" + ("\n".join(map(describe, sorted(second))) or "(nenhum)"))


@mcp.tool
def list_frontier_nodes() -> str:
    """Lista as notas verdes de fronteira (source firecrawl) e suas URLs de fonte. Use quando o
    usuario quiser explorar o que foi pesquisado na web ou pedir referencias."""
    rows = []
    for name, node in sorted(obsidian.read_vault().items()):
        fm = node["frontmatter"] or {}
        if str(fm.get("source")) != "firecrawl" and "source/firecrawl" not in [str(t) for t in fm.get("tags") or []]:
            continue
        urls = [str(url) for url in fm.get("source_urls") or []]
        rows.append(f"- **{name}**" + ("\n" + "\n".join(f"  - {url}" for url in urls) if urls else " (sem source_urls)"))
    return "# Notas de fronteira (verdes)\n\n" + ("\n".join(rows) or "(nenhuma nota source/firecrawl ainda)")


@mcp.tool
def get_cognitive_summary() -> str:
    """Resume a saude cognitiva do usuario: score, metricas, recomendacoes e conceitos em
    alert/brain-rot. Use no inicio da conversa para adaptar seu jeito de ajudar."""
    diag = {}
    for folder in (obsidian.DATA, obsidian.MOCK):
        path = folder / "diagnostics.json"
        if not path.exists():
            continue
        try:
            diag = json.loads(path.read_text(encoding="utf-8"))
            break
        except (OSError, json.JSONDecodeError) as error:
            print(f"[mcp] {path} invalido: {error}", file=sys.stderr)
    if not diag:
        return "Diagnostico indisponivel: rode diagnostics.run_cognitive_diagnosis()."
    alerts = [n for n, node in sorted(obsidian.read_vault().items())
              if "alert/brain-rot" in [str(t) for t in (node["frontmatter"] or {}).get("tags") or []]]
    lines = [f"# Saude cognitiva: {diag.get('cognitive_health_score', '?')}/100", "", "## Metricas"]
    lines += [f"- {k}: {v}" for k, v in (diag.get("summary_metrics") or {}).items()]
    lines += ["", "## Recomendacoes"] + [f"- {r}" for r in diag.get("recommendations") or []]
    lines += ["", "## Conceitos em alerta (brain-rot)"] + ([f"- {a}" for a in alerts] or ["(nenhum)"])
    lines += ["", "Incentive o usuario a tentar/esbocar antes da solucao pronta; em loops de erro, peca diagnostico."]
    return "\n".join(lines)


if __name__ == "__main__":
    if "--http" in sys.argv:
        mcp.run(transport="http", host="127.0.0.1", port=8000)
    else:
        mcp.run()
