import sqlite3, time
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
            lang          TEXT DEFAULT 'ar',
            plan          TEXT DEFAULT 'free',
            plan_expires  INTEGER DEFAULT 0,
            total_signals INTEGER DEFAULT 0,
            free_used     INTEGER DEFAULT 0,
            last_signal   INTEGER DEFAULT 0,
            free_reset_at INTEGER DEFAULT 0,
            banned        INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS signals_log (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   INTEGER,
            pair      TEXT,
            timeframe TEXT,
            direction TEXT,
            created   INTEGER
        );
        CREATE TABLE IF NOT EXISTS payments (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   INTEGER,
            plan      TEXT,
            amount    REAL,
            coin      TEXT,
            wallet    TEXT,
            status    TEXT DEFAULT 'pending',
            created   INTEGER,
            confirmed INTEGER
        );
        """)
        # Add banned column if missing (migration)
        try:
            c.execute("ALTER TABLE users ADD COLUMN banned INTEGER DEFAULT 0")
        except Exception:
            pass

def ensure_user(user_id, username, name, lang="ar"):
    with db() as c:
        c.execute("""
            INSERT INTO users(id,username,name,joined,lang)
            VALUES(?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                username=excluded.username,
                name=excluded.name
        """, (user_id, username or "", name or "", int(time.time()), lang))

def get_user(user_id):
    with db() as c:
        return c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()

def set_lang(user_id, lang):
    with db() as c:
        c.execute("UPDATE users SET lang=? WHERE id=?", (lang, user_id))

def get_lang(user_id):
    row = get_user(user_id)
    return row["lang"] if row else "ar"

def is_pro(user_id) -> bool:
    row = get_user(user_id)
    return bool(row and row["plan"] == "pro" and row["plan_expires"] > time.time())

def is_banned(user_id) -> bool:
    row = get_user(user_id)
    return bool(row and row["banned"])

def _get_free_used(user_id) -> int:
    row = get_user(user_id)
    if not row: return 0
    if is_pro(user_id): return 0
    plan_expired_at = row["plan_expires"] if row["plan_expires"] else 0
    count_since = max(plan_expired_at, row["free_reset_at"] or 0)
    if count_since > 0:
        with db() as c:
            r = c.execute(
                "SELECT COUNT(*) as cnt FROM signals_log WHERE user_id=? AND created>?",
                (user_id, count_since)
            ).fetchone()
            return r["cnt"] if r else 0
    return row["free_used"] or 0

def free_signals_used(user_id) -> int:
    return _get_free_used(user_id)

def can_use(user_id) -> bool:
    from config import FREE_SIGNALS
    if is_banned(user_id): return False
    if is_pro(user_id): return True
    return _get_free_used(user_id) < FREE_SIGNALS

COOLDOWN_SECONDS = 90  # reduced from 120

def check_cooldown(user_id) -> int:
    row = get_user(user_id)
    if not row: return 0
    elapsed   = int(time.time()) - (row["last_signal"] or 0)
    remaining = COOLDOWN_SECONDS - elapsed
    return max(0, remaining)

def update_last_signal(user_id):
    with db() as c:
        c.execute("UPDATE users SET last_signal=? WHERE id=?", (int(time.time()), user_id))

def log_signal(user_id, pair, timeframe, direction):
    pro = is_pro(user_id)
    with db() as c:
        c.execute(
            "INSERT INTO signals_log(user_id,pair,timeframe,direction,created) VALUES(?,?,?,?,?)",
            (user_id, pair, timeframe, direction, int(time.time()))
        )
        c.execute("""
            UPDATE users SET
                total_signals = total_signals + 1,
                free_used     = CASE WHEN ? = 0 THEN free_used + 1 ELSE free_used END,
                last_signal   = ?
            WHERE id=?
        """, (1 if pro else 0, int(time.time()), user_id))

def activate_pro(user_id, months):
    expires = int(time.time()) + months * 30 * 24 * 3600
    with db() as c:
        c.execute("UPDATE users SET plan='pro', plan_expires=? WHERE id=?", (expires, user_id))

def add_days(user_id, days):
    row = get_user(user_id)
    if not row: return False
    now = int(time.time())
    base = max(row["plan_expires"] or now, now)
    new_expires = base + days * 24 * 3600
    with db() as c:
        c.execute("UPDATE users SET plan='pro', plan_expires=? WHERE id=?", (new_expires, user_id))
    return True

def reset_free(user_id) -> bool:
    row = get_user(user_id)
    if not row: return False
    with db() as c:
        c.execute("UPDATE users SET free_used=0, free_reset_at=? WHERE id=?", (int(time.time()), user_id))
    return True

def toggle_ban(user_id) -> bool:
    """Toggle ban status. Returns True if now banned."""
    row = get_user(user_id)
    if not row: return False
    new_val = 0 if row.get("banned", 0) else 1
    with db() as c:
        c.execute("UPDATE users SET banned=? WHERE id=?", (new_val, user_id))
    return bool(new_val)

def add_payment(user_id, plan, amount, coin, wallet):
    with db() as c:
        cur = c.execute(
            "INSERT INTO payments(user_id,plan,amount,coin,wallet,status,created) VALUES(?,?,?,?,?,'pending',?)",
            (user_id, plan, amount, coin, wallet, int(time.time()))
        )
        return cur.lastrowid

def confirm_payment(pay_id, user_id, months):
    with db() as c:
        c.execute("UPDATE payments SET status='confirmed',confirmed=? WHERE id=?", (int(time.time()), pay_id))
    activate_pro(user_id, months)

def all_users_count():
    with db() as c:
        return c.execute("SELECT COUNT(*) FROM users").fetchone()[0]

def pro_users_count():
    with db() as c:
        return c.execute("SELECT COUNT(*) FROM users WHERE plan='pro' AND plan_expires>?", (int(time.time()),)).fetchone()[0]

def total_signals_count():
    with db() as c:
        return c.execute("SELECT COUNT(*) FROM signals_log").fetchone()[0]

def signals_today():
    start_of_day = int(time.time()) - (int(time.time()) % 86400)
    with db() as c:
        return c.execute("SELECT COUNT(*) FROM signals_log WHERE created>?", (start_of_day,)).fetchone()[0]

def pending_payments():
    with db() as c:
        return c.execute("SELECT * FROM payments WHERE status='pending' ORDER BY created DESC").fetchall()

def get_all_users(limit=50):
    with db() as c:
        return c.execute("SELECT * FROM users ORDER BY joined DESC LIMIT ?", (limit,)).fetchall()

def search_user(query: str):
    with db() as c:
        if query.isdigit():
            return c.execute("SELECT * FROM users WHERE id=?", (int(query),)).fetchone()
        return c.execute("SELECT * FROM users WHERE username LIKE ?", (f"%{query}%",)).fetchone()
