"""Unica porta de saida para LLM. Usa o claude-agent-sdk, que reaproveita o login do Claude Code
(nao precisa de ANTHROPIC_API_KEY). Usado por diagnostics, obsidian, research e train_wreinforce."""
import json
import os
import re

import anyio
from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query


def ask_json(prompt: str, model: str | None = None):
    """Manda um prompt ao Claude (sem ferramentas, 1 turno) e devolve o JSON (dict ou list) da resposta.
    Levanta excecao se o Claude nao estiver disponivel; quem chama decide o fallback."""
    options = ClaudeAgentOptions(
        tools=[], max_turns=1, setting_sources=[],
        model=model or os.getenv("LLM_MODEL", "haiku"),
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


if __name__ == "__main__":
    print(ask_json('Liste 3 conceitos vizinhos de "grafos de conhecimento" como {"topics": [...]}'))
