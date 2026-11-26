"""Diagnostico de saude cognitiva no uso de IA.
build_prompt + verify sao o contrato do classificador e TAMBEM a recompensa verificavel do treino
RLVR (train_wreinforce.py importa os dois): mudar aqui muda o que o modelo aprende."""
import json
import re

CATEGORIES = {
    "blind_delegation": "Pede a solucao pronta sem tentar nem entender.",
    "frustration_loop": "Repete o mesmo erro ou pedido sem investigar a causa.",
    "socratic_learning": "Pergunta o porque, busca intuicao, testa hipoteses proprias.",
    "active_cocreation": "Traz trabalho e ideias proprias e usa a IA para revisar ou decidir.",
}
KEYS = ("category", "severity", "evidence_quote", "topics", "recommendation")


def build_prompt(conversation: dict) -> str:
    """Prompt deterministico do classificador (mesmo texto no treino e na inferencia)."""
    lines = []
    for msg in (conversation or {}).get("messages") or []:
        user = msg.get("role") == "user"
        text = " ".join(str(msg.get("content") or "").split())[:1500 if user else 300]
        lines.append(f"{'USUARIO' if user else 'IA'}: {text}")
    chat = "\n".join(lines)
    if len(chat) > 6000:
        chat = chat[:3000] + "\n[...]\n" + chat[-3000:]
    definitions = "\n".join(f"- {name}: {desc}" for name, desc in CATEGORIES.items())
    return f"""Voce avalia a saude cognitiva de uma pessoa no uso de IA a partir de uma conversa dela com um assistente.

Categorias:
{definitions}

Conversa:
{chat}

Classifique a conversa. Responda primeiro com <think>raciocinio curto</think> e depois com UM objeto JSON com as chaves:
- "category": uma das categorias acima
- "severity": inteiro de 1 a 5 (5 = mais preocupante; categorias saudaveis usam 1)
- "evidence_quote": trecho LITERAL copiado de uma fala do USUARIO (10 a 200 caracteres), sem parafrasear
- "topics": lista de 1 a 5 conceitos tecnicos discutidos, em minusculas
- "recommendation": uma frase concreta do que a pessoa deveria fazer diferente"""


def is_grounded(quote, conversation) -> bool:
    """True se a citacao (>=10 chars) aparece literalmente numa fala do usuario (ignora caixa e espacos)."""
    norm = lambda s: " ".join(str(s or "").lower().split())
    q = norm(quote)
    return len(q) >= 10 and any(
        q in norm(m.get("content")) for m in (conversation or {}).get("messages") or [] if m.get("role") == "user"
    )


def verify(output_text, conversation, gold_category=None) -> dict:
    """Verificador de 3 camadas (formato, categoria, grounding). reward = +1 se tudo ok, senao -1. Nunca levanta."""
    out = {"format_ok": False, "category_ok": None if gold_category is None else False,
           "grounding_ok": False, "reward": -1.0, "parsed": None}
    try:
        match = re.search(r"<think>.*?</think>", str(output_text), re.S)
        rest = str(output_text)[match.end():] if match else ""
        parsed, _ = json.JSONDecoder().raw_decode(rest[rest.index("{"):]) if "{" in rest else (None, 0)
        if not isinstance(parsed, dict):
            return out
        out["parsed"] = parsed
        out["format_ok"] = bool(
            match and all(k in parsed for k in KEYS) and parsed["category"] in CATEGORIES
            and isinstance(parsed["severity"], int) and 1 <= parsed["severity"] <= 5
            and isinstance(parsed["topics"], list)
        )
        if gold_category is not None:
            out["category_ok"] = parsed.get("category") == gold_category
        out["grounding_ok"] = is_grounded(parsed.get("evidence_quote"), conversation)
        if out["format_ok"] and out["grounding_ok"] and out["category_ok"] in (True, None):
            out["reward"] = 1.0
    except Exception:
        pass
    return out
