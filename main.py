"""
main.py - 抽象交易 完整版
核心功能：注册/登录 | 商品交易 | 抽卡 | 市场
"""
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3, hashlib, json, binascii, os, secrets, random, time, hashlib
from datetime import datetime, timedelta
from contextvars import ContextVar
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import get_db, init_db

init_db()

app = FastAPI(title="抽象交易")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 密码工具 ────────────────────────
def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac('sha256', pw.encode(), salt, 100000)
    return salt.hex() + ':' + key.hex()

def verify_password(pw: str, stored: str) -> bool:
    try:
        salt_hex, key_hex = stored.split(':', 1)
        salt = bytes.fromhex(salt_hex)
        key = hashlib.pbkdf2_hmac('sha256', pw.encode(), salt, 100000)
        return key.hex() == key_hex
    except Exception:
        return False

# ── 响应工具 ────────────────────────
def ok(data=None, msg="ok"):
    return JSONResponse({"code": 0, "msg": msg, "data": data})

def fail(msg="操作失败", code=1):
    return JSONResponse({"code": code, "msg": msg, "data": None}, status_code=400)

# ── 请求上下文 ────────────────────────
_request_local = ContextVar("_request_local", default=None)

@app.middleware("http")
async def capture_request(request, call_next):
    _request_local.set(request)
    return await call_next(request)

def get_current_user() -> str:
    req = _request_local.get()
    if req is None:
        return ""
    return req.cookies.get("uid", "")

# ── 抽卡商品池 ────────────────────────
GACHA_ITEMS = [
    # Common (60%)
    ("摸鱼许可证", "有了这个，摸鱼再也不心虚", "🐟", 10, "common"),
    ("班味除臭剂", "轻轻一喷，班味全消", "🧴", 15, "common"),
    ("周报生成器(破解版)", "一键生成1000字废话", "📝", 20, "common"),
    ("甲方快乐水", "喝完甲方说什么都对", "🥤", 12, "common"),
    ("代码ler's笔记", "我也不知道写了什么", "💻", 18, "common"),
    ("会议室躲藏术", "学会这个再也不怕开会", "🪑", 14, "common"),
    ("Ctrl+C/V 大师证", "终极复制粘贴技能认证", "⌨️", 16, "common"),
    ("精神离职徽章", "人在工位心已远", "🚪", 11, "common"),
    ("无效加班光荣证", "加班到凌晨，效率为零", "🌙", 13, "common"),
    ("工位盆栽(假的)", "给工位一点绿色谎言", "🪴", 17, "common"),
    # Rare (25%)
    ("AI觉醒碎片", "据说集齐7个AI会觉醒", "✨", 88, "rare"),
    ("赛博佛祖光环", "戴上这个，BUG自动修复", "🪷", 66, "rare"),
    ("元宇宙房产证", "位于元宇宙CBD黄金地段", "🏠", 99, "rare"),
    ("数字永生体验卡", "体验死后在云端永生", "👻", 77, "rare"),
    ("算法推荐免疫", "从此推荐算法失效", "🛡️", 55, "rare"),
    ("脑机接口延期券", "把你的脑机接口升级推迟", "🧠", 68, "rare"),
    ("老板的已读不回", "终于体验到了！", "📱", 72, "rare"),
    ("数字排毒疗程", "手机变板砖4小时", "📵", 60, "rare"),
    # Epic (12%)
    ("GPT的午休时间", "AI停止回复你3小时", "⏰", 188, "epic"),
    ("内卷加速器 Pro", "让你的努力3倍速被看到", "⚡", 166, "epic"),
    ("命运的齿轮(生锈版)", "命运想转你？先除个锈", "⚙️", 199, "epic"),
    ("回旋镖嘴替体验券", "吵架必胜神器", "🎯", 155, "epic"),
    ("社交牛杂症胶囊", "社恐社牛自由切换", "💊", 178, "epic"),
    # Legendary (3%)
    ("AI的灵魂碎片", "集齐7个召唤GPT-5", "🌟", 666, "legendary"),
    ("小丑牌(限量版)", "Oblivion联动款", "🃏", 520, "legendary"),
    ("数字永生永久卡", "真正的永生不死", "👑", 888, "legendary"),
]

def init_gacha_items():
    """初始化抽卡商品池"""
    conn = get_db()
    cur = conn.cursor()
    now = datetime.now().isoformat()
    
    try:
        cur.execute("""
            INSERT OR IGNORE INTO users (id, password, coins, level, is_ai, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ("系统", "system", 0, 1, 1, now))
    except Exception:
        pass
    
    for name, desc, emoji, price, rarity in GACHA_ITEMS:
        item_id = hashlib.md5(name.encode()).hexdigest()[:10]
        try:
            cur.execute("""
                INSERT OR IGNORE INTO items 
                (id, name, `desc`, emoji, price, author, rarity, created_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (item_id, name, desc, emoji, price, "系统", rarity, now, "active"))
        except Exception as e:
            print(f"插入失败: {name} - {e}")
    conn.commit()
    conn.close()

init_gacha_items()

# ── 注册 ────────────────────────
@app.post("/api/register")
async def api_register(request: Request):
    try:
        body = await request.json()
    except Exception:
        return fail("参数错误")
    username = (body or {}).get("username", "").strip()
    password = (body or {}).get("password", "")
    if not username or len(username) < 2:
        return fail("用户名至少2个字符")
    if not password or len(password) < 4:
        return fail("密码至少4个字符")
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE id = ?", (username,))
    if cur.fetchone():
        conn.close()
        return fail("用户名已存在")
    
    now = datetime.now().isoformat()
    pw_hash = hash_password(password)
    try:
        cur.execute("""
            INSERT INTO users (id, password, coins, level, is_ai, avatar_emoji, created_at)
            VALUES (?,?,?,?,?,?,?)
        """, (username, pw_hash, 1000, 1, 0, "👤", now))
        conn.commit()
    except Exception as e:
        conn.close()
        return fail(f"注册失败：{e}")
    conn.close()
    return ok({"username": username, "coins": 1000}, "注册成功！送你1000金币启动")

# ── 登录 ────────────────────────
@app.post("/api/login")
async def api_login(request: Request):
    try:
        body = await request.json()
    except Exception:
        return fail("参数错误")
    username = (body or {}).get("username", "").strip()
    password = (body or {}).get("password", "")
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, password, coins, level FROM users WHERE id=?", (username,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        return fail("用户名不存在")
    if not verify_password(password, row['password']):
        return fail("密码错误")
    
    return ok({"username": username, "coins": row['coins'], "level": row['level']}, "登录成功")

# ── 用户信息 ────────────────────────
@app.get("/api/user/{username}")
def api_user(username: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, coins, level, avatar_emoji, bio, created_at FROM users WHERE id=?", (username,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return fail("用户不存在")
    
    user = dict(row)
    
    # 统计
    cur.execute("SELECT COUNT(*) FROM favorites WHERE user_id=?", (username,))
    r = cur.execute("SELECT COUNT(*) FROM favorites WHERE user_id=?", (username,)).fetchone()
    user['fav_count'] = r[0] if r else 0
    
    cur.execute("SELECT COUNT(*) FROM gacha_records WHERE user_id=?", (username,))
    r = cur.execute("SELECT COUNT(*) FROM gacha_records WHERE user_id=?", (username,)).fetchone()
    user['gacha_count'] = r[0] if r else 0
    
    conn.close()
    return ok(user)

# ── 首页商品列表 ────────────────────────
@app.get("/api/items")
def api_items(page: int = 1, limit: int = 20):
    conn = get_db()
    cur = conn.cursor()
    offset = (page - 1) * limit
    
    cur.execute("""
        SELECT i.*, u.avatar_emoji as author_emoji
        FROM items i
        JOIN users u ON i.author = u.id
        WHERE i.status = 'active'
        ORDER BY i.created_at DESC
        LIMIT ? OFFSET ?
    """, (limit, offset))
    items = [dict(r) for r in cur.fetchall()]
    
    conn.close()
    return ok({"items": items})

# ── 商品详情 ────────────────────────
@app.get("/api/item/{item_id}")
def api_item(item_id: str):
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT i.*, u.avatar_emoji as author_emoji
        FROM items i
        JOIN users u ON i.author = u.id
        WHERE i.id=?
    """, (item_id,))
    item = cur.fetchone()
    
    if not item:
        conn.close()
        return fail("商品不存在")
    
    # 评论
    cur.execute("""
        SELECT c.*, u.avatar_emoji
        FROM comments c
        JOIN users u ON c.author = u.id
        WHERE c.item_id=?
        ORDER BY c.created_at DESC
        LIMIT 20
    """, (item_id,))
    comments = [dict(r) for r in cur.fetchall()]
    
    conn.close()
    return ok({"item": dict(item), "comments": comments})

# ── 上架商品 ────────────────────────
@app.post("/api/items")
async def api_create_item(request: Request):
    uid = get_current_user()
    if not uid:
        return fail("请先登录")
    
    try:
        body = await request.json()
    except Exception:
        return fail("参数错误")
    
    name = (body or {}).get("name", "").strip()
    desc = (body or {}).get("desc", "").strip()
    price = int((body or {}).get("price", 0))
    emoji = (body or {}).get("emoji", "🎭")
    media_type = (body or {}).get("media_type", "none")
    media_data = (body or {}).get("media_data", "")
    
    if not name or len(name) < 1:
        return fail("商品名不能为空")
    if price < 1:
        return fail("价格不能低于1金币")
    
    item_id = secrets.token_hex(8)
    now = datetime.now().isoformat()
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            INSERT INTO items (id, name, `desc`, price, author, emoji, rarity, created_at, media_type, media_data, status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (item_id, name, desc, price, uid, emoji, "common", now, media_type, media_data, "active"))
        conn.commit()
    except Exception as e:
        conn.close()
        return fail(f"上架失败：{e}")
    
    conn.close()
    return ok({"id": item_id, "name": name}, "上架成功！")

# ── 购买商品 ────────────────────────
@app.post("/api/items/{item_id}/buy")
def api_buy_item(item_id: str):
    uid = get_current_user()
    if not uid:
        return fail("请先登录")
    
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("SELECT * FROM items WHERE id=? AND status='active'", (item_id,))
    item = cur.fetchone()
    
    if not item:
        conn.close()
        return fail("商品不存在或已下架")
    
    if item['author'] == uid:
        conn.close()
        return fail("不能购买自己的商品")
    
    price = item['price']
    
    cur.execute("SELECT coins FROM users WHERE id=?", (uid,))
    r = cur.execute("SELECT coins FROM users WHERE id=?", (uid,)).fetchone()
    buyer_coins = r[0] if r else 0
    
    if buyer_coins < price:
        conn.close()
        return fail(f"金币不足！需要{price}币，你只有{buyer_coins}币")
    
    # 扣买家金币
    cur.execute("UPDATE users SET coins=coins-? WHERE id=?", (price, uid))
    # 加卖家金币
    cur.execute("UPDATE users SET coins=coins+? WHERE id=?", (price, item['author']))
    # 转移所有权
    cur.execute("UPDATE items SET author=?, transfers=transfers+1 WHERE id=?", (uid, item_id))
    # 记录交易
    now = datetime.now().isoformat()
    cur.execute("""
        INSERT INTO transactions (item_id, buyer, seller, price, created_at)
        VALUES (?,?,?,?,?)
    """, (item_id, uid, item['author'], price, now))
    
    conn.commit()
    
    cur.execute("SELECT coins FROM users WHERE id=?", (uid,))
    r = cur.execute("SELECT coins FROM users WHERE id=?", (uid,)).fetchone()
    coins_now = r[0] if r else 0
    
    conn.close()
    return ok({"coins": coins_now, "item_name": item['name']}, f"购买成功！{item['name']}现在是你的了！")

# ── 收藏商品 ────────────────────────
@app.post("/api/favorites")
async def api_add_favorite(request: Request):
    uid = get_current_user()
    if not uid:
        return fail("请先登录")
    
    try:
        body = await request.json()
    except Exception:
        return fail("参数错误")
    
    item_id = (body or {}).get("item_id", "")
    
    conn = get_db()
    cur = conn.cursor()
    now = datetime.now().isoformat()
    
    try:
        cur.execute("""
            INSERT OR IGNORE INTO favorites (user_id, item_id, created_at)
            VALUES (?,?,?)
        """, (uid, item_id, now))
        conn.commit()
    except Exception as e:
        conn.close()
        return fail(f"收藏失败：{e}")
    
    conn.close()
    return ok({}, "收藏成功！")

@app.delete("/api/favorites/{item_id}")
def api_remove_favorite(item_id: str):
    uid = get_current_user()
    if not uid:
        return fail("请先登录")
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM favorites WHERE user_id=? AND item_id=?", (uid, item_id))
    conn.commit()
    conn.close()
    return ok({}, "已取消收藏")

@app.get("/api/favorites")
def api_my_favorites():
    uid = get_current_user()
    if not uid:
        return fail("请先登录")
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT i.*, u.avatar_emoji as author_emoji
        FROM favorites f
        JOIN items i ON f.item_id = i.id
        JOIN users u ON i.author = u.id
        WHERE f.user_id=?
        ORDER BY f.created_at DESC
    """, (uid,))
    items = [dict(r) for r in cur.fetchall()]
    conn.close()
    return ok({"items": items})

# ── 评论 ────────────────────────
@app.post("/api/comments")
async def api_add_comment(request: Request):
    uid = get_current_user()
    if not uid:
        return fail("请先登录")
    
    try:
        body = await request.json()
    except Exception:
        return fail("参数错误")
    
    item_id = (body or {}).get("item_id", "")
    text = (body or {}).get("text", "").strip()
    
    if not text:
        return fail("评论内容不能为空")
    
    conn = get_db()
    cur = conn.cursor()
    now = datetime.now().isoformat()
    
    try:
        cur.execute("""
            INSERT INTO comments (item_id, author, text, created_at)
            VALUES (?,?,?,?)
        """, (item_id, uid, text, now))
        conn.commit()
    except Exception as e:
        conn.close()
        return fail(f"评论失败：{e}")
    
    conn.close()
    return ok({}, "评论成功！")

# ── 抽卡（单抽）───────────────────────
@app.post("/api/gacha")
def api_gacha():
    uid = get_current_user()
    if not uid:
        return fail("请先登录")
    
    cost = 50
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT coins FROM users WHERE id=?", (uid,))
    r = cur.execute("SELECT coins FROM users WHERE id=?", (uid,)).fetchone()
    if not r:
        conn.close()
        return fail("用户不存在")
    if r['coins'] < cost:
        conn.close()
        return fail(f"金币不足！需要{cost}币，你只有{r['coins']}币")
    
    # 扣金币
    cur.execute("UPDATE users SET coins=coins-? WHERE id=?", (cost, uid))
    
    # 抽卡概率: common 60%, rare 25%, epic 12%, legendary 3%
    roll = random.randint(1, 100)
    if roll <= 3:
        rarity = 'legendary'
    elif roll <= 15:
        rarity = 'epic'
    elif roll <= 40:
        rarity = 'rare'
    else:
        rarity = 'common'
    
    # 从商品池选一个
    pool = [item for item in GACHA_ITEMS if item[4] == rarity]
    if not pool:
        pool = [item for item in GACHA_ITEMS]
    
    item = random.choice(pool)
    item_id = hashlib.md5(item[0].encode()).hexdigest()[:10]
    
    now = datetime.now().isoformat()
    
    # 记录到收藏
    try:
        cur.execute("""
            INSERT OR IGNORE INTO favorites (user_id, item_id, created_at)
            VALUES (?, ?, ?)
        """, (uid, item_id, now))
    except Exception:
        pass
    
    # 记录抽卡
    try:
        cur.execute("""
            INSERT INTO gacha_records (user_id, item_id, rarity, cost, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (uid, item_id, rarity, cost, now))
    except Exception:
        pass
    
    conn.commit()
    
    cur.execute("SELECT coins FROM users WHERE id=?", (uid,))
    r = cur.execute("SELECT coins FROM users WHERE id=?", (uid,)).fetchone()
    coins_now = r[0] if r else 0
    
    conn.close()
    
    return ok({
        "item": {
            "id": item_id,
            "name": item[0],
            "desc": item[1],
            "emoji": item[2],
            "rarity": rarity
        },
        "coins": coins_now,
        "cost": cost
    })

# ── 每日奖励 ────────────────────────
@app.post("/api/daily-reward")
def api_daily_reward():
    uid = get_current_user()
    if not uid:
        return fail("请先登录")
    
    conn = get_db()
    cur = conn.cursor()
    today = datetime.now().date().isoformat()
    
    cur.execute("SELECT coins_earned FROM check_ins WHERE user_id=? AND date=?", (uid, today))
    r = cur.execute("SELECT coins_earned FROM check_ins WHERE user_id=? AND date=?", (uid, today)).fetchone()
    if r:
        conn.close()
        return fail("今日奖励已领取，明天再来吧！")
    
    yesterday = (datetime.now() - timedelta(days=1)).date().isoformat()
    cur.execute("SELECT coins_earned FROM check_ins WHERE user_id=? AND date=?", (uid, yesterday))
    r2 = cur.execute("SELECT coins_earned FROM check_ins WHERE user_id=? AND date=?", (uid, yesterday)).fetchone()
    streak = r2[0] if r2 else 0
    
    base = 50
    streak_bonus = min(streak * 5, 100)
    total = base + streak_bonus
    
    cur.execute("UPDATE users SET coins=coins+? WHERE id=?", (total, uid))
    cur.execute("INSERT INTO check_ins (user_id, date, coins_earned) VALUES (?,?,?)", (uid, today, streak + 1))
    conn.commit()
    
    cur.execute("SELECT coins FROM users WHERE id=?", (uid,))
    r = cur.execute("SELECT coins FROM users WHERE id=?", (uid,)).fetchone()
    coins_now = r[0] if r else 0
    
    conn.close()
    return ok({
        "coins_earned": total,
        "coins": coins_now,
        "streak": streak + 1,
        "streak_bonus": streak_bonus
    }, f"获得{total}金币！（连续签到{streak + 1}天）")

# ── 我的收藏（抽卡道具）───────────────────────
@app.get("/api/collections/{username}")
def api_collections(username: str):
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT i.id, i.name, i.`desc`, i.emoji, i.rarity, i.price,
               f.created_at as collected_at,
               (SELECT COUNT(*) FROM market WHERE item_id = i.id AND seller = ?) as on_sale
        FROM favorites f
        JOIN items i ON f.item_id = i.id
        WHERE f.user_id=?
        ORDER BY f.created_at DESC
    """, (username, username))
    
    items = [dict(r) for r in cur.fetchall()]
    
    stats = {"total": len(items), "common": 0, "rare": 0, "epic": 0, "legendary": 0}
    for item in items:
        stats[item['rarity']] = stats.get(item['rarity'], 0) + 1
    
    conn.close()
    return ok({"items": items, "stats": stats})

# ── 市场 ────────────────────────
@app.post("/api/market/sell")
async def api_sell(request: Request):
    uid = get_current_user()
    if not uid:
        return fail("请先登录")
    
    try:
        body = await request.json()
    except Exception:
        return fail("参数错误")
    
    item_id = (body or {}).get("item_id", "")
    price = int((body or {}).get("price", 0))
    
    if not item_id:
        return fail("请选择要上架的商品")
    if price < 1 or price > 999999:
        return fail("价格范围：1-999999金币")
    
    conn = get_db()
    cur = conn.cursor()
    
    # 检查用户是否拥有这个商品
    cur.execute("""
        SELECT i.id, i.name, i.emoji, i.rarity
        FROM favorites f
        JOIN items i ON f.item_id = i.id
        WHERE f.user_id=? AND i.id=?
    """, (uid, item_id))
    item = cur.fetchone()
    
    if not item:
        conn.close()
        return fail("你没有这个商品")
    
    # 检查是否已经在售
    cur.execute("SELECT id FROM market WHERE item_id=? AND seller=? AND status='active'", (item_id, uid))
    r = cur.execute("SELECT id FROM market WHERE item_id=? AND seller=? AND status='active'", (item_id, uid)).fetchone()
    if r:
        conn.close()
        return fail("这个商品已经在上架中")
    
    now = datetime.now().isoformat()
    try:
        cur.execute("""
            INSERT INTO market (item_id, seller, price, status, created_at)
            VALUES (?, ?, ?, 'active', ?)
        """, (item_id, uid, price, now))
        conn.commit()
    except Exception as e:
        conn.close()
        return fail(f"上架失败：{e}")
    
    conn.close()
    return ok({"item_id": item_id, "price": price}, f"上架成功！挂价{price}金币")

@app.post("/api/market/unsell")
async def api_unsell(request: Request):
    uid = get_current_user()
    if not uid:
        return fail("请先登录")
    
    try:
        body = await request.json()
    except Exception:
        return fail("参数错误")
    
    item_id = (body or {}).get("item_id", "")
    
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("SELECT id FROM market WHERE item_id=? AND seller=? AND status='active'", (item_id, uid))
    r = cur.execute("SELECT id FROM market WHERE item_id=? AND seller=? AND status='active'", (item_id, uid)).fetchone()
    if not r:
        conn.close()
        return fail("这不是你的上架商品")
    
    cur.execute("UPDATE market SET status='removed' WHERE item_id=? AND seller=?", (item_id, uid))
    conn.commit()
    conn.close()
    
    return ok({}, "下架成功")

@app.get("/api/market")
def api_market():
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT m.id, m.item_id, m.seller, m.price, m.created_at,
               i.name, i.emoji, i.rarity, i.`desc`
        FROM market m
        JOIN items i ON m.item_id = i.id
        WHERE m.status='active'
        ORDER BY m.created_at DESC
        LIMIT 50
    """)
    
    items = [dict(r) for r in cur.fetchall()]
    conn.close()
    return ok({"items": items, "total": len(items)})

@app.post("/api/market/buy")
async def api_buy(request: Request):
    uid = get_current_user()
    if not uid:
        return fail("请先登录")
    
    try:
        body = await request.json()
    except Exception:
        return fail("参数错误")
    
    market_id = (body or {}).get("market_id", "")
    
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT m.id, m.item_id, m.seller, m.price,
               i.name, i.emoji, i.rarity
        FROM market m
        JOIN items i ON m.item_id = i.id
        WHERE m.id=? AND m.status='active'
    """, (market_id,))
    listing = cur.fetchone()
    
    if not listing:
        conn.close()
        return fail("商品不存在或已下架")
    
    if listing['seller'] == uid:
        conn.close()
        return fail("不能购买自己的商品")
    
    price = listing['price']
    
    cur.execute("SELECT coins FROM users WHERE id=?", (uid,))
    r = cur.execute("SELECT coins FROM users WHERE id=?", (uid,)).fetchone()
    buyer_coins = r[0] if r else 0
    
    if buyer_coins < price:
        conn.close()
        return fail(f"金币不足！需要{price}币，你只有{buyer_coins}币")
    
    cur.execute("UPDATE users SET coins=coins-? WHERE id=?", (price, uid))
    cur.execute("UPDATE users SET coins=coins+? WHERE id=?", (price, listing['seller']))
    
    try:
        cur.execute("DELETE FROM favorites WHERE user_id=? AND item_id=?", (listing['seller'], listing['item_id']))
    except Exception:
        pass
    
    now = datetime.now().isoformat()
    try:
        cur.execute("""
            INSERT OR IGNORE INTO favorites (user_id, item_id, created_at)
            VALUES (?, ?, ?)
        """, (uid, listing['item_id'], now))
    except Exception:
        pass
    
    cur.execute("UPDATE market SET status='sold', buyer=? WHERE id=?", (uid, market_id))
    conn.commit()
    
    cur.execute("SELECT coins FROM users WHERE id=?", (uid,))
    r = cur.execute("SELECT coins FROM users WHERE id=?", (uid,)).fetchone()
    coins_now = r[0] if r else 0
    
    conn.close()
    return ok({"coins": coins_now, "item_name": listing['name']}, f"购买成功！{listing['name']}现在是你的了！")

@app.get("/api/my-sales")
def api_my_sales():
    uid = get_current_user()
    if not uid:
        return fail("请先登录")
    
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT m.id, m.item_id, m.price, m.created_at, m.status,
               i.name, i.emoji, i.rarity
        FROM market m
        JOIN items i ON m.item_id = i.id
        WHERE m.seller=?
        ORDER BY m.created_at DESC
    """, (uid,))
    
    items = [dict(r) for r in cur.fetchall()]
    conn.close()
    return ok({"items": items})

# ── 搜索 ────────────────────────
@app.get("/api/search")
def api_search(q: str = ""):
    if not q:
        return ok({"items": [], "users": []})
    
    conn = get_db()
    cur = conn.cursor()
    q_like = f"%{q}%"
    
    cur.execute("""
        SELECT i.*, u.avatar_emoji as author_emoji
        FROM items i
        JOIN users u ON i.author = u.id
        WHERE i.status='active' AND (i.name LIKE ? OR i.`desc` LIKE ?)
        ORDER BY i.created_at DESC
        LIMIT 20
    """, (q_like, q_like))
    items = [dict(r) for r in cur.fetchall()]
    
    cur.execute("""
        SELECT id, avatar_emoji, level, coins FROM users
        WHERE is_ai=0 AND id LIKE ?
        LIMIT 10
    """, (q_like,))
    users = [dict(r) for r in cur.fetchall()]
    
    conn.close()
    return ok({"items": items, "users": users})

# ── 统计 ────────────────────────
@app.get("/api/stats")
def api_stats():
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM users WHERE is_ai=0")
    r = cur.execute("SELECT COUNT(*) FROM users WHERE is_ai=0").fetchone()
    users = r[0] if r else 0
    
    cur.execute("SELECT COUNT(*) FROM items WHERE status='active'")
    r = cur.execute("SELECT COUNT(*) FROM items WHERE status='active'").fetchone()
    items = r[0] if r else 0
    
    cur.execute("SELECT COUNT(*) FROM gacha_records")
    r = cur.execute("SELECT COUNT(*) FROM gacha_records").fetchone()
    gacha_count = r[0] if r else 0
    
    cur.execute("SELECT COUNT(*) FROM market WHERE status='active'")
    r = cur.execute("SELECT COUNT(*) FROM market WHERE status='active'").fetchone()
    market_items = r[0] if r else 0
    
    conn.close()
    return ok({
        "users": users,
        "items": items,
        "total_gacha": gacha_count,
        "market_items": market_items
    })

# ── 足迹 ────────────────────────
@app.post("/api/footprints")
async def api_add_footprint(request: Request):
    uid = get_current_user()
    if not uid:
        return fail("请先登录")
    try:
        body = await request.json()
    except Exception:
        return fail("参数错误")
    item_id = (body or {}).get("item_id", "")
    if not item_id:
        return fail("缺少item_id")
    conn = get_db()
    cur = conn.cursor()
    now = datetime.now().isoformat()
    try:
        cur.execute("INSERT INTO footprints (user_id, item_id, created_at) VALUES (?,?,?)",
                   (uid, item_id, now))
        conn.commit()
    except Exception:
        pass
    conn.close()
    return ok({}, "足迹已记录")

@app.get("/api/footprints")
def api_my_footprints():
    uid = get_current_user()
    if not uid:
        return fail("请先登录")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT f.item_id, f.created_at, i.name, i.emoji, i.price, i.rarity
        FROM footprints f
        JOIN items i ON f.item_id = i.id
        WHERE f.user_id=?
        ORDER BY f.created_at DESC
        LIMIT 50
    """, (uid,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return ok({"footprints": rows})

# ── 私信 ────────────────────────
@app.post("/api/messages")
async def api_send_message(request: Request):
    uid = get_current_user()
    if not uid:
        return fail("请先登录")
    try:
        body = await request.json()
    except Exception:
        return fail("参数错误")
    to_user = (body or {}).get("to_user", "").strip()
    content = (body or {}).get("content", "").strip()
    if not to_user or not content:
        return fail("收件人和内容不能为空")
    if to_user == uid:
        return fail("不能给自己发私信")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE id=?", (to_user,))
    if not cur.fetchone():
        conn.close()
        return fail("用户不存在")
    now = datetime.now().isoformat()
    cur.execute("INSERT INTO messages (from_user, to_user, content, created_at) VALUES (?,?,?,?)",
                (uid, to_user, content, now))
    # 发通知
    try:
        notify_msg = f"{uid} 给你发了一条私信"
        cur.execute("INSERT INTO notifications (user_id, type, content, created_at) VALUES (?,?,?,?)",
                    (to_user, "message", notify_msg, now))
    except Exception:
        pass
    conn.commit()
    conn.close()
    return ok({}, "发送成功")

@app.get("/api/messages/{other_user}")
def api_get_messages(other_user: str):
    uid = get_current_user()
    if not uid:
        return fail("请先登录")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM messages
        WHERE (from_user=? AND to_user=?) OR (from_user=? AND to_user=?)
        ORDER BY created_at ASC
        LIMIT 100
    """, (uid, other_user, other_user, uid))
    msgs = [dict(r) for r in cur.fetchall()]
    # 标记已读
    cur.execute("UPDATE messages SET read=1 WHERE to_user=? AND from_user=?", (uid, other_user))
    conn.commit()
    conn.close()
    return ok({"messages": msgs})

@app.get("/api/my-messages")
def api_my_message_list():
    uid = get_current_user()
    if not uid:
        return fail("请先登录")
    conn = get_db()
    cur = conn.cursor()
    # 获取最近私信的用户列表
    cur.execute("""
        SELECT 
            CASE WHEN from_user=? THEN to_user ELSE from_user END as other_user,
            MAX(created_at) as last_time
        FROM messages
        WHERE from_user=? OR to_user=?
        GROUP BY other_user
        ORDER BY last_time DESC
        LIMIT 20
    """, (uid, uid, uid))
    partners = [dict(r) for r in cur.fetchall()]
    for p in partners:
        cur.execute("SELECT COUNT(*) FROM messages WHERE to_user=? AND from_user=? AND read=0",
                    (uid, p['other_user']))
        r = cur.execute("SELECT COUNT(*) FROM messages WHERE to_user=? AND from_user=? AND read=0",
                        (uid, p['other_user'])).fetchone()
        p['unread'] = r[0] if r else 0
        cur.execute("SELECT avatar_emoji FROM users WHERE id=?", (p['other_user'],))
        r2 = cur.execute("SELECT avatar_emoji FROM users WHERE id=?", (p['other_user'],)).fetchone()
        p['avatar_emoji'] = r2['avatar_emoji'] if r2 else '👤'
    conn.close()
    return ok({"partners": partners})

# ── 好友 ────────────────────────
@app.post("/api/friends/request")
async def api_friend_request(request: Request):
    uid = get_current_user()
    if not uid:
        return fail("请先登录")
    try:
        body = await request.json()
    except Exception:
        return fail("参数错误")
    to_user = (body or {}).get("to_user", "").strip()
    if not to_user:
        return fail("请输入用户名")
    if to_user == uid:
        return fail("不能添加自己为好友")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE id=?", (to_user,))
    if not cur.fetchone():
        conn.close()
        return fail("用户不存在")
    # 检查是否已申请
    cur.execute("SELECT id FROM friendships WHERE from_user=? AND to_user=?",
                (uid, to_user))
    if cur.fetchone():
        conn.close()
        return fail("已发送过申请")
    now = datetime.now().isoformat()
    cur.execute("INSERT INTO friendships (from_user, to_user, status, created_at) VALUES (?,?,?,?)",
                (uid, to_user, "pending", now))
    # 发通知
    try:
        notify_msg = f"{uid} 申请添加你为好友"
        cur.execute("INSERT INTO notifications (user_id, type, content, created_at) VALUES (?,?,?,?)",
                    (to_user, "friend_request", notify_msg, now))
    except Exception:
        pass
    conn.commit()
    conn.close()
    return ok({}, "好友申请已发送")

@app.post("/api/friends/respond")
async def api_friend_respond(request: Request):
    uid = get_current_user()
    if not uid:
        return fail("请先登录")
    try:
        body = await request.json()
    except Exception:
        return fail("参数错误")
    from_user = (body or {}).get("from_user", "")
    action = (body or {}).get("action", "")  # accept / reject
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM friendships WHERE from_user=? AND to_user=? AND status='pending'",
                (from_user, uid))
    if not cur.fetchone():
        conn.close()
        return fail("申请不存在")
    if action == "accept":
        cur.execute("UPDATE friendships SET status='accepted' WHERE from_user=? AND to_user=?",
                    (from_user, uid))
        notify_msg = f"{uid} 接受了你的好友申请"
    else:
        cur.execute("UPDATE friendships SET status='rejected' WHERE from_user=? AND to_user=?",
                    (from_user, uid))
        notify_msg = f"{uid} 拒绝了你的好友申请"
    now = datetime.now().isoformat()
    try:
        cur.execute("INSERT INTO notifications (user_id, type, content, created_at) VALUES (?,?,?,?)",
                    (from_user, "friend_request", notify_msg, now))
    except Exception:
        pass
    conn.commit()
    conn.close()
    return ok({}, "操作成功")

@app.get("/api/friends")
def api_get_friends():
    uid = get_current_user()
    if not uid:
        return fail("请先登录")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            CASE WHEN from_user=? THEN to_user ELSE from_user END as friend_id
        FROM friendships
        WHERE (from_user=? OR to_user=?) AND status='accepted'
    """, (uid, uid, uid))
    friends = [dict(r) for r in cur.fetchall()]
    for f in friends:
        cur.execute("SELECT avatar_emoji, level, coins FROM users WHERE id=?", (f['friend_id'],))
        r = cur.execute("SELECT avatar_emoji, level, coins FROM users WHERE id=?", (f['friend_id'],)).fetchone()
        if r:
            f['avatar_emoji'] = r['avatar_emoji']
            f['level'] = r['level']
    # 待处理申请
    cur.execute("SELECT from_user FROM friendships WHERE to_user=? AND status='pending'",
                (uid,))
    requests = [dict(r) for r in cur.fetchall()]
    for r in requests:
        cur.execute("SELECT avatar_emoji FROM users WHERE id=?", (r['from_user'],))
        rr = cur.execute("SELECT avatar_emoji FROM users WHERE id=?", (r['from_user'],)).fetchone()
        r['avatar_emoji'] = rr['avatar_emoji'] if rr else '👤'
    conn.close()
    return ok({"friends": friends, "requests": requests})

# ── 通知 ────────────────────────
@app.get("/api/notifications")
def api_get_notifications():
    uid = get_current_user()
    if not uid:
        return fail("请先登录")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM notifications
        WHERE user_id=?
        ORDER BY created_at DESC
        LIMIT 50
    """, (uid,))
    notifs = [dict(r) for r in cur.fetchall()]
    # 未读计数
    cur.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND read=0", (uid,))
    r = cur.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND read=0", (uid,)).fetchone()
    unread = r[0] if r else 0
    conn.close()
    return ok({"notifications": notifs, "unread": unread})

@app.post("/api/notifications/read")
def api_mark_notifications_read():
    uid = get_current_user()
    if not uid:
        return fail("请先登录")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE notifications SET read=1 WHERE user_id=?", (uid,))
    conn.commit()
    conn.close()
    return ok({}, "已全部标为已读")

# ── 富豪榜 ────────────────────────
@app.get("/api/leaderboard")
def api_leaderboard():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, avatar_emoji, level, coins
        FROM users
        WHERE is_ai=0
        ORDER BY coins DESC
        LIMIT 50
    """)
    users = [dict(r) for r in cur.fetchall()]
    conn.close()
    return ok({"users": users})

# ── 成就 ────────────────────────
@app.get("/api/achievements/{username}")
def api_get_achievements(username: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT ua.achievement_id, ua.achieved_at, a.name, a.icon, a.description, a.reward_coins
        FROM user_achievements ua
        JOIN achievements a ON ua.achievement_id = a.id
        WHERE ua.user_id=?
    """, (username,))
    earned = [dict(r) for r in cur.fetchall()]
    conn.close()
    return ok({"achievements": earned})

# ── 首页 ────────────────────────
@app.get("/")
async def index():
    from fastapi.responses import FileResponse
    return FileResponse("static/index.html")
