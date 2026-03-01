"""
app/nl_query.py — NL → SQL using Ollama, scoped to internal_user_id
"""
import os
import re
import json
import ollama

OLLAMA_HOST  = os.getenv("OLLAMA_HOST",  "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

DB_SCHEMA = """
Tabelas PostgreSQL:

users (
    id SERIAL,
    internal_id UUID,          -- identificador único do usuário
    telegram_user_id BIGINT,
    email TEXT,
    first_name TEXT
)

purchases (
    id SERIAL,
    internal_user_id UUID,     -- FK → users.internal_id — SEMPRE filtre por este campo
    store_name TEXT,
    store_cnpj TEXT,
    store_address TEXT,
    purchase_date DATE,
    purchase_time TIME,
    total_gross NUMERIC,
    total_discount NUMERIC,
    total_net NUMERIC,
    payment_method TEXT,
    created_at TIMESTAMPTZ
)

items (
    id SERIAL,
    purchase_id INT,           -- FK → purchases.id
    name TEXT,                 -- abreviações SEFAZ: ex "REFR Z COCA 2L", "DORITOS CARNE DEF"
    product_code TEXT,
    quantity NUMERIC,
    unit TEXT,
    unit_price NUMERIC,
    total_price NUMERIC,
    discount NUMERIC
)
"""

SQL_SYSTEM = """\
Você converte perguntas em português para SQL PostgreSQL.

{schema}

REGRAS CRÍTICAS:
1. Retorne APENAS o SQL puro, sem markdown, sem ```.
2. Somente SELECT.
3. SEMPRE filtre por p.internal_user_id = '{user_id}' em purchases.
4. Formate valores com TO_CHAR(valor, 'FM999G999D99').
5. Formate datas com TO_CHAR(purchase_date, 'DD/MM/YYYY').
6. LIMIT 20 quando não especificado.

REGRA PARA BUSCA DE PRODUTOS (nomes são abreviações SEFAZ):
- "coca cola" / "coca" / "refrigerante coca" → name ILIKE '%COCA%'
- "doritos"   → name ILIKE '%DORIT%'
- "chocolate" → name ILIKE '%CHOC%'
- "leite"     → name ILIKE '%LT%' OR name ILIKE '%LEITE%'
- "arroz"     → name ILIKE '%ARR%'
- "feijão"    → name ILIKE '%FEIJ%'
Use sempre termos curtos com % em ambos os lados para buscas flexíveis.

TEMPLATE para gastos com produto:
SELECT i.name, SUM(i.total_price) AS total_gasto,
       SUM(i.quantity) AS total_qty, COUNT(*) AS vezes_comprado
FROM items i
JOIN purchases p ON p.id = i.purchase_id
WHERE p.internal_user_id = '{user_id}'
  AND (i.name ILIKE '%TERMO%')
GROUP BY i.name ORDER BY total_gasto DESC;
"""

ANSWER_SYSTEM = """\
Você é um assistente financeiro pessoal simpático.
Responda em português brasileiro, de forma concisa e amigável.
Use emojis com moderação. Formate valores como R$ X.XXX,XX.
Se não houver resultados, sugira que o produto pode ter outro nome no sistema
e ofereça listar todos os produtos registrados.\
"""


def _clean_sql(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"^```(?:sql)?", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"```$", "", raw)
    return raw.strip()


def question_to_sql(question: str, internal_user_id: str = None) -> str:
    system = SQL_SYSTEM.format(
        schema=DB_SCHEMA,
        user_id=str(internal_user_id) if internal_user_id else "00000000-0000-0000-0000-000000000000"
    )
    client = ollama.Client(host=OLLAMA_HOST)
    response = client.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": question},
        ],
        options={"temperature": 0},
    )
    return _clean_sql(response["message"]["content"])


def format_answer(question: str, rows: list) -> str:
    client = ollama.Client(host=OLLAMA_HOST)
    data_str = (
        json.dumps(rows, ensure_ascii=False, default=str, indent=2)
        if rows else "Nenhum resultado encontrado."
    )
    response = client.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": ANSWER_SYSTEM},
            {
                "role": "user",
                "content": f"Pergunta: {question}\n\nDados:\n{data_str}\n\nResponda de forma amigável.",
            },
        ],
        options={"temperature": 0.3},
    )
    return response["message"]["content"]