"""Integracoes externas: e-mail do relatorio (Resend) e checkout (AbacatePay REST v1).
Sem chave nos .env, tudo cai em modo local: o relatorio vira data/last_report.html e o checkout vira demo."""
import html
import json
import math
import os
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
MOCK = BASE / "mock"

try:
    from dotenv import load_dotenv
    load_dotenv(BASE / ".env")
except ImportError:
    pass

APP_URL = os.getenv("APP_URL", "http://127.0.0.1:8765")
ABACATEPAY_BASE = os.getenv("ABACATEPAY_BASE", "https://api.abacatepay.com")
try:
    import certifi  # macOS sem os certificados do sistema
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()


def pct(v, top=100.0):
    """float finito limitado a 0..top; NaN/inf/lixo/negativo viram 0."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return 0.0
    return min(v, top) if math.isfinite(v) and v > 0 else 0.0


def clip(text, n):
    text = "" if text is None else str(text)
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def load(name, kind=dict):
    """data/<name> com fallback para mock/<name>; JSON invalido ou tipo errado vira vazio."""
    for folder in (DATA, MOCK):
        try:
            raw = json.loads((folder / name).read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        return raw if isinstance(raw, kind) else kind()
    return kind()


def card(inner, border="#e5e7eb", bg="#ffffff"):
    """Cartao do e-mail, usado pelos diagnosticos e pelos nos verdes."""
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 12px;'
            f'border:1px solid {border};border-radius:8px;background:{bg};"><tr>'
            f'<td style="padding:14px 16px;">{inner}</td></tr></table>')


def sec(title, border, body):
    return (f'<tr><td style="padding:20px 24px 8px;"><h2 style="margin:0 0 12px;padding-left:10px;border-left:4px solid {border};'
            f'font-size:17px;line-height:22px;color:#111827;">{title}</h2>{body}</td></tr>')


def send_report(to: str | None = None) -> dict:
    """Monta o relatorio HTML e envia por e-mail. Sem chave/destinatario, grava um preview local."""
    diag = load("diagnostics.json")
    research = load("frontier_research.json", list)
    esc = html.escape

    score = None if diag.get("cognitive_health_score") is None else pct(diag["cognitive_health_score"])
    tiers = [(75, "#059669", "Saudável — bom equilíbrio no uso de IA"), (50, "#d97706", "Atenção — há espaço para evoluir"),
             (0, "#dc2626", "Risco — muita delegação, pouco protagonismo")]
    color, label = next(((c, t) for cut, c, t in tiers if score is not None and score >= cut),
                        ("#6b7280", "Sem dados suficientes"))
    score_html = "—" if score is None else f'{score:.0f}<span style="font-size:20px;font-weight:600;color:#94a3b8;">/100</span>'

    sm = diag.get("summary_metrics")
    sm = sm if isinstance(sm, dict) else {}
    bars = ""
    for n, k in [("Delegação cega", "blind_delegation_pct"), ("Aprendizado socrático", "socratic_pct"),
                 ("Loop de frustração", "frustration_loop_pct"), ("Cocriação ativa", "active_cocreation_pct")]:
        p = pct(sm.get(k))
        bars += (f'<tr><td style="padding:9px 0 4px;font-size:14px;color:#374151;">{n}</td>'
                 f'<td align="right" style="padding:9px 0 4px;font-size:14px;font-weight:700;color:#111827;">{p:.1f}%</td></tr>'
                 f'<tr><td colspan="2" style="padding:0 0 12px;"><div style="height:6px;border-radius:3px;'
                 f'background:linear-gradient(90deg,#6366f1 {p:.1f}%,#e5e7eb {p:.1f}%);"></div></td></tr>')

    recs = diag.get("recommendations")
    recs_html = "".join(
        '<tr><td valign="top" style="padding:6px 8px 6px 0;color:#6366f1;font-size:16px;font-weight:700;line-height:21px;">&rsaquo;</td>'
        f'<td style="padding:6px 0;font-size:14px;line-height:21px;color:#374151;">{esc(clip(r, 300))}</td></tr>'
        for r in (recs if isinstance(recs, list) else [])) or \
        '<tr><td style="font-size:14px;color:#6b7280;">Sem recomendações por enquanto.</td></tr>'

    categories = {"blind_delegation": ("Delegação cega", "#fee2e2", "#b91c1c"), "frustration_loop": ("Loop de frustração", "#ffedd5", "#c2410c"),
                  "socratic_learning": ("Aprendizado socrático", "#dcfce7", "#15803d"), "active_cocreation": ("Cocriação ativa", "#dbeafe", "#1d4ed8")}
    raw_diags = diag.get("conversation_diagnoses")
    diags = [d for d in raw_diags if isinstance(d, dict)] if isinstance(raw_diags, list) else []
    diag_cards = ""
    for d in sorted(diags, key=lambda d: pct(d.get("severity"), 5), reverse=True)[:3]:
        name, bg, fg = categories.get(d.get("category"), (d.get("category") or "Diagnóstico", "#e5e7eb", "#374151"))
        sev = int(pct(d.get("severity"), 5))
        dots = f'<span style="color:#ef4444;">{"&#9679;" * sev}</span><span style="color:#d1d5db;">{"&#9675;" * (5 - sev)}</span>'
        diag_cards += card(
            f'<p style="margin:0 0 8px;"><span style="display:inline-block;background:{bg};color:{fg};font-size:11px;font-weight:700;'
            f'letter-spacing:.4px;text-transform:uppercase;padding:3px 9px;border-radius:999px;">{esc(str(name))}</span>'
            f'<span style="float:right;font-size:13px;letter-spacing:2px;">{dots}</span></p>'
            f'<p style="margin:0 0 8px;padding:8px 12px;border-left:3px solid #cbd5e1;background:#f8fafc;font-size:13px;line-height:20px;'
            f'color:#475569;font-style:italic;">&ldquo;{esc(clip(d.get("evidence_quote"), 160))}&rdquo;</p>'
            f'<p style="margin:0;font-size:13px;line-height:20px;color:#374151;"><strong style="color:#111827;">Como agir:</strong> '
            f'{esc(clip(d.get("recommendation"), 300))}</p>')
    diag_cards = diag_cards or '<p style="margin:0;font-size:14px;color:#6b7280;">Nenhum diagnóstico registrado.</p>'

    node_cards = ""
    for node in (n for n in research if isinstance(n, dict)):
        links = ""
        for s in (node.get("sources") if isinstance(node.get("sources"), list) else []):
            if not isinstance(s, dict):
                continue
            url = str(s.get("url") or "")
            title = esc(str(s.get("title") or url))
            links += (f'<a href="{esc(url)}" style="font-size:13px;color:#059669;text-decoration:underline;">{title} &nearr;</a><br>'
                      if url.startswith(("http://", "https://")) else f'<span style="font-size:13px;color:#6b7280;">{title}</span><br>')
        node_cards += card(
            f'<p style="margin:0 0 6px;font-size:14px;font-weight:700;color:#065f46;">{esc(clip(node.get("topic") or node.get("note_title"), 300))}</p>'
            f'<p style="margin:0 0 8px;font-size:13px;line-height:20px;color:#374151;">{esc(clip(node.get("why"), 300))}</p>'
            f'<p style="margin:0;font-size:11px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;color:#6b7280;">Fontes</p>{links}',
            "#d1fae5", "#f0fdf4")
    node_cards = node_cards or '<p style="margin:0;font-size:14px;color:#6b7280;">Nenhum nó novo desta vez.</p>'

    sections = (
        sec("Seu jeito de usar IA", "#6366f1", f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{bars}</table>')
        + sec("O que mudar", "#6366f1", f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{recs_html}</table>')
        + sec("Top 3 pontos de atenção", "#ef4444", diag_cards)
        + sec("Novos nós verdes no seu Obsidian", "#059669", node_cards))
    report = f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Seu Raio-X Cognitivo de IA</title></head>
<body style="margin:0;padding:24px 12px;background:#eef1f6;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;margin:0 auto;background:#ffffff;border-radius:12px;overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#1f2937;">
<tr><td style="background:#0f172a;padding:26px 24px;"><h1 style="margin:0;font-size:24px;line-height:32px;color:#ffffff;">Seu Raio-X Cognitivo de IA</h1><p style="margin:7px 0 0;font-size:13px;line-height:20px;color:#94a3b8;">Como você pensa junto com a IA, a partir das suas próprias conversas.</p></td></tr>
<tr><td align="center" style="padding:28px 24px 24px;background:#f8fafc;border-bottom:1px solid #e5e7eb;"><p style="margin:0;font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#64748b;">Cognitive Health Score</p>
<p style="margin:6px 0 0;font-size:56px;line-height:60px;font-weight:800;color:{color};">{score_html}</p><p style="margin:8px 0 0;font-size:14px;font-weight:600;color:{color};">{esc(label)}</p></td></tr>
{sections}
<tr><td style="padding:18px 24px;background:#f8fafc;border-top:1px solid #e5e7eb;text-align:center;"><p style="margin:0;font-size:12px;line-height:18px;color:#94a3b8;">Cognitive Wiki OS &middot; Relatório gerado em {esc(str(diag.get("generated_at") or "")) or "data desconhecida"}</p></td></tr>
</table>
</body></html>"""

    preview = DATA / "last_report.html"
    DATA.mkdir(parents=True, exist_ok=True)
    preview.write_text(report, encoding="utf-8")

    to, key = to or os.getenv("USER_EMAIL"), os.getenv("RESEND_API_KEY")
    if not key or not to:
        reason = "RESEND_API_KEY ausente" if not key else "destinatario ausente (defina USER_EMAIL ou use --to)"
        print(f"E-mail nao enviado ({reason}). Preview: {preview}")
        return {"ok": True, "sent": False, "preview": str(preview), "reason": reason}
    try:
        import resend
        resend.api_key = key
        return {"ok": True, "sent": True, "id": resend.Emails.send({
            "from": "onboarding@resend.dev", "to": [to], "subject": "Seu Raio-X Cognitivo de IA", "html": report})["id"]}
    except Exception as e:
        return {"ok": False, "error": str(e), "preview": str(preview)}


def create_checkout() -> str:
    """Cria um checkout PIX na AbacatePay via REST v1. Sem chave, devolve a URL de demo local."""
    key = os.getenv("ABACATEPAY_API_KEY")
    if not key:
        print("ABACATEPAY_API_KEY ausente: checkout em modo demo.")
        return f"{APP_URL}/?pro=demo"
    body = json.dumps({
        "frequency": "ONE_TIME", "methods": ["PIX"], "returnUrl": f"{APP_URL}/", "completionUrl": f"{APP_URL}/?pro=true",
        "products": [{"externalId": "plano-pro", "name": "Plano Pro Cognitive Wiki", "quantity": 1, "price": 2990,
                      "description": "Relatorio cognitivo por e-mail + pesquisa de fronteira no seu Obsidian."}],
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{ABACATEPAY_BASE}/v1/billing/create", data=body, method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30, context=SSL_CONTEXT) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"AbacatePay {e.code}: {e.read().decode('utf-8', 'replace')[:300]}") from None
    except (OSError, ValueError) as e:
        raise RuntimeError(str(e)) from None
    data = payload.get("data") if isinstance(payload, dict) else None
    url = data.get("url") if isinstance(data, dict) else None
    if not isinstance(url, str) or not url:
        raise RuntimeError(f"Resposta inesperada da AbacatePay: {json.dumps(payload, ensure_ascii=False)[:300]}")
    return url


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["email"]:
        print(send_report(args[args.index("--to") + 1] if "--to" in args[:-1] else None))
    elif args[:1] == ["checkout"]:
        print(create_checkout())
    else:
        print("uso: python integrations.py email [--to X] | checkout")
