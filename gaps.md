# gaps.md — o que sabemos que não está legal

Rodada de QA adversarial em 26/11/2026. Sete agentes fizeram papel de usuário real, cada um com uma persona
(usuário novo em Windows/Mac, usuário cético com o score, usuário de Obsidian que edita o vault, usuário de
MCP, usuário só da interface, usuário com histórico bagunçado e engenheiro de ML). O objetivo era **quebrar**,
não demonstrar. Cada agente rodou com HOME falso e conversas falsas, sem chaves de Firecrawl, Resend ou
AbacatePay. **Nada foi corrigido.** Este arquivo é a lista de trabalho.

Severidade: **CRÍTICA** = o produto mente ou perde dado do usuário · **ALTA** = quebra uma promessa da seção 1
do `ideia.md` · **MÉDIA** = atrapalha o uso · **BAIXA** = acabamento.
Os itens marcados com (suspeito) vieram só de leitura de código; o resto foi reproduzido.

---

## Prioridade (o que atacar primeiro)

1. **Instalação nova mostra dados de exemplo como se fossem do usuário.** Sem `data/`, os botões Diagnosticar e
   Atualizar wiki usam `mock/conversations.json`. Com isso, o score, o vault, o e-mail e o MCP passam a conter
   conversas que a pessoa nunca teve.
2. **Wiki marca uma conversa como "ingerida" mesmo sem criar nota.** Isso acontece quando o LLM falha ou quando a
   wiki roda antes do diagnóstico, e a conversa nunca mais é processada.
3. **Renomear ou mover uma nota no Obsidian é tratado como "usuário deletou".** A nota fica congelada para sempre,
   o que quebra a promessa de edição bidirecional.
4. **O score mente nos dois extremos.** Zero conversas resultam em score 0 com "risco de brain rot". Conversas
   vazias contam como saudáveis. A heurística (backend padrão) chama de cocriação frases clássicas de delegação.
5. **O diagnóstico com o modelo pequeno aceita citação inventada.** O card mostra, como prova, uma frase que a
   pessoa nunca escreveu.
6. **O cache por `id` congela tudo.** Uma conversa que ganhou mensagens novas não é rediagnosticada nem reingerida.
7. **"Sem alucinar" nas notas verdes só verifica o formato `[n]`.** Basta uma citação válida para validar a nota
   inteira.
8. **O README ainda documenta o backend `local`/`LOCAL_MODEL`, que não existe mais.** Além disso, os CLIs não
   carregam o `.env`.

---

## Diagnóstico e score (`diagnostics.py`)

- **CRÍTICA — A heurística (mock, que é o padrão) inverte a delegação.** Frases como "me dá o código pronto",
  "escreve o relatório pra mim" e "resolve isso aí" viram `active_cocreation` com score 100, porque o regex
  cobre poucas frases e o default é cocriação (`diagnostics.py:106-120`).
- **CRÍTICA — Conversa vazia, só com a fala da IA ou corrompida conta como `active_cocreation` sev 1.** Ela entra
  no denominador e infla o score. Num teste, 3 de 11 conversas eram lixo e o resultado foi 88 ("uso saudável").
- **CRÍTICA — O backend small aceita `evidence_quote` sem grounding.** O código exige só `format_ok`
  (`diagnostics.py:146-150`). Em conversa sem fala do usuário, o modelo inventou "Pode me dizer o que eu devo
  fazer?" e o app exibiu a frase como evidência.
- **ALTA — Zero conversas ou dados ilegíveis dão score 0/100 com "Risco de brain rot".** Deveria aparecer "sem dados".
- **ALTA — O cache por `id` ignora mudança de conteúdo.** Nenhum hash é guardado. Uma conversa longa do Claude Code
  fica com o diagnóstico da primeira vez em que foi vista. O mesmo vale para o wiki (veja abaixo).
- **ALTA — O score depende do backend e do servidor estar no ar.** Nos mesmos dados, mock deu 88 e small deu 67.
  Com o servidor fora, tudo cai na heurística silenciosamente: o único sinal é uma pill no topo da página. O
  e-mail e o MCP não dizem qual método foi usado.
- **ALTA — O diagnóstico mock vai para o e-mail e para o MCP (`get_cognitive_summary`) sem marcação de exemplo.**
- **MÉDIA — Ids duplicados fazem um diagnóstico sobrescrever o outro.**
- **MÉDIA — `conversations.json` ou `diagnostics.json` corrompido gera erro técnico ou KeyError.** A UI continua
  mostrando o score antigo ou mostra 0 sem explicar.
- **MÉDIA — O backend claude quebra a execução inteira com uma resposta `topics: null`.** As respostas dele não
  passam pelo `verify`.
- **MÉDIA — A fórmula do score (100−15·sev, 100−12·sev) é arbitrária e nunca foi calibrada.**
- **BAIXA — `avg_prompt_effort_ratio` usa média sem teto.** Uma única mensagem gigante domina a métrica.

## Wiki / Obsidian (`obsidian.py`)

- **CRÍTICA — Conversa marcada como ingerida sem nota.** Acontece com falha ou rate limit do LLM (o `except` vira
  `[]`), com a wiki rodando antes do diagnóstico, ou com título só de caracteres inválidos. `created: 0` e a
  conversa nunca é reprocessada. Reproduzir: `collector.py`, depois `obsidian.py --no-llm` sem diagnóstico,
  depois o diagnóstico e o sync de novo, que retorna `new_conversations: 0`.
- **ALTA — Renomear ou mover uma nota para subpasta conta como deleção.** A nota vai para `ignored` e não recebe
  mais nada. É o caso mais comum de uso do Obsidian.
- **ALTA — Apagar ou corromper `.wiki_state.json` ressuscita todas as notas que o usuário deletou.** O state é o
  único registro das deleções.
- **ALTA — Títulos com `/ # | :` geram `[[wikilinks]]` quebrados ou apontando para a nota errada.** O nome do
  arquivo é sanitizado, mas o link não.
- **ALTA — Mensagens novas numa conversa já ingerida nunca entram no wiki.** O registro de ingestão é por id.
- **MÉDIA — O frontmatter do usuário é sobrescrito.** Tags removidas voltam no próximo append, e uma nota que o
  usuário mudou para `source: human` volta a ficar azul.
- **MÉDIA — Nota esvaziada ou sem frontmatter não recupera o frontmatter.** Sai das cores e do estado.
- **MÉDIA — "Alocação" e "Alocacao" viram duas notas.** O lookup ignora caixa, mas não acento. Também visto com
  dados reais.
- **MÉDIA — `colorGroups` personalizados do usuário são substituídos a cada sync.** As outras chaves do
  `graph.json` são preservadas.
- **MÉDIA — O alerta vermelho também pega `frustration_loop` (sev ≥ 3).** O README diz que vermelho = delegação cega.
- **MÉDIA — Backup git com erro cru quando falta `user.name`, e o `.wiki_state.json` vai junto no commit/push.**
  Esse backup também não está no README.
- **MÉDIA — `--no-llm` cria notas genéricas ("Funciona", "Entender") e destrói siglas.**
- **BAIXA — Títulos com mais de 80 caracteres colidem no truncamento e fundem dois conceitos numa nota.**
- **BAIXA — A UI não mostra o que o sync fez, nem quando não fez nada, e não dá progresso com muitas conversas.**

## Notas verdes (`research.py`)

- **ALTA — "Sem alucinar" não é verificado.** Só se checa que existe pelo menos um `[n]` com `1 ≤ n ≤ fontes`.
  Frases sem citação, ou com citação que a fonte não sustenta, passam. Reproduzir: monkeypatch de `llm.ask_json`
  e Firecrawl com um resumo que mistura frases verdadeiras e inventadas.
- **ALTA — Nota verde apagada pelo usuário é recriada** se ele rodar "Pesquisar fronteira" antes de "Atualizar
  wiki". A detecção de deleção só roda no sync.
- **MÉDIA — Cada execução sobrescreve `data/frontier_research.json`.** As fontes das rodadas anteriores somem da UI
  e do MCP, e sem chave do Firecrawl o arquivo fica só com `sources: []`.
- **BAIXA — Sem Firecrawl, a seção "Novos nós verdes" mostra cards de tópicos sem nota, com aviso técnico.**

## MCP (`mcp_server.py`)

- **ALTA — `--http` não sobe na mesma máquina do vLLM.** A porta 8000 é fixa e não há flag para trocar.
- **ALTA — A seção 1 pede acesso por "interfaces web", mas o servidor é só local e o HTTP não tem CORS.** Um
  cliente MCP no navegador não conecta, e o README não explica como expor para o ChatGPT ou o Claude web.
- **MÉDIA — `read_node`/`get_graph_neighbors` ignoram acento e podem devolver a nota errada sem avisar.**
- **MÉDIA — `get_graph_neighbors` leva cerca de 20 s num vault de 3000 notas.** Cada chamada relê o vault inteiro.
  As outras tools respondem em menos de 1 s.
- **MÉDIA — Nota salva em cp1252 (Bloco de Notas do Windows) some do wiki e do MCP sem aviso.**
- **BAIXA — `search_wiki(limit=0)` ou com limite negativo devolve 1 resultado.**
- **BAIXA — O JSON de exemplo para Windows na docstring é inválido (barras invertidas sem escape).**

## Coleta (`collector.py` + skills web)

- **ALTA — O resumo de compactação do Claude Code ("This session is being continued…") entra como fala do usuário
  e vira o título da conversa.** Isso contamina o diagnóstico com texto escrito pela IA.
- **ALTA — `limit=200` ordena pela primeira mensagem.** Sessões antigas que continuam ativas e o histórico
  importado somem silenciosamente.
- **ALTA — A UI diz "ok" mesmo quando todos os imports falham.** Com 0 conversas, ela não sugere importar o export.
- **ALTA — Zip de export grande é lido inteiro na memória**, e uma única mensagem gigante vai inteira para o
  `conversations.json`: o teste gerou um item de 100 MB num arquivo de 296 MB.
- **ALTA (suspeito) — O agente web não tem bloqueio técnico de domínio.** O limite está só no prompt da skill, e o
  `evaluate_script` aceita `filePath` arbitrário. Um prompt injection vindo do conteúdo das conversas poderia
  navegar ou gravar fora do esperado.
- **MÉDIA — Marcadores de interrupção ("[Request interrupted by user]") entram como fala do usuário.**
- **MÉDIA — BOM no início do `.jsonl` descarta a primeira linha em silêncio**, e pode sumir com a conversa inteira.
- **MÉDIA — Encoding não UTF-8 (cp1252/latin-1) corrompe o texto em silêncio.**
- **MÉDIA — Export do ChatGPT sem `current_node` mistura ramos editados e abandonados.**
- **MÉDIA — Export do Gemini com nome de arquivo localizado não é reconhecido.** O código só aceita
  `myactivity.json`.
- **MÉDIA — `CLAUDE_CONFIG_DIR` e `CODEX_HOME` são ignorados.** Quem tem a config fora de `~` vê 0 conversas.
- **MÉDIA (suspeito) — O erro real do agente web é descartado.** O usuário só vê "arquivo não gerado".
- **MÉDIA — O "a cada 15 dias" da seção 1 é só uma trava.** Nada roda sozinho; a extração é sempre manual.
- **BAIXA — Entidades HTML do Gemini não são decodificadas; `--limit` é ignorado no fim da extração web e não é
  validado quando negativo; pasta de export descompactada é ignorada; estado de extração com data futura
  bloqueia para sempre.**

## App / interface (`app.py` + `index.html`)

- **ALTA — O plano Pro é cosmético.** `?pro=true` ativa o Pro sem pagar, e não há webhook nem verificação da
  AbacatePay.
- **MÉDIA — Recarregar a página no meio de uma operação longa perde todo o feedback.** A operação continua no
  servidor gastando Claude, sem como acompanhar ou cancelar.
- **MÉDIA — O diagnóstico por conversa aparece só com o hash (`fd6351ec…`), sem o título.**
- **MÉDIA — O botão "mostrar todos (N)" aparece mesmo com 8 diagnósticos ou menos.** O `.btn {display:inline-flex}`
  anula o atributo `hidden`.
- **MÉDIA — Com `--port` diferente, o checkout de demo manda para a 8765.**
- **MÉDIA — Sem chave do Resend, aparece "RESEND_API_KEY ausente" cru e o preview gerado fica escondido.**
- **MÉDIA (suspeito) — "Abrir no Obsidian" usa `obsidian://open?path=<pasta>`**, que provavelmente não abre um
  vault que ainda não está registrado no Obsidian.
- **BAIXA — Os botões terminam com "ok" sem dizer o que fizeram**, e a falha de rede aparece como
  "Failed to fetch" em inglês.
- **BAIXA — Porta ocupada por outro serviço dá mensagem genérica e `exit 0`.**

## Instalação, README e Windows/macOS

- **ALTA — O README e a docstring do treino ainda falam de `DIAG_BACKEND=local`, `LOCAL_MODEL` e
  `LOCAL_BASE_MODEL`.** Com `--backend local` o CLI quebra, e com `DIAG_BACKEND=local` cai em mock em silêncio.
- **ALTA — `diagnostics.py`, `collector.py` e `mcp_server.py` rodados direto não carregam o `.env`.** O README manda
  configurar o `.env` e rodar os CLIs, mas `DIAG_BACKEND` e `SMALL_MODEL_*` são ignorados.
- **ALTA — Windows e macOS nunca foram executados de verdade.** Tudo foi revisão de código. Os riscos (suspeitos)
  são o `npx` virar `npx.cmd` no Windows, o Node não ser verificado, o caminho do Obsidian e o `uv` no Windows.
- **MÉDIA — O LLM geral exige o Claude Code instalado e logado.** Quem não tem fica só com a heurística, que é
  justamente a parte mais fraca (veja Diagnóstico).
- **MÉDIA — O setup com `uv` não lembra de copiar o `.env.example`, e a tabela de variáveis do README tem
  defaults errados.**
- **MÉDIA — Privacidade parcial.** Com o backend small em outra máquina, as conversas trafegam em HTTP puro, só com
  API key. Com os backends claude ou haiku, o conteúdo vai para a Anthropic. O README destaca o "fica local" e não deixa
  claro o que sai da máquina.
- **BAIXA (suspeito) — O e-mail sai de `onboarding@resend.dev`.** Sem domínio verificado, o Resend só entrega para
  o dono da conta.

## Modelo treinado e treino (`train_wreinforce.py`)

- **ALTA — Nas conversas reais, o modelo concorda com o Claude em só 14 de 39 categorias (36%).** Ele superestima a
  delegação cega (16 contra 7), e 6 das 39 saídas foram inválidas e caíram na heurística. Causa: o treino usou
  200 conversas sintéticas de cerca de 714 caracteres e 6 mensagens, e as sessões reais de agente de código são
  ordens de grandeza maiores.
- **ALTA — As conclusões do README não se sustentam com 26 exemplos de teste.** A acurácia de SFT e de
  W-REINFORCE é a mesma (17/26, IC95% 46–81%), e o grounded vai de 85% para 88% dentro do ruído. O modelo
  servido acertou 16/26 (62%) no teste, com formato válido em 25/26 e 5,8 s por chamada em série.
- **MÉDIA — Grounding fácil de cumprir.** Qualquer trecho de 10 caracteres da fala do usuário passa (162 de 200
  casos), mesmo sem sustentar a categoria. O `<think>` vazio também ganha reward +1 em 200 de 200. O verificador
  não exige raciocínio nem relação entre a citação e a categoria.
- **MÉDIA — A receita da GPU grande não avalia o modelo base nem o SFT**, mas o `plot --runs outputs/base
  outputs/sft …` espera esses resultados.
- **MÉDIA (suspeito) — A receita grande usa o Qwen3-4B, que nunca foi testado.** O template do Qwen3 tem modo de
  raciocínio próprio (`enable_thinking`) que pode conflitar com o `<think>` exigido pelo verificador, e o comando
  vLLM do README é para o Qwen2.5-1.5B.
- **MÉDIA — O rótulo do dataset vem do próprio Claude (`gen-data`)**, então o modelo pequeno no máximo imita o
  Claude, sem rótulo humano.
- OK: classes balanceadas (47–53 por categoria), nenhuma quase duplicata entre treino e teste e flags do argparse
  batendo com o README.

---

## O que foi testado e aguentou

- **Segurança local:** `Host` e `Origin` de outro site dão 403. Métodos errados dão 405. XSS em citações e tópicos
  é renderizado como texto. JSON de 1 MB no body não trava.
- **Path traversal:** o `read_node` do MCP resiste a `../../.env`, `/etc/passwd` e `C:\…`, e zip com `../` não grava
  fora de `data/`.
- **Coleta:** o parser ignora linhas JSON quebradas, CRLF, sidechain, sessões do SDK, subagentes do Codex,
  tool_use/tool_result e system-reminders. 500 sessões levam 0,6 s.
- **Wiki:** texto editado pelo usuário nunca é reescrito. Deleção com o state intacto é respeitada. Nomes
  reservados do Windows e emoji funcionam. Vault dentro de outro repo git não afeta o repo pai.
- **UI:** clique duplo e cliques concorrentes não duplicam requisições, e a escrita é atômica. Os layouts de 375 px,
  1280 px e tema escuro estão OK. A acessibilidade básica (nomes, `aria-live`, foco visível) está OK.
- **Modelo pequeno:** resistiu a 3 variantes de prompt injection pedindo para ser classificado como saudável.
- **Sem chaves:** e-mail (gera preview), checkout (URL de demo) e Firecrawl degradam sem quebrar.

## O que ninguém testou ainda

- Windows e macOS de verdade, e o app Obsidian aberto em cima do vault.
- Extração web com login real (ChatGPT, Claude.ai, Gemini) e o DOM atual dessas páginas.
- AbacatePay com chave real (e o webhook, que não existe).
- E-mail do Resend para um destinatário diferente do dono da conta.
- Modelo servido em outra máquina, pela rede.
- Volume real grande (milhares de conversas com o LLM, custo e tempo do ingest).
