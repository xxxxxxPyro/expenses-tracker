"""
app/sefaz.py — Parses SEFAZ SP NFC-e pages (nfce.fazenda.sp.gov.br)
"""
import re
from datetime import date, time
from typing import Optional
import httpx
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}


def _parse_brl(value: str) -> float:
    if not value:
        return 0.0
    cleaned = value.strip().replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _clean(text: str) -> str:
    """Collapse all whitespace (including \\r\\n\\t) into single spaces."""
    return re.sub(r'\s+', ' ', text).strip()


def fetch_and_parse(url: str) -> dict:
    resp = httpx.get(url, headers=HEADERS, timeout=20, follow_redirects=True)
    resp.raise_for_status()
    return parse_html(resp.text, url)


def parse_html(html: str, url: str = "") -> dict:
    soup = BeautifulSoup(html, "html.parser")
    # Use cleaned text for all regex searches
    text = _clean(soup.get_text(separator=" "))
    lines = [l.strip() for l in soup.get_text(separator="\n").split("\n") if l.strip()]

    # ── Store info ───────────────────────────────────────────
    store_name    = ""
    store_cnpj    = ""
    store_address = ""

    cnpj_line_idx = None
    for i, line in enumerate(lines):
        cnpj_match = re.search(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", line)
        if cnpj_match:
            store_cnpj = cnpj_match.group()
            cnpj_line_idx = i
            for back in range(1, 8):
                candidate = lines[i - back] if i - back >= 0 else ""
                candidate = candidate.strip()
                if candidate and not any(x in candidate for x in
                        ["NFC-e", "DOCUMENTO", "CNPJ", "Fazenda", "Consulta"]):
                    store_name = candidate
                    break
            break

    address_parts = []
    if cnpj_line_idx is not None:
        for line in lines[cnpj_line_idx + 1:]:
            stripped = line.strip()
            if not stripped or len(stripped) <= 1:
                continue
            if any(kw in stripped.upper() for kw in
                    ["ITEM", "CÓDIGO", "QTD", "DETALHE", "QTDE", "REFR", "Qtde"]):
                break
            address_parts.append(stripped)
            if len(address_parts) >= 5:
                break
    store_address = " ".join(p.strip(",").strip() for p in address_parts if p)

    # ── Items ────────────────────────────────────────────────
    items = []
    item_pattern = re.compile(
        r"^(.+?)\s*\(Código:\s*(\d+)\s*\)"
        r"\s*Qtde\.:\s*([\d,]+)"
        r"\s*UN:\s*(\w+)"
        r"\s*Vl\.\s*Unit\.:\s*([\d.,]+)"
        r"\s*Vl\.\s*Total\s*([\d.,]+)",
        re.IGNORECASE,
    )

    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue
        cell0 = _clean(tds[0].get_text(separator=" "))
        cell1 = _clean(tds[1].get_text(separator=" "))
        row_text = cell0 + " " + cell1
        m = item_pattern.match(row_text)
        if m:
            items.append({
                "product_code": m.group(2).strip(),
                "name":         m.group(1).strip(),
                "quantity":     float(m.group(3).replace(",", ".")),
                "unit":         m.group(4).strip(),
                "unit_price":   _parse_brl(m.group(5)),
                "total_price":  _parse_brl(m.group(6)),
                "discount":     0.0,
            })

    # ── Totals — regex now handles optional colon after R$ ───
    total_gross    = 0.0
    total_discount = 0.0
    total_net      = 0.0
    payment_method = ""

    gross_m = re.search(r"Valor total R\$:?\s*([\d.,]+)", text, re.IGNORECASE)
    if gross_m:
        total_gross = _parse_brl(gross_m.group(1))

    disc_m = re.search(r"Descontos R\$:?\s*([\d.,]+)", text, re.IGNORECASE)
    if disc_m:
        total_discount = _parse_brl(disc_m.group(1))

    net_m = re.search(r"Valor a pagar R\$:?\s*([\d.,]+)", text, re.IGNORECASE)
    if net_m:
        total_net = _parse_brl(net_m.group(1))
    elif total_gross:
        total_net = round(total_gross - total_discount, 2)

    # Payment method — stop before any digits to avoid grabbing the amount
    pay_m = re.search(
        r"Valor pago R\$:?\s*(Cart[aã]o de (?:Cr[eé]dito|D[eé]bito)|Dinheiro|PIX)",
        text, re.IGNORECASE
    )
    if pay_m:
        payment_method = pay_m.group(1).strip()

    # ── Date / Time ──────────────────────────────────────────
    purchase_date:     Optional[date] = None
    purchase_time_val: Optional[time] = None

    date_m = re.search(
        r"Emiss[aã]o[:\s]*([\d]{2}/[\d]{2}/[\d]{4})\s*([\d]{2}:[\d]{2}:[\d]{2})?",
        text
    )
    if date_m:
        d, m_d, y = date_m.group(1).split("/")
        purchase_date = date(int(y), int(m_d), int(d))
        if date_m.group(2):
            h, mi, s = date_m.group(2).split(":")
            purchase_time_val = time(int(h), int(mi), int(s))

    # ── NF-e metadata ────────────────────────────────────────
    nfe_number = ""
    nfe_series  = ""
    nfe_key     = ""

    num_m = re.search(r"N[uú]mero[:\s]*([\d]+)", text)
    if num_m:
        nfe_number = num_m.group(1)

    ser_m = re.search(r"S[eé]rie[:\s]*([\d]+)", text)
    if ser_m:
        nfe_series = ser_m.group(1)

    key_m = re.search(r"Chave de acesso[:\s]*([\d\s]{44,})", text)
    if key_m:
        nfe_key = re.sub(r"\s", "", key_m.group(1))[:44]

    return {
        "store_name":     store_name or "Desconhecida",
        "store_cnpj":     store_cnpj,
        "store_address":  store_address,
        "nfe_number":     nfe_number,
        "nfe_series":     nfe_series,
        "nfe_key":        nfe_key,
        "invoice_url":    url,
        "purchase_date":  str(purchase_date)     if purchase_date     else None,
        "purchase_time":  str(purchase_time_val) if purchase_time_val else None,
        "total_gross":    total_gross,
        "total_discount": total_discount,
        "total_net":      total_net,
        "payment_method": payment_method,
        "items":          items,
    }