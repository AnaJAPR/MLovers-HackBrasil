# AGENTS.md — regras para qualquer agente que escreva codigo aqui

Projeto de hackathon (1 semana): app LOCAL que (A) diagnostica saude cognitiva no uso de IA a partir do
historico de conversas e (B) constroi um "LLM Wiki" (estilo Karpathy) em grafo no Obsidian a partir dessas
conversas, expandido com pesquisa web real (Firecrawl), e exposto via MCP.
Fonte de verdade do produto: `ideia.md` SECAO 1. As secoes 2-9 do ideia.md sao sugestoes antigas e
OBSOLETAS — onde conflitarem, vale este AGENTS.md.

## Regra maxima
**O mais simples possivel. Pouco codigo. Direto. Zero overengineering.** Na duvida, escreva menos.

- Proibido: Docker, banco de dados, ORM, Redis, filas, classes abstratas, dependency injection,
  "managers", "services", "utils", pastas de pacote, frameworks de frontend, bundlers.
- Um arquivo Python por conceito de negocio (mapa abaixo). Nao crie arquivos novos sem necessidade.
- Nao crie funcoes de 2-15 linhas usadas em um so lugar: escreva inline. Funcoes so para conceitos de
  negocio ou codigo realmente reutilizado.
- Dicts simples, `pathlib.Path`, `print` para log, `try/except` claro. Sem dataclasses/pydantic/classes.
- Estado = arquivos `.json` e `.md` locais.
- Sem pasta tests/. Cada modulo tem um `if __name__ == "__main__":` que roda sua etapa de ponta a ponta.

## Windows + macOS + Linux (obrigatorio, mesmo que voce so rode no Linux)
- SEMPRE `pathlib.Path` (`Path.home() / ".claude" / "projects"`). Nunca strings com `/` ou `\`.
- SEMPRE `encoding="utf-8"` em todo `open()`, `read_text()`, `write_text()`. `json.dumps(..., ensure_ascii=False)`.
- Nunca `os.system`, `subprocess` com `ls/cat/grep/rm/cp`, nem `shell=True`. Use `shutil`/`pathlib`.
  Para chamar Python: `[sys.executable, "script.py"]`.
- Proibido: `fcntl`, `resource`, `pty`, `uvloop`, `signal.SIGKILL`, caminhos `/tmp` fixos
  (use `tempfile`), `os.getuid`, symlinks, `os.path.expanduser` em string com `/` (use `Path.home()`).
- Nome de arquivo gerado de texto: remova `<>:"/\|?*#^[]` e limite a ~80 chars (Windows + Obsidian).
- Servidor sempre em `127.0.0.1`.

## Mapa de arquivos
| arquivo | o que faz |
|---|---|
| `llm.py` | `ask_json(prompt) -> dict/list` via claude-agent-sdk (usa o login do Claude Code; sem API key). Unica porta para o Claude. |
| `collector.py` | Le Claude Code (`~/.claude/projects/**/*.jsonl`) e Codex (`~/.codex/sessions/**/*.jsonl`), importa exports .zip/.json de `data/imports/`, e roda a extracao web (Agent SDK + Chrome DevTools MCP, instrucoes em `skills/*.md`, pausa para login humano). -> `data/conversations.json` |
| `diagnostics.py` | Prompt do classificador + verificador de 3 camadas + metricas sem LLM + inferencia por conversa (`DIAG_BACKEND=mock\|claude\|local`, cache por id) + relatorio geral (score + recomendacoes). -> `data/diagnostics.json` |
| `train_wreinforce.py` | Dataset sintetico, SFT baseline, treino W-REINFORCE, avaliacao. Importa `build_prompt`/`verify` de `diagnostics.py`. |
| `obsidian.py` | O wiki. Le o vault do disco (notas + `[[links]]`), faz o ingest das conversas em notas de conceito (azuis), marca alertas (vermelho), escreve `.obsidian/graph.json`, respeita edicoes/delecoes do usuario. Expoe `read_vault()` e `write_note()` para os outros modulos. |
| `research.py` | Notas verdes: escolhe os conceitos centrais do grafo, pede ao LLM 2-3 topicos vizinhos que faltam, pesquisa no Firecrawl, escreve nota verde so com base nas fontes (com URLs) via `obsidian.write_note`. -> tambem `data/frontier_research.json` |
| `mcp_server.py` | FastMCP (stdio; `--http` opcional) expondo vault + diagnostico. |
| `integrations.py` | E-mail Resend (relatorio) + checkout AbacatePay. |
| `app.py` + `index.html` | FastAPI em 127.0.0.1:8765, abre o navegador (`webbrowser.open`), botoes chamam as funcoes acima. HTML/CSS/JS puro, um arquivo. |

## Contratos de dados
- Leitura de entrada: se `data/<arquivo>.json` nao existir, use `mock/<arquivo>.json` (cada modulo roda isolado).
- `data/conversations.json`: lista de
  `{"id", "source": "claude_code|codex|chatgpt_web|claude_web|gemini_web", "title", "created_at", "messages": [{"role": "user|assistant", "content", "timestamp"}]}`
  So texto humano/assistente: sem tool calls, tool results, system-reminders ou saidas de comando.
- `data/diagnostics.json`:
  `{"generated_at", "cognitive_health_score": 0-100, "summary_metrics": {"blind_delegation_pct", "socratic_pct", "frustration_loop_pct", "active_cocreation_pct", "avg_prompt_effort_ratio"}, "recommendations": [str], "conversation_diagnoses": [{"conversation_id", "category": "blind_delegation|frustration_loop|socratic_learning|active_cocreation", "severity": 1-5, "evidence_quote", "grounding_verified", "topics": [str], "recommendation"}]}`
- Vault (`OBSIDIAN_VAULT_PATH`, padrao `~/AIWikiVault`): uma nota `.md` por conceito, frontmatter YAML:
  `type: concept`, `source: prompt|firecrawl|human`, `tags: [source/prompt]` (ou `source/firecrawl`; + `alert/brain-rot`
  quando houver delegacao cega no conceito), `source_urls: [...]` (verdes), `conversations: [ids]`. Corpo em
  Markdown com `[[Outro Conceito]]`.
- Sync bidirecional SIMPLES: o agente NUNCA reescreve texto existente de uma nota — so cria notas novas ou
  ACRESCENTA secoes/links ao final. `<vault>/.wiki_state.json` guarda as notas criadas pelo agente e as conversas
  ja ingeridas; nota criada pelo agente que sumiu do disco = usuario deletou -> vai para `ignored` e nunca e
  recriada. Notas criadas pelo usuario (sem estar no state) entram no grafo como `source: human`.
- Cores em `.obsidian/graph.json` (`colorGroups`, ordem importa): `tag:#alert/brain-rot` vermelho,
  `tag:#source/firecrawl` verde, `tag:#source/prompt` azul.
- `data/` e gitignored (dados reais). Exemplos versionados ficam em `mock/`.

## Ambiente
- Python 3.11+, dependencias no `pyproject.toml`. Venv compartilhada: `/home/tironi/codigos/MLovers-GitTrees/.venv`
  (rode com `/home/tironi/codigos/MLovers-GitTrees/.venv/bin/python arquivo.py`). Nao instale pacotes sem pedir.
- Chaves em `.env` (`.env.example`). Sem chave -> modulo cai em mock, avisa com `print`, nunca quebra.
- LLM sempre via `llm.ask_json`. Firecrawl recebe so nomes de topicos. Resend recebe so o relatorio agregado.

## Funcoes publicas (contrato entre modulos — nao mude a assinatura sem combinar)
- `collector.collect(limit=200) -> list` (grava `data/conversations.json`)
- `collector.run_web_extraction(platform: str) -> dict` (`"chatgpt"|"claude"|"gemini"`)
- `diagnostics.build_prompt(conversation: dict) -> str`
- `diagnostics.verify(output_text: str, conversation: dict, gold_category: str | None = None) -> dict`
  -> `{"format_ok", "category_ok", "grounding_ok", "reward", "parsed"}`
- `diagnostics.run_cognitive_diagnosis(backend: str | None = None) -> dict` (grava `data/diagnostics.json`)
- `obsidian.VAULT` (Path), `obsidian.read_vault() -> dict`, `obsidian.write_note(title, body, frontmatter) -> str`
- `obsidian.sync_conversations_to_obsidian() -> dict`
- `research.expand_frontier(n=3) -> list` (grava `data/frontier_research.json`)
- `integrations.send_report(to: str | None = None) -> dict`, `integrations.create_checkout() -> str` (URL)
