"""
app/nl_query.py — Natural language → SQL using keyword pattern matching.
No LLM or external model required.
"""
import re
from datetime import datetime


# ── Keyword → SQL patterns ────────────────────────────────────────────────────

def question_to_sql(question: str, internal_user_id: str = None) -> str:
    uid = str(internal_user_id) if internal_user_id else "00000000-0000-0000-0000-000000000000"
    q = question.lower().strip()

    # ── Top items / most bought ───────────────────────────────────────────────
    if any(k in q for k in ["mais compro", "mais comprado", "top", "frequente", "produto mais"]):
        limit = _extract_limit(q, default=10)
        return f"""
            SELECT i.name,
                   SUM(i.quantity)    AS total_qty,
                   COUNT(*)           AS vezes_comprado,
                   SUM(i.total_price) AS total_gasto
            FROM items i
            JOIN purchases p ON p.id = i.purchase_id
            WHERE p.internal_user_id = '{uid}'
            GROUP BY i.name
            ORDER BY vezes_comprado DESC
            LIMIT {limit};
        """

    # ── Most expensive item ───────────────────────────────────────────────────
    if any(k in q for k in ["mais caro", "mais cara", "caro", "cara"]):
        return f"""
            SELECT i.name,
                   MAX(i.unit_price)  AS preco_unitario,
                   SUM(i.total_price) AS total_gasto
            FROM items i
            JOIN purchases p ON p.id = i.purchase_id
            WHERE p.internal_user_id = '{uid}'
            GROUP BY i.name
            ORDER BY preco_unitario DESC
            LIMIT 10;
        """

    # ── Specific product search ───────────────────────────────────────────────
    product = _extract_product(q)
    if product:
        term = product.upper()
        return f"""
            SELECT i.name,
                   SUM(i.total_price) AS total_gasto,
                   SUM(i.quantity)    AS total_qty,
                   COUNT(*)           AS vezes_comprado
            FROM items i
            JOIN purchases p ON p.id = i.purchase_id
            WHERE p.internal_user_id = '{uid}'
              AND i.name ILIKE '%{term}%'
            GROUP BY i.name
            ORDER BY total_gasto DESC;
        """

    # ── Store ranking ─────────────────────────────────────────────────────────
    if any(k in q for k in ["loja", "mercado", "estabelecimento", "onde gasto"]):
        return f"""
            SELECT store_name,
                   COUNT(*)       AS total_visitas,
                   SUM(total_net) AS total_gasto,
                   AVG(total_net) AS ticket_medio
            FROM purchases
            WHERE internal_user_id = '{uid}'
            GROUP BY store_name
            ORDER BY total_gasto DESC
            LIMIT 10;
        """

    # ── Discounts / savings ───────────────────────────────────────────────────
    if any(k in q for k in ["desconto", "economiz", "poupei", "economiei"]):
        month_filter = _extract_month_filter(q, uid, table="purchases", alias="")
        return f"""
            SELECT
                TO_CHAR(purchase_date, 'MM/YYYY')  AS mes,
                SUM(total_discount)                AS total_descontos,
                COUNT(*)                           AS num_compras
            FROM purchases
            WHERE internal_user_id = '{uid}'
              {month_filter}
            GROUP BY mes
            ORDER BY mes DESC
            LIMIT 12;
        """

    # ── Last purchases ────────────────────────────────────────────────────────
    if any(k in q for k in ["última", "ultimas", "últimas", "recente", "histórico"]):
        limit = _extract_limit(q, default=5)
        return f"""
            SELECT
                TO_CHAR(purchase_date, 'DD/MM/YYYY') AS data,
                store_name,
                total_net,
                payment_method
            FROM purchases
            WHERE internal_user_id = '{uid}'
            ORDER BY purchase_date DESC, created_at DESC
            LIMIT {limit};
        """

    # ── Monthly summary ───────────────────────────────────────────────────────
    if any(k in q for k in ["resumo", "summary", "meses", "mensal"]):
        return f"""
            SELECT
                TO_CHAR(purchase_date, 'MM/YYYY') AS mes,
                COUNT(*)                          AS total_compras,
                SUM(total_net)                    AS total_gasto,
                SUM(total_discount)               AS total_desconto,
                AVG(total_net)                    AS ticket_medio
            FROM purchases
            WHERE internal_user_id = '{uid}'
            GROUP BY mes
            ORDER BY mes DESC
            LIMIT 12;
        """

    # ── Total spent — with optional month/period filter ───────────────────────
    month_clause = _month_where_clause(q)
    period_label = _period_label(q)

    return f"""
        SELECT
            '{period_label}'            AS periodo,
            COUNT(*)                    AS total_compras,
            SUM(total_net)              AS total_gasto,
            SUM(total_discount)         AS total_economizado,
            AVG(total_net)              AS ticket_medio
        FROM purchases
        WHERE internal_user_id = '{uid}'
          {month_clause};
    """


# ── Answer formatter (no LLM) ─────────────────────────────────────────────────

def format_answer(question: str, rows: list) -> str:
    if not rows:
        return (
            "😕 Não encontrei dados para essa consulta.\n\n"
            "Se buscou um produto, ele pode estar com outro nome no sistema — "
            "os nomes são abreviações da SEFAZ (ex: *REFR Z COCA 2L* em vez de *Coca-Cola*).\n\n"
            "Tente `/top` para ver todos os produtos registrados."
        )

    q = question.lower()

    # Top products
    if any(k in q for k in ["mais compro", "top", "frequente", "produto"]):
        lines = ["🛒 *Produtos mais comprados:*\n"]
        for i, r in enumerate(rows, 1):
            lines.append(
                f"  {i}. *{r.get('name', '?')}* — "
                f"{int(r.get('vezes_comprado', 0))}x comprado · "
                f"R$ {float(r.get('total_gasto', 0)):.2f} total"
            )
        return "\n".join(lines)

    # Most expensive
    if any(k in q for k in ["mais caro", "caro"]):
        lines = ["💸 *Itens mais caros:*\n"]
        for i, r in enumerate(rows, 1):
            lines.append(
                f"  {i}. *{r.get('name', '?')}* — "
                f"R$ {float(r.get('preco_unitario', 0)):.2f} por unidade"
            )
        return "\n".join(lines)

    # Store ranking
    if any(k in q for k in ["loja", "mercado", "estabelecimento"]):
        lines = ["🏪 *Gastos por loja:*\n"]
        for i, r in enumerate(rows, 1):
            lines.append(
                f"  {i}. *{r.get('store_name', '?')}* — "
                f"R$ {float(r.get('total_gasto', 0)):.2f} "
                f"({int(r.get('total_visitas', 0))} visitas)"
            )
        return "\n".join(lines)

    # Last purchases
    if any(k in q for k in ["última", "ultimas", "últimas", "recente"]):
        lines = ["🕐 *Últimas compras:*\n"]
        for r in rows:
            lines.append(
                f"  📅 {r.get('data', '?')} — "
                f"*{r.get('store_name', '?')}* — "
                f"R$ {float(r.get('total_net', 0)):.2f}"
            )
        return "\n".join(lines)

    # Discounts
    if any(k in q for k in ["desconto", "economiz"]):
        total = sum(float(r.get('total_descontos', 0)) for r in rows)
        lines = [f"🏷️ *Total economizado em descontos: R$ {total:.2f}*\n"]
        for r in rows:
            lines.append(
                f"  {r.get('mes', '?')}: R$ {float(r.get('total_descontos', 0)):.2f}"
            )
        return "\n".join(lines)

    # Monthly summary
    if any(k in q for k in ["resumo", "meses", "mensal"]):
        lines = ["📊 *Resumo mensal:*\n"]
        for r in rows:
            lines.append(
                f"  📅 *{r.get('mes', '?')}* — "
                f"R$ {float(r.get('total_gasto', 0)):.2f} "
                f"({int(r.get('total_compras', 0))} compras)"
            )
        return "\n".join(lines)

    # Generic total
    if rows and len(rows) == 1:
        r = rows[0]
        periodo  = r.get('periodo', 'período')
        gasto    = float(r.get('total_gasto') or 0)
        compras  = int(r.get('total_compras') or 0)
        econ     = float(r.get('total_economizado') or 0)
        ticket   = float(r.get('ticket_medio') or 0)
        msg = f"💰 *Total gasto {periodo}: R$ {gasto:.2f}*\n\n"
        msg += f"🛒 {compras} compra(s) realizadas\n"
        if econ > 0:
            msg += f"🏷️ R$ {econ:.2f} economizados em descontos\n"
        if ticket > 0:
            msg += f"📊 Ticket médio: R$ {ticket:.2f}"
        return msg

    # Product search result
    lines = []
    for r in rows:
        name   = r.get('name', '?')
        gasto  = float(r.get('total_gasto') or 0)
        qty    = float(r.get('total_qty') or 0)
        vezes  = int(r.get('vezes_comprado') or 0)
        lines.append(f"• *{name}* — R$ {gasto:.2f} ({vezes}x, {qty} unidades)")
    return "🔍 *Resultado da busca:*\n\n" + "\n".join(lines)


# ── Helpers ───────────────────────────────────────────────────────────────────

_MONTH_NAMES = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3,
    "abril": 4, "maio": 5, "junho": 6, "julho": 7,
    "agosto": 8, "setembro": 9, "outubro": 10,
    "novembro": 11, "dezembro": 12,
}

_PRODUCT_KEYWORDS = [
    "gastei em", "gastei com", "quanto de", "comprei de",
    "pesquisar", "buscar", "procurar", "produto",
]


def _extract_product(q: str) -> str | None:
    """Try to extract a product name from the question."""
    for kw in _PRODUCT_KEYWORDS:
        if kw in q:
            after = q.split(kw, 1)[-1].strip()
            # Take first 3 words
            words = after.split()[:3]
            product = " ".join(w for w in words if len(w) > 2)
            if product:
                return product
    return None


def _extract_limit(q: str, default: int = 10) -> int:
    m = re.search(r"\b(\d+)\b", q)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 100:
            return n
    return default


def _extract_month_filter(q: str, uid: str, table: str, alias: str) -> str:
    prefix = f"{alias}." if alias else ""
    now = datetime.now()

    if "esse mês" in q or "este mês" in q or "mês atual" in q:
        return f"AND {prefix}purchase_date >= date_trunc('month', CURRENT_DATE)"
    if "mês passado" in q or "mes passado" in q:
        return (
            f"AND {prefix}purchase_date >= date_trunc('month', CURRENT_DATE - interval '1 month') "
            f"AND {prefix}purchase_date < date_trunc('month', CURRENT_DATE)"
        )
    if "esse ano" in q or "este ano" in q or "ano atual" in q:
        return f"AND EXTRACT(YEAR FROM {prefix}purchase_date) = {now.year}"

    for name, num in _MONTH_NAMES.items():
        if name in q:
            year = now.year
            yr_m = re.search(r"\b(20\d{2})\b", q)
            if yr_m:
                year = int(yr_m.group(1))
            return (
                f"AND EXTRACT(MONTH FROM {prefix}purchase_date) = {num} "
                f"AND EXTRACT(YEAR FROM {prefix}purchase_date) = {year}"
            )
    return ""


def _month_where_clause(q: str) -> str:
    return _extract_month_filter(q, "", "purchases", "")


def _period_label(q: str) -> str:
    now = datetime.now()
    if "esse mês" in q or "este mês" in q or "mês atual" in q:
        return f"em {now.strftime('%B/%Y')}"
    if "mês passado" in q or "mes passado" in q:
        return "no mês passado"
    if "esse ano" in q or "este ano" in q:
        return f"em {now.year}"
    for name in _MONTH_NAMES:
        if name in q:
            return f"em {name}"
    return "no total"
