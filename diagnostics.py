"""Diagnostico de saude cognitiva no uso de IA.
build_prompt + verify sao o contrato do classificador e TAMBEM a recompensa verificavel do treino
RLVR (train_wreinforce.py importa os dois): mudar aqui muda o que o modelo aprende."""
import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

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


# --- diagnostico por conversa -------------------------------------------------------------------
RULES = [
    ("frustration_loop", r"não funcionou|nao funcionou|continua|ainda d[áa] erro|mesmo erro|same error|"
                         r"still (?:not|the same|failing|broken)"),
    ("blind_delegation", r"s[óo] manda|faz pra mim|faz tudo|faz o \w+ inteiro|n[ãa]o precisa (?:me )?explicar|"
                        r"just give me|write it for me|resume .{0,80}pra mim"),
    ("socratic_learning", r"por que|porque|intui[çc][ãa]o|entender|why|how does"),
]
STOPWORDS = set("""a o e de da do das dos em um uma para pra por que com sem no na nos nas se eu voce voce
meu minha seu sua isso isto esse essa este esta ao aos as os mais como quando onde qual quais sobre
ainda algo tem ter fazer faz fazendo fazia pode posso preciso quero vou veja ver the and for with
that this you your are was were have has had not but can could would should just what how why""".split())
TEMPLATES = {
    "blind_delegation": "Antes de pedir a solucao pronta, escreva voce um esboco em 5 passos e peca revisao critica.",
    "frustration_loop": "Quando o erro repetir 2 vezes, pare e mande logs/diagnostico em vez de pedir outra tentativa.",
    "socratic_learning": "Bom uso: continue pedindo intuicao e testando hipoteses proprias antes da resposta pronta.",
    "active_cocreation": "Continue trazendo seu trabalho e suas decisoes para a IA revisar em vez de criar do zero.",
}


def _fallback(conv, users):
    """Heuristica deterministica (mock): regras por palavra-chave nas falas do usuario."""
    hits, quote = {}, ""
    for name, pattern in RULES:
        for text in users:
            if re.search(pattern, text, re.I):
                hits.setdefault(name, []).append(text)
    category = next((name for name, _ in RULES if name in hits), "active_cocreation")
    matched = hits.get(category)
    bad = category in ("frustration_loop", "blind_delegation")
    severity = (4 if len(matched) >= 2 else 3) if bad else 1
    source = (matched or users or [""])[0]
    for q in ([source] if matched else users or [""]):
        quote = " ".join(q.split())[:200]
        if quote:
            break
    words = re.findall(r"[a-záàâãéêíóôõúç]{5,}", " ".join(users).lower())
    topics = [w for w, _ in Counter(w for w in words if w not in STOPWORDS).most_common(3)]
    return {"conversation_id": conv.get("id"), "category": category, "severity": severity,
            "evidence_quote": quote, "grounding_verified": is_grounded(quote, conv),
            "topics": topics, "recommendation": TEMPLATES[category], "backend": "mock"}


_LOCAL = {}


def _local_generate(conv):
    """Modelo local (LoRA ou HF completo), carregado uma vez. Dependencias opcionais."""
    if not _LOCAL:
        model_id = os.getenv("LOCAL_MODEL", "").strip()
        if not model_id:
            raise RuntimeError("LOCAL_MODEL vazio: defina o adapter LoRA ou um modelo HF")
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError(f"backend local precisa de torch/transformers instalados: {exc}")
        adapter = (Path(model_id) / "adapter_config.json").exists()
        base_id = os.getenv("LOCAL_BASE_MODEL", "Qwen/Qwen2.5-0.5B-Instruct")
        tokenizer = AutoTokenizer.from_pretrained(base_id if adapter else model_id)
        model = AutoModelForCausalLM.from_pretrained(base_id if adapter else model_id)
        if adapter:
            try:
                from peft import PeftModel
            except ImportError as exc:
                raise RuntimeError(f"adapter LoRA exige peft instalado: {exc}")
            model = PeftModel.from_pretrained(model, model_id)
        device = ("cuda" if torch.cuda.is_available()
                  else "mps" if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available()
                  else "cpu")
        model.to(device).eval()
        _LOCAL.update(model=model, tokenizer=tokenizer, torch=torch, device=device)
    tok, torch, device = _LOCAL["tokenizer"], _LOCAL["torch"], _LOCAL["device"]
    text = tok.apply_chat_template([{"role": "user", "content": build_prompt(conv)}],
                                   add_generation_prompt=True, tokenize=False)
    inputs = tok(text, return_tensors="pt").to(device)
    with torch.no_grad():
        out = _LOCAL["model"].generate(**inputs, max_new_tokens=384, do_sample=False)
    return tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)


def diagnose_conversation(conv, backend="mock"):
    """Classifica uma conversa. Fallback deterministico em qualquer falha do LLM."""
    conv = conv or {}
    users = [str(m.get("content") or "") for m in conv.get("messages") or [] if m.get("role") == "user"]
    parsed, grounding = None, False
    if backend == "claude":
        try:
            import llm
            parsed = llm.ask_json(build_prompt(conv))
        except Exception as exc:
            print(f"claude falhou em {conv.get('id')}: {exc}")
        ok = isinstance(parsed, dict) and parsed.get("category") in CATEGORIES
        if ok and isinstance(parsed.get("severity"), int) and 1 <= parsed["severity"] <= 5:
            grounding = is_grounded(parsed.get("evidence_quote"), conv)
        else:
            parsed = None
    elif backend == "local":
        try:
            checked = verify(_local_generate(conv), conv)
            parsed, grounding = checked["parsed"], checked["grounding_ok"]
            if not checked["format_ok"]:
                parsed = None
        except Exception as exc:
            print(f"local falhou em {conv.get('id')}: {exc}")
        if not parsed:
            print(f"local sem formato valido em {conv.get('id')}")
    if not parsed:
        return _fallback(conv, users)
    return {"conversation_id": conv.get("id"), "category": parsed["category"],
            "severity": parsed["severity"], "evidence_quote": str(parsed.get("evidence_quote") or ""),
            "grounding_verified": grounding,
            "topics": [str(t).lower() for t in parsed.get("topics") or []][:5],
            "recommendation": str(parsed.get("recommendation") or TEMPLATES[parsed["category"]]), "backend": backend}


def run_cognitive_diagnosis(backend=None):
    """Diagnostica todas as conversas (com cache por id) e grava data/diagnostics.json."""
    backend = backend or os.getenv("DIAG_BACKEND", "mock")
    if backend not in ("mock", "claude", "local"):
        backend = "mock"
    src = DATA / "conversations.json"
    conversations = json.loads((src if src.exists() else ROOT / "mock" / "conversations.json").read_text(encoding="utf-8"))
    out_file = DATA / "diagnostics.json"
    old = {}
    if out_file.exists():
        try:
            old = {d["conversation_id"]: d for d in json.loads(out_file.read_text(encoding="utf-8")).get("conversation_diagnoses", [])}
        except Exception:
            old = {}
    ids = [c.get("id") for c in conversations]
    diagnoses, new = [], 0
    for conv in conversations:
        if old.get(conv.get("id"), {}).get("backend") == backend:  # cache so vale para o mesmo backend
            diagnoses.append(old[conv["id"]])
        else:
            diagnoses.append(diagnose_conversation(conv, backend))
            new += 1
    print(f"{new} novas, {len(ids) - new} do cache (backend {backend})")

    n = len(diagnoses) or 1
    pct = {cat: round(100.0 * sum(d["category"] == cat for d in diagnoses) / n, 1) for cat in CATEGORIES}
    summary = {"blind_delegation_pct": pct["blind_delegation"], "socratic_pct": pct["socratic_learning"],
               "frustration_loop_pct": pct["frustration_loop"], "active_cocreation_pct": pct["active_cocreation"]}
    ratios = []
    for conv in conversations:
        u = sum(len(str(m.get("content") or "")) for m in conv.get("messages") or [] if m.get("role") == "user")
        a = sum(len(str(m.get("content") or "")) for m in conv.get("messages") or [] if m.get("role") == "assistant")
        if a:
            ratios.append(u / a)
    summary["avg_prompt_effort_ratio"] = round(sum(ratios) / len(ratios), 2) if ratios else 0.0

    def health(d):
        if d["category"] == "blind_delegation":
            return 100 - 15 * d["severity"]
        if d["category"] == "frustration_loop":
            return 100 - 12 * d["severity"]
        return 100

    score = int(sum(health(d) for d in diagnoses) / len(diagnoses)) if diagnoses else 0
    healthy = max(("socratic_learning", "active_cocreation"), key=lambda c: pct[c])
    problems = sorted(("blind_delegation", "frustration_loop"), key=lambda c: -pct[c])[:2]
    recommendations = [TEMPLATES[c] for c in problems] + [TEMPLATES[healthy]]
    if backend != "mock" and diagnoses:
        worst = sorted(diagnoses, key=lambda d: -d["severity"])[:5]
        prompt = ("Voce e um coach de uso critico de IA. Com base SO nos agregados abaixo, escreva 3 recomendacoes "
                  "concretas em portugues, respondendo {\"recommendations\": [3 frases]}.\n"
                  + json.dumps({"metrics": summary, "score": score,
                                "worst": [{k: d[k] for k in ("category", "severity", "recommendation")} for d in worst]},
                               ensure_ascii=False))
        try:
            import llm
            got = llm.ask_json(prompt)
            got = got.get("recommendations") if isinstance(got, dict) else got
            if isinstance(got, list) and len(got) >= 3:
                recommendations = [str(r) for r in got[:3]]
        except Exception as exc:
            print(f"recomendacoes via LLM falharam ({exc}); usando template")

    result = {"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "cognitive_health_score": score, "summary_metrics": summary,
              "recommendations": recommendations, "conversation_diagnoses": diagnoses}
    out_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_file.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(out_file)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Diagnostico de saude cognitiva no uso de IA")
    parser.add_argument("--backend", choices=("mock", "claude", "local"), default=None)
    args = parser.parse_args()
    report = run_cognitive_diagnosis(args.backend)
    print(f"\nScore de saude cognitiva: {report['cognitive_health_score']}/100")
    print(json.dumps(report["summary_metrics"], indent=2, ensure_ascii=False))
    print("\nRecomendacoes:")
    for rec in report["recommendations"]:
        print(f"- {rec}")
    print("\nConversas:")
    for diag in report["conversation_diagnoses"]:
        print(f"- {diag['conversation_id']}: {diag['category']} (sev {diag['severity']}, "
              f"grounding={diag['grounding_verified']})")
