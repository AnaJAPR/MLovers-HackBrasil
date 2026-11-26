"""Pos-treino RLVR (W-REINFORCE, arXiv 2506.01347) do classificador de saude cognitiva.

A recompensa e verificavel e deterministica: diagnostics.verify (formato <think>+JSON, categoria = gabarito,
evidence_quote literal na fala do usuario). W-REINFORCE pondera o gradiente das amostras corretas por
lam=0.1 (PSR) e das incorretas por 1.0 (NSR): empurra probabilidade para fora dos erros sem colapsar a
diversidade do modelo base. Sem baseline, sem KL, sem clipping de razao.

Subcomandos (rode da raiz do repo; precisa do extra "train": torch transformers peft matplotlib):
  gen-data  dataset sintetico rotulado por um LLM forte (llm.ask_json) -> train_data/synthetic.jsonl (retomavel)
  sft       baseline supervisionado (LoRA) nas respostas-gabarito
  rl        W-REINFORCE (LoRA), opcionalmente partindo do adapter do SFT
  eval      geracao greedy no split de teste: acuracia, formato, alucinacao na evidencia
  plot      grafico Base vs SFT vs W-REINFORCE

Teste pequeno (GPU 16GB, ~30 min):
  python train_wreinforce.py eval --model Qwen/Qwen2.5-0.5B-Instruct --out outputs/base/eval.json
  python train_wreinforce.py sft  --model Qwen/Qwen2.5-0.5B-Instruct --out outputs/sft
  python train_wreinforce.py eval --model Qwen/Qwen2.5-0.5B-Instruct --adapter outputs/sft --out outputs/sft/eval.json
  python train_wreinforce.py rl   --model Qwen/Qwen2.5-0.5B-Instruct --init-adapter outputs/sft --out outputs/wreinforce --steps 30
  python train_wreinforce.py eval --model Qwen/Qwen2.5-0.5B-Instruct --adapter outputs/wreinforce --out outputs/wreinforce/eval.json
  python train_wreinforce.py plot --runs outputs/base outputs/sft outputs/wreinforce --out outputs/comparison.png

Escala (GPU grande, ex. A100/H100 80GB; Qwen3-4B ou Qwen2.5-7B-Instruct):
  python train_wreinforce.py gen-data --n 1500
  python train_wreinforce.py sft --model Qwen/Qwen3-4B --out outputs/sft-4b --epochs 2
  python train_wreinforce.py rl  --model Qwen/Qwen3-4B --init-adapter outputs/sft-4b --out outputs/wr-4b \
         --steps 300 --prompts-per-step 16 --rollouts 8 --micro-batch 8 --lam 0.1 --lr 2e-6
  ablacoes: --lam 1.0 (REINFORCE), --lam 0.0 (NSR puro), --psr-only (so positivas)
Usar no app: DIAG_BACKEND=local LOCAL_BASE_MODEL=Qwen/Qwen3-4B LOCAL_MODEL=outputs/wr-4b
"""
import argparse
import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path

from diagnostics import CATEGORIES, build_prompt, is_grounded, verify
from llm import ask_json

DOMAINS = [
    "desenvolvimento web", "machine learning", "debugging", "devops", "estudo para prova",
    "escrita academica", "analise de dados", "carreira", "matematica", "design de sistemas",
    "mobile", "seguranca",
]
HEALTHY = ("socratic_learning", "active_cocreation")


def gen_data(n: int, out: str) -> None:
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()] if path.exists() else []
    ids = {row["id"] for row in existing}
    done = len(existing)
    invalid = 0
    fails = 0
    empty = 0
    print(f"{done} exemplos ja no arquivo, faltam {max(0, n - done)}")

    while done < n:
        cat = list(CATEGORIES)[(done // 4) % len(CATEGORIES)]
        sev = "1" if cat in HEALTHY else "2 a 5 (variado)"
        prompt = f"""Gere 4 conversas REALISTAS entre um usuario e uma IA, para treinar um classificador de saude cognitiva no uso de IA.

Categoria pedida (todas as 4 conversas): {cat}
Definicao: {CATEGORIES[cat]}
Dominio: {random.choice(DOMAINS)}
Idioma: {"portugues brasileiro informal" if random.random() < 0.8 else "ingles"}
Severidade: {sev}

Regras:
- Cada conversa tem de 2 a 8 mensagens (alternando user/assistant). Falas do usuario realistas: as vezes com erros de digitacao e abreviacoes, curtas ou longas. Respostas da IA mais curtas (ate ~400 caracteres).
- Inclua casos DIFICEIS: conversas que comecam parecendo uma categoria e viram outra; usuario educado que mesmo assim delega cegamente; usuario que pede codigo pronto mas depois questiona e entende (cocreation).
- evidence_quote: trecho LITERAL de 10 a 200 caracteres copiado de UMA fala do usuario (sem parafrasear).

Responda JSON: {{"conversations": [{{"messages": [{{"role": "user|assistant", "content": "..."}}], "category": "{cat}", "severity": 1-5, "evidence_quote": "...", "topics": ["1 a 5 em minusculas"], "recommendation": "uma frase", "rationale": "1-2 frases"}}]}}"""
        try:
            batch = ask_json(prompt)
            if isinstance(batch, dict):
                batch = batch.get("conversations") or batch.get("data") or []
            if not isinstance(batch, list):
                raise ValueError("resposta sem lista de conversas")
            fails = 0
        except Exception as e:
            fails += 1
            invalid += 4
            print(f"  erro no LLM ({fails}/8): {e}")
            if fails >= 8:
                raise SystemExit("LLM indisponivel; abortando")
            continue

        new_rows = []
        for item in batch:
            if not isinstance(item, dict):
                invalid += 1
                continue
            msgs = item.get("messages")
            conv = {"messages": [{"role": m.get("role"), "content": str(m.get("content") or "").strip()}
                                 for m in (msgs or []) if isinstance(m, dict)]}
            label = {k: item.get(k) for k in ("category", "severity", "evidence_quote", "topics", "recommendation", "rationale")}
            ok = (
                label["category"] in CATEGORIES and label["category"] == cat
                and isinstance(label["severity"], int) and 1 <= label["severity"] <= 5
                and isinstance(label["topics"], list) and 1 <= len(label["topics"]) <= 5
                and all(isinstance(t, str) and t.strip() for t in label["topics"])
                and isinstance(label["recommendation"], str) and label["recommendation"].strip()
                and isinstance(label["rationale"], str) and label["rationale"].strip()
                and 2 <= len(conv["messages"]) <= 8
                and any(m["role"] == "user" and m["content"] for m in conv["messages"])
                and is_grounded(label["evidence_quote"], conv)
            )
            if not ok or done + len(new_rows) >= n:
                invalid += 0 if ok else 1
                continue
            raw = json.dumps(conv["messages"], ensure_ascii=False, sort_keys=True)
            item_id = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
            if item_id in ids:
                continue
            ids.add(item_id)
            first = next(m["content"] for m in conv["messages"] if m["role"] == "user")
            now = datetime.now(timezone.utc).isoformat()
            new_rows.append({
                "id": item_id,
                "split": "test" if int(item_id, 16) % 100 < 15 else "train",
                "conversation": {
                    "id": item_id, "source": "synthetic",
                    "title": " ".join(first.split())[:60], "created_at": now,
                    "messages": [{**m, "timestamp": now} for m in conv["messages"]],
                },
                "label": label,
            })

        if new_rows:
            with path.open("a", encoding="utf-8") as f:
                for row in new_rows:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            done += len(new_rows)
            empty = 0
            print(f"  +{len(new_rows)} ({done}/{n}) categoria={cat}")
        else:
            empty += 1
            print(f"  0 validos para {cat} ({empty}/10)")
            if empty >= 10:
                raise SystemExit("LLM nao produziu exemplos validos; abortando")

    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    by_cat = {c: sum(r["label"]["category"] == c for r in rows) for c in CATEGORIES}
    by_split = {s: sum(r["split"] == s for r in rows) for s in ("train", "test")}
    print(f"\n{path}: {len(rows)} exemplos")
    print(f"categorias: {by_cat}")
    print(f"splits: {by_split}")
    print(f"descartes nesta execucao: {invalid} (taxa {invalid / max(1, invalid + done - len(existing)):.1%})")

# ---------------------------------------------------------------------------------------------
# Treino: SFT (baseline) e W-REINFORCE (RLVR com Negative Sample Reinforcement), avaliacao e grafico.
# torch/transformers/peft sao dependencias opcionais (extra "train"): importados so aqui dentro.
# ---------------------------------------------------------------------------------------------
def load_examples(path, split):
    rows = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
    return [r for r in rows if r["split"] == split]


def target_text(label):
    """Resposta-gabarito no formato que o verificador exige: <think>rationale</think> + JSON."""
    answer = {k: label[k] for k in ("category", "severity", "evidence_quote", "topics", "recommendation")}
    return f"<think>{label['rationale']}</think>\n{json.dumps(answer, ensure_ascii=False)}"


def load_model(model_id, adapter=None, trainable=True):
    """Modelo base em bf16 + LoRA (novo, ou carregado de `adapter`). Devolve (torch, tokenizer, modelo, device)."""
    import torch
    from peft import LoraConfig, PeftModel, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer

    device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(model_id)
    tok.padding_side = "left"  # geracao em batch
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(model_id, dtype=torch.bfloat16).to(device)
    if adapter:
        model = PeftModel.from_pretrained(model, adapter, is_trainable=trainable)
    elif trainable:
        model = get_peft_model(model, LoraConfig(
            r=16, lora_alpha=32, lora_dropout=0.0, task_type="CAUSAL_LM",
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]))
    if trainable:
        model.gradient_checkpointing_enable()
        model.enable_input_require_grads()
    return torch, tok, model, device


def generate(torch, tok, model, device, convs, n=1, sample=False, max_new_tokens=384, temperature=1.0):
    """Gera n respostas por conversa. Devolve (ids completos, comprimento do prompt, mascara da resposta, textos)."""
    prompts = [tok.apply_chat_template([{"role": "user", "content": build_prompt(c)}],
                                       add_generation_prompt=True, tokenize=False) for c in convs]
    enc = tok(prompts, return_tensors="pt", padding=True, add_special_tokens=False).to(device)
    model.eval()
    with torch.no_grad():
        out = model.generate(**enc, do_sample=sample, temperature=temperature if sample else None, top_p=1.0 if sample else None,
                             top_k=None, max_new_tokens=max_new_tokens, num_return_sequences=n,
                             pad_token_id=tok.pad_token_id)
    plen = enc["input_ids"].shape[1]
    gen = out[:, plen:]
    # resposta = tokens ate o primeiro EOS (inclusive); depois disso e padding
    is_end = (gen == tok.eos_token_id) | (gen == tok.pad_token_id)
    mask = (torch.cumsum(is_end.int(), dim=1) - is_end.int()) == 0
    texts = [tok.decode(g[m & ~e], skip_special_tokens=False) for g, m, e in zip(gen, mask, is_end)]
    return out, enc["attention_mask"].repeat_interleave(n, dim=0), mask, texts


def cmd_sft(args):
    torch, tok, model, device = load_model(args.model)
    data = load_examples(args.data, "train")
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=args.lr)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    model.train()
    step = 0
    for epoch in range(args.epochs):
        random.Random(epoch).shuffle(data)
        for i, ex in enumerate(data):
            prompt = tok.apply_chat_template([{"role": "user", "content": build_prompt(ex["conversation"])}],
                                             add_generation_prompt=True, tokenize=False)
            p_ids = tok(prompt, add_special_tokens=False)["input_ids"]
            t_ids = tok(target_text(ex["label"]) + tok.eos_token, add_special_tokens=False)["input_ids"]
            ids = torch.tensor([p_ids + t_ids], device=device)
            labels = torch.tensor([[-100] * len(p_ids) + t_ids], device=device)  # loss so na resposta
            loss = model(input_ids=ids, labels=labels).loss / args.grad_accum
            loss.backward()
            if (i + 1) % args.grad_accum == 0 or i + 1 == len(data):
                opt.step()
                opt.zero_grad()
                step += 1
                print(f"sft epoca {epoch} passo {step} loss {loss.item() * args.grad_accum:.4f}", flush=True)
    model.save_pretrained(out)
    tok.save_pretrained(out)
    print(f"adapter salvo em {out}")


def cmd_rl(args):
    """W-REINFORCE: loss = -(lam * sum_{r=+1} logp(y) - sum_{r=-1} logp(y)) / tokens (sem baseline, sem KL).
    Dois cuidados para modelos pequenos com recompensa esparsa: respostas truncadas ficam fora da loss e o NSR
    nao penaliza o token EOS (sem isso o modelo para de terminar as respostas e colapsa)."""
    import time

    torch, tok, model, device = load_model(args.model, args.init_adapter)
    data = load_examples(args.data, "train")[: args.limit_prompts or None]
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=args.lr)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    log = (out / "log.jsonl").open("a", encoding="utf-8")
    rng = random.Random(0)
    for step in range(1, args.steps + 1):
        t0 = time.time()
        batch = rng.sample(data, min(args.prompts_per_step, len(data)))
        seqs, prompt_mask, resp_mask, texts = generate(
            torch, tok, model, device, [ex["conversation"] for ex in batch], n=args.rollouts, sample=True,
            max_new_tokens=args.max_new_tokens, temperature=args.temperature)
        checks = [verify(t, batch[i // args.rollouts]["conversation"], batch[i // args.rollouts]["label"]["category"])
                  for i, t in enumerate(texts)]
        rewards = torch.tensor([c["reward"] for c in checks], device=device)
        # peso por amostra: corretas recebem lam (PSR), incorretas -1 (NSR)
        coef = torch.where(rewards > 0, torch.tensor(1.0 if args.psr_only else args.lam, device=device),
                           torch.tensor(0.0 if args.psr_only else -1.0, device=device))
        plen = prompt_mask.shape[1]
        gen = seqs[:, plen:]
        is_end = resp_mask & ((gen == tok.eos_token_id) | (gen == tok.pad_token_id))  # o 1o EOS de cada resposta
        # overlong filtering (DAPO): resposta cortada no limite nao e "errada", so incompleta -> fora da loss
        finished = is_end.any(dim=1)
        coef = coef * finished
        # NSR nao empurra o EOS para baixo: senao o modelo aprende a nao parar e as respostas crescem sem fim
        weight = coef[:, None] * resp_mask * ~(is_end & (coef < 0)[:, None])
        n_tokens = (resp_mask * (coef != 0)[:, None]).sum().clamp(min=1)
        attn = torch.cat([prompt_mask, resp_mask.long()], dim=1)
        model.train()
        opt.zero_grad()
        total = 0.0
        for s in range(0, len(texts), args.micro_batch):
            if not weight[s:s + args.micro_batch].any():
                continue
            ids, am, w = seqs[s:s + args.micro_batch], attn[s:s + args.micro_batch], weight[s:s + args.micro_batch]
            # logits so das posicoes que preveem os tokens gerados (economiza memoria do vocabulario)
            logits = model(input_ids=ids, attention_mask=am, logits_to_keep=w.shape[1] + 1).logits[:, :-1].float()
            logp = torch.log_softmax(logits, dim=-1).gather(-1, ids[:, plen:].unsqueeze(-1)).squeeze(-1)
            loss = -(w * logp).sum() / n_tokens
            loss.backward()
            total += loss.item()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        row = {"step": step, "reward_mean": rewards.mean().item(),
               "format_ok": sum(c["format_ok"] for c in checks) / len(checks),
               "category_ok": sum(bool(c["category_ok"]) for c in checks) / len(checks),
               "grounding_ok": sum(c["grounding_ok"] for c in checks) / len(checks),
               "n_pos": int((rewards > 0).sum()), "n_neg": int((rewards < 0).sum()),
               "truncated": int((~finished).sum()), "loss": total, "tokens": int(resp_mask.sum()),
               "seconds": round(time.time() - t0, 1)}
        log.write(json.dumps(row) + "\n")
        log.flush()
        print(json.dumps(row), flush=True)
        if step % 25 == 0 or step == args.steps:
            model.save_pretrained(out)
            tok.save_pretrained(out)
    print(f"adapter salvo em {out}")


def cmd_eval(args):
    torch, tok, model, device = load_model(args.model, args.adapter, trainable=False)
    data = load_examples(args.data, args.split)[: args.limit or None]
    checks, samples = [], []
    for s in range(0, len(data), args.batch):
        chunk = data[s:s + args.batch]
        _, _, _, texts = generate(torch, tok, model, device, [ex["conversation"] for ex in chunk],
                                  max_new_tokens=args.max_new_tokens)
        for ex, text in zip(chunk, texts):
            checks.append(verify(text, ex["conversation"], ex["label"]["category"]))
            if len(samples) < 5:
                samples.append({"gold": ex["label"]["category"], "output": text[:600]})
        print(f"eval {len(checks)}/{len(data)}", flush=True)
    n, parsed = len(checks) or 1, [c for c in checks if c["parsed"]]
    metrics = {
        "model": args.model, "adapter": args.adapter, "n": len(checks), "n_parsed": len(parsed),
        "format_rate": sum(c["format_ok"] for c in checks) / n,
        "accuracy": sum(bool(c["category_ok"]) for c in checks) / n,
        # evidencia verificada = citacao literal da fala do usuario, sobre TODAS as saidas (maior = melhor)
        "grounded_rate": sum(c["grounding_ok"] for c in checks) / n,
        # alucinacao = entre as saidas com JSON, citacao que NAO existe na conversa (None se nenhuma tem JSON)
        "hallucination_rate": sum(not c["grounding_ok"] for c in parsed) / len(parsed) if parsed else None,
        "reward_mean": sum(c["reward"] for c in checks) / n,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({**metrics, "samples": samples}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))


def cmd_plot(args):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    runs = [(Path(r).name, json.loads((Path(r) / "eval.json").read_text(encoding="utf-8"))) for r in args.runs]
    keys = [("accuracy", "Acuracia de categoria"), ("format_rate", "Formato valido"),
            ("grounded_rate", "Evidencia literal verificada")]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    width = 0.8 / len(runs)
    for i, (name, m) in enumerate(runs):
        bars = ax.bar([k + i * width for k in range(len(keys))], [m[key] for key, _ in keys], width, label=name)
        ax.bar_label(bars, fmt="%.2f", fontsize=8)
    ax.set_xticks([k + width * (len(runs) - 1) / 2 for k in range(len(keys))], [label for _, label in keys])
    ax.set_ylim(0, 1.05)
    ax.set_title("Base vs SFT vs W-REINFORCE (NSR) — classificador de saude cognitiva")
    ax.legend()
    fig.tight_layout()
    fig.savefig(args.out, dpi=150)
    print(f"grafico salvo em {args.out}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Treino RLVR (W-REINFORCE) do classificador de saude cognitiva.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    data = str(Path("train_data") / "synthetic.jsonl")
    p = sub.add_parser("gen-data", help="gera dataset sintetico rotulado")
    p.add_argument("--n", type=int, default=200)
    p.add_argument("--out", default=data)
    p = sub.add_parser("sft", help="baseline supervisionado (LoRA)")
    p.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    p.add_argument("--data", default=data)
    p.add_argument("--out", default=str(Path("outputs") / "sft"))
    p.add_argument("--epochs", type=int, default=1)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--grad-accum", type=int, default=4)
    p = sub.add_parser("rl", help="W-REINFORCE (LoRA)")
    p.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    p.add_argument("--data", default=data)
    p.add_argument("--out", default=str(Path("outputs") / "wreinforce"))
    p.add_argument("--init-adapter", default=None)
    p.add_argument("--lam", type=float, default=0.1, help="peso das amostras corretas (PSR); incorretas pesam 1.0")
    p.add_argument("--psr-only", action="store_true", help="ablacao: so reforco positivo")
    p.add_argument("--steps", type=int, default=30)
    p.add_argument("--prompts-per-step", type=int, default=8)
    p.add_argument("--rollouts", type=int, default=4)
    p.add_argument("--micro-batch", type=int, default=4)
    p.add_argument("--max-new-tokens", type=int, default=320)
    p.add_argument("--lr", type=float, default=2e-6)
    p.add_argument("--temperature", type=float, default=1.0)
    p.add_argument("--limit-prompts", type=int, default=0, help="usa so os N primeiros prompts (teste de sanidade)")
    p = sub.add_parser("eval", help="avalia no split de teste")
    p.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    p.add_argument("--adapter", default=None)
    p.add_argument("--data", default=data)
    p.add_argument("--split", default="test")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--batch", type=int, default=8)
    p.add_argument("--max-new-tokens", type=int, default=384)
    p.add_argument("--out", default=str(Path("outputs") / "eval.json"))
    p = sub.add_parser("plot", help="grafico comparativo")
    p.add_argument("--runs", nargs="+", required=True)
    p.add_argument("--out", default=str(Path("outputs") / "comparison.png"))
    args = parser.parse_args()
    if args.cmd == "gen-data":
        gen_data(args.n, args.out)
    else:
        {"sft": cmd_sft, "rl": cmd_rl, "eval": cmd_eval, "plot": cmd_plot}[args.cmd](args)
