"""Unica porta de saida para os dois LLMs do app:
- ask_json: LLM "geral" (Claude via claude-agent-sdk, usa o login do Claude Code; sem API key).
- ask_small: LLM "pequeno" treinado (W-REINFORCE) servido via vLLM, API compativel com OpenAI.
Usado por diagnostics, obsidian, research e train_wreinforce."""
import json
import os
import re
import ssl
import urllib.error
import urllib.request

import anyio
from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

try:
    import certifi  # macOS sem os certificados do sistema
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()


def ask_json(prompt: str, fast: bool = False):
    """Manda um prompt ao LLM geral (sem ferramentas, 1 turno) e devolve o JSON (dict ou list) da resposta.
    fast=True -> modelo rapido/barato para varredura (LLM_MODEL_FAST, padrao haiku);
    senao -> modelo de decisao (LLM_MODEL, padrao sonnet). Levanta excecao se indisponivel."""
    options = ClaudeAgentOptions(
        tools=[], max_turns=1, setting_sources=[],
        extra_args={"no-session-persistence": None},  # nao poluir ~/.claude/projects (o collector leria como conversa)
        model=os.getenv("LLM_MODEL_FAST", "haiku") if fast else os.getenv("LLM_MODEL", "sonnet"),
        system_prompt="Responda APENAS com JSON valido, sem markdown e sem texto extra.",
    )

    async def run():
        text = ""
        async for msg in query(prompt=prompt, options=options):
            if isinstance(msg, ResultMessage):
                text = msg.result or ""
        return text

    text = anyio.run(run)
    match = re.search(r"(\{.*\}|\[.*\])", text, re.S)
    return json.loads(match.group(1) if match else text)


def ask_small(prompt: str) -> str:
    """Manda o prompt ao modelo treinado (vLLM/OpenAI-compatible) e devolve o texto cru da resposta."""
    url = os.getenv("SMALL_MODEL_URL", "").strip().rstrip("/")
    if not url:
        raise RuntimeError("SMALL_MODEL_URL vazio: aponte para o servidor vLLM do modelo treinado")
    body = json.dumps({"model": os.getenv("SMALL_MODEL_NAME", "cognitive"),
                       "messages": [{"role": "user", "content": prompt}],
                       "temperature": 0, "max_tokens": 384}).encode("utf-8")
    req = urllib.request.Request(url + "/v1/chat/completions", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    key = os.getenv("SMALL_MODEL_API_KEY", "").strip()
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(req, timeout=120, context=SSL_CONTEXT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"modelo pequeno HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:300]}")
    return data["choices"][0]["message"]["content"]


if __name__ == "__main__":
    print(ask_json('Liste 3 conceitos vizinhos de "grafos de conhecimento" como {"topics": [...]}'))
