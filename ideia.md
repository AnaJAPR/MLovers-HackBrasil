DOCUMENTO DE CONTEXTO, ARQUITETURA E DIVISAO DE TASKS — PROJETO DE HACKATHON
Finalidade: Este documento contem todo o contexto de produto, decisoes tecnicas, diretrizes de codigo e divisao de tarefas para uma equipe de 4 pessoas executar o prototipo em 2 a 3 dias usando vibe coding. Qualquer agente de IA que ler este documento deve seguir rigorosamente as diretrizes de simplicidade e os contratos de arquivos definidos aqui.

1. REGISTRO CONSOLIDADO DO QUE O USUARIO PEDIU (CONTEXTO ORIGINAL)

O projeto une duas vertentes complementares em um unico aplicativo local de computador:

Vertente A — Diagnostico de Saude Cognitiva no Uso de IA (Anti-Brain Rot):
Todo mundo hoje usa IA o tempo inteiro, e o uso passivo ou excessivo pode causar dependencia cognitiva ("brain rot"), deixando a pessoa dependente da IA para tudo em vez de usar a ferramenta de forma inteligente. A ideia e criar uma ferramenta local que analisa o historico de conversas de IA da pessoa (Claude Code, Codex, ChatGPT Web, Claude Web, Gemini Web) e faz um diagnostico: o uso esta saudavel ou nao? Onde a pessoa esta dependendo demais da IA? O que ela deveria mudar? A ferramenta gera recomendacoes tanto de como tirar mais proveito da IA quanto de como nao ficar dependente.

Vertente B — Grafo de Conhecimento / LLM Wiki Integrado ao Obsidian + MCP:
As pessoas usam ChatGPT e outros LLMs para muita coisa e acabam esquecendo tudo o que discutirao e aprenderao porque esse conhecimento nunca fica estruturado. Inspirado na ideia de "LLM Wiki" (Andrej Karpathy), em vez de o usuario precisar jogar fontes externas manualmente, nosso sistema constroi proativamente uma wiki estruturada em formato de grafo a partir das proprias conversas do usuario.

O Obsidian sera usado como interface visual do grafo de conhecimento (evitando construir um frontend de grafo do zero).
Nos azuis representam conceitos e temas extraidos diretamente das conversas/prompts do usuario.
Nos verdes representam conceitos nas bordas do grafo (topicos adjacentes que o usuario ainda nao falou sobre, mas que agregariam muito valor ao que ele esta construindo/estudando). O sistema identifica essas bordas usando o grafo e um LLM, usa o Firecrawl para pesquisar materiais reais e atualizados na internet (sem inventar/alucinar) e adiciona essas notas verdes automaticamente ao Obsidian do usuario.
Edicao bidirecional no Obsidian: o usuario deve conseguir editar notas, adicionar contexto novo ou apagar nos irrelevantes diretamente no Obsidian, e o agente precisa enxergar e respeitar essas alteracoes na proxima execucao.
Acesso dos LLMs ao Grafo (MCP): expor esse grafo de conhecimento por meio de um servidor MCP (Model Context Protocol) para que tanto ferramentas locais (Claude Code, Claude Desktop) quanto interfaces web consigam consultar esse contexto estruturado do usuario. Opcionalmente, permitir sincronizacao/backup do vault em um repositorio GitHub do usuario.

Coleta de Dados (Local + Human-in-the-Loop na Web):

Para ferramentas locais de codigo (como pastas .claude, .codex, etc.), o aplicativo acessa diretamente os arquivos no computador do usuario, sem precisar subir as conversas brutas para a nuvem.
Para interfaces web (ChatGPT Web, Claude Web, Gemini Web), que nao tem API simples para exportar historico, a abordagem escolhida e criar Skills de agente (ex: extrair ChatGPT, extrair Claude, extrair Gemini) executadas com Claude in Chrome (ou Claude Agent SDK). Nao queremos automatizar o login nem brigar com CAPTCHA/2FA: o agente navega no navegador do proprio usuario, para na tela de login e pede para o humano logar, e assim que o humano faz login, o agente reassume e exporta as conversas para arquivos locais. Isso pode rodar sob demanda ou periodicamente (ex: a cada 15 dias).

Patrocinadores e Integracoes do Hackathon:

Firecrawl: buscar contexto atualizado na internet sobre os temas que o usuario esta trabalhando e preencher os nos verdes nas bordas do grafo sem alucinar.
Resend: enviar e-mails para o usuario (relatorio periodico / raio-x cognitivo, alertas de uso, resumo dos novos nos verdes adicionados ao Obsidian com links curados).
AbacatePay: fluxo simples de checkout para o usuario pagar uma assinatura (plano Pro), sem complexidade extra.
Outros sponsors presentes no evento (referencia: Cognition, Convex, Puentes, Capivarafy, WorkOS, Jumpstart, Nvoip, Globalfy, Vibe Space, C6 Bank, Fundacao Estudar, Kipper Academy) sao opcionais — focar no essencial: Firecrawl, Resend e AbacatePay.

Diferencial de Machine Learning (Para Impressionar a Banca):
A equipe tem forte base em Machine Learning. Um agente wrapper de LLM qualquer grupo consegue fazer em um hackathon. Para se destacar nos criterios de inovacao e qualidade tecnica, vamos treinar/fazer pos-treino de um modelo pequeno local usando uma tecnica recente de RLVR (Reinforcement Learning with Verifiable Rewards) baseada em Negative Reinforcement (NSR / W-REINFORCE), do paper de NeurIPS 2025 do grupo da Danqi Chen. A justificativa tecnica e solida e chama muita atencao na apresentacao, mesmo que o modelo seja um prototipo de hackathon e nao precise ser perfeito em producao.

Escopo e Filosofia Geral:

Prazo: prototipo de hackathon (2 a 3 dias), executado por 4 pessoas dividindo tarefas.
Privacidade e simplicidade: tudo rodando localmente no computador da pessoa (sem infra de nuvem pesada). Por agora, sera rodado localmente como aplicativo de computador (nao precisa construir instalador/distribuicao publica elaborada).
Obrigatorio funcionar bem tanto em macOS quanto em Windows (o time usa ambos os sistemas).

2. DIRETRIZES INEGOCIAVEIS DE CODIGO (REGRAS PARA O AGENTE DE VIBE CODING)

Qualquer agente de IA escrevendo codigo neste repositorio DEVE obedecer estas 7 regras sem excecao:

Zero Overengineering: Este e um prototipo de hackathon de 2 a 3 dias. Proibido adicionar Docker, Postgres, Redis, Celery, ORMs, arquitetura hexagonal, interfaces abstratas, dependency injection, Redux ou pipelines de build complexos. Persistencia de estado e feita em arquivos .json e .md locais.
Backend Majoritariamente em Python: Toda a logica de negocio, coleta, grafo, ML, MCP e integracoes deve ser escrita em Python 3.11+. O frontend deve ser o mais simples possivel (HTML + CSS + JS puro ou HTMX leve em um unico arquivo servido pelo FastAPI dentro de uma janela pywebview).
Um Modulo (Um Arquivo Python) por Grande Conceito de Negocio: Nao pulverizar o codigo em dezenas de arquivos pequenos (nao criar obsidian_reader.py, obsidian_writer.py, obsidian_parser.py, obsidian_utils.py). Tudo relacionado a Obsidian fica em obsidian.py, mesmo que o arquivo tenha 500 ou 2.000 linhas. Tudo de coleta fica em collector.py, tudo de MCP fica em mcp_server.py, etc.
Sem Micro-Funcoes Desnecessarias: Se um trecho de codigo (ex: ler um arquivo, formatar um JSON, filtrar uma lista) e usado em apenas um lugar, escreva o codigo diretamente inline onde ele e usado. NAO crie funcoes auxiliares de 2 a 15 linhas so para "deixar bonito". Crie funcoes apenas para grandes conceitos de negocio (ex: sync_conversations_to_obsidian, run_cognitive_diagnosis) ou quando o codigo for genuinamente reutilizado em varios lugares.
Reaproveite o que Ja Existe: Nao reinvente protocolo MCP (use fastmcp), nao reinvente agente (use claude-agent-sdk), nao reinvente visualizacao de grafo (use o proprio Obsidian), nao reinvente busca web (use firecrawl-py), nao reinvente checkout (use abacatepay).
Local-First por Padrao: Nunca envie conversas brutas inteiras do usuario para bancos de dados remotos. Envie para APIs externas apenas o minimo necessario (ex: nomes de topicos abstratos para o Firecrawl pesquisar, resumo estruturado para o Resend enviar e-mail).
Codigo Direto, Legivel e Manutenivel: Prefira dicionarios Python simples, pathlib.Path, blocos try/except claros com logs simples (print) e variaveis de ambiente em um unico .env.

3. GUIA OBRIGATORIO DE COMPATIBILIDADE WINDOWS + MACOS

Como parte do time desenvolve em macOS e parte em Windows, todo codigo deve seguir estas regras desde o primeiro commit:

Sempre use pathlib.Path: Nunca use strings com / ou \ fixas. Exemplo correto: Path.home() / ".claude" / "projects".
Sempre especifique encoding="utf-8": No Windows, o open() padrao usa cp1252, o que quebra imediatamente com acentos em portugues e emojis de conversas de IA. Todo open(...), read_text(encoding="utf-8") e write_text(..., encoding="utf-8") DEVE declarar encoding="utf-8".
Pasta de dados padronizada na Home do usuario: Salve dados do app em Path.home() / ".ai_cognitive_os" e o Vault do Obsidian em Path.home() / "AIWikiVault" (configuravel via .env). Evite pastas do sistema ou Desktop/Documents onde o macOS exige permissoes extras de privacidade.
Zero comandos bash/shell dependentes de OS: Nao use os.system("rm -rf ..."), ls, cat ou grep. Use shutil, pathlib e bibliotecas Python puras. Quando precisar chamar Python em subprocesso, use [sys.executable, "script.py"] em vez de "python3".
Ambiente Python unificado com uv (ou venv padrao): Use um unico pyproject.toml (ou requirements.txt) sem pacotes exclusivos de Unix (proibido uvloop, fcntl, resource, pty). Recomenda-se instalar com uv sync (funciona identicamente no PowerShell do Windows e no Terminal do Mac).
Quebras de linha no Git: Crie um arquivo .gitattributes na raiz contendo * text=auto eol=lf para evitar conflitos de CRLF vs LF entre Windows e Mac.
Permissoes de execucao e portas: Rode o servidor local sempre em 127.0.0.1 (nao 0.0.0.0) para evitar alertas bloqueantes de Firewall do Windows. Para o app desktop, use pywebview (que usa WebKit nativo no Mac e WebView2/Edge nativo no Windows) com fallback automatico: se o usuario passar --browser ou se pywebview falhar, abre http://127.0.0.1:8765 no navegador padrao via webbrowser.open(...).

4. ARQUITETURA SIMPLIFICADA DO PROJETO (MAPA DE ARQUIVOS)

O repositorio inteiro deve ter esta estrutura enxuta (um arquivo por dominio de negocio):

app.py — Aplicativo desktop local: servidor FastAPI + janela nativa pywebview + rotas HTTP para disparar coleta, rodar diagnostico, atualizar Obsidian, rodar pesquisa Firecrawl, enviar e-mail Resend e gerar checkout AbacatePay.
index.html — Frontend unico (HTML + CSS limpo + JS vanilla/fetch chamando as rotas locais do app.py). Sem npm, sem React build, sem bundler.
collector.py — Leitura automatica dos logs locais (.claude, .codex), importacao manual de exports .json/.zip do ChatGPT/Claude/Gemini (fallback garantido) e orquestracao do agente com skills (claude-agent-sdk) para acionar a extracao web com pausa humana no login. Normaliza tudo para data/conversations.json.
diagnostics.py — Roda o modelo local treinado com W-REINFORCE (ou fallback configuravel) sobre data/conversations.json, calcula metricas quantitativas de Cognitive Offloading (sem LLM) e gera data/diagnostics.json.
obsidian.py — Toda a logica do Grafo de Conhecimento no Vault do Obsidian: gera/atualiza notas .md com YAML frontmatter e [[wikilinks]], configura cores no .obsidian/graph.json (azuis, verdes, vermelhos), detecta edicoes e delecoes manuais do usuario (.ignore_nodes.json), usa networkx para encontrar buracos estruturais e bordas do grafo, e faz commit/push opcional para GitHub se o usuario ativar.
research.py — Recebe os topicos de fronteira detectados pelo obsidian.py (e pontos cegos do diagnostics.py), usa firecrawl-py para buscar e raspar referencias reais da web em Markdown e devolve conteudo estruturado para virar notas verdes no Obsidian e links no e-mail.
mcp_server.py — Servidor FastMCP que expoe o Vault do Obsidian e o diagnostico cognitivo como ferramentas MCP (search_wiki, read_node, get_graph_neighbors, get_cognitive_summary) em modo stdio (para Claude Code / Claude Desktop) e modo http (para clientes web).
integrations.py — Envio do relatorio HTML por e-mail via resend e criacao do link de pagamento/assinatura via abacatepay.
train_wreinforce.py — Script isolado (rodado em maquina com GPU) para gerar dataset sintetico de conversas, executar o verificador deterministico de 3 camadas e treinar o modelo local (Qwen3-4B ou Qwen2.5-7B-Instruct) com W-REINFORCE / NSR.
skills/ — Pasta com os arquivos .md de instrucoes das skills do agente: extract_chatgpt.md, extract_claude.md, extract_gemini.md.
data/ — Pasta local de arquivos intermediarios (contratos entre os modulos): conversations.json, diagnostics.json, frontier_research.json.
.env.example e pyproject.toml — Variaveis de ambiente (FIRECRAWL_API_KEY, RESEND_API_KEY, ABACATEPAY_API_KEY, ANTHROPIC_API_KEY, OBSIDIAN_VAULT_PATH, USER_EMAIL) e lista minima de dependencias.

5. CONTRATOS DE DADOS ENTRE AS 4 PESSOAS (PARA TRABALHAR EM PARALELO SEM TRAVAR)

Definir estes 3 formatos logo na primeira hora permite que as 4 pessoas desenvolvam e testem seus modulos independentemente usando dados mockados:

Contrato 1 — data/conversations.json (Produzido por collector.py):
Lista JSON de objetos, onde cada conversa tem:

id: string unica (hash do arquivo/conversa)
source: "claude_code" | "codex" | "chatgpt_web" | "claude_web" | "gemini_web"
|---|---|---|
title: string
messages: lista de { "role": "user" | "assistant", "content": "...", "timestamp": "..." }

Contrato 2 — data/diagnostics.json (Produzido por diagnostics.py):
Objeto JSON com:

generated_at: string ISO-8601
cognitive_health_score: inteiro de 0 a 100
summary_metrics: { "blind_delegation_pct": float, "socratic_pct": float, "frustration_loop_pct": float, "active_cocreation_pct": float, "avg_prompt_effort_ratio": float }
conversation_diagnoses: lista de objetos com { "conversation_id": str, "category": "blind_delegation" | "frustration_loop" | "socratic_learning" | "active_cocreation", "severity": 1-5, "evidence_quote": str, "grounding_verified": bool, "topics": [str], "recommendation": str }

Contrato 3 — Vault do Obsidian (OBSIDIAN_VAULT_PATH, compartilhado por obsidian.py, research.py e mcp_server.py):
Cada conceito e um arquivo .md com YAML frontmatter padrao no topo:

type: concept
source: prompt (no azul) ou firecrawl (no verde) ou human (criado na mao pelo usuario)
cognitive_status: healthy | blind_delegation | frustration_loop
tags: [source/prompt, topic/exemplo] (ou source/firecrawl, ou adicionar alert/brain-rot quando houver delegacao cega)
locked_by_user: false (passa para true se o hash do conteudo mudar por edicao humana)
source_urls: [...] (para nos verdes vindos do Firecrawl)
Corpo em Markdown usando [[Nome do Outro Conceito]] para criar arestas no grafo.

Regra de Sync Bidirecional do Obsidian:
Manter um arquivo .vault_state.json (mapeando filename -> sha256_hash) e .ignore_nodes.json (lista de titulos deletados pelo usuario). Antes de escrever qualquer nota:

Se o arquivo existia em .vault_state.json e sumiu do disco: o usuario deletou no Obsidian -> adicionar o titulo em .ignore_nodes.json e nunca recriar.
Se o hash atual no disco e diferente do salvo em .vault_state.json: o usuario editou manualmente -> marcar locked_by_user: true, preservar o texto humano e apenas ler o novo conteudo como contexto para o agente e para o MCP.

Cores Automaticas no Obsidian (.obsidian/graph.json):
O script obsidian.py escreve automaticamente .obsidian/graph.json configurando colorGroups por tag:

tag:#source/prompt -> Azul (#3b82f6)
tag:#source/firecrawl -> Verde (#22c55e)
tag:#alert/brain-rot -> Vermelho/Laranja (#ef4444)

6. GUIA DE INTEGRACAO RAPIDA DAS BIBLIOTECAS (SNIPPETS VERIFICADOS)

Use exatamente estas bibliotecas e padroes minimos (sem wrappers complexos):

1. Firecrawl (pip install firecrawl-py):
Documentacao oficial: Firecrawl Python SDK e Firecrawl Search.
Uso mais simples (busca na web e ja retorna Markdown limpo em uma unica chamada):

from firecrawl import Firecrawl
app = Firecrawl(api_key=os.environ["FIRECRAWL_API_KEY"])
results = app.search(
    query="AI agent architecture best practices 2026",
    limit=3,
    scrape_options={"formats": ["markdown"]}
)

Para raspar uma URL especifica: doc = app.scrape(url, formats=["markdown"]) e ler doc.markdown.

2. Resend (pip install resend):
Documentacao oficial: Resend Python Docs.

import os, resend
resend.api_key = os.environ["RESEND_API_KEY"]
email = resend.Emails.send({
    "from": "onboarding@resend.dev",
    "to": [user_email],
    "subject": "Seu Raio-X Cognitivo de IA + Novos Nos no Obsidian",
    "html": html_string
})

Nota pratica de hackathon: onboarding@resend.dev permite testar enviando para o proprio e-mail da conta Resend imediatamente, sem precisar configurar DNS se o tempo estiver curto. Se tiverem dominio proprio verificado, trocar o from.

3. AbacatePay (pip install abacatepay):
Documentacao oficial: AbacatePay Python SDK e PyPI abacatepay.

import os, abacatepay
from abacatepay.products import Product
client = abacatepay.AbacatePay(os.environ["ABACATEPAY_API_KEY"])
billing = client.billing.create(
    products=[Product(external_id="pro-monthly", name="Plano Pro Cognitive OS", quantity=1, price=2990)],
    return_url="http://127.0.0.1:8765/",
    completion_url="http://127.0.0.1:8765/?pro=true"
)
checkout_url = billing.data.url

No frontend, o botao "Assinar Pro" chama a rota local, recebe checkout_url e abre no navegador padrao via webbrowser.open(checkout_url).

4. FastMCP (pip install fastmcp):
Documentacao oficial: FastMCP Quickstart.

from fastmcp import FastMCP
mcp = FastMCP("CognitiveWikiMCP")

@mcp.tool
def search_wiki(query: str) -> str:
    """Busca notas relevantes no vault do Obsidian do usuario."""
    ...

if __name__ == "__main__":
    # Para Claude Code / Claude Desktop local:
    mcp.run()
    # Ou para clientes web via HTTP (trocar por flag --http):
    # mcp.run(transport="http", port=8000)

5. Claude Agent SDK (pip install claude-agent-sdk):
Documentacao oficial: anthropics/claude-agent-sdk-python e Agent SDK Overview.
Ja vem com o Claude Code CLI embutido (nao precisa instalar separadamente). Permite rodar sessoes com skills customizadas, ferramentas de leitura/escrita local e conexao MCP:

import anyio
from claude_agent_sdk import query, ClaudeAgentOptions

async def run_skill(prompt_text: str):
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Write", "Bash"],
        permission_mode="acceptEdits"
    )
    async for message in query(prompt=prompt_text, options=options):
        ...

Para as skills de browser com Claude in Chrome, estruturar cada skill em skills/*.md com instrucao explicita: navegar ate a pagina de exportacao/historico da plataforma, detectar se esta na tela de login, interromper e solicitar que o usuario realize o login manualmente no navegador, e somente apos confirmacao prosseguir com o download/extracao dos arquivos para a pasta local de importacao.

6. App Desktop Cross-Platform (pip install fastapi uvicorn pywebview):
Documentacao oficial: pywebview.
No app.py, inicie o uvicorn.run(fastapi_app, host="127.0.0.1", port=8765) em uma threading.Thread(daemon=True) e chame webview.create_window("Cognitive Wiki OS", "http://127.0.0.1:8765", width=1100, height=750) seguido de webview.start(). Em 15 linhas de Python voce tem um app desktop nativo rodando no Mac e no Windows.

7. PESQUISA E ARQUITETURA DE ML — RLVR COM W-REINFORCE / NSR

Base Cientifica:
Paper "The Surprising Effectiveness of Negative Reinforcement in LLM Reasoning" (Zhu et al., grupo da Danqi Chen / Princeton, aceito na NeurIPS 2025).

Artigo: arXiv:2506.01347
Repositorio oficial: TianHongZXY/RLVR-Decomposed

Como funciona a tecnica:
Em RLVR (Reinforcement Learning with Verifiable Rewards), o gradiente pode ser decomposto em dois componentes:

PSR (Positive Sample Reinforcement): reforca amostras certas. Aumenta acuracia imediata, mas causa colapso de diversidade (distribution sharpening) e pode degradar a generalizacao do modelo base.
NSR (Negative Sample Reinforcement): atualiza os pesos apenas onde o modelo erra, removendo massa de probabilidade dos caminhos que levaram ao erro e redistribuindo essa probabilidade entre as estrategias corretas que o modelo pre-treinado ja sabe.
W-REINFORCE: combina ambos dando peso muito maior ao erro do que ao acerto (no paper, o hiperparametro recomendado e positive_advantage_weight = 0.1 contra peso 1.0 para amostras negativas). Funciona muito bem em modelos compactos como Qwen3-4B e Qwen2.5-7B-Instruct.

Como transformar nosso diagnostico em Recompensas Verificaveis (RLVR):
Em vez de pedir texto livre subjetivo, o modelo recebe uma conversa e deve gerar <think>raciocinio</think> seguido de um JSON estrito:

{
  "category": "blind_delegation",
  "severity": 4,
  "evidence_quote": "trecho literal exato da fala do usuario",
  "topics": ["agentes de ia", "mcp"],
  "recommendation": "acao curta e concreta"
}

Nosso Verifier programatico de 3 camadas atribui recompensa deterministica para cada rollout:

Verificacao de Formato: <think> presente + JSON valido com todas as chaves obrigatorias e categoria valida (blind_delegation, frustration_loop, socratic_learning, active_cocreation).
Verificacao de Classificacao: category coincide com o gabarito do dataset sintetico.
Verificacao de Grounding (Anti-Alucinacao): o codigo checa deterministicamente se evidence_quote existe como substring exata (normalizando espacos/caixa) nas mensagens do usuario na conversa original. Se o modelo inventar ou parafrasear uma citacao -> recompensa negativa (penalizada fortemente pelo NSR).

Pipeline pratico para o Hackathon:

Gerar de 1.000 a 2.000 conversas sinteticas realistas (desenvolvimento, estudos, debugging, arquitetura) usando um LLM frontier, ja rotuladas com categoria, citacao-evidencia exata e topicos.
Rodar pos-treino com LoRA em Qwen3-4B ou Qwen2.5-7B-Instruct usando o repositorio RLVR-Decomposed (ou GRPOTrainer do TRL ajustando a vantagem positiva por 0.1 e mantendo a negativa em 1.0).
Salvar um grafico comparativo simples para o pitch: Modelo Base vs. SFT padrao vs. W-REINFORCE (NSR) medindo (a) acuracia de classificacao cognitiva e (b) taxa de alucinacao na citacao-evidencia.
Na execucao local (diagnostics.py), carregar o modelo fine-tunado (via Ollama/llama.cpp/transformers) com uma flag de fallback para garantir que a demo nunca trave se o notebook da apresentacao estiver sem GPU.
Complementar com metricas matematicas sem LLM: razao de tamanho/esforco entre prompt do usuario e resposta da IA, frequencia de repeticao de erro (similaridade de embeddings locais) e distribuicao temporal.

Justificativa pronta para o Pitch:
"Em vez de montar apenas um wrapper de prompt ou um SFT basico que decora dados sinteticos e estraga o raciocinio do modelo, aplicamos RLVR com W-REINFORCE (NeurIPS 2025) em um modelo local pequeno. Nosso verificador programatico checa deterministicamente a classificacao cognitiva e o grounding literal da evidencia na conversa. Usando Negative Sample Reinforcement, suprimimos alucinacoes e diagnosticos errados preservando o raciocinio do modelo base — rodando 100% local com privacidade total."

8. DIVISAO DE TRABALHO EM TASKS PARA 4 PESSOAS

Pessoa 1 — ML, Dataset Sintetico, Treino W-REINFORCE e diagnostics.py

Task 1.1: Definir os exemplos-guia das 4 categorias cognitivas (blind_delegation, frustration_loop, socratic_learning, active_cocreation) e criar o script gerador de 1.000 a 2.000 conversas sinteticas com gabarito e evidence_quote literal.
Task 1.2: Implementar o Verifier deterministico de 3 camadas (formato JSON, categoria e grounding exato de substring).
Task 1.3: Configurar e rodar o treinamento LoRA com W-REINFORCE (positive_advantage_weight = 0.1, peso negativo 1.0) em Qwen3-4B ou Qwen2.5-7B-Instruct usando RLVR-Decomposed ou TRL.
Task 1.4: Rodar benchmark rapido (Base vs. SFT vs. W-REINFORCE) e salvar os numeros/grafico para a apresentacao.
Task 1.5: Implementar diagnostics.py lendo data/conversations.json, executando inferencia + metricas quantitativas de esforco de prompt e gravando data/diagnostics.json conforme o Contrato 2 (incluindo modo mock/fallback para testes da equipe desde o Dia 1).

Pessoa 2 — Grafo de Conhecimento Obsidian (obsidian.py) e Pesquisa Proativa (research.py)

Task 2.1: Implementar obsidian.py para inicializar o Vault local (OBSIDIAN_VAULT_PATH) e gerar .obsidian/graph.json automaticamente com cores azul (#source/prompt), verde (#source/firecrawl) e vermelho (#alert/brain-rot).
Task 2.2: Implementar a geracao e atualizacao de notas .md a partir de data/conversations.json e data/diagnostics.json, com YAML frontmatter padrao e [[wikilinks]] conectando conceitos correlatos.
Task 2.3: Implementar o sync bidirecional com .vault_state.json e .ignore_nodes.json (respeitar edicoes manuais e nunca recriar nos deletados pelo usuario no Obsidian).
Task 2.4: Implementar a analise de topologia do grafo com networkx (ler todos os [[wikilinks]], identificar clusters centrais, nos isolados e nos com blind_delegation) e usar LLM para propor 2 a 3 nos de fronteira por execucao.
Task 2.5: Implementar research.py usando firecrawl-py (app.search(..., scrape_options={"formats": ["markdown"]})) para pesquisar cada no de fronteira, sintetizar a nota verde com fontes reais e salvar em obsidian.py conectada ao grafo existente.
Task 2.6 (Bonus se sobrar tempo): Adicionar funcao simples em obsidian.py para fazer git add / commit / push do vault para um repositorio privado do usuario no GitHub.

Pessoa 3 — Coleta de Dados (collector.py), Skills de Agente (skills/) e Servidor MCP (mcp_server.py)

Task 3.1: Mapear os caminhos exatos das pastas locais do Claude Code (.claude) e Codex (.codex) em macOS e Windows usando Path.home(), e escrever o parser em collector.py gerando data/conversations.json (Contrato 1).
Task 3.2: Implementar no mesmo collector.py o importador de exports nativos .json/.zip do ChatGPT Web, Claude Web e Gemini Web (garantia 100% funcional para a demo).
Task 3.3: Testar manualmente o fluxo de exportacao web uma vez em cada plataforma e escrever as 3 skills em skills/ (extract_chatgpt.md, extract_claude.md, extract_gemini.md) com parada obrigatoria human-in-the-loop na tela de login para uso com Claude in Chrome / claude-agent-sdk.
Task 3.4: Integrar a chamada da skill no collector.py (com suporte a execucao sob demanda e verificacao de periodicidade de 15 dias via timestamp salvo localmente).
Task 3.5: Implementar mcp_server.py usando fastmcp expondo ferramentas para ler o grafo do Obsidian (search_wiki, read_node, list_frontier_nodes, get_cognitive_summary), testado tanto via stdio no Claude Code quanto via http para interface web.

Pessoa 4 — Base do Repositorio, App Desktop Local (app.py + index.html), Resend e AbacatePay (integrations.py)

Task 4.1: Criar o repositorio inicial com pyproject.toml, .env.example, .gitattributes (LF), pasta data/ com arquivos mock validos dos Contratos 1 e 2, e validar instalacao limpa no Mac e no Windows.
Task 4.2: Implementar integrations.py com o envio de e-mail via resend (template HTML limpo com Score Cognitivo, diagnosticos principais, recomendacoes e links dos novos nos verdes do Firecrawl) e geracao de link de checkout Pro via abacatepay.
Task 4.3: Implementar app.py (FastAPI + pywebview com fallback --browser) e index.html (interface unica e enxuta com botoes: Sincronizar Conversas Locais, Rodar Skill Web, Analisar Saude Cognitiva, Atualizar Grafo Obsidian + Firecrawl, Enviar Relatorio por E-mail, Abrir Vault no Obsidian, Assinar Plano Pro).
Task 4.4: Integrar os modulos das Pessoas 1, 2 e 3 no fluxo ponta a ponta dentro do app.py e garantir que tudo roda com um unico comando (uv run python app.py) tanto no Mac quanto no Windows.
Task 4.5: Montar o roteiro da demo de 3 minutos (execucao local -> inferencia do modelo W-REINFORCE -> abrir Obsidian ao vivo mostrando nos azuis, alertas vermelhos e nos verdes recem-criados pelo Firecrawl -> abrir caixa de entrada mostrando o e-mail do Resend -> demonstrar MCP respondendo com contexto do grafo -> checkout AbacatePay).

9. SEQUENCIA PRATICA DE EXECUCAO (48 A 72 HORAS)

Primeiras 4 horas (Desbloqueio): Pessoa 4 sobe o scaffold + contratos JSON mockados; todos testam uv sync no Mac e no Windows; Pessoa 1 ja dispara a geracao do dataset sintetico; Pessoa 2 testa Firecrawl e gera o primeiro vault com .obsidian/graph.json; Pessoa 3 ja extrai logs reais de .claude/.codex.
Dia 1 (Noite) — Primeiro Loop Ponta a Ponta: App abre localmente, le conversas reais da maquina, roda diagnostico (mesmo que com modelo base/mock enquanto o W-REINFORCE treina), cria nos azuis e verdes no Obsidian e envia o primeiro e-mail no Resend.
Dia 2 — Diferenciais de Peso: Pessoa 1 pluga o modelo treinado com W-REINFORCE e fecha os graficos comparativos; Pessoa 2 finaliza sync bidirecional (edicao/delecao no Obsidian) e bordas com networkx; Pessoa 3 fecha o servidor FastMCP conectado ao Claude Code + skill do Claude in Chrome com pausa de login; Pessoa 4 pluga AbacatePay e poli a UI local.
Dia 3 (Manha) — Congelamento e Ensaio: Zero refatoracao estrutural. Testar a demo completa em modo offline/online, validar fallback do modelo local, verificar se o Obsidian abre com as cores certas e ensaiar o pitch de 3 minutos.

