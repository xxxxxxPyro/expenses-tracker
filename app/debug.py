"""
debug.py — Diagnose SEFAZ item parsing
"""
import os, sys, re
sys.path.insert(0, "/app")

os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_USER", "nfe")
os.environ.setdefault("DB_PASSWORD", "nfepass")
os.environ.setdefault("DB_NAME", "expenses_tracker")

import httpx
from bs4 import BeautifulSoup

TEST_URL = (
    "https://www.nfce.fazenda.sp.gov.br/NFCeConsultaPublica/Paginas/ConsultaQRCode.aspx"
    "?p=35260257508426001573650830000149811083778856|3|1"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

print("Fetching SEFAZ page...")
resp = httpx.get(TEST_URL, headers=HEADERS, timeout=20, follow_redirects=True)
soup = BeautifulSoup(resp.text, "html.parser")

# Print every table row
print("\n=== ALL TABLE ROWS (first 8) ===")
rows = soup.find_all("tr")
print(f"Total <tr> found: {len(rows)}")
for i, tr in enumerate(rows[:8]):
    tds = tr.find_all("td")
    print(f"\n--- Row {i+1} ({len(tds)} cells) ---")
    for j, td in enumerate(tds):
        print(f"  Cell {j}: {repr(td.get_text(separator=' ', strip=True)[:150])}")

# Print raw text around key fields
print("\n=== RAW TEXT LINES CONTAINING KEY FIELDS ===")
full_text = soup.get_text(separator="\n")
for line in full_text.split("\n"):
    stripped = line.strip()
    if stripped and any(k in stripped for k in ["Código", "Qtde", "Vl. Unit", "Vl. Total"]):
        print(repr(stripped[:150]))