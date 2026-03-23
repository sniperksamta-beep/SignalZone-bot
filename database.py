"""
database.py — All persistence for Flareposts Bot.
Tables: users, generations, payments
"""

import sqlite3, time, calendar
from contextlib import contextmanager
from config import DB_FILE


@contextmanager
def db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except:
        conn.rollback()
        raise
    finally:
        conn.close()


def init():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY,
            username      TEXT,
            name          TEXT,
            joined        INTEGER,
            plan          TEXT DEFAULT 'free',
            plan_expires  INTEGER DEFAULT 0,
            total_uses    INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS generations (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            source     TEXT,
            created    INTEGER
        );

        CREATE TABLE IF NOT EXISTS payments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            plan        TEXT,
            amount      REAL,
            coin        TEXT,
            wallet      TEXT,
            status      TEXT DEFAULT 'pending',
            created     INTEGER,
            confirmed   INTEGER
        );
        """)


# ── User helpers ─────────────────────────────────────────────────

def ensure_user(user_id: int, username: str, name: str):
    with db() as c:
        c.execute("""
            INSERT INTO users(id, username, name, joined)
            VALUES(?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET username=excluded.username, name=excluded.name
        """, (user_id, username or "", name or "", int(time.time())))


def get_user(user_id: int):
    with db() as c:
        return c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()


def is_pro(user_id: int) -> bool:
    row = get_user(user_id)
    if not row:
        return False
    if row["plan"] == "pro" and row["plan_expires"] > time.time():
        return True
    return False


def uses_this_month(user_id: int) -> int:
    """Count how many generations the user did this calendar month."""
    now = time.gmtime()
    month_start = calendar.timegm((now.tm_year, now.tm_mon, 1, 0, 0, 0, 0, 0, 0))
    with db() as c:
        row = c.execute("""
            SELECT COUNT(*) as cnt FROM generations
            WHERE user_id=? AND created>=?
        """, (user_id, month_start)).fetchone()
        return row["cnt"] if row else 0


def log_generation(user_id: int, source: str):
    with db() as c:
        c.execute("INSERT INTO generations(user_id,source,created) VALUES(?,?,?)",
                  (user_id, source[:200], int(time.time())))
        c.execute("UPDATE users SET total_uses=total_uses+1 WHERE id=?", (user_id,))


def activate_pro(user_id: int, months: int):
    now = int(time.time())
    expires = now + (months * 30 * 24 * 3600)
    with db() as c:
        c.execute("""
            UPDATE users SET plan='pro', plan_expires=?
            WHERE id=?
        """, (expires, user_id))


def add_payment(user_id: int, plan: str, amount: float, coin: str, wallet: str) -> int:
    with db() as c:
        cur = c.execute("""
            INSERT INTO payments(user_id,plan,amount,coin,wallet,status,created)
            VALUES(?,?,?,?,?,'pending',?)
        """, (user_id, plan, amount, coin, wallet, int(time.time())))
        return cur.lastrowid


def confirm_payment(payment_id: int, user_id: int, months: int):
    with db() as c:
        c.execute("""
            UPDATE payments SET status='confirmed', confirmed=?
            WHERE id=?
        """, (int(time.time()), payment_id))
    activate_pro(user_id, months)


def all_users_count() -> int:
    with db() as c:
        return c.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def pro_users_count() -> int:
    now = int(time.time())
    with db() as c:
        return c.execute(
            "SELECT COUNT(*) FROM users WHERE plan='pro' AND plan_expires>?", (now,)
        ).fetchone()[0]


def total_generations() -> int:
    with db() as c:
        return c.execute("SELECT COUNT(*) FROM generations").fetchone()[0]


def pending_payments():
    with db() as c:
        return c.execute(
            "SELECT * FROM payments WHERE status='pending' ORDER BY created DESC"
        ).fetchall()
