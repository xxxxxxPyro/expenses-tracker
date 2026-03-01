-- ============================================================
-- NF-e Tracker — Full Schema (multi-user)
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
    id               SERIAL PRIMARY KEY,
    internal_id      UUID DEFAULT gen_random_uuid() UNIQUE NOT NULL,
    telegram_user_id BIGINT UNIQUE NOT NULL,
    email            TEXT UNIQUE NOT NULL,
    first_name       TEXT,
    username         TEXT,
    created_at       TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS purchases (
    id               SERIAL PRIMARY KEY,
    internal_user_id UUID NOT NULL REFERENCES users(internal_id) ON DELETE CASCADE,
    nfe_key          TEXT,
    nfe_number       TEXT,
    nfe_series       TEXT,
    invoice_url      TEXT,
    store_name       TEXT NOT NULL,
    store_cnpj       TEXT,
    store_address    TEXT,
    purchase_date    DATE NOT NULL,
    purchase_time    TIME,
    total_gross      NUMERIC(10,2),
    total_discount   NUMERIC(10,2) DEFAULT 0,
    total_net        NUMERIC(10,2) NOT NULL,
    payment_method   TEXT,
    created_at       TIMESTAMPTZ DEFAULT now(),
    UNIQUE (internal_user_id, nfe_key)
);

CREATE TABLE IF NOT EXISTS items (
    id               SERIAL PRIMARY KEY,
    purchase_id      INT NOT NULL REFERENCES purchases(id) ON DELETE CASCADE,
    product_code     TEXT,
    name             TEXT NOT NULL,
    quantity         NUMERIC(10,3) NOT NULL,
    unit             TEXT,
    unit_price       NUMERIC(10,2) NOT NULL,
    total_price      NUMERIC(10,2) NOT NULL,
    discount         NUMERIC(10,2) DEFAULT 0
);

-- ── Views ─────────────────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW monthly_summary AS
SELECT
    u.internal_id                          AS internal_user_id,
    TO_CHAR(p.purchase_date, 'YYYY-MM')    AS month,
    COUNT(*)                               AS total_purchases,
    SUM(p.total_net)                       AS total_spent,
    SUM(p.total_discount)                  AS total_saved,
    AVG(p.total_net)                       AS avg_basket
FROM purchases p
JOIN users u ON u.internal_id = p.internal_user_id
GROUP BY 1, 2
ORDER BY 2 DESC;

CREATE OR REPLACE VIEW top_items AS
SELECT
    p.internal_user_id,
    i.name,
    SUM(i.quantity)    AS total_qty,
    COUNT(*)           AS times_bought,
    AVG(i.unit_price)  AS avg_price,
    SUM(i.total_price) AS total_spent
FROM items i
JOIN purchases p ON p.id = i.purchase_id
GROUP BY 1, 2
ORDER BY times_bought DESC;

-- ── Indexes ───────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_users_telegram    ON users(telegram_user_id);
CREATE INDEX IF NOT EXISTS idx_users_email       ON users(email);
CREATE INDEX IF NOT EXISTS idx_purchases_user    ON purchases(internal_user_id);
CREATE INDEX IF NOT EXISTS idx_purchases_date    ON purchases(purchase_date);
CREATE INDEX IF NOT EXISTS idx_purchases_store   ON purchases(store_name);
CREATE INDEX IF NOT EXISTS idx_items_name        ON items(name);
CREATE INDEX IF NOT EXISTS idx_items_purchase    ON items(purchase_id);