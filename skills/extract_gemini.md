# Skill: extrair conversas do Gemini (melhor esforco)

Objetivo: abrir o gemini.google.com no Chrome ja aberto pela ferramenta MCP `chrome-devtools`, raspar o DOM das
conversas do usuario logado e salvar uma lista compativel com o importador do collector (formato do Google
Takeout), no caminho exato informado no prompt.

O Gemini nao tem API REST estavel (`batchexecute` e fragil e muda sem aviso). Portanto: raspe o DOM; se falhar,
NAO invente dados e oriente o usuario a usar o Google Takeout.

Trabalhe sozinho e direto: sem pedir confirmacao, sem usar ferramentas fora das permitidas.

## Passo 1 — abrir o site

1. Chame `new_page` com `url: "https://gemini.google.com/app"` e guarde o `pageId` retornado.
2. Se ja houver uma aba do Gemini, use `list_pages` e `select_page` com esse `pageId` (nao abra outra).
3. Passe sempre esse `pageId` nas chamadas seguintes.

## Passo 2 — detectar login (obrigatorio)

1. Chame `take_snapshot` e observe a tela e a URL.
2. Se houver botao/link "Sign in"/"Fazer login", campo de e-mail/senha ou a URL for de autenticacao
   (`accounts.google.com`, `login`, `signin`, `auth`):
   responda APENAS a linha `AGUARDANDO_LOGIN` e encerre o turno imediatamente.
3. NUNCA digite e-mail, senha ou codigo, nunca resolva captcha/2FA e nunca clique em "Sign in".

## Passo 3 — raspar e salvar

1. Chame `evaluate_script` com o script abaixo, `waitForStableDom: false` e `filePath` igual ao caminho de
   destino informado no prompt (caminho absoluto, terminando em `gemini_web.json`). O MCP grava no disco
   exatamente o JSON retornado.
2. Troque `LIMIT` pelo limite de conversas informado no prompt.
3. Se o `filePath` falhar, rode o mesmo script sem `filePath` e grave a lista retornada com a ferramenta
   `Write` no caminho exato (JSON puro, sem markdown).
4. Cada item da lista deve ter `title` (primeira fala do usuario), `time` (ISO), `titleUrl` e
   `safeHtmlItem` (lista de `{"html": texto}`): e o formato que `_import_gemini` entende.

```js
async () => {
  const LIMIT = 50;
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const hrefs = Array.from(document.querySelectorAll('a[href*="/app/"]'))
    .map((a) => a.href)
    .filter((href, i, all) => /\/app\/[0-9A-Za-z_-]{6,}/.test(href) && all.indexOf(href) === i)
    .slice(0, LIMIT);
  const readTurns = () => {
    const turns = [];
    for (const node of document.querySelectorAll('user-query, model-response')) {
      const text = (node.innerText || '').trim();
      if (text) turns.push({ role: node.tagName.toLowerCase() === 'user-query' ? 'user' : 'assistant', text });
    }
    return turns;
  };
  const out = [];
  for (const href of hrefs) {
    const link = Array.from(document.querySelectorAll('a[href*="/app/"]')).find((a) => a.href === href);
    if (link) link.click();
    for (let i = 0; i < 20 && !document.querySelector('model-response'); i++) await sleep(400);
    await sleep(800);
    const turns = readTurns();
    if (!turns.length) continue;
    const first = turns.find((turn) => turn.role === 'user');
    out.push({
      title: (first ? first.text : document.title).slice(0, 200),
      time: new Date().toISOString(),
      titleUrl: href,
      safeHtmlItem: turns.filter((turn) => turn !== first).map((turn) => ({
        html: (turn.role === 'user' ? '**Usuario:** ' : '**Assistente:** ') + turn.text,
      })),
    });
    await sleep(300);
  }
  return out;
}
```

Se a lista voltar vazia ou o DOM nao tiver as falas, responda `FALHOU: use o Google Takeout` e pare sem
gravar arquivo. Nao invente conversas.

## Passo 4 — confirmar

Depois que o arquivo existir e for uma lista JSON, responda apenas: `CONCLUIDO <n>` (n = numero de conversas
salvas). Nao cole o JSON na resposta. Avise em uma linha que a extracao do Gemini e aproximada e que o
Google Takeout e o caminho recomendado.
