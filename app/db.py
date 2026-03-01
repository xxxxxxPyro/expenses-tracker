"""
app/db.py — PostgreSQL connection and query helpers (multi-user)
"""
import os
import psycopg2
import psycopg2.extras
from contextlib import contextmanager

DSN = (
    f"host={os.getenv('DB_HOST', 'localhost')} "
    f"port={os.getenv('DB_PORT', '5432')} "
    f"dbname={os.getenv('DB_NAME', 'expenses_tracker')} "
    f"user={os.getenv('DB_USER', 'expenses')} "
    f"password={os.getenv('DB_PASSWORD', 'expensespass')}"
)


@contextmanager
def get_conn():
    conn = psycopg2.connect(DSN, cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── User management ───────────────────────────────────────────────────────────

def get_user_by_telegram_id(telegram_user_id: int) -> dict | None:
    """Return user row or None if not registered."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM users WHERE telegram_user_id = %s",
            (telegram_user_id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None


def get_user_by_email(email: str) -> dict | None:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s", (email.lower().strip(),))
        row = cur.fetchone()
        return dict(row) if row else None


def create_user(telegram_user_id: int, email: str,
                first_name: str = None, username: str = None) -> dict:
    """Create a new user and return the created row."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO users (telegram_user_id, email, first_name, username)
            VALUES (%s, %s, %s, %s)
            RETURNING *
            """,
            (telegram_user_id, email.lower().strip(), first_name, username)
        )
        return dict(cur.fetchone())


def update_user_telegram(internal_id: str, telegram_user_id: int) -> dict:
    """Link an existing email account to a new Telegram user ID."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET telegram_user_id = %s WHERE internal_id = %s RETURNING *",
            (telegram_user_id, internal_id)
        )
        return dict(cur.fetchone())


# ── Purchases ─────────────────────────────────────────────────────────────────

def save_purchase(data: dict, internal_user_id: str) -> tuple:
    """
    Insert purchase + items. Returns (purchase_id, already_exists).
    """
    with get_conn() as conn:
        cur = conn.cursor()

        # Duplicate check per user
        if data.get("nfe_key"):
            cur.execute(
                "SELECT id FROM purchases WHERE nfe_key = %s AND internal_user_id = %s",
                (data["nfe_key"], internal_user_id)
            )
            row = cur.fetchone()
            if row:
                return row["id"], True

        cur.execute(
            """
            INSERT INTO purchases
                (internal_user_id, nfe_key, nfe_number, nfe_series, invoice_url,
                 store_name, store_cnpj, store_address,
                 purchase_date, purchase_time,
                 total_gross, total_discount, total_net, payment_method)
            VALUES
                (%(internal_user_id)s, %(nfe_key)s, %(nfe_number)s, %(nfe_series)s,
                 %(invoice_url)s, %(store_name)s, %(store_cnpj)s, %(store_address)s,
                 %(purchase_date)s, %(purchase_time)s,
                 %(total_gross)s, %(total_discount)s, %(total_net)s, %(payment_method)s)
            RETURNING id
            """,
            {**data, "internal_user_id": internal_user_id},
        )
        purchase_id = cur.fetchone()["id"]

        for item in data.get("items", []):
            cur.execute(
                """
                INSERT INTO items
                    (purchase_id, product_code, name, quantity, unit,
                     unit_price, total_price, discount)
                VALUES
                    (%(purchase_id)s, %(product_code)s, %(name)s, %(quantity)s,
                     %(unit)s, %(unit_price)s, %(total_price)s, %(discount)s)
                """,
                {**item, "purchase_id": purchase_id},
            )

        return purchase_id, False


def run_query(sql: str, params: tuple = None) -> list:
    """Execute a read-only SELECT and return rows as list of dicts."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]