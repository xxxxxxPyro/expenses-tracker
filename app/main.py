"""
main.py — Expenses Tracker Tool Server

Exposes two tools for OpenClaw/Ollama via HTTP:
  POST /tools/process-qr    — receives an image, decodes QR, fetches SEFAZ, saves to DB
  POST /tools/query         — natural language question → SQL → friendly answer
  GET  /tools/schema        — Ollama tool definitions (for registration)
  GET  /health              — health check
"""
import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.qr_decoder import decode_qr_from_bytes
from app.sefaz import fetch_and_parse
from app.db import save_purchase, run_query
from app.nl_query import question_to_sql, format_answer

app = FastAPI(
    title="Expenses Tracker",
    description="Tool server for tracking Brazilian NF-e purchases via Telegram + Ollama",
    version="1.0.0",
)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


# ── Tool: Process QR Code ─────────────────────────────────────────────────────

@app.post("/tools/process-qr")
async def process_qr(image: UploadFile = File(...)):
    """
    Receive an image file → decode QR → fetch SEFAZ → parse → save to DB.
    Returns a human-readable summary.
    """
    image_bytes = await image.read()

    # 1. Decode QR
    url = decode_qr_from_bytes(image_bytes)
    if not url:
        raise HTTPException(
            status_code=422,
            detail="Não consegui encontrar um QR code na imagem. "
                   "Tente uma foto mais nítida, com boa iluminação e o QR centralizado.",
        )

    # Validate it looks like a SEFAZ URL
    if "fazenda" not in url and "nfce" not in url.lower():
        raise HTTPException(
            status_code=422,
            detail=f"QR decodificado mas não parece ser uma NF-e SEFAZ: {url}",
        )

    # 2. Fetch + parse SEFAZ page
    try:
        invoice = fetch_and_parse(url)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao acessar SEFAZ: {str(e)}")

    # 3. Save to DB
    try:
        purchase_id, already_exists = save_purchase(invoice)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao salvar no banco: {str(e)}")

    # 4. Build response summary
    items_summary = "\n".join(
        f"  • {item['name']} × {item['quantity']} → R$ {item['total_price']:.2f}"
        for item in invoice.get("items", [])
    )

    if already_exists:
        msg = f"⚠️ Esta nota fiscal já foi registrada anteriormente (ID #{purchase_id})."
    else:
        msg = (
            f"✅ *Nota fiscal salva com sucesso!*\n\n"
            f"🏪 *Loja:* {invoice['store_name']}\n"
            f"📅 *Data:* {invoice.get('purchase_date', 'N/A')}\n"
            f"🛍️ *Itens ({len(invoice.get('items', []))}):\n{items_summary}\n\n"
            f"💰 *Subtotal:* R$ {invoice.get('total_gross', 0):.2f}\n"
            f"🏷️ *Desconto:* R$ {invoice.get('total_discount', 0):.2f}\n"
            f"✅ *Total pago:* R$ {invoice.get('total_net', 0):.2f}\n"
            f"💳 *Pagamento:* {invoice.get('payment_method', 'N/A')}"
        )

    return {
        "message": msg,
        "purchase_id": purchase_id,
        "already_exists": already_exists,
        "data": invoice,
    }


# ── Tool: Natural Language Query ──────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str


@app.post("/tools/query")
async def query(req: QueryRequest):
    """
    Accept a natural language question in Portuguese and return a friendly answer
    based on the purchase database.
    """
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Pergunta vazia.")

    # 1. Convert to SQL
    try:
        sql = question_to_sql(question)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar SQL: {str(e)}")

    # Safety guard — only allow SELECT
    if not sql.strip().upper().startswith("SELECT"):
        raise HTTPException(
            status_code=400,
            detail="Só consigo responder perguntas de consulta (SELECT).",
        )

    # 2. Run SQL
    try:
        rows = run_query(sql)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na consulta: {str(e)}\nSQL: {sql}")

    # 3. Format answer
    try:
        answer = format_answer(question, rows)
    except Exception as e:
        # Fallback: return raw data if Ollama is down
        answer = f"Dados encontrados:\n{rows}"

    return {
        "answer": answer,
        "sql": sql,
        "rows": rows,
    }


# ── Tool Schema (for OpenClaw registration) ───────────────────────────────────

@app.get("/tools/schema")
def tools_schema():
    """
    Returns the Ollama tool definitions so OpenClaw knows what tools are available.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "process_nfe_qr",
                "description": (
                    "Processa uma imagem de nota fiscal (NF-e) brasileira. "
                    "Decodifica o QR code, busca os dados na SEFAZ e salva no banco de dados. "
                    "Use quando o usuário enviar uma foto de cupom fiscal ou nota fiscal."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "image_path": {
                            "type": "string",
                            "description": "Caminho local para o arquivo de imagem",
                        }
                    },
                    "required": ["image_path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "query_purchases",
                "description": (
                    "Responde perguntas sobre os gastos e compras registrados no banco. "
                    "Use quando o usuário perguntar sobre: total gasto no mês, "
                    "itens mais comprados, comparação de períodos, gastos por loja, etc."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "Pergunta em português sobre os gastos",
                        }
                    },
                    "required": ["question"],
                },
            },
        },
    ]
