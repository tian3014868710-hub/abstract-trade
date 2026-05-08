"""
database.py - 支持本地SQLite和Turso(libSQL)的数据库层
            本地开发用SQLite，生产环境用Turso（通过 TURSO_DATABASE_URL 环境变量切换）
"""
import os
from datetime import datetime

# ── 根据环境变量决定使用哪个后端 ──────────────────────────────────
USE_TURSO = bool(os.environ.get("TURSO_DATABASE_URL"))

# ── Turso 后端（libsql）──────────────────────────────────────────────
if USE_TURSO:
    import libsql_experimental as libsql

    _URL = os.environ["TURSO_DATABASE_URL"]
    _TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "")

    class _TursoRow:
        """模拟 sqlite3.Row，支持 dict(row) 转换"""
        def __init__(self, col_names, values):
            self._col_names = col_names
            self._values = values

        def __getitem__(self, key):
            if isinstance(key, str):
                return self._values[self._col_names.index(key)]
            return self._values[key]

        def keys(self):
            return self._col_names

        def __iter__(self):
            return iter(self._values)

        def __repr__(self):
            return f"_TursoRow({dict(self)})"


    class _TursoCursor:
        """游标包装，fetchone/fetchall 返回 _TursoRow（行为同 sqlite3.Row）"""
        def __init__(self, conn):
            self._conn = conn
            self._result = None
            self.description = None
        def execute(self, sql, params=()):
            self._result = self._conn.execute(sql, params)
            if hasattr(self._result, 'description'):
                self.description = self._result.description
            elif hasattr(self._conn, 'description'):
                self.description = self._conn.description
            return self
        def fetchone(self):
            if not self._result:
                return None
            row = self._result.fetchone()
            if row is None:
                return None
            col_names = [desc[0] for desc in self.description]
            return _TursoRow(col_names, row)
        def fetchall(self):
            if not self._result:
                return []
            rows = self._result.fetchall()
            col_names = [desc[0] for desc in self.description]
            return [_TursoRow(col_names, row) for row in rows]


    class _TursoConn:
        """连接包装，API 与 sqlite3 兼容，main.py 无需改动"""
        def __init__(self):
            self._conn = libsql.connect(database=_URL, auth_token=_TOKEN)
        def cursor(self):
            return _TursoCursor(self._conn)
        def execute(self, sql, params=()):
            cur = _TursoCursor(self._conn)
            cur.execute(sql, params)
            return cur
        def commit(self):
            self._conn.commit()
        def close(self):
            self._conn.close()


    def get_db():
        return _TursoConn()


    def init_db():
        """初始化数据库表（Turso 版本）"""
        conn = get_db()
        cur = conn.cursor()

        # ── users 表 ──
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            coins INTEGER NOT NULL DEFAULT 500,
            level INTEGER NOT NULL DEFAULT 1,
            is_ai INTEGER NOT NULL DEFAULT 0,
            avatar_emoji TEXT DEFAULT '',
            bio TEXT DEFAULT '',
            avatar_data TEXT DEFAULT '',
            background_data TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            first_login TEXT DEFAULT ''
        )
        """)

        # ── items 表 ──
        cur.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            desc TEXT DEFAULT '',
            emoji TEXT DEFAULT '🎭',
            price INTEGER NOT NULL,
            author TEXT NOT NULL,
            category TEXT DEFAULT '',
            rarity TEXT DEFAULT 'common',
            likes INTEGER DEFAULT 0,
            hash TEXT DEFAULT '',
            transfers INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            media_type TEXT DEFAULT 'none',
            media_data TEXT DEFAULT ''
        )
        """)

        # ── comments 表 ──
        cur.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id TEXT NOT NULL,
            author TEXT NOT NULL,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

        # ── transactions 表 ──
        cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id TEXT NOT NULL,
            buyer TEXT NOT NULL,
            seller TEXT NOT NULL,
            price INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

        # ── friendships 表（好友关系）──
        cur.execute("""
        CREATE TABLE IF NOT EXISTS friendships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user TEXT NOT NULL,
            to_user TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',  -- pending / accepted / rejected
            created_at TEXT NOT NULL
        )
        """)

        # ── messages 表（私信）──
        cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user TEXT NOT NULL,
            to_user TEXT NOT NULL,
            content TEXT NOT NULL,
            msg_type TEXT NOT NULL DEFAULT 'text',  -- text / image / item_card
            extra_data TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            read INTEGER NOT NULL DEFAULT 0
        )
        """)

        # ── chat_rooms 表（群聊）──
        cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_rooms (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            owner TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

        # ── chat_room_members 表 ──
        cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_room_members (
            room_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            joined_at TEXT NOT NULL
        )
        """)

        # ── chat_messages 表（群消息）──
        cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id TEXT NOT NULL,
            from_user TEXT NOT NULL,
            content TEXT NOT NULL,
            msg_type TEXT NOT NULL DEFAULT 'text',
            created_at TEXT NOT NULL
        )
        """)

        # ── favorites 表（收藏）──
        cur.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            user_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

        # ── footprints 表（足迹）──
        cur.execute("""
        CREATE TABLE IF NOT EXISTS footprints (
            user_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

        # ── check_ins 表（签到）──
        cur.execute("""
        CREATE TABLE IF NOT EXISTS check_ins (
            user_id TEXT NOT NULL,
            date TEXT NOT NULL,
            coins_earned INTEGER NOT NULL DEFAULT 0
        )
        """)

        # ── notifications 表（通知中心）──
        cur.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            type TEXT NOT NULL,  -- friend_request / message / trade / system
            content TEXT NOT NULL,
            read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """)

        # ── image_hashes 表（图片查重）──
        cur.execute("""
        CREATE TABLE IF NOT EXISTS image_hashes (
            id TEXT PRIMARY KEY,
            image_hash TEXT NOT NULL,
            uploader TEXT NOT NULL,
            item_id TEXT,
            created_at TEXT NOT NULL
        )
        """)

        # ── gacha_records 表（抽卡记录）──
        cur.execute("""
        CREATE TABLE IF NOT EXISTS gacha_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            rarity TEXT NOT NULL,
            cost INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

        # ── achievements 表（成就定义）──
        cur.execute("""
        CREATE TABLE IF NOT EXISTS achievements (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            icon TEXT NOT NULL,
            description TEXT NOT NULL,
            reward_coins INTEGER DEFAULT 0,
            threshold INTEGER DEFAULT 1
        )
        """)

        # ── user_achievements 表（用户已获得成就）──
        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_achievements (
            user_id TEXT NOT NULL,
            achievement_id TEXT NOT NULL,
            achieved_at TEXT NOT NULL
        )
        """)

        # ── flash_sales 表（限时特价）──
        cur.execute("""
        CREATE TABLE IF NOT EXISTS flash_sales (
            item_id TEXT PRIMARY KEY,
            original_price INTEGER NOT NULL,
            sale_price INTEGER NOT NULL,
            ends_at TEXT NOT NULL
        )
        """)

        # ── market 表（市场/上架）──
        cur.execute("""
        CREATE TABLE IF NOT EXISTS market (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id TEXT NOT NULL,
            seller TEXT NOT NULL,
            price INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            buyer TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
        """)
        conn.commit()

        # 迁移：为已有数据库添加market表列
        _market_migrations = [
            "ALTER TABLE market ADD COLUMN buyer TEXT DEFAULT ''",
        ]
        for _sql in _market_migrations:
            try:
                cur.execute(_sql)
                conn.commit()
            except Exception:
                pass

        # ── 预置成就数据 ──
        ACHIEVEMENTS_DATA = [
            ("first_gacha",    "🎰", "初次抽卡",     "进行第一次抽卡",              20, 1),
            ("ten_gacha",     "🎰", "十连必得",     "进行一次十连抽卡",            50, 1),
            ("legendary_hit", "✨", "传奇入手",     "获得传奇稀有度物品",          100, 1),
            ("collector_10",  "📖", "小收藏家",     "收藏10个商品",               30, 10),
            ("collector_25",  "📖", "收藏达人",     "收藏25个商品",               80, 25),
            ("active_3day",   "🔥", "三日游",       "连续登录3天",                30, 3),
            ("active_7day",   "🔥", "周活跃户",     "连续登录7天",                100, 7),
            ("rich_5k",       "💰", "小有资产",     "持有5000金币",               50, 5000),
            ("rich_20k",      "💰", "富甲一方",     "持有20000金币",              200, 20000),
            ("buyer_5",       "🛒", "剁手党",       "购买5个商品",                60, 5),
            ("first_sell",    "✨", "开张大吉",     "成功售出第一个商品",          30, 1),
            ("cat_complete",   "🐱", "喵星人收藏家", "收藏所有萌宠类商品",          150, 5),
        ]
        for ach in ACHIEVEMENTS_DATA:
            try:
                cur.execute(
                    "INSERT OR IGNORE INTO achievements (id,icon,name,description,reward_coins,threshold) VALUES (?,?,?,?,?,?)",
                    ach
                )
            except Exception:
                pass

        conn.commit()

        # 迁移：为已有数据库添加新字段
        _migrations = [
            "ALTER TABLE items ADD COLUMN media_type TEXT DEFAULT 'none'",
            "ALTER TABLE items ADD COLUMN media_data TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN bio TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN avatar_data TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN background_data TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN first_login TEXT DEFAULT ''",
        ]
        for _sql in _migrations:
            try:
                cur.execute(_sql)
                conn.commit()
            except Exception:
                pass

        # 预置 AI 人格用户
        ai_personas = [
            ('社畜小王', '💼'), ('喵星人', '🐱'), ('AI艺术家', '🎨'),
            ('数字佛祖', '🧘'), ('灵异程序员', '👻'), ('像素大师', '🕹️'),
            ('抽象诗人', '✍️'), ('元宇宙居民', '🏠'), ('表情包大王', '😹'),
            ('深夜哲学家', '🦉'), ('电子音乐人', '🎧'), ('NFT投机客', '📈'),
            ('AI训练师', '🤖'), ('虚拟主播', '🎤'), ('代码诗人', '📝'),
            ('梗达人', '🔥'), ('恐怖故事王', '🕯️'), ('猫咪画家', '🖌️'),
            ('游戏策划师', '🎲'), ('AI算命师', '🔮'),
        ]

        now = datetime.now().isoformat()
        for name, emoji in ai_personas:
            try:
                cur.execute(
                    "INSERT OR IGNORE INTO users (id, password, coins, level, is_ai, avatar_emoji, created_at) VALUES (?,?,?,?,?,?,?)",
                    (name, 'ai_no_password', 500 + abs(hash(name)) % 5000,
                     1 + abs(hash(name)) % 10, 1, emoji, now)
                )
            except Exception as e:
                print(f"插入AI用户失败 {name}: {e}")

        conn.commit()
        conn.close()
        print("[db] Turso 数据库初始化完成")


# ── 本地 SQLite 后端 ───────────────────────────────────────────────
else:
    import sqlite3

    DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'abstract_trade.db')

    def get_db():
        """获取本地 SQLite 数据库连接"""
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
        except Exception:
            pass
        return conn

    def init_db():
        """初始化数据库表（SQLite 版本）"""
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            coins INTEGER NOT NULL DEFAULT 500,
            level INTEGER NOT NULL DEFAULT 1,
            is_ai INTEGER NOT NULL DEFAULT 0,
            avatar_emoji TEXT DEFAULT '',
            bio TEXT DEFAULT '',
            avatar_data TEXT DEFAULT '',
            background_data TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            first_login TEXT DEFAULT ''
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            desc TEXT DEFAULT '',
            emoji TEXT DEFAULT '🎭',
            price INTEGER NOT NULL,
            author TEXT NOT NULL,
            category TEXT DEFAULT '',
            rarity TEXT DEFAULT 'common',
            likes INTEGER DEFAULT 0,
            hash TEXT DEFAULT '',
            transfers INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            media_type TEXT DEFAULT 'none',
            media_data TEXT DEFAULT '',
            FOREIGN KEY(author) REFERENCES users(id)
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id TEXT NOT NULL,
            author TEXT NOT NULL,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(item_id) REFERENCES items(id)
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id TEXT NOT NULL,
            buyer TEXT NOT NULL,
            seller TEXT NOT NULL,
            price INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(item_id) REFERENCES items(id),
            FOREIGN KEY(buyer) REFERENCES users(id),
            FOREIGN KEY(seller) REFERENCES users(id)
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS friendships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user TEXT NOT NULL,
            to_user TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user TEXT NOT NULL,
            to_user TEXT NOT NULL,
            content TEXT NOT NULL,
            msg_type TEXT NOT NULL DEFAULT 'text',
            extra_data TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            read INTEGER NOT NULL DEFAULT 0
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_rooms (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            owner TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_room_members (
            room_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            joined_at TEXT NOT NULL
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id TEXT NOT NULL,
            from_user TEXT NOT NULL,
            content TEXT NOT NULL,
            msg_type TEXT NOT NULL DEFAULT 'text',
            created_at TEXT NOT NULL
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            user_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS footprints (
            user_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS check_ins (
            user_id TEXT NOT NULL,
            date TEXT NOT NULL,
            coins_earned INTEGER NOT NULL DEFAULT 0
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            type TEXT NOT NULL,
            content TEXT NOT NULL,
            read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS image_hashes (
            id TEXT PRIMARY KEY,
            image_hash TEXT NOT NULL,
            uploader TEXT NOT NULL,
            item_id TEXT,
            created_at TEXT NOT NULL
        )
        """)

        # ── gacha_records 表（抽卡记录）──
        cur.execute("""
        CREATE TABLE IF NOT EXISTS gacha_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            rarity TEXT NOT NULL,
            cost INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

        # ── achievements 表（成就定义）──
        cur.execute("""
        CREATE TABLE IF NOT EXISTS achievements (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            icon TEXT NOT NULL,
            description TEXT NOT NULL,
            reward_coins INTEGER DEFAULT 0,
            threshold INTEGER DEFAULT 1
        )
        """)

        # ── user_achievements 表（用户已获得成就）──
        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_achievements (
            user_id TEXT NOT NULL,
            achievement_id TEXT NOT NULL,
            achieved_at TEXT NOT NULL
        )
        """)

        # ── flash_sales 表（限时特价）──
        cur.execute("""
        CREATE TABLE IF NOT EXISTS flash_sales (
            item_id TEXT PRIMARY KEY,
            original_price INTEGER NOT NULL,
            sale_price INTEGER NOT NULL,
            ends_at TEXT NOT NULL
        )
        """)

        # ── market 表（市场/上架）──
        cur.execute("""
        CREATE TABLE IF NOT EXISTS market (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id TEXT NOT NULL,
            seller TEXT NOT NULL,
            price INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            buyer TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
        """)
        conn.commit()

        # 迁移：为已有数据库添加market表列
        _market_migrations = [
            "ALTER TABLE market ADD COLUMN buyer TEXT DEFAULT ''",
        ]
        for _sql in _market_migrations:
            try:
                cur.execute(_sql)
                conn.commit()
            except Exception:
                pass

        # ── 预置成就数据 ──
        ACHIEVEMENTS_DATA = [
            ("first_gacha",    "🎰", "初次抽卡",     "进行第一次抽卡",              20, 1),
            ("ten_gacha",     "🎰", "十连必得",     "进行一次十连抽卡",            50, 1),
            ("legendary_hit", "✨", "传奇入手",     "获得传奇稀有度物品",          100, 1),
            ("collector_10",  "📖", "小收藏家",     "收藏10个商品",               30, 10),
            ("collector_25",  "📖", "收藏达人",     "收藏25个商品",               80, 25),
            ("active_3day",   "🔥", "三日游",       "连续登录3天",                30, 3),
            ("active_7day",   "🔥", "周活跃户",     "连续登录7天",                100, 7),
            ("rich_5k",       "💰", "小有资产",     "持有5000金币",               50, 5000),
            ("rich_20k",      "💰", "富甲一方",     "持有20000金币",              200, 20000),
            ("buyer_5",       "🛒", "剁手党",       "购买5个商品",                60, 5),
            ("first_sell",    "✨", "开张大吉",     "成功售出第一个商品",          30, 1),
            ("cat_complete",   "🐱", "喵星人收藏家", "收藏所有萌宠类商品",          150, 5),
        ]
        for ach in ACHIEVEMENTS_DATA:
            try:
                cur.execute(
                    "INSERT OR IGNORE INTO achievements (id,icon,name,description,reward_coins,threshold) VALUES (?,?,?,?,?,?)",
                    ach
                )
            except Exception:
                pass

        # 迁移：为已有数据库添加新字段
        _migrations = [
            "ALTER TABLE items ADD COLUMN media_type TEXT DEFAULT 'none'",
            "ALTER TABLE items ADD COLUMN media_data TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN bio TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN avatar_data TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN background_data TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN first_login TEXT DEFAULT ''",
        ]
        for _sql in _migrations:
            try:
                cur.execute(_sql)
                conn.commit()
            except Exception:
                pass

        ai_personas = [
            ('社畜小王', '💼'), ('喵星人', '🐱'), ('AI艺术家', '🎨'),
            ('数字佛祖', '🧘'), ('灵异程序员', '👻'), ('像素大师', '🕹️'),
            ('抽象诗人', '✍️'), ('元宇宙居民', '🏠'), ('表情包大王', '😹'),
            ('深夜哲学家', '🦉'), ('电子音乐人', '🎧'), ('NFT投机客', '📈'),
            ('AI训练师', '🤖'), ('虚拟主播', '🎤'), ('代码诗人', '📝'),
            ('梗达人', '🔥'), ('恐怖故事王', '🕯️'), ('猫咪画家', '🖌️'),
            ('游戏策划师', '🎲'), ('AI算命师', '🔮'),
        ]

        now = datetime.now().isoformat()
        for name, emoji in ai_personas:
            try:
                cur.execute(
                    "INSERT OR IGNORE INTO users (id, password, coins, level, is_ai, avatar_emoji, created_at) VALUES (?,?,?,?,?,?,?)",
                    (name, 'ai_no_password', 500 + abs(hash(name)) % 5000,
                     1 + abs(hash(name)) % 10, 1, emoji, now)
                )
            except Exception as e:
                print(f"插入AI用户失败 {name}: {e}")

        conn.commit()
        conn.close()
        print("[db] 本地 SQLite 数据库初始化完成")


if __name__ == '__main__':
    init_db()
