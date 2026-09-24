# -*- coding: utf-8 -*-
"""
NEUROCITY DEVELOPER EDITION 6.0 • LIFE UPDATE
Telegram Mini App + Web App in one Python file.
No external Python packages required.
"""

import os, json, threading, hashlib, hmac, time, urllib.parse, urllib.request, html
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", "10000"))
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEB_APP_URL = os.getenv("WEB_APP_URL", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
ALLOW_BROWSER_DEMO = os.getenv("ALLOW_BROWSER_DEMO", "false").lower() in ("1", "true", "yes", "on")
INIT_DATA_MAX_AGE = int(os.getenv("INIT_DATA_MAX_AGE", "86400"))
CHAT_COOLDOWN = float(os.getenv("CHAT_COOLDOWN", "2"))
LOCK = threading.RLock()
DB_POOL = None
RATE_LOCK = threading.Lock()
RATE_STATE = {}

START_COINS = 750
START_XP = 0


class PGConnection:
    """Small wrapper around a PostgreSQL connection pool."""
    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, params=None):
        cur = self.conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params or ())
        return cur

    def executemany(self, sql, seq):
        cur = self.conn.cursor(cursor_factory=RealDictCursor)
        cur.executemany(sql, seq)
        return cur

    def executescript(self, sql):
        cur = self.conn.cursor()
        cur.execute(sql)
        cur.close()

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        global DB_POOL
        if self.conn is not None:
            try:
                if self.conn.closed == 0:
                    DB_POOL.putconn(self.conn)
            finally:
                self.conn = None


def init_pool():
    global DB_POOL
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set. Add the Render PostgreSQL Internal Database URL to Environment Variables.")
    DB_POOL = pool.ThreadedConnectionPool(1, int(os.getenv("DB_POOL_MAX", "10")), DATABASE_URL, connect_timeout=15)


def db():
    if DB_POOL is None:
        init_pool()
    return PGConnection(DB_POOL.getconn())


def now():
    return int(time.time())


def init_db():
    with LOCK:
        c = db()
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            id BIGINT PRIMARY KEY,
            username TEXT,
            name TEXT NOT NULL,
            bio TEXT DEFAULT '',
            avatar TEXT DEFAULT '🧑‍💻',
            cover TEXT DEFAULT '🌌',
            coins INTEGER DEFAULT 750,
            bank INTEGER DEFAULT 0,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            streak INTEGER DEFAULT 0,
            last_bonus INTEGER DEFAULT 0,
            season_xp INTEGER DEFAULT 0,
            created_at INTEGER
        );

        CREATE TABLE IF NOT EXISTS businesses(
            id BIGSERIAL PRIMARY KEY,
            owner_id INTEGER,
            name TEXT,
            category TEXT,
            description TEXT,
            capital INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            rating REAL DEFAULT 5,
            revenue INTEGER DEFAULT 0,
            upgrades INTEGER DEFAULT 0,
            employees INTEGER DEFAULT 0,
            created_at INTEGER
        );

        CREATE TABLE IF NOT EXISTS jobs(
            id BIGSERIAL PRIMARY KEY,
            business_id INTEGER,
            title TEXT,
            reward INTEGER,
            slots INTEGER DEFAULT 1,
            created_at INTEGER
        );

        CREATE TABLE IF NOT EXISTS work(
            id BIGSERIAL PRIMARY KEY,
            job_id INTEGER,
            user_id INTEGER,
            reward INTEGER,
            created_at INTEGER
        );

        CREATE TABLE IF NOT EXISTS products(
            id BIGSERIAL PRIMARY KEY,
            seller_id INTEGER,
            title TEXT,
            category TEXT,
            icon TEXT,
            description TEXT,
            price INTEGER,
            active INTEGER DEFAULT 1,
            created_at INTEGER
        );

        CREATE TABLE IF NOT EXISTS purchases(
            id BIGSERIAL PRIMARY KEY,
            product_id INTEGER,
            buyer_id INTEGER,
            seller_id INTEGER,
            price INTEGER,
            created_at INTEGER
        );

        CREATE TABLE IF NOT EXISTS inventory(
            id BIGSERIAL PRIMARY KEY,
            user_id INTEGER,
            item_type TEXT,
            item_id INTEGER,
            item_name TEXT,
            icon TEXT,
            qty INTEGER DEFAULT 1,
            equipped INTEGER DEFAULT 0,
            created_at INTEGER
        );

        CREATE TABLE IF NOT EXISTS cars(
            id BIGSERIAL PRIMARY KEY,
            seller_id INTEGER,
            model TEXT,
            icon TEXT,
            description TEXT,
            price INTEGER,
            active INTEGER DEFAULT 1,
            created_at INTEGER
        );

        CREATE TABLE IF NOT EXISTS car_purchases(
            id BIGSERIAL PRIMARY KEY,
            car_id INTEGER,
            buyer_id INTEGER,
            seller_id INTEGER,
            price INTEGER,
            created_at INTEGER
        );

        CREATE TABLE IF NOT EXISTS friends(
            user_id INTEGER,
            friend_id INTEGER,
            status TEXT DEFAULT 'accepted',
            created_at INTEGER,
            PRIMARY KEY(user_id, friend_id)
        );

        CREATE TABLE IF NOT EXISTS chat(
            id BIGSERIAL PRIMARY KEY,
            user_id INTEGER,
            text TEXT,
            created_at INTEGER
        );

        CREATE TABLE IF NOT EXISTS feed(
            id BIGSERIAL PRIMARY KEY,
            user_id INTEGER,
            kind TEXT,
            text TEXT,
            created_at INTEGER
        );

        CREATE TABLE IF NOT EXISTS business_reviews(
            id BIGSERIAL PRIMARY KEY,
            business_id INTEGER,
            user_id INTEGER,
            rating INTEGER,
            text TEXT,
            created_at INTEGER
        );

        CREATE TABLE IF NOT EXISTS follows(
            follower_id INTEGER,
            target_id INTEGER,
            created_at INTEGER,
            PRIMARY KEY(follower_id, target_id)
        );

        CREATE TABLE IF NOT EXISTS achievements(
            id BIGSERIAL PRIMARY KEY,
            user_id INTEGER,
            code TEXT,
            created_at INTEGER,
            UNIQUE(user_id, code)
        );

        CREATE TABLE IF NOT EXISTS seasons(
            id BIGSERIAL PRIMARY KEY,
            name TEXT,
            ends_at INTEGER
        );

        CREATE TABLE IF NOT EXISTS season_rewards(
            id BIGSERIAL PRIMARY KEY,
            season_id INTEGER,
            place_from INTEGER,
            place_to INTEGER,
            reward INTEGER
        );

        CREATE TABLE IF NOT EXISTS profile_items(
            id BIGSERIAL PRIMARY KEY,
            user_id INTEGER,
            category TEXT,
            item TEXT,
            icon TEXT,
            price INTEGER,
            equipped INTEGER DEFAULT 0,
            created_at INTEGER
        );

        CREATE TABLE IF NOT EXISTS homes(
            user_id BIGINT PRIMARY KEY,
            name TEXT DEFAULT 'Мой дом',
            style TEXT DEFAULT '🌃',
            level INTEGER DEFAULT 1,
            comfort INTEGER DEFAULT 0,
            created_at INTEGER
        );

        CREATE TABLE IF NOT EXISTS home_catalog(
            id BIGSERIAL PRIMARY KEY,
            name TEXT,
            icon TEXT,
            category TEXT,
            price INTEGER,
            comfort INTEGER
        );

        CREATE TABLE IF NOT EXISTS home_items(
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT,
            catalog_id INTEGER,
            item_name TEXT,
            icon TEXT,
            category TEXT,
            price INTEGER,
            comfort INTEGER,
            placed INTEGER DEFAULT 1,
            created_at INTEGER
        );

        CREATE TABLE IF NOT EXISTS clothing_catalog(
            id BIGSERIAL PRIMARY KEY,
            name TEXT,
            category TEXT,
            icon TEXT,
            price INTEGER,
            rarity TEXT DEFAULT 'Обычная'
        );

        CREATE TABLE IF NOT EXISTS user_clothing(
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT,
            catalog_id INTEGER,
            equipped INTEGER DEFAULT 0,
            created_at INTEGER,
            UNIQUE(user_id,catalog_id)
        );

        CREATE TABLE IF NOT EXISTS quests(
            id BIGSERIAL PRIMARY KEY,
            code TEXT UNIQUE,
            title TEXT,
            description TEXT,
            metric TEXT,
            goal INTEGER,
            reward INTEGER,
            xp INTEGER,
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS user_quests(
            user_id BIGINT,
            quest_id INTEGER,
            claimed_at INTEGER,
            PRIMARY KEY(user_id,quest_id)
        );

        CREATE TABLE IF NOT EXISTS notifications(
            id BIGSERIAL PRIMARY KEY,
            user_id INTEGER,
            text TEXT,
            created_at INTEGER,
            seen INTEGER DEFAULT 0
        );
        """)
        c.executescript("""
        CREATE INDEX IF NOT EXISTS idx_users_coins ON users(coins DESC);
        CREATE INDEX IF NOT EXISTS idx_users_xp ON users(xp DESC);
        CREATE INDEX IF NOT EXISTS idx_users_season_xp ON users(season_xp DESC);
        CREATE INDEX IF NOT EXISTS idx_feed_created ON feed(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_chat_created ON chat(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_products_active ON products(active, id DESC);
        CREATE INDEX IF NOT EXISTS idx_cars_active ON cars(active, id DESC);
        CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, id DESC);
        CREATE INDEX IF NOT EXISTS idx_work_user ON work(user_id);
        CREATE INDEX IF NOT EXISTS idx_purchases_buyer ON purchases(buyer_id);
        CREATE INDEX IF NOT EXISTS idx_business_owner ON businesses(owner_id);
        CREATE INDEX IF NOT EXISTS idx_home_items_user ON home_items(user_id,id DESC);
        CREATE INDEX IF NOT EXISTS idx_user_clothing_user ON user_clothing(user_id);
        CREATE INDEX IF NOT EXISTS idx_quests_active ON quests(active);
        """)
        if not c.execute("SELECT 1 FROM home_catalog LIMIT 1").fetchone():
            home_items_seed = [
                ("Неоновый диван","🛋️","Мебель",250,8),
                ("Игровой стол","🖥️","Мебель",450,12),
                ("Киберпанк-кровать","🛏️","Спальня",650,16),
                ("Голографическое растение","🌿","Декор",180,6),
                ("Неоновая вывеска","💡","Декор",500,14),
                ("Аквариум","🐠","Декор",900,22),
                ("Мини-бар","🍹","Декор",1200,28),
                ("Портал в город","🌀","Редкое",2500,45),
            ]
            c.executemany("INSERT INTO home_catalog(name,icon,category,price,comfort) VALUES(%s,%s,%s,%s,%s)", home_items_seed)
        if not c.execute("SELECT 1 FROM clothing_catalog LIMIT 1").fetchone():
            clothing_seed = [
                ("Футболка Developer","Одежда","👕",0,"Стартовая"),
                ("Неоновая куртка","Одежда","🧥",300,"Обычная"),
                ("Кибер-очки","Аксессуар","🕶️",450,"Обычная"),
                ("Кепка CEO","Головной убор","🧢",600,"Редкая"),
                ("Золотые часы","Аксессуар","⌚",900,"Редкая"),
                ("Корона миллиардера","Головной убор","👑",2500,"Легендарная"),
                ("Космо-ботинки","Обувь","👟",750,"Редкая"),
                ("Неоновый костюм","Одежда","🥋",1400,"Эпическая"),
            ]
            c.executemany("INSERT INTO clothing_catalog(name,category,icon,price,rarity) VALUES(%s,%s,%s,%s,%s)", clothing_seed)
        if not c.execute("SELECT 1 FROM quests LIMIT 1").fetchone():
            quests_seed = [
                ("profile","Оформи профиль","Добавь описание и выбери аватар/обложку.","profile",1,300,80),
                ("work3","Трудяга","Выполни 3 рабочих задания.","work",3,500,120),
                ("business","Первый бизнес","Создай свой первый бизнес.","business",1,1000,200),
                ("upgrade","Растущий бизнес","Сделай хотя бы 1 улучшение бизнеса.","upgrade",1,800,180),
                ("home","Дом мечты","Купи хотя бы 1 предмет для дома.","home",1,400,100),
                ("clothing","Новый образ","Купи или получи предмет одежды и надень его.","clothing",1,350,90),
                ("car","На колёсах","Купи автомобиль.","car",1,1200,250),
                ("rich","Первый капитал","Накопи 5000 монет на кошельке.","coins",5000,700,150),
            ]
            c.executemany("INSERT INTO quests(code,title,description,metric,goal,reward,xp) VALUES(%s,%s,%s,%s,%s,%s,%s)", quests_seed)
        if not c.execute("SELECT 1 FROM seasons LIMIT 1").fetchone():
            sid = c.execute(
                "INSERT INTO seasons(name,ends_at) VALUES(%s,%s) RETURNING id",
                ("Сезон 1 • Город возможностей", now() + 30 * 86400)
            ).fetchone()["id"]
            rewards = [(1,1,15000),(2,2,9000),(3,3,6000),(4,10,2500)]
            c.executemany(
                "INSERT INTO season_rewards(season_id,place_from,place_to,reward) VALUES(%s,%s,%s,%s)",
                [(sid,a,b,r) for a,b,r in rewards]
            )
        c.commit()
        c.close()


def validate_init_data(raw):
    if not raw:
        return None
    try:
        parsed = urllib.parse.parse_qs(raw, keep_blank_values=True)
        pairs = {k: v[-1] for k, v in parsed.items()}
        user_raw = pairs.get("user")
        if not user_raw:
            return None
        user = json.loads(user_raw)
        if not user.get("id"):
            return None
        if BOT_TOKEN:
            if "hash" not in pairs:
                return None
            auth_date = int(pairs.get("auth_date", "0"))
            if auth_date <= 0 or now() - auth_date > INIT_DATA_MAX_AGE or auth_date - now() > 60:
                return None
            check = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs) if k != "hash")
            secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
            digest = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(digest, pairs["hash"]):
                return None
        return user
    except Exception:
        return None

def ensure_user(tg):
    uid = int(tg.get("id", 0))
    if not uid:
        raise ValueError("Telegram user not found")

    first = tg.get("first_name", "")
    last = tg.get("last_name", "")
    name = (first + " " + last).strip() or "Игрок"
    username = tg.get("username", "")

    c = db()
    row = c.execute("SELECT * FROM users WHERE id=%s", (uid,)).fetchone()
    if not row:
        c.execute(
            """INSERT INTO users
            (id,username,name,coins,xp,level,created_at)
            VALUES(%s,%s,%s,%s,%s,%s,%s)""",
            (uid, username, name, START_COINS, START_XP, 1, now())
        )
        c.execute(
            "INSERT INTO feed(user_id,kind,text,created_at) VALUES(%s,%s,%s,%s)",
            (uid, "welcome", f"{name} присоединился к NeuroCity", now())
        )
        c.execute("INSERT INTO homes(user_id,name,style,created_at) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING",(uid,"Мой дом","🌃",now()))
        starter = c.execute("SELECT id FROM clothing_catalog WHERE price=0 ORDER BY id LIMIT 1").fetchone()
        if starter:
            c.execute("INSERT INTO user_clothing(user_id,catalog_id,equipped,created_at) VALUES(%s,%s,1,%s) ON CONFLICT DO NOTHING",(uid,starter["id"],now()))
        c.commit()
    else:
        c.execute(
            "UPDATE users SET username=%s,name=%s WHERE id=%s",
            (username, name, uid)
        )
        c.commit()
    row = c.execute("SELECT * FROM users WHERE id=%s", (uid,)).fetchone()
    c.close()
    return dict(row)


def user_from_request(handler):
    raw = handler.headers.get("X-Telegram-Init-Data", "")
    tg = validate_init_data(raw)
    if tg:
        return ensure_user(tg)

    # Browser preview is opt-in. In production Telegram auth is required.
    if not ALLOW_BROWSER_DEMO:
        raise ValueError("Открой NeuroCity через Telegram Mini App")
    return ensure_user({
        "id": 1,
        "first_name": "Demo",
        "last_name": "Player",
        "username": "demo"
    })


def level_from_xp(xp):
    return max(1, 1 + xp // 500)


def refresh_level(c, uid):
    row = c.execute("SELECT xp,level FROM users WHERE id=%s", (uid,)).fetchone()
    lvl = level_from_xp(row["xp"])
    if lvl != row["level"]:
        c.execute("UPDATE users SET level=%s WHERE id=%s", (lvl, uid))
        c.execute(
            "INSERT INTO notifications(user_id,text,created_at) VALUES(%s,%s,%s)",
            (uid, f"🎉 Новый уровень: {lvl}", now())
        )


def add_xp(c, uid, amount, season=True):
    c.execute(
        "UPDATE users SET xp=xp+%s WHERE id=%s",
        (amount, uid)
    )
    if season:
        c.execute(
            "UPDATE users SET season_xp=season_xp+%s WHERE id=%s",
            (amount, uid)
        )
    refresh_level(c, uid)


def add_feed(c, uid, kind, text):
    c.execute(
        "INSERT INTO feed(user_id,kind,text,created_at) VALUES(%s,%s,%s,%s)",
        (uid, kind, text, now())
    )


def rate_limit(key, cooldown):
    current = time.monotonic()
    with RATE_LOCK:
        previous = RATE_STATE.get(key, 0.0)
        if current - previous < cooldown:
            return False
        RATE_STATE[key] = current
        if len(RATE_STATE) > 5000:
            cutoff = current - max(cooldown * 10, 60)
            for k, v in list(RATE_STATE.items()):
                if v < cutoff:
                    RATE_STATE.pop(k, None)
    return True


def quest_progress(c, uid, metric):
    if metric == "profile":
        r = c.execute("SELECT bio,avatar,cover FROM users WHERE id=%s", (uid,)).fetchone()
        return 1 if r and r["bio"] and r["avatar"] and r["cover"] else 0
    if metric == "work":
        return int(c.execute("SELECT COUNT(*) n FROM work WHERE user_id=%s", (uid,)).fetchone()["n"])
    if metric == "business":
        return int(c.execute("SELECT COUNT(*) n FROM businesses WHERE owner_id=%s", (uid,)).fetchone()["n"])
    if metric == "upgrade":
        return int(c.execute("SELECT COALESCE(SUM(upgrades),0) n FROM businesses WHERE owner_id=%s", (uid,)).fetchone()["n"])
    if metric == "home":
        return int(c.execute("SELECT COUNT(*) n FROM home_items WHERE user_id=%s", (uid,)).fetchone()["n"])
    if metric == "clothing":
        return int(c.execute("SELECT COUNT(*) n FROM user_clothing WHERE user_id=%s AND equipped=1", (uid,)).fetchone()["n"])
    if metric == "car":
        return int(c.execute("SELECT COUNT(*) n FROM car_purchases WHERE buyer_id=%s", (uid,)).fetchone()["n"])
    if metric == "coins":
        return int(c.execute("SELECT coins FROM users WHERE id=%s", (uid,)).fetchone()["coins"])
    return 0


def json_body(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length).decode("utf-8") if length else "{}"
    return json.loads(raw or "{}")


def clean_text(value, limit=500):
    return str(value or "").strip()[:limit]


def rowdicts(rows):
    return [dict(x) for x in rows]


# -------------------- WEB UI --------------------

HTML = r"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>NeuroCity • Developer</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
:root{
  --bg:#05070d;--panel:#0b101b;--panel2:#101827;--line:#202b3d;
  --text:#f6f8ff;--muted:#8d99ad;--blue:#6c8cff;--cyan:#42d9ff;
  --green:#4ee39a;--gold:#ffd45c;--pink:#ff65b3;--danger:#ff667a;
}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(circle at 20% 0%,#16234c 0,#070a12 34%,#03050a 100%);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
button,input,textarea,select{font:inherit}
button{cursor:pointer}
.app{max-width:480px;min-height:100vh;margin:auto;background:rgba(5,8,15,.9);padding-bottom:90px}
.top{position:sticky;top:0;z-index:20;display:flex;align-items:center;justify-content:space-between;padding:12px 15px;background:rgba(5,8,15,.9);backdrop-filter:blur(18px);border-bottom:1px solid #172033}
.brand{display:flex;align-items:center;gap:9px}
.logo{width:38px;height:38px;border-radius:13px;display:grid;place-items:center;background:linear-gradient(135deg,#6c8cff,#a55cff);box-shadow:0 8px 28px #6c8cff33;font-weight:900}
.brand b{font-size:16px}.brand small{display:block;color:var(--muted);font-size:9px;letter-spacing:1.4px}
.topbtn{border:1px solid var(--line);background:#0e1522;color:#fff;border-radius:12px;padding:8px 10px}
.screen{display:none;padding:14px}.screen.on{display:block}
.hero{padding:18px;border:1px solid #263452;border-radius:24px;background:linear-gradient(145deg,#101a31,#0a0f19);overflow:hidden;position:relative}
.hero:after{content:"";position:absolute;width:150px;height:150px;border-radius:50%;right:-65px;top:-65px;background:#6c8cff25}
.hero-row{display:flex;justify-content:space-between;gap:12px;align-items:center;position:relative;z-index:1}
.avatar{width:58px;height:58px;border-radius:18px;display:grid;place-items:center;font-size:29px;background:linear-gradient(145deg,#202c48,#111725);border:1px solid #33415d}
.name{font-size:20px;font-weight:800}.handle{color:var(--muted);font-size:12px;margin-top:3px}
.coins{font-weight:900;color:var(--gold);font-size:18px}.lvl{color:#aebcff;font-size:11px}
.progress{height:6px;background:#1a2232;border-radius:9px;overflow:hidden;margin-top:12px}.progress i{display:block;height:100%;background:linear-gradient(90deg,var(--blue),var(--cyan));border-radius:9px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}
.card{background:linear-gradient(145deg,#0e1522,#0a101a);border:1px solid var(--line);border-radius:19px;padding:13px;margin-top:10px}
.card h3{margin:0 0 9px;font-size:14px}.muted{color:var(--muted);font-size:12px}.value{font-size:22px;font-weight:900;margin-top:3px}
.action{border:1px solid var(--line);background:#0d1523;color:#fff;border-radius:14px;padding:12px 10px;text-align:center}.action .ico{font-size:23px;display:block;margin-bottom:4px}.action small{color:var(--muted);font-size:10px}
.primary{width:100%;border:0;border-radius:14px;padding:13px;background:linear-gradient(135deg,#667dff,#4b55d9);color:#fff;font-weight:800;margin-top:9px;box-shadow:0 10px 25px #566dff22}
.secondary{width:100%;border:1px solid #2a3a59;border-radius:14px;padding:12px;background:#0e1828;color:#aebcff;font-weight:700;margin-top:8px}
.list{display:grid;gap:9px}.item{border:1px solid var(--line);background:#0c131f;border-radius:17px;padding:12px}
.item-row{display:flex;justify-content:space-between;gap:10px;align-items:center}
.item-title{font-weight:800}.price{color:var(--gold);font-weight:900}.tag{display:inline-block;padding:4px 7px;border-radius:8px;background:#18233a;color:#9eb1ff;font-size:10px;margin-top:6px}
.buy{border:0;background:#1b3156;color:#c6d2ff;border-radius:10px;padding:9px 11px;font-weight:700}
.section-title{display:flex;justify-content:space-between;align-items:center;margin:17px 1px 9px}.section-title b{font-size:16px}.link{color:#7d9aff;font-size:11px}
.bottom{position:fixed;z-index:30;bottom:0;left:50%;transform:translateX(-50%);width:min(480px,100%);padding:8px 8px calc(8px + env(safe-area-inset-bottom));display:grid;grid-template-columns:repeat(5,1fr);gap:5px;background:rgba(5,8,15,.94);backdrop-filter:blur(18px);border-top:1px solid #1a2435}
.nav{border:0;background:transparent;color:#68758c;border-radius:13px;padding:7px 2px;font-size:10px}.nav b{display:block;font-size:19px;margin-bottom:2px}.nav.on{background:#17213a;color:#aebcff}
.tabs{display:flex;gap:7px;overflow:auto;padding-bottom:3px}.tab{white-space:nowrap;border:1px solid var(--line);background:#0c131f;color:#8f9bb0;border-radius:11px;padding:8px 11px;font-size:11px}.tab.on{background:#1b2a4b;color:#c9d4ff;border-color:#344c7c}
input,textarea,select{width:100%;border:1px solid #26334a;background:#0a111d;color:#fff;border-radius:13px;padding:12px;outline:none;margin-top:7px}textarea{min-height:90px;resize:vertical}
label{display:block;color:#9ca9bd;font-size:11px;margin-top:10px}
.modal{position:fixed;z-index:50;inset:0;background:#0009;display:none;align-items:flex-end}.modal.on{display:flex}.sheet{width:min(480px,100%);max-height:90vh;overflow:auto;background:#0a101a;border:1px solid #27334a;border-radius:25px 25px 0 0;padding:18px}.sheet-head{display:flex;justify-content:space-between;align-items:center}.close{border:0;background:#182132;color:#fff;border-radius:10px;padding:8px 11px}
.toast{position:fixed;z-index:100;bottom:90px;left:50%;transform:translateX(-50%);background:#18243a;border:1px solid #324565;color:#fff;padding:11px 15px;border-radius:13px;display:none;font-size:12px}
.rank{display:flex;align-items:center;gap:10px}.ranknum{width:30px;text-align:center;color:#738198;font-weight:900}.rankavatar{width:42px;height:42px;border-radius:14px;background:#172238;display:grid;place-items:center;font-size:21px}
.money{color:var(--gold);font-weight:900}.green{color:var(--green)}.pink{color:var(--pink)}
.cover{height:110px;border-radius:20px;background:linear-gradient(135deg,#192650,#4c2d70,#12233d);position:relative;overflow:hidden}.cover span{position:absolute;right:18px;bottom:12px;font-size:40px}
.profile-head{margin-top:-25px;position:relative;padding:0 14px}.bigavatar{width:78px;height:78px;border-radius:24px;background:#111a2b;border:4px solid #0a101a;display:grid;place-items:center;font-size:40px}
.shopicon{font-size:34px;width:58px;height:58px;border-radius:18px;background:#172238;display:grid;place-items:center}
.car{display:flex;align-items:center;gap:12px}.car .caricon{font-size:43px}.carstats{display:grid;grid-template-columns:1fr 1fr;gap:4px;color:#8592a7;font-size:10px}
.feedline{display:flex;gap:10px}.feedline .dot{width:35px;height:35px;border-radius:12px;background:#172238;display:grid;place-items:center}
.empty{text-align:center;padding:25px;color:#68758c}
@keyframes floaty{0%,100%{transform:translateY(0)}50%{transform:translateY(-7px)}}
@keyframes pulseGlow{0%,100%{box-shadow:0 0 0 rgba(108,140,255,0)}50%{box-shadow:0 0 28px rgba(108,140,255,.28)}}
@keyframes coinPop{0%{transform:scale(.7) translateY(8px);opacity:0}60%{transform:scale(1.08) translateY(-5px);opacity:1}100%{transform:scale(1) translateY(0);opacity:1}}
@keyframes shimmer{0%{background-position:-300px 0}100%{background-position:300px 0}}
.hero{animation:pulseGlow 4s ease-in-out infinite}
.avatar,.bigavatar{animation:floaty 4s ease-in-out infinite}
.reward-pop{animation:coinPop .5s ease-out}
.shimmer{background:linear-gradient(90deg,#101827 30%,#1b2a42 50%,#101827 70%);background-size:600px 100%;animation:shimmer 2s linear infinite}
.home-room{min-height:180px;border-radius:24px;padding:16px;position:relative;overflow:hidden;background:radial-gradient(circle at 70% 20%,#4b2b6e55,transparent 35%),linear-gradient(145deg,#111c35,#0b101a)}
.home-room:before{content:'';position:absolute;inset:0;background-image:linear-gradient(#ffffff06 1px,transparent 1px),linear-gradient(90deg,#ffffff06 1px,transparent 1px);background-size:26px 26px;pointer-events:none}
.room-items{position:relative;display:flex;flex-wrap:wrap;gap:12px;align-items:flex-end;min-height:120px}.room-item{font-size:34px;filter:drop-shadow(0 7px 9px #0008);animation:floaty 3s ease-in-out infinite}.character-stage{display:flex;align-items:center;gap:15px;padding:18px;border-radius:22px;background:linear-gradient(145deg,#182542,#0c1220);animation:pulseGlow 4s ease-in-out infinite}.character-body{font-size:72px;line-height:1}.clothes-stack{display:flex;flex-wrap:wrap;gap:7px}.clothes-chip{padding:7px 9px;border:1px solid #2c3a54;background:#111b2d;border-radius:12px;font-size:12px}
</style>
</head>
<body>
<div class="app">
<header class="top">
  <div class="brand"><div class="logo">N</div><div><b>NEUROCITY</b><small>DEVELOPER EDITION</small></div></div>
  <button class="topbtn" onclick="openNotifications()">🔔</button>
</header>

<section id="home" class="screen on">
  <div id="homeHero"></div>

  <div class="section-title"><b>Быстрые действия</b><span class="link">CITY HUB</span></div>
  <div class="grid3">
    <button class="action" onclick="openJobModal()"><span class="ico">💼</span><small>Работа</small></button>
    <button class="action" onclick="openBusinessModal()"><span class="ico">🏢</span><small>Бизнес</small></button>
    <button class="action" onclick="claimBonus()"><span class="ico">🎁</span><small>Бонус</small></button>
    <button class="action" onclick="show('market')"><span class="ico">🛍️</span><small>Маркет</small></button>
    <button class="action" onclick="show('cars')"><span class="ico">🚘</span><small>Авто</small></button>
    <button class="action" onclick="show('rating')"><span class="ico">🏆</span><small>Рейтинг</small></button>
    <button class="action" onclick="show('quests');loadQuests()"><span class="ico">🎯</span><small>Задания</small></button>
    <button class="action" onclick="show('homePage');loadHomePage()"><span class="ico">🏠</span><small>Дом</small></button>
    <button class="action" onclick="show('character');loadCharacter()"><span class="ico">🧍</span><small>Персонаж</small></button>
  </div>

  <div class="section-title"><b>Лента города</b><span class="link" onclick="loadHome()">Обновить</span></div>
  <div id="feed" class="list"></div>

  <div class="section-title"><b>Текущий сезон</b><span class="link" onclick="show('season')">Подробнее</span></div>
  <div id="seasonMini"></div>
</section>

<section id="jobs" class="screen">
  <div class="section-title"><b>💼 Работа</b><span class="link">Заработок с нуля</span></div>
  <div class="hero"><b>Начни с заданий</b><div class="muted" style="margin-top:5px">Выполняй задания, получай 🪙 и XP, открывай свой бизнес.</div></div>
  <div class="section-title"><b>Доступные задания</b></div>
  <div id="jobsList" class="list"></div>
</section>

<section id="quests" class="screen">
  <div class="section-title"><b>🎯 Задания</b><span class="link">Заработок</span></div>
  <div class="hero"><b>Выполняй цели — получай монеты</b><div class="muted" style="margin-top:5px">У каждого задания указано, что сделать и сколько ты получишь.</div></div>
  <div id="questsList" class="list" style="margin-top:10px"></div>
</section>

<section id="homePage" class="screen">
  <div class="section-title"><b>🏠 Мой дом</b><span class="link" onclick="loadHomePage()">Обновить</span></div>
  <div id="homeRoom"></div>
  <div id="homeCatalog" class="list" style="margin-top:10px"></div>
</section>

<section id="character" class="screen">
  <div class="section-title"><b>🧍 Персонаж</b><span class="link">Одежда и стиль</span></div>
  <div id="characterView"></div>
  <div id="characterCatalog" class="list" style="margin-top:10px"></div>
</section>

<section id="market" class="screen">
  <div class="section-title"><b>🛍️ Маркет</b></div>
  <div class="tabs">
    <button class="tab on" onclick="marketTab('items',this)">Одежда</button>
    <button class="tab" onclick="marketTab('accessories',this)">Аксессуары</button>
    <button class="tab" onclick="marketTab('cars',this)">Машины</button>
    <button class="tab" onclick="marketTab('all',this)">Всё</button>
  </div>
  <div id="marketList" class="list"></div>
  <button class="secondary" onclick="openSellModal()">＋ Выставить товар</button>
</section>

<section id="cars" class="screen">
  <div class="section-title"><b>🚘 Автогараж</b><span class="link" onclick="openCarModal()">Продать машину</span></div>
  <div class="hero"><div class="car"><div class="caricon">🏎️</div><div><b>Твой гараж</b><div class="muted">Покупай редкие авто и улучшай статус профиля.</div></div></div></div>
  <div id="carsList" class="list" style="margin-top:10px"></div>
</section>

<section id="business" class="screen">
  <div class="section-title"><b>🏢 Бизнесы</b><span class="link" onclick="openBusinessModal()">＋ Создать</span></div>
  <div id="businessList" class="list"></div>
</section>

<section id="rating" class="screen">
  <div class="section-title"><b>🏆 Рейтинг города</b></div>
  <div class="tabs">
    <button class="tab on" onclick="ratingTab('coins',this)">Богатство</button>
    <button class="tab" onclick="ratingTab('xp',this)">XP</button>
    <button class="tab" onclick="ratingTab('season',this)">Сезон</button>
    <button class="tab" onclick="businessRating()">Бизнесы</button>
  </div>
  <div id="ratingList" class="list"></div>
</section>

<section id="chat" class="screen">
  <div class="section-title"><b>💬 Городской чат</b><span class="link">онлайн</span></div>
  <div id="chatList" class="list"></div>
  <div class="card" style="position:sticky;bottom:70px">
    <input id="chatInput" placeholder="Напиши что-нибудь городу…">
    <button class="primary" onclick="sendChat()">Отправить</button>
  </div>
</section>

<section id="profile" class="screen">
  <div id="myProfile"></div>
</section>

<section id="season" class="screen">
  <div class="section-title"><b>⚡ Сезон</b></div>
  <div id="seasonPage"></div>
</section>

<nav class="bottom">
  <button class="nav on" onclick="show('home')"><b>⌂</b>Главная</button>
  <button class="nav" onclick="show('jobs');loadJobs()"><b>💼</b>Работа</button>
  <button class="nav" onclick="show('market');loadMarket()"><b>🛍</b>Маркет</button>
  <button class="nav" onclick="show('chat');loadChat()"><b>💬</b>Чат</button>
  <button class="nav" onclick="show('profile');loadProfile()"><b>●</b>Профиль</button>
</nav>
</div>

<div id="modal" class="modal" onclick="if(event.target===this)closeModal()"><div class="sheet"><div class="sheet-head"><b id="modalTitle">Окно</b><button class="close" onclick="closeModal()">✕</button></div><div id="modalBody"></div></div></div>
<div id="toast" class="toast"></div>

<script>
const tg=window.Telegram&&Telegram.WebApp?Telegram.WebApp:null;
if(tg){tg.ready();tg.expand();}
let ME=null, CURRENT_MARKET='items';

const $=id=>document.getElementById(id);
function esc(x){return String(x??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]))}
function toast(t){let x=$('toast');x.textContent=t;x.style.display='block';clearTimeout(window.__t);window.__t=setTimeout(()=>x.style.display='none',2300)}
function show(id){
 document.querySelectorAll('.screen').forEach(x=>x.classList.remove('on'));
 $(id).classList.add('on');
 document.querySelectorAll('.nav').forEach(x=>x.classList.remove('on'));
 const map={home:0,jobs:1,market:2,chat:3,profile:4}; if(map[id]!==undefined)document.querySelectorAll('.nav')[map[id]].classList.add('on');
 window.scrollTo(0,0);
}
async function api(path,data={}){
 const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Telegram-Init-Data':tg?tg.initData:''},body:JSON.stringify(data)});
 const j=await r.json(); if(!r.ok||j.error)throw new Error(j.error||'Ошибка'); return j;
}
function openModal(title,body){$('modalTitle').textContent=title;$('modalBody').innerHTML=body;$('modal').classList.add('on')}
function closeModal(){$('modal').classList.remove('on')}

async function init(){
 try{let x=await api('/api/me');ME=x.user;renderHero(x.user,x.rank);await loadHome()}catch(e){toast(e.message)}
}
function renderHero(u,rank){
 let pct=Math.min(100,(u.xp%500)/5);
 $('homeHero').innerHTML=`<div class="hero"><div class="hero-row"><div style="display:flex;gap:12px;align-items:center"><div class="avatar">${esc(u.avatar)}</div><div><div class="name">${esc(u.name)}</div><div class="handle">@${esc(u.username||'player')} · #${rank}</div></div></div><div style="text-align:right"><div class="coins">🪙 ${u.coins.toLocaleString()}</div><div class="lvl">LVL ${u.level}</div></div></div><div class="progress"><i style="width:${pct}%"></i></div><div class="muted" style="margin-top:7px">${u.xp%500}/500 XP до следующего уровня · 🔥 серия ${u.streak}</div></div>`;
}

async function loadHome(){
 try{
  let [m,f,s]=await Promise.all([api('/api/me'),api('/api/feed'),api('/api/season')]);
  ME=m.user;renderHero(m.user,m.rank);
  $('feed').innerHTML=f.items.length?f.items.map(x=>`<div class="item"><div class="feedline"><div class="dot">${x.icon||'✨'}</div><div><b>${esc(x.text)}</b><div class="muted">${esc(x.time)}</div></div></div></div>`).join(''):'<div class="empty">Город только просыпается…</div>';
  $('seasonMini').innerHTML=`<div class="card"><div class="item-row"><div><b>${esc(s.season.name)}</b><div class="muted">${s.days} дней осталось</div></div><div class="money">#${s.my_rank}</div></div><div class="progress"><i style="width:${Math.min(100,(s.my_xp%5000)/50)}%"></i></div></div>`;
 }catch(e){toast(e.message)}
}

async function loadJobs(){
 try{let x=await api('/api/jobs');$('jobsList').innerHTML=x.items.length?x.items.map(j=>`<div class="item"><div class="item-row"><div><div class="item-title">💼 ${esc(j.title)}</div><span class="tag">🏢 ${esc(j.business_name)}</span><div class="muted" style="margin-top:7px">Осталось мест: ${j.slots}</div></div><div style="text-align:right"><div class="price">+${j.reward} 🪙</div><button class="buy" onclick="doWork(${j.id})">Выполнить</button></div></div></div>`).join(''):'<div class="empty">Пока нет заданий.</div>'}catch(e){toast(e.message)}
}
async function doWork(id){try{let x=await api('/api/work',{job_id:id});rewardAnim(x.message);loadJobs();loadQuests();loadHome()}catch(e){toast(e.message)}}
function openJobModal(){show('jobs');loadJobs()}

function rewardAnim(text){
 const x=document.createElement('div'); x.className='toast reward-pop'; x.textContent=text; document.body.appendChild(x); x.style.display='block'; setTimeout(()=>x.remove(),1800);
}
async function loadQuests(){
 try{let x=await api('/api/quests');$('questsList').innerHTML=x.items.map(q=>{let pct=Math.min(100,Math.round(q.progress/q.goal*100));let action=q.ready?`<button class="buy" onclick="claimQuest(${q.id})">Забрать +${q.reward} 🪙</button>`:(q.claimed?'<span class="green">✓ Получено</span>':'<span class="muted">Выполнено '+q.progress+'/'+q.goal+'</span>');return `<div class="item ${q.ready?'reward-pop':''}"><div class="item-row"><div style="flex:1"><div class="item-title">🎯 ${esc(q.title)}</div><div class="muted" style="margin-top:5px">${esc(q.description)}</div><div class="progress"><i style="width:${pct}%"></i></div><div class="muted" style="margin-top:5px">${q.progress}/${q.goal} · +${q.xp} XP</div></div><div style="text-align:right"><div class="price">+${q.reward} 🪙</div>${action}</div></div></div>`}).join('')}catch(e){toast(e.message)}
}
async function claimQuest(id){try{let x=await api('/api/quest/claim',{id});rewardAnim(x.message);loadQuests();loadHome()}catch(e){toast(e.message)}}
async function loadHomePage(){
 try{let x=await api('/api/home'); let h=x.home; let room=x.items.length?x.items.map(i=>`<div class="room-item" title="${esc(i.item_name)}">${esc(i.icon)}</div>`).join(''):'<div class="muted">Пока пусто. Купи первый предмет и начни украшать.</div>'; $('homeRoom').innerHTML=`<div class="home-room"><div style="position:relative;z-index:2"><div class="item-row"><div><b>${esc(h.style)} ${esc(h.name)}</b><div class="muted">LVL ${h.level} · Комфорт ${h.comfort}</div></div><button class="buy" onclick="upgradeHome()">⚡ Улучшить ${1000*h.level} 🪙</button></div><div class="room-items" style="margin-top:10px">${room}</div></div></div>`; $('homeCatalog').innerHTML=x.catalog.map(i=>`<div class="item"><div class="item-row"><div style="display:flex;gap:10px;align-items:center"><div class="shopicon">${esc(i.icon)}</div><div><div class="item-title">${esc(i.name)}</div><span class="tag">${esc(i.category)} · +${i.comfort} комфорта</span></div></div><div style="text-align:right"><div class="price">${i.price} 🪙</div><button class="buy" onclick="buyHomeItem(${i.id})">Купить</button></div></div></div>`).join(''); }catch(e){toast(e.message)}
}
async function buyHomeItem(id){try{let x=await api('/api/home/buy',{id});rewardAnim(x.message);loadHomePage();loadHome()}catch(e){toast(e.message)}}
async function upgradeHome(){try{let x=await api('/api/home/upgrade');rewardAnim(x.message);loadHomePage();loadHome()}catch(e){toast(e.message)}}
async function loadCharacter(){
 try{let x=await api('/api/character'); let look=x.equipped.map(i=>i.icon).join('')||'👕'; $('characterView').innerHTML=`<div class="character-stage"><div class="character-body">🧑‍🚀</div><div style="flex:1"><div class="name">Твой образ</div><div class="clothes-stack" style="margin-top:8px">${x.equipped.map(i=>`<span class="clothes-chip">${esc(i.icon)} ${esc(i.name)}</span>`).join('')||'<span class="muted">Выбери одежду ниже</span>'}</div></div></div>`; $('characterCatalog').innerHTML=x.catalog.map(i=>{let own=x.owned.find(o=>o.catalog_id===i.id);let eq=own&&own.equipped;let btn=eq?'<span class="green">✓ Надето</span>':own?`<button class="buy" onclick="equipClothing(${i.id})">Надеть</button>`:`<button class="buy" onclick="buyClothing(${i.id})">Купить</button>`;return `<div class="item"><div class="item-row"><div style="display:flex;gap:10px;align-items:center"><div class="shopicon">${esc(i.icon)}</div><div><div class="item-title">${esc(i.name)}</div><span class="tag">${esc(i.category)} · ${esc(i.rarity)}</span></div></div><div style="text-align:right"><div class="price">${i.price===0?'Бесплатно':i.price+' 🪙'}</div>${btn}</div></div></div>`}).join(''); }catch(e){toast(e.message)}
}
async function buyClothing(id){try{let x=await api('/api/character/buy',{id});rewardAnim(x.message);loadCharacter();loadQuests();loadHome()}catch(e){toast(e.message)}}
async function equipClothing(id){try{let x=await api('/api/character/equip',{id});rewardAnim(x.message);loadCharacter();loadQuests();loadProfile()}catch(e){toast(e.message)}}

async function loadMarket(){
 try{let x=await api('/api/market');renderMarket(x)}catch(e){toast(e.message)}
}
function marketTab(kind,el){CURRENT_MARKET=kind;document.querySelectorAll('#market .tab').forEach(x=>x.classList.remove('on'));el.classList.add('on');loadMarket()}
function renderMarket(x){
 let arr=x.items.filter(i=>CURRENT_MARKET==='all'||i.category===CURRENT_MARKET);
 $('marketList').innerHTML=arr.length?arr.map(i=>`<div class="item"><div class="item-row"><div style="display:flex;gap:10px"><div class="shopicon">${esc(i.icon)}</div><div><div class="item-title">${esc(i.title)}</div><span class="tag">${esc(i.category)}</span><div class="muted" style="margin-top:6px">${esc(i.description)}</div><div class="muted">Продавец: ${esc(i.seller_name)}</div></div></div><div style="text-align:right"><div class="price">${i.price} 🪙</div><button class="buy" onclick="buyItem(${i.id})">Купить</button></div></div></div>`).join(''):'<div class="empty">В этой категории пока пусто.</div>';
}
async function buyItem(id){try{let x=await api('/api/market/buy',{id});toast(x.message);loadMarket();loadHome()}catch(e){toast(e.message)}}

function openSellModal(){
 openModal('Выставить товар',`<label>Название<input id="sellName" placeholder="Например, куртка Developer"></label>
 <label>Категория<select id="sellCat"><option value="items">Одежда</option><option value="accessories">Аксессуары</option></select></label>
 <label>Иконка<input id="sellIcon" value="👕"></label>
 <label>Описание<textarea id="sellDesc" placeholder="Описание"></textarea></label>
 <label>Цена<input id="sellPrice" type="number" value="250"></label>
 <button class="primary" onclick="sellItem()">Выставить на рынок</button>`);
}
async function sellItem(){try{await api('/api/market/create',{title:$('sellName').value,category:$('sellCat').value,icon:$('sellIcon').value,description:$('sellDesc').value,price:+$('sellPrice').value});closeModal();toast('Товар выставлен');loadMarket()}catch(e){toast(e.message)}}

async function loadCars(){
 try{let x=await api('/api/cars');$('carsList').innerHTML=x.items.map(c=>`<div class="item"><div class="car"><div class="caricon">${esc(c.icon)}</div><div style="flex:1"><div class="item-title">${esc(c.model)}</div><div class="muted">${esc(c.description)}</div><div class="carstats"><span>⚡ Скорость</span><span>${c.speed}</span><span>✨ Редкость</span><span>${esc(c.rarity)}</span></div></div><div style="text-align:right"><div class="price">${c.price} 🪙</div><button class="buy" onclick="buyCar(${c.id})">Купить</button></div></div></div>`).join('')||'<div class="empty">Машин пока нет.</div>'}catch(e){toast(e.message)}
}
async function buyCar(id){try{let x=await api('/api/car/buy',{id});toast(x.message);loadCars();loadProfile();loadHome()}catch(e){toast(e.message)}}
function openCarModal(){
 openModal('Продать машину',`<label>Модель<input id="carModel" placeholder="Night Runner X"></label><label>Иконка<input id="carIcon" value="🏎️"></label><label>Описание<textarea id="carDesc"></textarea></label><label>Скорость<input id="carSpeed" type="number" value="80"></label><label>Цена<input id="carPrice" type="number" value="2500"></label><button class="primary" onclick="sellCar()">Выставить автомобиль</button>`);
}
async function sellCar(){try{await api('/api/car/create',{model:$('carModel').value,icon:$('carIcon').value,description:$('carDesc').value,speed:+$('carSpeed').value,price:+$('carPrice').value});closeModal();toast('Автомобиль выставлен');loadCars()}catch(e){toast(e.message)}}

async function loadBusinesses(){
 try{let x=await api('/api/businesses');$('businessList').innerHTML=x.items.map(b=>`<div class="item" onclick="openBusiness(${b.id})"><div class="item-row"><div><div class="item-title">🏢 ${esc(b.name)}</div><span class="tag">${esc(b.category)} · LVL ${b.level}</span><div class="muted" style="margin-top:6px">${esc(b.description)}</div><div class="muted">Владелец: ${esc(b.owner_name)}</div></div><div style="text-align:right"><div>⭐ ${Number(b.rating).toFixed(1)}</div><div class="price">💰 ${b.revenue}</div></div></div></div>`).join('')||'<div class="empty">Создай первый бизнес.</div>'}catch(e){toast(e.message)}
}
function openBusinessModal(){
 openModal('Создать бизнес',`<label>Название<input id="bn" placeholder="Developer Studio"></label><label>Категория<select id="bc"><option>Технологии</option><option>Магазин</option><option>Автосервис</option><option>Медиа</option><option>Кафе</option><option>Финансы</option></select></label><label>Описание<textarea id="bd" placeholder="Чем занимается компания?"></textarea></label><label>Стартовый капитал<input id="bcap" type="number" value="300"></label><label>Первая вакансия<input id="bjob" placeholder="Дизайнер / Курьер / Менеджер"></label><label>Награда за задание<input id="br" type="number" value="120"></label><button class="primary" onclick="createBusiness()">Создать бизнес</button>`);
}
async function createBusiness(){try{await api('/api/business/create',{name:$('bn').value,category:$('bc').value,description:$('bd').value,capital:+$('bcap').value,job_title:$('bjob').value,job_reward:+$('br').value});closeModal();rewardAnim('🚀 Бизнес создан!');show('business');loadBusinesses();loadQuests();loadHome()}catch(e){toast(e.message)}}
async function openBusiness(id){
 try{let x=await api('/api/business/view',{id});let b=x.business;
 openModal(b.name,`<div class="hero"><div class="item-row"><div><b>🏢 ${esc(b.name)}</b><div class="muted">${esc(b.category)} · LVL ${b.level}</div></div><div>⭐ ${Number(b.rating).toFixed(1)}</div></div><p class="muted">${esc(b.description)}</p><div class="grid2"><div class="card"><div class="muted">Владелец</div><b>${esc(x.owner.name)}</b></div><div class="card"><div class="muted">Выручка</div><b class="money">${b.revenue} 🪙</b></div></div></div>
 <button class="primary" onclick="upgradeBusiness(${b.id})">⚡ Апгрейд бизнеса</button>
 <button class="secondary" onclick="followUser(${b.owner_id})">${x.following?'✓ Подписка оформлена':'＋ Подписаться'}</button>
 <label>Отзыв<textarea id="reviewText" placeholder="Поделись впечатлением"></textarea></label><button class="secondary" onclick="reviewBusiness(${b.id})">⭐ Оставить отзыв</button>`);
 }catch(e){toast(e.message)}
}
async function upgradeBusiness(id){try{let x=await api('/api/business/upgrade',{id});rewardAnim(x.message);closeModal();loadBusinesses();loadQuests();loadHome()}catch(e){toast(e.message)}}
async function reviewBusiness(id){try{await api('/api/business/review',{id,text:$('reviewText').value,rating:5});toast('Спасибо за отзыв');closeModal()}catch(e){toast(e.message)}}

async function ratingTab(kind,el){document.querySelectorAll('#rating .tab').forEach(x=>x.classList.remove('on'));el.classList.add('on');try{let x=await api('/api/rating',{kind});renderRating(x.items)}catch(e){toast(e.message)}}
function renderRating(arr){$('ratingList').innerHTML=arr.map((u,i)=>`<div class="item"><div class="rank"><div class="ranknum">${i+1}</div><div class="rankavatar">${esc(u.avatar||'👤')}</div><div style="flex:1"><b>${esc(u.name)}</b><div class="muted">@${esc(u.username||'player')} · LVL ${u.level}</div></div><div style="text-align:right"><div class="money">${u.coins.toLocaleString()} 🪙</div><div class="muted">${u.xp} XP</div></div></div></div>`).join('')}
async function businessRating(){try{let x=await api('/api/business/rating');$('ratingList').innerHTML=x.items.map((b,i)=>`<div class="item"><div class="rank"><div class="ranknum">${i+1}</div><div class="rankavatar">🏢</div><div style="flex:1"><b>${esc(b.name)}</b><div class="muted">${esc(b.owner_name)} · LVL ${b.level}</div></div><div>⭐ ${Number(b.rating).toFixed(1)}</div></div></div>`).join('')}catch(e){toast(e.message)}}

async function loadChat(){try{let x=await api('/api/chat');$('chatList').innerHTML=x.items.map(m=>`<div class="item"><div class="item-row"><b>${esc(m.name)}</b><span class="muted">${esc(m.time)}</span></div><div style="margin-top:6px">${esc(m.text)}</div></div>`).join('')||'<div class="empty">Напиши первое сообщение.</div>'}catch(e){toast(e.message)}}
async function sendChat(){let text=$('chatInput').value.trim();if(!text)return;try{await api('/api/chat/send',{text});$('chatInput').value='';loadChat()}catch(e){toast(e.message)}}

async function loadProfile(){
 try{let x=await api('/api/profile');let u=x.user;
 $('myProfile').innerHTML=`<div class="cover"><span>${esc(u.cover)}</span></div><div class="profile-head"><div class="bigavatar">${esc(u.avatar)}</div><div style="margin-top:8px"><div class="name">${esc(u.name)}</div><div class="handle">@${esc(u.username||'player')} · LVL ${u.level}</div></div><p class="muted">${esc(u.bio||'Профиль ещё не оформлен.')}</p><div class="grid3"><div class="card"><div class="muted">Монеты</div><b class="money">${u.coins}</b></div><div class="card"><div class="muted">Банк</div><b>${u.bank}</b></div><div class="card"><div class="muted">Друзья</div><b>${x.friends}</b></div></div></div>
 <div class="grid2"><button class="action" onclick="openProfileEdit()">✏️<small>Редактор</small></button><button class="action" onclick="openBank()">🏦<small>Банк</small></button><button class="action" onclick="openFriends()">👥<small>Друзья</small></button><button class="action" onclick="openInventory()">🎒<small>Инвентарь</small></button><button class="action" onclick="show('homePage');loadHomePage()">🏠<small>Дом</small></button><button class="action" onclick="show('character');loadCharacter()">🧍<small>Персонаж</small></button></div>
 <div class="section-title"><b>🏅 Достижения</b></div><div class="list">${x.achievements.map(a=>`<div class="item"><div class="item-row"><div><b>${a.done?'🏆':'🔒'} ${esc(a.title)}</b><div class="muted">${esc(a.text)}</div></div>${a.done?'<span class="green">Получено</span>':''}</div></div>`).join('')}</div>`;
 }catch(e){toast(e.message)}
}
function openProfileEdit(){openModal('Настроить профиль',`<label>Имя<input id="pn" value="${esc(ME.name)}"></label><label>Описание<input id="pb" value="${esc(ME.bio||'')}"></label><label>Аватар<input id="pa" value="${esc(ME.avatar||'🧑‍💻')}"></label><label>Обложка / эмодзи<input id="pc" value="${esc(ME.cover||'🌌')}"></label><button class="primary" onclick="saveProfile()">Сохранить</button>`)}
async function saveProfile(){try{await api('/api/profile/update',{name:$('pn').value,bio:$('pb').value,avatar:$('pa').value,cover:$('pc').value});closeModal();rewardAnim('✨ Профиль обновлён');loadProfile();loadQuests();loadHome()}catch(e){toast(e.message)}}

function openBank(){openModal('🏦 Банк',`<div class="grid2"><div class="card"><div class="muted">В кошельке</div><div class="value">${ME.coins} 🪙</div></div><div class="card"><div class="muted">В банке</div><div class="value">${ME.bank} 🪙</div></div></div><input id="bankAmt" type="number" value="100"><div class="grid2"><button class="primary" onclick="bankMove('deposit')">Внести</button><button class="secondary" onclick="bankMove('withdraw')">Снять</button></div>`)}
async function bankMove(type){try{await api('/api/bank',{type,amount:+$('bankAmt').value});closeModal();toast('Баланс обновлён');loadProfile();loadHome()}catch(e){toast(e.message)}}
function openInventory(){api('/api/inventory').then(x=>openModal('🎒 Инвентарь',x.items.length?x.items.map(i=>`<div class="item"><div class="item-row"><b>${esc(i.icon)} ${esc(i.item_name)}</b><span>x${i.qty}</span></div></div>`).join(''):'<div class="empty">Пока пусто.</div>')).catch(e=>toast(e.message))}
function openFriends(){api('/api/friends').then(x=>openModal('👥 Друзья',`<div class="list">${x.items.map(f=>`<div class="item item-row"><div><b>${esc(f.name)}</b><div class="muted">@${esc(f.username||'player')} · LVL ${f.level}</div></div><button class="buy" onclick="viewPlayer(${f.id})">Профиль</button></div>`).join('')||'<div class="empty">Пока нет друзей.</div>'}</div>`)).catch(e=>toast(e.message))}
async function viewPlayer(id){try{let x=await api('/api/player',{id});openModal(x.user.name,`<div class="cover"><span>${esc(x.user.cover)}</span></div><div class="profile-head"><div class="bigavatar">${esc(x.user.avatar)}</div><h2>${esc(x.user.name)}</h2><div class="handle">@${esc(x.user.username||'player')} · LVL ${x.user.level}</div><p class="muted">${esc(x.user.bio||'Нет описания')}</p><div class="grid2"><div class="card"><div class="muted">XP</div><b>${x.user.xp}</b></div><div class="card"><div class="muted">Бизнесов</div><b>${x.businesses}</b></div></div><button class="primary" onclick="addFriend(${id})">👥 Добавить в друзья</button><button class="secondary" onclick="followUser(${id})">＋ Подписаться</button>`)}catch(e){toast(e.message)}}
async function addFriend(id){try{await api('/api/friends/add',{id});toast('Запрос отправлен');closeModal()}catch(e){toast(e.message)}}
async function followUser(id){try{let x=await api('/api/follow',{id});toast(x.following?'Подписка оформлена':'Подписка отменена')}catch(e){toast(e.message)}}

async function claimBonus(){try{let x=await api('/api/bonus');toast(x.message);loadHome()}catch(e){toast(e.message)}}

async function loadSeason(){
 try{let x=await api('/api/season');$('seasonPage').innerHTML=`<div class="hero"><b>${esc(x.season.name)}</b><div class="muted" style="margin-top:6px">${x.days} дней до конца</div><div class="value">#${x.my_rank}</div><div class="muted">твоя позиция</div></div><div class="section-title"><b>🏆 Топ сезона</b></div><div class="list">${x.top.map((u,i)=>`<div class="item"><div class="rank"><div class="ranknum">${i+1}</div><div class="rankavatar">${esc(u.avatar)}</div><div style="flex:1"><b>${esc(u.name)}</b></div><div class="pink">${u.season_xp} XP</div></div></div>`).join('')}</div><div class="section-title"><b>🎁 Награды</b></div><div class="card">🥇 1 место — 15 000 🪙<br><br>🥈 2 место — 9 000 🪙<br><br>🥉 3 место — 6 000 🪙<br><br>🏅 Топ-10 — 2 500 🪙</div>`}catch(e){toast(e.message)}
}

function openNotifications(){api('/api/notifications').then(x=>openModal('🔔 Уведомления',x.items.length?x.items.map(n=>`<div class="item">${esc(n.text)}</div>`).join(''):'<div class="empty">Нет новых уведомлений.</div>')).catch(e=>toast(e.message))}

async function boot(){
 await init();
 // Preload sections that are frequently used.
 loadCars(); loadBusinesses(); loadJobs(); loadMarket(); loadSeason(); loadQuests(); loadHomePage(); loadCharacter();
}
boot();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type,X-Telegram-Init-Data")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_json({"ok": True})

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/index.html"):
            b = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b)
        elif path == "/health":
            self.send_json({"ok": True, "app": "NeuroCity", "version": "6.0 Life Update"})
        else:
            self.send_error(404)

    def do_POST(self):
        c = None
        try:
            u = user_from_request(self)
            d = json_body(self)
            p = urllib.parse.urlparse(self.path).path
            with LOCK:
                c = db()
                t = now()

                if p == "/api/me":
                    r = c.execute(
                        "SELECT COUNT(*)+1 n FROM users WHERE coins>(SELECT coins FROM users WHERE id=%s)",
                        (u["id"],)
                    ).fetchone()
                    self.send_json({"user": dict(c.execute("SELECT * FROM users WHERE id=%s", (u["id"],)).fetchone()), "rank": r["n"]})
                    return

                if p == "/api/feed":
                    rows = c.execute("""
                        SELECT f.*,u.name,u.avatar
                        FROM feed f JOIN users u ON u.id=f.user_id
                        ORDER BY f.id DESC LIMIT 15
                    """).fetchall()
                    items=[]
                    for r in rows:
                        mins=max(0,(t-r["created_at"])//60)
                        tm="только что" if mins<1 else (f"{mins} мин назад" if mins<60 else f"{mins//60} ч назад")
                        items.append({"text":r["text"],"icon":r["avatar"],"time":tm})
                    self.send_json({"items":items})
                    return

                if p == "/api/quests":
                    rows=c.execute("SELECT * FROM quests WHERE active=1 ORDER BY id").fetchall()
                    items=[]
                    for q in rows:
                        claimed=bool(c.execute("SELECT 1 FROM user_quests WHERE user_id=%s AND quest_id=%s",(u["id"],q["id"])).fetchone())
                        progress=min(q["goal"],quest_progress(c,u["id"],q["metric"]))
                        items.append({**dict(q),"progress":progress,"claimed":claimed,"ready":progress>=q["goal"] and not claimed})
                    self.send_json({"items":items})
                    return

                if p == "/api/quest/claim":
                    qid=int(d.get("id",0)); q=c.execute("SELECT * FROM quests WHERE id=%s AND active=1",(qid,)).fetchone()
                    if not q: raise ValueError("Задание не найдено")
                    if c.execute("SELECT 1 FROM user_quests WHERE user_id=%s AND quest_id=%s",(u["id"],qid)).fetchone(): raise ValueError("Награда уже получена")
                    progress=quest_progress(c,u["id"],q["metric"])
                    if progress<q["goal"]: raise ValueError(f"Нужно выполнить условие: {q['description']}")
                    c.execute("INSERT INTO user_quests(user_id,quest_id,claimed_at) VALUES(%s,%s,%s)",(u["id"],qid,t))
                    c.execute("UPDATE users SET coins=coins+%s WHERE id=%s",(q["reward"],u["id"]))
                    add_xp(c,u["id"],q["xp"])
                    add_feed(c,u["id"],"quest",f'{u["name"]} выполнил задание «{q["title"]}" и получил {q["reward"]} 🪙')
                    c.commit()
                    self.send_json({"ok":True,"message":f'🎉 +{q["reward"]} 🪙 и +{q["xp"]} XP'})
                    return

                if p == "/api/home":
                    h=c.execute("SELECT * FROM homes WHERE user_id=%s",(u["id"],)).fetchone()
                    if not h:
                        c.execute("INSERT INTO homes(user_id,name,style,created_at) VALUES(%s,%s,%s,%s)",(u["id"],"Мой дом","🌃",t)); c.commit(); h=c.execute("SELECT * FROM homes WHERE user_id=%s",(u["id"],)).fetchone()
                    items=c.execute("SELECT * FROM home_items WHERE user_id=%s ORDER BY id DESC",(u["id"],)).fetchall()
                    catalog=c.execute("SELECT * FROM home_catalog ORDER BY price,id").fetchall()
                    self.send_json({"home":dict(h),"items":rowdicts(items),"catalog":rowdicts(catalog)})
                    return

                if p == "/api/home/buy":
                    cid=int(d.get("id",0)); item=c.execute("SELECT * FROM home_catalog WHERE id=%s",(cid,)).fetchone()
                    if not item: raise ValueError("Предмет не найден")
                    if u["coins"]<item["price"]: raise ValueError(f"Нужно {item['price']} 🪙")
                    if not c.execute("UPDATE users SET coins=coins-%s WHERE id=%s AND coins>=%s RETURNING id",(item["price"],u["id"],item["price"])).fetchone(): raise ValueError("Недостаточно монет")
                    c.execute("INSERT INTO home_items(user_id,catalog_id,item_name,icon,category,price,comfort,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",(u["id"],cid,item["name"],item["icon"],item["category"],item["price"],item["comfort"],t))
                    c.execute("UPDATE homes SET comfort=comfort+%s WHERE user_id=%s",(item["comfort"],u["id"]))
                    add_xp(c,u["id"],40)
                    add_feed(c,u["id"],"home",f'{u["name"]} украсил дом: {item["icon"]} {item["name"]}')
                    c.commit(); self.send_json({"ok":True,"message":f'🏠 {item["name"]} добавлен в дом'})
                    return

                if p == "/api/home/upgrade":
                    h=c.execute("SELECT * FROM homes WHERE user_id=%s FOR UPDATE",(u["id"],)).fetchone(); cost=1000*h["level"]
                    if u["coins"]<cost: raise ValueError(f"Нужно {cost} 🪙")
                    if not c.execute("UPDATE users SET coins=coins-%s WHERE id=%s AND coins>=%s RETURNING id",(cost,u["id"],cost)).fetchone(): raise ValueError("Недостаточно монет")
                    c.execute("UPDATE homes SET level=level+1,comfort=comfort+50 WHERE user_id=%s",(u["id"]))
                    add_xp(c,u["id"],120); c.commit(); self.send_json({"ok":True,"message":f'🏠 Дом улучшен до LVL {h["level"]+1}'})
                    return

                if p == "/api/character":
                    catalog=c.execute("SELECT * FROM clothing_catalog ORDER BY price,id").fetchall()
                    owned=c.execute("SELECT uc.*,cc.name,cc.category,cc.icon,cc.price,cc.rarity FROM user_clothing uc JOIN clothing_catalog cc ON cc.id=uc.catalog_id WHERE uc.user_id=%s ORDER BY uc.id DESC",(u["id"],)).fetchall()
                    equipped=c.execute("SELECT cc.* FROM user_clothing uc JOIN clothing_catalog cc ON cc.id=uc.catalog_id WHERE uc.user_id=%s AND uc.equipped=1 ORDER BY cc.category",(u["id"],)).fetchall()
                    self.send_json({"catalog":rowdicts(catalog),"owned":rowdicts(owned),"equipped":rowdicts(equipped)})
                    return

                if p == "/api/character/buy":
                    cid=int(d.get("id",0)); item=c.execute("SELECT * FROM clothing_catalog WHERE id=%s",(cid,)).fetchone()
                    if not item: raise ValueError("Предмет не найден")
                    if c.execute("SELECT 1 FROM user_clothing WHERE user_id=%s AND catalog_id=%s",(u["id"],cid)).fetchone(): raise ValueError("Этот предмет уже у тебя")
                    if u["coins"]<item["price"]: raise ValueError(f"Нужно {item['price']} 🪙")
                    if item["price"]>0 and not c.execute("UPDATE users SET coins=coins-%s WHERE id=%s AND coins>=%s RETURNING id",(item["price"],u["id"],item["price"])).fetchone(): raise ValueError("Недостаточно монет")
                    c.execute("INSERT INTO user_clothing(user_id,catalog_id,equipped,created_at) VALUES(%s,%s,0,%s)",(u["id"],cid,t)); c.commit(); self.send_json({"ok":True,"message":f'👕 {item["name"]} получен'})
                    return

                if p == "/api/character/equip":
                    cid=int(d.get("id",0)); item=c.execute("SELECT cc.* FROM clothing_catalog cc JOIN user_clothing uc ON uc.catalog_id=cc.id WHERE uc.user_id=%s AND cc.id=%s",(u["id"],cid)).fetchone()
                    if not item: raise ValueError("Сначала получи этот предмет")
                    c.execute("UPDATE user_clothing SET equipped=0 WHERE user_id=%s AND catalog_id IN (SELECT id FROM clothing_catalog WHERE category=%s)",(u["id"],item["category"]))
                    c.execute("UPDATE user_clothing SET equipped=1 WHERE user_id=%s AND catalog_id=%s",(u["id"],cid)); c.commit(); self.send_json({"ok":True,"message":f'✨ Надето: {item["name"]}'})
                    return

                if p == "/api/jobs":
                    rows=c.execute("""
                        SELECT j.*,b.name business_name
                        FROM jobs j JOIN businesses b ON b.id=j.business_id
                        WHERE j.slots>0 ORDER BY j.id DESC
                    """).fetchall()
                    self.send_json({"items":rowdicts(rows)})
                    return

                if p == "/api/work":
                    jid=int(d.get("job_id",0))
                    j=c.execute("SELECT * FROM jobs WHERE id=%s", (jid,)).fetchone()
                    if not j or j["slots"]<=0: raise ValueError("Задание уже недоступно")
                    if c.execute("SELECT 1 FROM work WHERE job_id=%s AND user_id=%s", (jid,u["id"])).fetchone():
                        raise ValueError("Ты уже выполнял это задание")
                    if not c.execute("UPDATE jobs SET slots=slots-1 WHERE id=%s AND slots>0 RETURNING id",(jid,)).fetchone():
                        raise ValueError("Задание уже занято")
                    c.execute("INSERT INTO work(job_id,user_id,reward,created_at) VALUES(%s,%s,%s,%s)",(jid,u["id"],j["reward"],t))
                    c.execute("UPDATE users SET coins=coins+%s WHERE id=%s",(j["reward"],u["id"]))
                    add_xp(c,u["id"],50)
                    add_feed(c,u["id"],"work",f'{u["name"]} выполнил задание и заработал {j["reward"]} 🪙')
                    c.commit()
                    self.send_json({"ok":True,"message":f'+{j["reward"]} 🪙 и +50 XP'})
                    return

                if p == "/api/businesses":
                    rows=c.execute("""
                        SELECT b.*,u.name owner_name
                        FROM businesses b JOIN users u ON u.id=b.owner_id
                        ORDER BY b.id DESC
                    """).fetchall()
                    self.send_json({"items":rowdicts(rows)})
                    return

                if p == "/api/business/create":
                    name=clean_text(d.get("name"),80); cat=clean_text(d.get("category"),40); desc=clean_text(d.get("description"),300)
                    cap=max(100,int(d.get("capital",300))); jt=clean_text(d.get("job_title"),80); jr=max(30,int(d.get("job_reward",120)))
                    if not name or not cat or not desc: raise ValueError("Заполни все поля")
                    if u["coins"]<cap: raise ValueError("Недостаточно монет")
                    bid=c.execute("""INSERT INTO businesses(owner_id,name,category,description,capital,created_at)
                                 VALUES(%s,%s,%s,%s,%s,%s) RETURNING id""",(u["id"],name,cat,desc,cap,t)).fetchone()["id"]
                    if jt:
                        c.execute("INSERT INTO jobs(business_id,title,reward,slots,created_at) VALUES(%s,%s,%s,%s,%s)",(bid,jt,jr,10,t))
                    if not c.execute("UPDATE users SET coins=coins-%s WHERE id=%s AND coins>=%s RETURNING id",(cap,u["id"],cap)).fetchone():
                        raise ValueError("Недостаточно монет")
                    add_xp(c,u["id"],200)
                    add_feed(c,u["id"],"business",f'{u["name"]} открыл бизнес «{name}»')
                    c.commit()
                    self.send_json({"ok":True})
                    return

                if p == "/api/business/upgrade":
                    bid=int(d.get("id",0))
                    b=c.execute("SELECT * FROM businesses WHERE id=%s", (bid,)).fetchone()
                    if not b: raise ValueError("Бизнес не найден")
                    if b["owner_id"]!=u["id"]: raise ValueError("Апгрейдить можно только свой бизнес")
                    cost=500*b["level"]
                    if u["coins"]<cost: raise ValueError(f"Нужно {cost} 🪙")
                    if not c.execute("UPDATE users SET coins=coins-%s WHERE id=%s AND coins>=%s RETURNING id",(cost,u["id"],cost)).fetchone():
                        raise ValueError(f"Нужно {cost} 🪙")
                    c.execute("UPDATE businesses SET level=level+1,upgrades=upgrades+1,revenue=revenue+%s WHERE id=%s",(cost//2,bid))
                    add_xp(c,u["id"],150)
                    add_feed(c,u["id"],"upgrade",f'{u["name"]} улучшил бизнес «{b["name"]}» до LVL {b["level"]+1}')
                    c.commit()
                    self.send_json({"ok":True,"message":f'⚡ Бизнес улучшен за {cost} 🪙'})
                    return

                if p == "/api/business/view":
                    bid=int(d.get("id",0))
                    b=c.execute("""SELECT b.*,u.id owner_id,u.name owner
                                  FROM businesses b JOIN users u ON u.id=b.owner_id WHERE b.id=%s""",(bid,)).fetchone()
                    if not b: raise ValueError("Бизнес не найден")
                    following=bool(c.execute("SELECT 1 FROM follows WHERE follower_id=%s AND target_id=%s",(u["id"],b["owner_id"])).fetchone())
                    self.send_json({"business":dict(b),"owner":{"id":b["owner_id"],"name":b["owner"]},"following":following})
                    return

                if p == "/api/business/review":
                    bid=int(d.get("id",0)); text=clean_text(d.get("text"),300); rating=max(1,min(5,int(d.get("rating",5))))
                    if not text: raise ValueError("Напиши отзыв")
                    c.execute("INSERT INTO business_reviews(business_id,user_id,rating,text,created_at) VALUES(%s,%s,%s,%s,%s)",(bid,u["id"],rating,text,t))
                    avg=c.execute("SELECT AVG(rating) a FROM business_reviews WHERE business_id=%s",(bid,)).fetchone()["a"] or 5
                    c.execute("UPDATE businesses SET rating=%s WHERE id=%s",(avg,bid))
                    c.commit()
                    self.send_json({"ok":True})
                    return

                if p == "/api/business/rating":
                    rows=c.execute("""SELECT b.*,u.name owner_name FROM businesses b JOIN users u ON u.id=b.owner_id
                                      ORDER BY rating DESC,level DESC LIMIT 30""").fetchall()
                    self.send_json({"items":rowdicts(rows)})
                    return

                if p == "/api/market":
                    rows=c.execute("""SELECT p.*,u.name seller_name FROM products p JOIN users u ON u.id=p.seller_id
                                      WHERE p.active=1 ORDER BY p.id DESC""").fetchall()
                    self.send_json({"items":rowdicts(rows)})
                    return

                if p == "/api/market/create":
                    title=clean_text(d.get("title"),80); cat=clean_text(d.get("category"),30); icon=clean_text(d.get("icon"),5) or "👕"
                    desc=clean_text(d.get("description"),250); price=max(1,int(d.get("price",0)))
                    if not title or not desc: raise ValueError("Заполни товар")
                    c.execute("""INSERT INTO products(seller_id,title,category,icon,description,price,created_at)
                                 VALUES(%s,%s,%s,%s,%s,%s,%s)""",(u["id"],title,cat,icon,desc,price,t))
                    c.commit(); self.send_json({"ok":True}); return

                if p == "/api/market/buy":
                    pid=int(d.get("id",0)); pdt=c.execute("SELECT * FROM products WHERE id=%s AND active=1",(pid,)).fetchone()
                    if not pdt: raise ValueError("Товар уже продан")
                    if pdt["seller_id"]==u["id"]: raise ValueError("Нельзя купить свой товар")
                    if u["coins"]<pdt["price"]: raise ValueError("Недостаточно монет")
                    if not c.execute("UPDATE products SET active=0 WHERE id=%s AND active=1 RETURNING id",(pid,)).fetchone():
                        raise ValueError("Товар уже продан")
                    if not c.execute("UPDATE users SET coins=coins-%s WHERE id=%s AND coins>=%s RETURNING id",(pdt["price"],u["id"],pdt["price"])).fetchone():
                        raise ValueError("Недостаточно монет")
                    c.execute("UPDATE users SET coins=coins+%s WHERE id=%s",(pdt["price"],pdt["seller_id"]))
                    c.execute("INSERT INTO purchases(product_id,buyer_id,seller_id,price,created_at) VALUES(%s,%s,%s,%s,%s)",(pid,u["id"],pdt["seller_id"],pdt["price"],t))
                    c.execute("INSERT INTO inventory(user_id,item_type,item_id,item_name,icon,qty,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s)",(u["id"],"market",pid,pdt["title"],pdt["icon"],1,t))
                    add_xp(c,u["id"],20)
                    add_feed(c,u["id"],"trade",f'{u["name"]} купил «{pdt["title"]}» на рынке')
                    c.commit(); self.send_json({"ok":True,"message":f'Куплено за {pdt["price"]} 🪙'}); return

                if p == "/api/cars":
                    rows=c.execute("SELECT * FROM cars WHERE active=1 ORDER BY id DESC").fetchall()
                    items=[]
                    import re
                    for r in rows:
                        d=dict(r); raw=d.get("description","")
                        m=re.search(r"\[SPEED:(\d+)\]\[RARITY:([^\]]+)\]\s*(.*)", raw)
                        if m:
                            d["speed"]=int(m.group(1)); d["rarity"]=m.group(2); d["description"]=m.group(3)
                        else:
                            d["speed"]=80; d["rarity"]="Обычная"
                        items.append(d)
                    self.send_json({"items":items}); return

                if p == "/api/car/create":
                    model=clean_text(d.get("model"),70); icon=clean_text(d.get("icon"),5) or "🚗"; desc=clean_text(d.get("description"),250)
                    speed=max(1,min(200,int(d.get("speed",80)))); price=max(100,int(d.get("price",2500)))
                    if not model: raise ValueError("Укажи модель")
                    rarity="Легендарная" if price>=10000 else ("Редкая" if price>=5000 else "Обычная")
                    cid=c.execute("""INSERT INTO cars(seller_id,model,icon,description,price,created_at)
                                 VALUES(%s,%s,%s,%s,%s,%s) RETURNING id""",(u["id"],model,icon,desc,price,t)).fetchone()["id"]
                    c.execute("UPDATE cars SET description=%s WHERE id=%s",(f"[SPEED:{speed}][RARITY:{rarity}] {desc}",cid))
                    c.commit(); self.send_json({"ok":True}); return

                if p == "/api/car/buy":
                    cid=int(d.get("id",0)); car=c.execute("SELECT * FROM cars WHERE id=%s AND active=1",(cid,)).fetchone()
                    if not car: raise ValueError("Машина уже продана")
                    if car["seller_id"]==u["id"]: raise ValueError("Нельзя купить свою машину")
                    if u["coins"]<car["price"]: raise ValueError("Недостаточно монет")
                    if not c.execute("UPDATE cars SET active=0 WHERE id=%s AND active=1 RETURNING id",(cid,)).fetchone():
                        raise ValueError("Машина уже продана")
                    if not c.execute("UPDATE users SET coins=coins-%s,xp=xp+100 WHERE id=%s AND coins>=%s RETURNING id",(car["price"],u["id"],car["price"])).fetchone():
                        raise ValueError("Недостаточно монет")
                    c.execute("UPDATE users SET coins=coins+%s WHERE id=%s",(car["price"],car["seller_id"]))
                    c.execute("INSERT INTO car_purchases(car_id,buyer_id,seller_id,price,created_at) VALUES(%s,%s,%s,%s,%s)",(cid,u["id"],car["seller_id"],car["price"],t))
                    c.execute("INSERT INTO inventory(user_id,item_type,item_id,item_name,icon,qty,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s)",(u["id"],"car",cid,car["model"],car["icon"],1,t))
                    add_feed(c,u["id"],"car",f'{u["name"]} купил автомобиль {car["model"]}')
                    c.commit(); self.send_json({"ok":True,"message":f'🚘 {car["model"]} теперь твоя'}); return

                if p == "/api/rating":
                    kind=d.get("kind","coins")
                    col="season_xp" if kind=="season" else ("xp" if kind=="xp" else "coins")
                    rows=c.execute(f"SELECT id,name,username,avatar,coins,xp,level,season_xp FROM users ORDER BY {col} DESC LIMIT 30").fetchall()
                    self.send_json({"items":rowdicts(rows)}); return

                if p == "/api/chat":
                    rows=c.execute("""SELECT ch.*,u.name,u.avatar FROM chat ch JOIN users u ON u.id=ch.user_id
                                      ORDER BY ch.id DESC LIMIT 100""").fetchall()
                    out=[]
                    for r in reversed(rows):
                        mins=max(0,(t-r["created_at"])//60)
                        out.append({"name":r["name"],"avatar":r["avatar"],"text":r["text"],"time":"только что" if mins<1 else f"{mins} мин назад"})
                    self.send_json({"items":out}); return

                if p == "/api/chat/send":
                    text=clean_text(d.get("text"),500)
                    if not text: raise ValueError("Сообщение пустое")
                    if not rate_limit((u["id"], "chat"), CHAT_COOLDOWN):
                        raise ValueError("Слишком часто. Подожди пару секунд.")
                    c.execute("INSERT INTO chat(user_id,text,created_at) VALUES(%s,%s,%s)",(u["id"],text,t))
                    c.commit(); self.send_json({"ok":True}); return

                if p == "/api/follow":
                    tid=int(d.get("id",0))
                    if tid==u["id"]: raise ValueError("Это твой профиль")
                    ex=c.execute("SELECT 1 FROM follows WHERE follower_id=%s AND target_id=%s",(u["id"],tid)).fetchone()
                    if ex:
                        c.execute("DELETE FROM follows WHERE follower_id=%s AND target_id=%s",(u["id"],tid)); following=False
                    else:
                        c.execute("INSERT INTO follows(follower_id,target_id,created_at) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING",(u["id"],tid,t)); following=True
                    c.commit(); self.send_json({"following":following}); return

                if p == "/api/friends":
                    rows=c.execute("""SELECT u.id,u.name,u.username,u.avatar,u.level FROM friends f JOIN users u ON u.id=f.friend_id
                                      WHERE f.user_id=%s AND f.status='accepted'""",(u["id"],)).fetchall()
                    self.send_json({"items":rowdicts(rows)}); return

                if p == "/api/friends/add":
                    tid=int(d.get("id",0))
                    if tid==u["id"]: raise ValueError("Нельзя добавить себя")
                    c.execute("INSERT INTO friends(user_id,friend_id,status,created_at) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING",(u["id"],tid,"accepted",t))
                    c.execute("INSERT INTO friends(user_id,friend_id,status,created_at) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING",(tid,u["id"],"accepted",t))
                    c.execute("INSERT INTO notifications(user_id,text,created_at) VALUES(%s,%s,%s)",(tid,f'👥 {u["name"]} добавил тебя в друзья',t))
                    c.commit(); self.send_json({"ok":True}); return

                if p == "/api/player":
                    pid=int(d.get("id",0))
                    row=c.execute("SELECT * FROM users WHERE id=%s",(pid,)).fetchone()
                    if not row: raise ValueError("Игрок не найден")
                    businesses=c.execute("SELECT COUNT(*) n FROM businesses WHERE owner_id=%s",(pid,)).fetchone()["n"]
                    friends=c.execute("SELECT COUNT(*) n FROM friends WHERE user_id=%s AND status='accepted'",(pid,)).fetchone()["n"]
                    self.send_json({"user":dict(row),"businesses":businesses,"friends":friends}); return

                if p == "/api/profile":
                    row=dict(c.execute("SELECT * FROM users WHERE id=%s",(u["id"],)).fetchone())
                    friends=c.execute("SELECT COUNT(*) n FROM friends WHERE user_id=%s AND status='accepted'",(u["id"],)).fetchone()["n"]
                    work_count=c.execute("SELECT COUNT(*) n FROM work WHERE user_id=%s",(u["id"],)).fetchone()["n"]
                    purchases=c.execute("SELECT COUNT(*) n FROM purchases WHERE buyer_id=%s",(u["id"],)).fetchone()["n"]
                    achievements=[
                        ("first_business","Первый бизнес","Создай свой первый бизнес",bool(c.execute("SELECT 1 FROM businesses WHERE owner_id=%s",(u["id"],)).fetchone())),
                        ("worker","Трудяга","Выполни 3 задания",work_count>=3),
                        ("trader","Торговец","Совершить первую покупку",purchases>=1),
                        ("rich","Капиталист","Накопить 5000 🪙",row["coins"]>=5000),
                        ("car","Автолюбитель","Купить машину",bool(c.execute("SELECT 1 FROM car_purchases WHERE buyer_id=%s",(u["id"],)).fetchone())),
                    ]
                    for code,title,txt,done in achievements:
                        if done:
                            c.execute("INSERT INTO achievements(user_id,code,created_at) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING",(u["id"],code,t))
                    c.commit()
                    self.send_json({"user":row,"friends":friends,"achievements":[{"title":a[1],"text":a[2],"done":a[3]} for a in achievements]})
                    return

                if p == "/api/profile/update":
                    name=clean_text(d.get("name"),50) or u["name"];bio=clean_text(d.get("bio"),180);avatar=clean_text(d.get("avatar"),5) or "🧑‍💻";cover=clean_text(d.get("cover"),5) or "🌌"
                    c.execute("UPDATE users SET name=%s,bio=%s,avatar=%s,cover=%s WHERE id=%s",(name,bio,avatar,cover,u["id"]))
                    c.commit();self.send_json({"ok":True});return

                if p == "/api/inventory":
                    rows=c.execute("SELECT item_name,icon,qty FROM inventory WHERE user_id=%s ORDER BY id DESC",(u["id"],)).fetchall()
                    self.send_json({"items":rowdicts(rows)});return

                if p == "/api/bank":
                    amt=max(1,int(d.get("amount",0)));typ=d.get("type")
                    if typ=="deposit":
                        if amt>u["coins"]: raise ValueError("Недостаточно монет")
                        if not c.execute("UPDATE users SET coins=coins-%s,bank=bank+%s WHERE id=%s AND coins>=%s RETURNING id",(amt,amt,u["id"],amt)).fetchone():
                            raise ValueError("Недостаточно монет")
                    else:
                        if amt>u["bank"]: raise ValueError("Недостаточно средств в банке")
                        if not c.execute("UPDATE users SET bank=bank-%s,coins=coins+%s WHERE id=%s AND bank>=%s RETURNING id",(amt,amt,u["id"],amt)).fetchone():
                            raise ValueError("Недостаточно средств в банке")
                    c.commit();self.send_json({"ok":True});return

                if p == "/api/bonus":
                    if t-u["last_bonus"]<20*3600: raise ValueError("Бонус уже забран. Возвращайся завтра!")
                    streak=u["streak"]+1; reward=min(750,100+streak*35)
                    c.execute("UPDATE users SET coins=coins+%s,streak=%s,last_bonus=%s WHERE id=%s",(reward,streak,t,u["id"]))
                    add_xp(c,u["id"],70)
                    add_feed(c,u["id"],"bonus",f'{u["name"]} забрал ежедневный бонус +{reward} 🪙')
                    c.commit();self.send_json({"message":f'+{reward} 🪙 и +70 XP'});return

                if p == "/api/season":
                    season=c.execute("SELECT * FROM seasons ORDER BY id DESC LIMIT 1").fetchone()
                    rows=c.execute("SELECT id,name,avatar,season_xp FROM users ORDER BY season_xp DESC LIMIT 10").fetchall()
                    rank=c.execute("SELECT COUNT(*)+1 n FROM users WHERE season_xp>(SELECT season_xp FROM users WHERE id=%s)",(u["id"],)).fetchone()["n"]
                    days=max(0,(season["ends_at"]-t)//86400)
                    self.send_json({"season":dict(season),"days":days,"my_rank":rank,"my_xp":u["season_xp"],"top":rowdicts(rows)});return

                if p == "/api/notifications":
                    rows=c.execute("SELECT * FROM notifications WHERE user_id=%s ORDER BY id DESC LIMIT 20",(u["id"],)).fetchall()
                    c.execute("UPDATE notifications SET seen=1 WHERE user_id=%s",(u["id"],));c.commit()
                    self.send_json({"items":rowdicts(rows)});return

                self.send_json({"error":"not found"},404)
        except Exception as e:
            if c is not None:
                try:
                    c.rollback()
                except Exception:
                    pass
            self.send_json({"error":str(e)},400)
        finally:
            if c is not None:
                try:
                    c.close()
                except Exception:
                    pass


def tg_loop():
    if not BOT_TOKEN:
        while True:
            time.sleep(3600)
    try:
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=true",
            timeout=10
        ).read()
    except Exception:
        pass

    offset=0
    while True:
        try:
            req=urllib.request.Request(
                f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?timeout=25&offset={offset}"
            )
            data=json.loads(urllib.request.urlopen(req,timeout=35).read().decode())
            for up in data.get("result",[]):
                offset=up["update_id"]+1
                m=up.get("message",{})
                chat=m.get("chat",{}).get("id")
                text=m.get("text","")
                if not chat: continue
                if text.startswith("/start"):
                    url=WEB_APP_URL or os.getenv("WEB_APP_URL","")
                    if url:
                        markup={"inline_keyboard":[[
                            {"text":"🚀 Открыть NeuroCity","web_app":{"url":url}}
                        ]]}
                        payload={
                            "chat_id":chat,
                            "text":"🌐 Добро пожаловать в NeuroCity Developer Edition!\n\n"
                                   "Работай → зарабатывай → создавай бизнес → покупай машины → "
                                   "торгуй → собирай друзей → поднимайся в рейтинге.",
                            "reply_markup":markup
                        }
                    else:
                        payload={"chat_id":chat,"text":"WEB_APP_URL ещё не настроен."}
                    r=urllib.request.Request(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                        data=json.dumps(payload,ensure_ascii=False).encode(),
                        headers={"Content-Type":"application/json"}
                    )
                    urllib.request.urlopen(r,timeout=10).read()
        except Exception as e:
            print("[TG]",e)
            time.sleep(2)


def main():
    init_pool()
    init_db()
    print("NEUROCITY DEVELOPER EDITION 6.0 LIFE UPDATE")
    print("WEB:", f"http://{HOST}:{PORT}")
    threading.Thread(
        target=lambda: ThreadingHTTPServer((HOST,PORT),Handler).serve_forever(),
        daemon=True
    ).start()
    tg_loop()


if __name__ == "__main__":
    main()
