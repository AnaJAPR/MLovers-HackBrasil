"""Integracoes externas: e-mail do relatorio (Resend) e checkout (AbacatePay REST v1).
Sem chave nos .env, tudo cai em modo local: o relatorio vira data/last_report.html e o checkout vira demo."""
import argparse
import html
import json
import os
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


def send_report(to: str | None = None) -> dict:
    """Monta o relatorio HTML e envia por e-mail. Sem chave/destinatario, grava um preview local."""
    diag_file = DATA / "diagnostics.json"
    if not diag_file.exists():
        diag_file = MOCK / "diagnostics.json"
    research_file = DATA / "frontier_research.json"
    if not research_file.exists():
        research_file = MOCK / "frontier_research.json"
    diag = json.loads(diag_file.read_text(encoding="utf-8")) if diag_file.exists() else {}
    research = json.loads(research_file.read_text(encoding="utf-8")) if research_file.exists() else []

    esc = html.escape
    try:
        score = max(0.0, min(100.0, float(diag.get("cognitive_health_score") or 0)))
    except (TypeError, ValueError):
        score = 0.0
    if score >= 75:
        score_color, score_label = "#059669", "Saudável — bom equilíbrio no uso de IA"
    elif score >= 50:
        score_color, score_label = "#d97706", "Atenção — há espaço para evoluir"
    else:
        score_color, score_label = "#dc2626", "Risco — muita delegação, pouco protagonismo"

    metrics = [
        ("Delegação cega", (diag.get("summary_metrics") or {}).get("blind_delegation_pct")),
        ("Aprendizado socrático", (diag.get("summary_metrics") or {}).get("socratic_pct")),
        ("Loop de frustração", (diag.get("summary_metrics") or {}).get("frustration_loop_pct")),
        ("Cocriação ativa", (diag.get("summary_metrics") or {}).get("active_cocreation_pct")),
    ]
    metric_rows = ""
    for label, value in metrics:
        try:
            pct = max(0.0, min(100.0, float(value or 0)))
        except (TypeError, ValueError):
            pct = 0.0
        metric_rows += f"""
            <tr>
              <td style="padding:9px 0 4px;font-size:14px;color:#374151;">{esc(label)}</td>
              <td align="right" style="padding:9px 0 4px;font-size:14px;font-weight:700;color:#111827;">{pct:.1f}%</td>
            </tr>
            <tr>
              <td colspan="2" style="padding:0 0 10px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                  <tr>
                    <td style="background:#e5e7eb;height:6px;border-radius:3px;">
                      <table role="presentation" width="{pct:.0f}%" cellpadding="0" cellspacing="0">
                        <tr><td style="background:#6366f1;height:6px;border-radius:3px;font-size:0;line-height:0;">&nbsp;</td></tr>
                      </table>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>"""

    recommendations = diag.get("recommendations") or []
    rec_rows = ""
    for rec in recommendations:
        rec_rows += f"""
            <tr>
              <td valign="top" style="padding:6px 8px 6px 0;color:#6366f1;font-size:16px;font-weight:700;line-height:21px;">&rsaquo;</td>
              <td style="padding:6px 0;font-size:14px;line-height:21px;color:#374151;">{esc(str(rec))}</td>
            </tr>"""
    if not rec_rows:
        rec_rows = '<tr><td style="font-size:14px;color:#6b7280;">Sem recomendações por enquanto.</td></tr>'

    categories = {
        "blind_delegation": ("Delegação cega", "#fee2e2", "#b91c1c"),
        "frustration_loop": ("Loop de frustração", "#ffedd5", "#c2410c"),
        "socratic_learning": ("Aprendizado socrático", "#dcfce7", "#15803d"),
        "active_cocreation": ("Cocriação ativa", "#dbeafe", "#1d4ed8"),
    }
    top = sorted(
        diag.get("conversation_diagnoses") or [],
        key=lambda d: d.get("severity") or 0,
        reverse=True,
    )[:3]
    diag_cards = ""
    for item in top:
        name, bg, fg = categories.get(item.get("category"), (item.get("category") or "Diagnóstico", "#e5e7eb", "#374151"))
        try:
            severity = max(0, min(5, int(item.get("severity") or 0)))
        except (TypeError, ValueError):
            severity = 0
        dots = (f'<span style="color:#ef4444;">{"&#9679;" * severity}</span>'
                f'<span style="color:#d1d5db;">{"&#9675;" * (5 - severity)}</span>')
        diag_cards += f"""
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 12px;border:1px solid #e5e7eb;border-radius:8px;">
              <tr>
                <td style="padding:14px 16px;">
                  <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                    <tr>
                      <td><span style="display:inline-block;background:{bg};color:{fg};font-size:11px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;padding:3px 9px;border-radius:999px;">{esc(str(name))}</span></td>
                      <td align="right" style="font-size:13px;letter-spacing:2px;">{dots}</td>
                    </tr>
                  </table>
                  <p style="margin:10px 0 8px;padding:8px 12px;border-left:3px solid #cbd5e1;background:#f8fafc;font-size:13px;line-height:20px;color:#475569;font-style:italic;">&ldquo;{esc(str(item.get("evidence_quote") or ""))}&rdquo;</p>
                  <p style="margin:0;font-size:13px;line-height:20px;color:#374151;"><strong style="color:#111827;">Como agir:</strong> {esc(str(item.get("recommendation") or ""))}</p>
                </td>
              </tr>
            </table>"""
    if not diag_cards:
        diag_cards = '<p style="margin:0;font-size:14px;color:#6b7280;">Nenhum diagnóstico registrado.</p>'

    node_cards = ""
    for node in research if isinstance(research, list) else []:
        links = ""
        for source in node.get("sources") or []:
            url = str(source.get("url") or "")
            title = str(source.get("title") or url)
            if url.startswith(("http://", "https://")):
                links += f'<a href="{esc(url)}" style="font-size:13px;color:#059669;text-decoration:underline;">{esc(title)} &nearr;</a><br>'
            else:
                links += f'<span style="font-size:13px;color:#6b7280;">{esc(title)}</span><br>'
        node_cards += f"""
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 12px;border:1px solid #d1fae5;border-radius:8px;background:#f0fdf4;">
              <tr>
                <td style="padding:14px 16px;">
                  <p style="margin:0 0 6px;font-size:14px;font-weight:700;color:#065f46;">{esc(str(node.get("topic") or node.get("note_title") or ""))}</p>
                  <p style="margin:0 0 8px;font-size:13px;line-height:20px;color:#374151;">{esc(str(node.get("why") or ""))}</p>
                  <p style="margin:0;font-size:11px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;color:#6b7280;">Fontes</p>
                  {links}
                </td>
              </tr>
            </table>"""
    if not node_cards:
        node_cards = '<p style="margin:0;font-size:14px;color:#6b7280;">Nenhum nó novo desta vez.</p>'

    generated_at = esc(str(diag.get("generated_at") or ""))
    report = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Seu Raio-X Cognitivo de IA</title>
</head>
<body style="margin:0;padding:0;background:#eef1f6;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#eef1f6;padding:24px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;background:#ffffff;border-radius:12px;overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#1f2937;">
          <tr>
            <td style="background:#0f172a;padding:26px 24px;">
              <h1 style="margin:0;font-size:24px;line-height:32px;color:#ffffff;">Seu Raio-X Cognitivo de IA</h1>
              <p style="margin:7px 0 0;font-size:13px;line-height:20px;color:#94a3b8;">Como você pensa junto com a IA, a partir das suas próprias conversas.</p>
            </td>
          </tr>
          <tr>
            <td align="center" style="padding:28px 24px 24px;background:#f8fafc;border-bottom:1px solid #e5e7eb;">
              <p style="margin:0;font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#64748b;">Cognitive Health Score</p>
              <p style="margin:6px 0 0;font-size:56px;line-height:60px;font-weight:800;color:{score_color};">{score:.0f}<span style="font-size:20px;font-weight:600;color:#94a3b8;">/100</span></p>
              <p style="margin:8px 0 0;font-size:14px;font-weight:600;color:{score_color};">{esc(score_label)}</p>
            </td>
          </tr>
          <tr>
            <td style="padding:24px 24px 6px;">
              <h2 style="margin:0 0 12px;padding-left:10px;border-left:4px solid #6366f1;font-size:17px;line-height:22px;color:#111827;">Seu jeito de usar IA</h2>
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">{metric_rows}
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:18px 24px 8px;">
              <h2 style="margin:0 0 10px;padding-left:10px;border-left:4px solid #6366f1;font-size:17px;line-height:22px;color:#111827;">O que mudar</h2>
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rec_rows}
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:18px 24px 8px;">
              <h2 style="margin:0 0 12px;padding-left:10px;border-left:4px solid #ef4444;font-size:17px;line-height:22px;color:#111827;">Top 3 pontos de atenção</h2>
              {diag_cards}
            </td>
          </tr>
          <tr>
            <td style="padding:18px 24px 24px;">
              <h2 style="margin:0 0 12px;padding-left:10px;border-left:4px solid #059669;font-size:17px;line-height:22px;color:#111827;">Novos nós verdes no seu Obsidian</h2>
              {node_cards}
            </td>
          </tr>
          <tr>
            <td style="padding:18px 24px;background:#f8fafc;border-top:1px solid #e5e7eb;text-align:center;">
              <p style="margin:0;font-size:12px;line-height:18px;color:#94a3b8;">Cognitive Wiki OS &middot; Relatório gerado em {generated_at or "data desconhecida"}</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    to = to or os.getenv("USER_EMAIL")
    key = os.getenv("RESEND_API_KEY")
    if not key or not to:
        reason = "RESEND_API_KEY ausente" if not key else "destinatario ausente (defina USER_EMAIL ou use --to)"
        DATA.mkdir(parents=True, exist_ok=True)
        preview = DATA / "last_report.html"
        preview.write_text(report, encoding="utf-8")
        print(f"E-mail nao enviado ({reason}). Preview: {preview}")
        return {"ok": True, "sent": False, "preview": str(preview), "reason": reason}

    try:
        import resend
        resend.api_key = key
        result = resend.Emails.send({
            "from": "onboarding@resend.dev",
            "to": [to],
            "subject": "Seu Raio-X Cognitivo de IA",
            "html": report,
        })
        return {"ok": True, "sent": True, "id": result["id"]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def create_checkout() -> str:
    """Cria um checkout PIX na AbacatePay via REST v1. Sem chave, devolve a URL de demo local."""
    key = os.getenv("ABACATEPAY_API_KEY")
    if not key:
        print("ABACATEPAY_API_KEY ausente: checkout em modo demo.")
        return "http://127.0.0.1:8765/?pro=demo"

    body = json.dumps({
        "frequency": "ONE_TIME",
        "methods": ["PIX"],
        "products": [{
            "externalId": "plano-pro",
            "name": "Plano Pro Cognitive Wiki",
            "description": "Relatorio cognitivo por e-mail + pesquisa de fronteira no seu Obsidian.",
            "quantity": 1,
            "price": 2990,
        }],
        "returnUrl": "http://127.0.0.1:8765/",
        "completionUrl": "http://127.0.0.1:8765/?pro=true",
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.abacatepay.com/v1/billing/create",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            error = json.loads(raw).get("error")
        except ValueError:
            error = raw
        detail = json.dumps(error, ensure_ascii=False) if isinstance(error, (dict, list)) else error
        raise RuntimeError(f"AbacatePay {e.code}: {detail}")
    except Exception as e:
        raise RuntimeError(str(e))

    url = (payload.get("data") or {}).get("url")
    if not url:
        raise RuntimeError(f"Resposta inesperada da AbacatePay: {json.dumps(payload, ensure_ascii=False)}")
    return url


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="E-mail do relatorio cognitivo e checkout.")
    sub = parser.add_subparsers(dest="command", required=True)
    email_cmd = sub.add_parser("email", help="monta e envia (ou salva preview) o relatorio")
    email_cmd.add_argument("--to", help="destinatario (padrao: USER_EMAIL)")
    sub.add_parser("checkout", help="cria o checkout do plano Pro")
    args = parser.parse_args()

    if args.command == "email":
        print(send_report(args.to))
    else:
        print(create_checkout())
