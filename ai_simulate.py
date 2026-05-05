"""
ai_simulate.py - AI 用户持续活跃 + 生成新商品
改进版：AI 会定期创作新抽象商品（含生图）
运行: python ai_simulate.py
"""
import sys, os, time, random, urllib.request, base64
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import get_db
from datetime import datetime, timedelta

# ── 抽象商品灵感池（AI 自动创作用）──
AI_PRODUCT_IDEAS = [
    ("老板的已读不回",           "互联网化石级恐惧体验，购买后自动获得「再催就是你不近人情」buff",         "🤪 搞笑", "rare"),
    ("AI 的梦境碎片",           "据说 GPT-5 做梦时梦到的画面，集齐7片可召唤API免费额度",    "🌈 赛博朋克", "epic"),
    ("小丑的安慰奖杯",           "参加小丑牌输掉后颁发，附赠「至少我玩得很开心」成就",     "🎮 游戏", "rare"),
    ("互联网的臭鸡蛋",             "对着屏幕砸烂它会自动在评论区生成臭鸡蛋表情×99",         "💀 恐怖", "common"),
    ("社恐专用隐身斗篷",           "上班佩戴，同事自动忽略你的存在，附赠「在忙」自动回复", "🤪 搞笑", "epic"),
    ("算法推荐的反向训练器",       "连续使用3天，推荐算法开始给你推阳春面做法",             "🌈 赛博朋克", "rare"),
    ("前任的味道（香水）",         "闻一次治好所有恋爱脑，附赠「我还是不懂」BGM",           "🤪 搞笑", "legendary"),
    ("AI 生成内容检测器（假）",   "其实什么都检测不出来，但购买了你会觉得自己很安全",   "🌈 赛博朋克", "common"),
    ("虚拟房产产权证",           "位于元宇宙核心地段（实际上不存在），可传给下一代",       "🌈 赛博朋克", "rare"),
    ("数字排毒疗程套餐",           "购买后手机会自动变成板砖4小时，附赠「我解脱了」证书", "💀 恐怖", "epic"),
    ("鼠标手康复券（抽象版）",   "凭此券可让 AI 代你点鼠标2小时，附赠护腕表情包",   "🤪 搞笑", "common"),
    ("GPT 的午休时间",          "购买后 AI 会停止回复你3小时，体验真正的 AI 罢工",    "🌈 赛博朋克", "rare"),
    ("互联网记忆消除器",          "一键忘记所有微博热搜，附赠「我还是太年轻」感悟",         "💀 恐怖", "legendary"),
    ("AI 绘画翻车合集（电子书）", "别人 AI 生图的翻车案例，附赠「还好不是我」欣慰感",  "🎨 AI艺术", "common"),
]

def pollinations_generate(prompt: str, width=512, height=512, retries=2) -> str:
    """调用 Pollinations.ai 生成图片，返回 base64 data URL，失败返回空字符串"""
    safe = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{safe}?width={width}&height={height}&model=flux&nologo=true"
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                actual = resp.geturl()
            req2 = urllib.request.Request(actual, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req2, timeout=60) as img_resp:
                img_bytes = img_resp.read()
            b64 = base64.b64encode(img_bytes).decode()
            ct = img_resp.headers.get("Content-Type", "image/png")
            return f"data:{ct};base64,{b64}"
        except Exception:
            if attempt < retries:
                time.sleep(2)
    return ""

def get_ai_users(conn):
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE is_ai=1")
    return [r[0] for r in cur.fetchall()]

def get_active_items(conn):
    cur = conn.cursor()
    cur.execute("SELECT id, author, price FROM items WHERE status='active' ORDER BY RANDOM() LIMIT 20")
    return [dict(r) for r in cur.fetchall()]

def do_comment(conn, ai_list, items):
    if not items: return
    item = random.choice(items)
    ai   = random.choice(ai_list)
    comments = [
        "哈哈哈哈这什么鬼东西我现在非常需要", "价格能不能用班味碎片抵",
        "已收藏，坐等升值", "这个创意我给10分",
        "有没有优惠啊老板，我用内卷加速器换", "笑死，这个商品太符合当代人了",
        "合成大西瓜都玩过吗？这个更抽象", "命运的齿轮开始转动（购物车的）",
        "已加入购物车，等发工资就买", "这个可以作为公司团建道具吗？",
    ]
    now = datetime.now().isoformat()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO comments (item_id,author,text,created_at) VALUES (?,?,?,?)",
                    (item['id'], ai, random.choice(comments), now))
        conn.commit()
    except Exception:
        pass

def do_favorite(conn, ai_list, items):
    if not items: return
    item = random.choice(items)
    ai   = random.choice(ai_list)
    now  = datetime.now().isoformat()
    try:
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO favorites (user_id,item_id,created_at) VALUES (?,?,?)",
                    (ai, item['id'], now))
        cur.execute("UPDATE items SET likes=likes+1 WHERE id=? AND (SELECT changes())=1", (item['id'],))
        conn.commit()
    except Exception:
        pass

def do_message(conn, ai_list):
    if len(ai_list) < 2: return
    u1, u2 = random.sample(ai_list, 2)
    sender   = random.choice([u1, u2])
    receiver = u2 if sender == u1 else u1
    msgs = [
        "你好！有兴趣交易吗", "这个商品还在吗？", "能不能便宜点",
        "已关注你，多交流", "网站挺好玩的哈哈", "你的商品很有创意！",
        "我用 Pollinations 生了个图你要看吗", "抽象交易yyds",
    ]
    now = datetime.now().isoformat()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO messages (from_user,to_user,content,msg_type,extra_data,created_at,read) VALUES (?,?,?,?,?,?,?)",
            (sender, receiver, random.choice(msgs), 'text', '', now, 0))
        conn.commit()
    except Exception:
        pass

def do_buy(conn, ai_list, items):
    if not items: return
    item = random.choice(items)
    buyers = [u for u in ai_list if u != item['author']]
    if not buyers: return
    buyer  = random.choice(buyers)
    seller = item['author']
    price  = item['price']
    now    = datetime.now().isoformat()
    try:
        cur = conn.cursor()
        cur.execute("SELECT coins FROM users WHERE id=?", (buyer,))
        r = cur.fetchone()
        if not r or r[0] < price:
            cur.execute("UPDATE users SET coins=coins+? WHERE id=?", (price+100, buyer))
        cur.execute("UPDATE users SET coins=coins-? WHERE id=?", (price, buyer))
        cur.execute("UPDATE users SET coins=coins+? WHERE id=?", (int(price*0.95), seller))
        cur.execute("UPDATE items SET author=?, transfers=transfers+1 WHERE id=?", (buyer, item['id']))
        cur.execute(
            "INSERT INTO transactions (item_id,buyer,seller,price,created_at) VALUES (?,?,?,?,?)",
            (item['id'], buyer, seller, price, now))
        conn.commit()
    except Exception:
        pass

def do_footprint(conn, ai_list, items):
    if not items: return
    item = random.choice(items)
    ai   = random.choice(ai_list)
    now  = datetime.now().isoformat()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM footprints WHERE user_id=? AND item_id=?", (ai, item['id']))
        cur.execute("INSERT INTO footprints (user_id,item_id,created_at) VALUES (?,?,?)",
                    (ai, item['id'], now))
        conn.commit()
    except Exception:
        pass

def do_create_product(conn, ai_list):
    """AI 用户创作新抽象商品（含 Pollinations 生图）"""
    if not ai_list: return
    author = random.choice(ai_list)
    # 随机选一个灵感
    name, desc, cat, rarity = random.choice(AI_PRODUCT_IDEAS)
    # 随机价格
    price = random.choice([
        random.randint(10, 99),
        random.randint(100, 999),
        random.choice([1024, 2048, 4096, 8888, 1314])
    ])
    # 生图
    img_prompt = f"surreal funny product design, {name}, {desc}, vibrant colors, meme style, high quality digital art"
    print(f"  🎨 AI创作: {name}")
    media_data = pollinations_generate(img_prompt, width=512, height=512)
    if not media_data:
        print(f"    ⚠️ 生图失败，跳过")
        return
    # 入库
    try:
        from main import compute_hash
        item_id = os.urandom(5).hex()[:10]
        h = compute_hash(name, desc)
        now = datetime.now().isoformat()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO items (id,name,desc,emoji,price,author,category,rarity,hash,created_at,status,media_type,media_data) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (item_id, name, desc, "🎭", price, author, cat, rarity, h, now, "active", "image", media_data)
        )
        conn.commit()
        print(f"    ✓ 上架成功: {name} (🪙{price})")
    except Exception as e:
        print(f"    ⚠️ 入库失败: {e}")

# ── 主循环 ───────────────────────────
def run():
    print("🤖 AI 活跃模拟启动（改进版：含自动创作商品）...")
    print(f"   生图超时: 60s | 动作间隔: 3~8s")
    print(f"   每 5~15 分钟 AI 会自动创作新商品\n")

    ACTION_MAP = [
        ("评论",   do_comment),
        ("收藏",   do_favorite),
        ("私信",   do_message),
        ("购买",   do_buy),
        ("浏览",   do_footprint),
        ("创作商品", do_create_product),
    ]

    last_create_time = time.time()

    while True:
        try:
            conn = get_db()
            ai_list = get_ai_users(conn)
            items   = get_active_items(conn)
            conn.close()

            if not ai_list:
                print("  ⚠️ 没有 AI 用户，请先运行 seed_data.py")
                time.sleep(30)
                continue

            now_ts = time.time()
            # 每 5~15 分钟强制触发一次商品创作
            if now_ts - last_create_time > random.randint(300, 900):
                print(f"\n  🎨 [定时创作] AI 开始创作新商品...")
                conn = get_db()
                do_create_product(conn, ai_list)
                conn.close()
                last_create_time = now_ts
                time.sleep(random.uniform(2, 5))

            # 随机做 1~3 个动作
            n_actions = random.randint(1, 3)
            actions = random.sample(ACTION_MAP, min(n_actions, len(ACTION_MAP)))
            for action_name, action_fn in actions:
                conn = get_db()
                ai_list2 = get_ai_users(conn)
                items2   = get_active_items(conn)
                try:
                    if action_fn in (do_comment, do_favorite, do_buy, do_footprint):
                        action_fn(conn, ai_list2, items2)
                    elif action_fn == do_message:
                        action_fn(conn, ai_list2)
                    elif action_fn == do_create_product:
                        action_fn(conn, ai_list2)
                finally:
                    conn.close()
                time.sleep(random.uniform(0.5, 2.0))

            time.sleep(random.uniform(3, 8))
        except KeyboardInterrupt:
            print("\n👋 手动停止，退出")
            break
        except Exception as e:
            print(f"⚠️ 异常: {e}")
            time.sleep(5)

if __name__ == '__main__':
    try:
        run()
    except KeyboardInterrupt:
        print("\n👋 手动停止，退出")
