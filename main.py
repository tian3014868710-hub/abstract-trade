"""
main.py - FastAPI 主应用
抽象交易后端：密码注册/登录 / 商品 / 评论 / AI模拟 / 社交全功能
"""
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3, hashlib, json, binascii, os, secrets
from datetime import datetime
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import get_db, init_db
from dedupe import compute_hash, is_duplicate

init_db()

app = FastAPI(title="抽象交易 API")
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

def get_uid(request: Request) -> str:
    return request.cookies.get("uid", "")

# ── 认证接口 ────────────────────────
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
        return fail("用户名已存在，请换一个")
    now = datetime.now().isoformat()
    pw_hash = hash_password(password)
    try:
        cur.execute(
            "INSERT INTO users (id, password, coins, level, is_ai, avatar_emoji, created_at) VALUES (?,?,?,?,?,?,?)",
            (username, pw_hash, 500, 1, 0, "", now)
        )
        conn.commit()
    except Exception as e:
        conn.close()
        return fail(f"注册失败：{e}")
    conn.close()
    resp = JSONResponse({
        "code": 0, "msg": "注册成功！已送你 🪙500 启动资金",
        "data": {"username": username, "coins": 500, "level": 1}
    })
    resp.set_cookie("uid", username, max_age=86400 * 30, httponly=False)
    return resp

@app.post("/api/login")
async def api_login(request: Request):
    try:
        body = await request.json()
    except Exception:
        return fail("参数错误")
    username = (body or {}).get("username", "").strip()
    password = (body or {}).get("password", "")
    if not username or not password:
        return fail("请输入用户名和密码")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, password, coins, level FROM users WHERE id = ?", (username,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return fail("用户不存在")
    if not verify_password(password, row["password"]):
        return fail("密码错误")
    resp = JSONResponse({
        "code": 0, "msg": "登录成功！",
        "data": {"username": row[0], "coins": row[2], "level": row[3]}
    })
    resp.set_cookie("uid", row[0], max_age=86400 * 30, httponly=False)
    return resp

@app.post("/api/logout")
def api_logout():
    resp = ok(None, "已退出登录")
    resp.delete_cookie("uid")
    return resp

# ── 用户资料接口 ────────────────────────
@app.get("/api/user/{username}")
def api_get_user(username: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, coins, level, avatar_emoji, bio, created_at FROM users WHERE id=?", (username,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return fail("用户不存在")
    user = dict(row)
    cur.execute("SELECT COUNT(*) as cnt FROM items WHERE author=?", (username,))
    r = cur.fetchone()
    user["item_count"] = r["cnt"] if r else 0
    conn.close()
    return ok(user)

@app.put("/api/user/profile")
async def api_update_profile(request: Request):
    uid = get_uid(request)
    if not uid:
        return fail("请先登录")
    try:
        body = await request.json()
    except Exception:
        return fail("参数错误")
    bio = (body or {}).get("bio", "")[:200]
    avatar_data = (body or {}).get("avatar_data", "")
    conn = get_db()
    cur = conn.cursor()
    if bio:
        cur.execute("UPDATE users SET bio=? WHERE id=?", (bio, uid))
    if avatar_data and len(avatar_data) < 2_000_000:
        cur.execute("UPDATE users SET avatar_data=? WHERE id=?", (avatar_data, uid))
    conn.commit()
    conn.close()
    return ok(None, "资料更新成功")

# ── 好友接口 ────────────────────────
@app.get("/api/friends")
def api_list_friends(request: Request):
    uid = get_uid(request)
    if not uid:
        return fail("请先登录")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT u.id, u.avatar_emoji, u.bio
        FROM users u
        JOIN friendships f ON (
            (f.from_user=? AND f.to_user=u.id) OR
            (f.to_user=? AND f.from_user=u.id)
        )
        WHERE f.status='accepted'
    """, (uid, uid))
    friends = [dict(r) for r in cur.fetchall()]
    cur.execute("SELECT from_user, to_user, status FROM friendships WHERE (from_user=? OR to_user=?) AND status='pending'",
                (uid, uid))
    pending = []
    for r in cur.fetchall():
        if r["to_user"] == uid:
            pending.append({"from_user": r["from_user"], "status": "incoming"})
        else:
            pending.append({"to_user": r["to_user"], "status": "outgoing"})
    conn.close()
    return ok({"friends": friends, "pending": pending})

@app.post("/api/friends/request")
async def api_friend_request(request: Request):
    uid = get_uid(request)
    if not uid:
        return fail("请先登录")
    try:
        body = await request.json()
    except Exception:
        return fail("参数错误")
    target = (body or {}).get("username", "").strip()
    if not target or target == uid:
        return fail("无效的用户名")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE id=?", (target,))
    if not cur.fetchone():
        conn.close()
        return fail("用户不存在")
    cur.execute("SELECT status FROM friendships WHERE from_user=? AND to_user=?",
                (uid, target))
    row = cur.fetchone()
    if row:
        conn.close()
        return fail("已存在好友关系或申请")
    now = datetime.now().isoformat()
    cur.execute("INSERT INTO friendships (from_user, to_user, status, created_at) VALUES (?,?,?,?)",
                (uid, target, "pending", now))
    conn.commit()
    conn.close()
    return ok(None, f"已向 {target} 发送好友申请")

@app.post("/api/friends/respond")
async def api_friend_respond(request: Request):
    uid = get_uid(request)
    if not uid:
        return fail("请先登录")
    try:
        body = await request.json()
    except Exception:
        return fail("参数错误")
    from_user = (body or {}).get("from_user", "")
    action = (body or {}).get("action", "")  # accept / reject
    if action not in ("accept", "reject"):
        return fail("无效操作")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM friendships WHERE from_user=? AND to_user=? AND status='pending'",
                (from_user, uid))
    if not cur.fetchone():
        conn.close()
        return fail("申请不存在")
    if action == "accept":
        cur.execute("UPDATE friendships SET status='accepted' WHERE from_user=? AND to_user=?",
                    (from_user, uid))
    else:
        cur.execute("DELETE FROM friendships WHERE from_user=? AND to_user=?",
                    (from_user, uid))
    conn.commit()
    conn.close()
    return ok(None, "已接受" if action == "accept" else "已拒绝")

@app.delete("/api/friends/{username}")
def api_remove_friend(username: str, request: Request):
    uid = get_uid(request)
    if not uid:
        return fail("请先登录")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM friendships WHERE (from_user=? AND to_user=?) OR (from_user=? AND to_user=?)",
                (uid, username, username, uid))
    conn.commit()
    conn.close()
    return ok(None, f"已删除好友 {username}")

# ── 私信接口 ────────────────────────
@app.get("/api/messages/{username}")
def api_get_messages(username: str, request: Request):
    uid = get_uid(request)
    if not uid:
        return fail("请先登录")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM messages
        WHERE (from_user=? AND to_user=?) OR (from_user=? AND to_user=?)
        ORDER BY created_at
    """, (uid, username, username, uid))
    msgs = [dict(r) for r in cur.fetchall()]
    cur.execute("UPDATE messages SET read=1 WHERE to_user=? AND from_user=? AND read=0",
                (uid, username))
    conn.commit()
    conn.close()
    return ok(msgs)

@app.post("/api/messages/send")
async def api_send_message(request: Request):
    uid = get_uid(request)
    if not uid:
        return fail("请先登录")
    try:
        body = await request.json()
    except Exception:
        return fail("参数错误")
    to_user = (body or {}).get("to_user", "").strip()
    content = (body or {}).get("content", "").strip()
    msg_type = (body or {}).get("msg_type", "text")
    extra_data = (body or {}).get("extra_data", "")
    if not to_user or not content:
        return fail("收件人和内容不能为空")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE id=?", (to_user,))
    if not cur.fetchone():
        conn.close()
        return fail("用户不存在")
    now = datetime.now().isoformat()
    cur.execute(
        "INSERT INTO messages (from_user, to_user, content, msg_type, extra_data, created_at, read) VALUES (?,?,?,?,?,?,?)",
        (uid, to_user, content, msg_type, extra_data, now, 0)
    )
    conn.commit()
    conn.close()
    return ok(None, "发送成功")

@app.get("/api/messages/unread")
def api_unread_count(request: Request):
    uid = get_uid(request)
    if not uid:
        return ok({"count": 0})
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as cnt FROM messages WHERE to_user=? AND read=0", (uid,))
    r = cur.fetchone()
    count = r["cnt"] if r else 0
    conn.close()
    return ok({"count": count})

# ── 群聊接口 ────────────────────────
@app.get("/api/rooms")
def api_list_rooms(request: Request):
    uid = get_uid(request)
    if not uid:
        return fail("请先登录")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT r.* FROM chat_rooms r
        JOIN chat_room_members m ON r.id=m.room_id
        WHERE m.user_id=?
    """, (uid,))
    rooms = [dict(r) for r in cur.fetchall()]
    conn.close()
    return ok(rooms)

@app.post("/api/rooms/create")
async def api_create_room(request: Request):
    uid = get_uid(request)
    if not uid:
        return fail("请先登录")
    try:
        body = await request.json()
    except Exception:
        return fail("参数错误")
    name = (body or {}).get("name", "").strip()
    if not name:
        return fail("群名不能为空")
    room_id = "room_" + binascii.hexlify(os.urandom(5)).decode()[:8]
    now = datetime.now().isoformat()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO chat_rooms (id, name, owner, created_at) VALUES (?,?,?,?)",
                (room_id, name, uid, now))
    cur.execute("INSERT INTO chat_room_members (room_id, user_id, joined_at) VALUES (?,?,?)",
                (room_id, uid, now))
    conn.commit()
    conn.close()
    return ok({"id": room_id, "name": name}, "群聊创建成功")

@app.post("/api/rooms/{room_id}/join")
async def api_join_room(room_id: str, request: Request):
    uid = get_uid(request)
    if not uid:
        return fail("请先登录")
    now = datetime.now().isoformat()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM chat_rooms WHERE id=?", (room_id,))
    if not cur.fetchone():
        conn.close()
        return fail("群聊不存在")
    try:
        cur.execute("INSERT INTO chat_room_members (room_id, user_id, joined_at) VALUES (?,?,?)",
                    (room_id, uid, now))
        conn.commit()
    except Exception:
        pass
    conn.close()
    return ok(None, "已加入群聊")

@app.post("/api/rooms/{room_id}/send")
async def api_send_room_message(room_id: str, request: Request):
    uid = get_uid(request)
    if not uid:
        return fail("请先登录")
    try:
        body = await request.json()
    except Exception:
        return fail("参数错误")
    content = (body or {}).get("content", "").strip()
    if not content:
        return fail("内容不能为空")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM chat_room_members WHERE room_id=? AND user_id=?", (room_id, uid))
    if not cur.fetchone():
        conn.close()
        return fail("你不在该群聊中")
    now = datetime.now().isoformat()
    cur.execute(
        "INSERT INTO chat_messages (room_id, from_user, content, msg_type, created_at) VALUES (?,?,?,?,?)",
        (room_id, uid, content, "text", now)
    )
    conn.commit()
    conn.close()
    return ok(None, "发送成功")

@app.get("/api/rooms/{room_id}/messages")
def api_get_room_messages(room_id: str, request: Request):
    uid = get_uid(request)
    if not uid:
        return fail("请先登录")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM chat_room_members WHERE room_id=? AND user_id=?", (room_id, uid))
    if not cur.fetchone():
        conn.close()
        return fail("你不在该群聊中")
    cur.execute("SELECT * FROM chat_messages WHERE room_id=? ORDER BY created_at", (room_id,))
    msgs = [dict(r) for r in cur.fetchall()]
    conn.close()
    return ok(msgs)

# ── 商品接口 ────────────────────────
@app.get("/api/items")
def api_list_items(category: str = ""):
    conn = get_db()
    cur = conn.cursor()
    if category and category != "全部":
        cur.execute("SELECT * FROM items WHERE status='active' AND category=? ORDER BY created_at DESC", (category,))
    else:
        cur.execute("SELECT * FROM items WHERE status='active' ORDER BY created_at DESC")
    items = [dict(r) for r in cur.fetchall()]
    cur.execute("SELECT id, coins FROM users ORDER BY coins DESC LIMIT 5")
    lb = [{"name": r["id"], "coins": r["coins"]} for r in cur.fetchall()]
    conn.close()
    return ok({"items": items, "leaderboard": lb})

@app.get("/api/items/{item_id}")
def api_get_item(item_id: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM items WHERE id=?", (item_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return fail("商品不存在")
    item = dict(row)
    cur.execute("SELECT * FROM transactions WHERE item_id=? ORDER BY created_at", (item_id,))
    tx = [dict(r) for r in cur.fetchall()]
    conn.close()
    item["transactions"] = tx
    return ok(item)

@app.post("/api/items")
async def api_create_item(request: Request):
    try:
        body = await request.json()
    except Exception:
        return fail("参数错误")
    name       = (body or {}).get("name", "").strip()
    desc       = (body or {}).get("desc", "")
    price      = int((body or {}).get("price", 0) or 0)
    category   = (body or {}).get("category", "🤪 搞笑")
    emoji      = (body or {}).get("emoji", "🎭")
    author     = (body or {}).get("author", "")
    media_type = (body or {}).get("media_type", "none")
    media_data = (body or {}).get("media_data", "")
    if not name or price < 10:
        return fail("名称不能为空且价格≥10")
    if media_type == "none" or not media_data:
        return fail("请上传图片或视频后再上架")
    conn = get_db()
    cur = conn.cursor()
    h = compute_hash(name, desc)
    if is_duplicate(conn, h):
        conn.close()
        return fail("⚠️ 检测到重复商品，请修改内容后重新上架")
    item_id = binascii.hexlify(os.urandom(5)).decode()[:10]
    now = datetime.now().isoformat()
    try:
        cur.execute(
            "INSERT INTO items (id,name,desc,emoji,price,author,category,rarity,hash,created_at,status,media_type,media_data) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (item_id, name, desc, emoji, price, author, category, "common", h, now, "active", media_type, media_data)
        )
        conn.commit()
    except Exception as e:
        conn.close()
        return fail(f"上架失败：{e}")
    conn.close()
    return ok({"id": item_id}, "上架成功！")

@app.post("/api/items/{item_id}/buy")
async def api_buy_item(item_id: str, request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    buyer = (body or {}).get("buyer", "")
    if not buyer:
        return fail("请先登录")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM items WHERE id=? AND status='active'", (item_id,))
    row = cur.fetchone()
    if not row:
        conn.close(); return fail("商品不存在或已下架")
    item = dict(row)
    if item["author"] == buyer:
        conn.close(); return fail("不能购买自己的商品")
    cur.execute("SELECT coins FROM users WHERE id=?", (buyer,))
    u = cur.fetchone()
    if not u or u["coins"] < item["price"]:
        conn.close(); return fail("游戏币不足！")
    cur.execute("UPDATE users SET coins=coins-? WHERE id=?", (item["price"], buyer))
    cur.execute("UPDATE users SET coins=coins+? WHERE id=?", (int(item["price"] * 0.95), item["author"]))
    cur.execute("UPDATE items SET author=?, transfers=transfers+1 WHERE id=?", (buyer, item_id))
    now = datetime.now().isoformat()
    cur.execute(
        "INSERT INTO transactions (item_id,buyer,seller,price,created_at) VALUES (?,?,?,?,?)",
        (item_id, buyer, item["author"], item["price"], now)
    )
    conn.commit(); conn.close()
    return ok(None, f"🎉 购买成功！「{item['name']}」现在属于你")

# ── 收藏接口 ────────────────────────
@app.get("/api/favorites")
def api_list_favorites(request: Request):
    uid = get_uid(request)
    if not uid:
        return fail("请先登录")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT i.* FROM items i
        JOIN favorites f ON i.id=f.item_id
        WHERE f.user_id=?
        ORDER BY f.created_at DESC
    """, (uid,))
    items = [dict(r) for r in cur.fetchall()]
    conn.close()
    return ok(items)

@app.post("/api/favorites/add")
async def api_add_favorite(request: Request):
    uid = get_uid(request)
    if not uid:
        return fail("请先登录")
    try:
        body = await request.json()
    except Exception:
        return fail("参数错误")
    item_id = (body or {}).get("item_id", "")
    if not item_id:
        return fail("缺少 item_id")
    now = datetime.now().isoformat()
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO favorites (user_id, item_id, created_at) VALUES (?,?,?)",
                    (uid, item_id, now))
        cur.execute("UPDATE items SET likes=likes+1 WHERE id=?", (item_id,))
        conn.commit()
    except Exception:
        conn.close()
        return fail("已收藏过该商品")
    conn.close()
    return ok(None, "收藏成功")

# ── 足迹接口 ────────────────────────
@app.post("/api/footprints/add")
async def api_add_footprint(request: Request):
    uid = get_uid(request)
    if not uid:
        return fail("请先登录")
    try:
        body = await request.json()
    except Exception:
        return fail("参数错误")
    item_id = (body or {}).get("item_id", "")
    if not item_id:
        return fail("缺少 item_id")
    now = datetime.now().isoformat()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM footprints WHERE user_id=? AND item_id=?", (uid, item_id))
    cur.execute("INSERT INTO footprints (user_id, item_id, created_at) VALUES (?,?,?)",
                (uid, item_id, now))
    conn.commit(); conn.close()
    return ok(None)

@app.get("/api/footprints")
def api_list_footprints(request: Request):
    uid = get_uid(request)
    if not uid:
        return fail("请先登录")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT i.* FROM items i
        JOIN footprints f ON i.id=f.item_id
        WHERE f.user_id=?
        ORDER BY f.created_at DESC LIMIT 50
    """, (uid,))
    items = [dict(r) for r in cur.fetchall()]
    conn.close()
    return ok(items)

# ── 签到接口 ────────────────────────
@app.post("/api/checkin")
def api_checkin(request: Request):
    uid = get_uid(request)
    if not uid:
        return fail("请先登录")
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM check_ins WHERE user_id=? AND date=?", (uid, today))
    if cur.fetchone():
        conn.close()
        return fail("今天已经签到过了，明天再来吧！")
    bonus = 10 + (hash(today + uid) % 41)
    cur.execute("UPDATE users SET coins=coins+? WHERE id=?", (bonus, uid))
    cur.execute("INSERT INTO check_ins (user_id, date, coins_earned) VALUES (?,?,?)",
                (uid, today, bonus))
    cur.execute("SELECT coins FROM users WHERE id=?", (uid,))
    r = cur.fetchone()
    new_coins = r["coins"] if r else bonus
    conn.commit(); conn.close()
    return ok({"coins_earned": bonus, "coins": new_coins}, f"签到成功！获得 🪙{bonus}")

# ── 通知接口 ────────────────────────
@app.get("/api/notifications")
def api_list_notifications(request: Request):
    uid = get_uid(request)
    if not uid:
        return fail("请先登录")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 50", (uid,))
    notifs = [dict(r) for r in cur.fetchall()]
    conn.close()
    return ok(notifs)

@app.post("/api/notifications/read")
async def api_mark_notifications_read(request: Request):
    uid = get_uid(request)
    if not uid:
        return fail("请先登录")
    try:
        body = await request.json()
    except Exception:
        body = {}
    notif_id = (body or {}).get("id")
    conn = get_db()
    cur = conn.cursor()
    if notif_id:
        cur.execute("UPDATE notifications SET read=1 WHERE id=? AND user_id=?", (notif_id, uid))
    else:
        cur.execute("UPDATE notifications SET read=1 WHERE user_id=?", (uid,))
    conn.commit(); conn.close()
    return ok(None, "已标记已读")

# ── 评论接口 ────────────────────────
@app.get("/api/items/{item_id}/comments")
def api_get_comments(item_id: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM comments WHERE item_id=? ORDER BY created_at", (item_id,))
    rows = cur.fetchall()
    conn.close()
    return ok([dict(r) for r in rows])

@app.post("/api/items/{item_id}/comments")
async def api_add_comment(item_id: str, request: Request):
    try:
        body = await request.json()
    except Exception:
        return fail("参数错误")
    author = (body or {}).get("author", "")
    text   = (body or {}).get("text", "").strip()
    if not author or not text:
        return fail("作者和评论内容不能为空")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM items WHERE id=?", (item_id,))
    if not cur.fetchone():
        conn.close(); return fail("商品不存在")
    now = datetime.now().isoformat()
    cur.execute("INSERT INTO comments (item_id,author,text,created_at) VALUES (?,?,?,?)",
               (item_id, author, text, now))
    conn.commit(); conn.close()
    return ok(None, "评论成功")

# ── Feed 接口 ────────────────────────
@app.get("/api/feed")
def api_feed():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT item_id,buyer,seller,price,created_at FROM transactions ORDER BY created_at DESC LIMIT 10")
    txs = cur.fetchall()
    cur.execute("SELECT id,name,author,created_at FROM items ORDER BY created_at DESC LIMIT 10")
    new_items = cur.fetchall()
    conn.close()
    feed = []
    for r in txs:
        feed.append({"type": "buy", "name": r["buyer"], "action": f"以 🪙{r['price']} 购买了",
                     "target": r["item_id"], "time": r["created_at"][:16]})
    for r in new_items:
        feed.append({"type": "list", "name": r["author"], "action": "上架了新作品",
                     "target": r["name"], "time": r["created_at"][:16]})
    feed.sort(key=lambda x: x["time"], reverse=True)
    return ok(feed[:15])

# ── 用户主页 ────────────────────────
@app.get("/api/profile/{username}")
def api_profile(username: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, coins, level, is_ai, avatar_emoji, bio, avatar_data, background_data, created_at FROM users WHERE id=?", (username,))
    u = cur.fetchone()
    if not u:
        conn.close(); return fail("用户不存在")
    cur.execute("SELECT * FROM items WHERE author=? ORDER BY created_at DESC", (username,))
    items = [dict(r) for r in cur.fetchall()]
    conn.close()
    return ok({"user": dict(u), "items": items})

# ── 静态文件 ────────────────────────
if os.path.exists(os.path.join(os.path.dirname(__file__), "static", "index.html")):
    app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static"), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    print("🚀 抽象交易后端启动中... http://0.0.0.0:5020")
    uvicorn.run("main:app", host="0.0.0.0", port=5020, reload=True)
