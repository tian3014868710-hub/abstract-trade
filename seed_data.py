"""
seed_data.py - 填充抽象商品数据（改进版）
- 接入 Pollinations.ai 生图
- 商品主题来自热梗/搞怪创意
运行: python seed_data.py
"""
import sys, os, hashlib, base64, urllib.request, urllib.parse, json, random, time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import get_db, init_db
from main import compute_hash, is_duplicate, ok

init_db()

# ── 抽象热梗商品模板 ─────────────────────────
# 每个商品：名称模板、描述模板、分类、稀有度
MEME_TEMPLATES = [
    # 政治/名人梗
    ("特朗普的假发（已开光）",       "前总统同款，附赠一道闪电特效，戴上即可秒变懂王",       "🤪 搞笑", "rare"),
    ("马斯克的生产力秘诀",             "熬夜+咖啡+发推特，三件套合集，附NFT认证",             "🎨 AI艺术", "epic"),
    ("拜登的递增眼镜",                 "看懂此眼镜者自动获得递增说话能力",                 "🤪 搞笑", "common"),
    ("普京的冰球球杆",                 "附赠硬汉认证，使用后力量+100",                     "💀 恐怖", "rare"),
    # 网络热梗
    ("回旋镖嘴替体验券",               "输入任意文字自动生成回旋镖式回复，吵架必胜",       "🤪 搞笑", "epic"),
    ("小丑牌（限量版）",               "Oblivion 联动款，使用后你的对手自动变成小丑",  "🎮 游戏", "legendary"),
    ("听劝蛋（孵化版）",               "上传你的照片，AI自动生成听劝前后的对比图",       "🎨 AI艺术", "rare"),
    ("鼠鼠我呀有声书",                 "鼠鼠文学全集配音版，附赠「判别」BGM",           "🤪 搞笑", "common"),
    ("王臭臭的臭豆腐（香水版）",       "闻一次终身难忘，附赠呕吐表情包一套",               "🤪 搞笑", "rare"),
    # 抽象概念
    ("他人的凝视（实体版）",             "让你在社死现场感受800人的凝视，恐社必备",      "💀 恐怖", "rare"),
    ("班味的碎片",                     "每个上班族体内都有一点班味，本商品为提纯版",     "🌈 赛博朋克", "epic"),
    ("命运的齿轮（生锈版）",             "命运想转动你？先除个锈！附赠「还在转」BGM",    "🌈 赛博朋克", "legendary"),
    ("社交牛杂症胶囊",                 "服下后立即获得社交牛杂/社恐双形态切换能力",     "🤪 搞笑", "rare"),
    ("内卷加速器 Pro",                  "让你的努力以3倍速度被老板看到，限时附赠996证书", "🌈 赛博朋克", "epic"),
    # 赛博朋克/AI 主题
    ("AI 的灵魂碎片",                  "据说集齐7个可以召唤GPT-5，每个碎片有不同性格", "🌈 赛博朋克", "legendary"),
    ("提示词祭坛",                     "把你最失败的提示词放进去烧掉，AI会自动优化",       "🌈 赛博朋克", "rare"),
    ("算法推荐的外卖（盲盒版）",       "算法认为你最爱吃的，可能是你最讨厌的，刺激！",   "🤪 搞笑", "common"),
    ("数据残渣饼干",                   "用互联网废弃数据烘焙而成，每口都有不同网站的味", "🌈 赛博朋克", "rare"),
    ("数字永生体验卡",                 "试用版30分钟，体验死后数据在云端永生的感觉",     "💀 恐怖", "legendary"),
    # 萌宠
    ("猫猫祟（召唤版）",               "深夜自动出现偷你零食，附赠「猫猫拳」技能书",     "🐱 萌宠", "epic"),
    ("修勾的孤独星球",                 "一只修勾独自在星球上看夕阳，购买即获得治愈光环", "🐱 萌宠", "rare"),
    ("鸟鸟法律咨询",                   "你的鸟鸟其实是个律师，本商品解锁它的说话能力",     "🐱 萌宠", "common"),
    # 游戏/二次元
    ("抽卡保底计算器",                 "输入你的非酋程度，自动计算还需要氪多少",         "🎮 游戏", "common"),
    ("氪金后悔药",                     "服用后可以看到如果不氪金你的账号会是什么样",     "🎮 游戏", "rare"),
    ("抽卡沉没成本证明书",               "官方认证你在这个游戏里浪费了多少钱，附赠哭脸",   "🎮 游戏", "epic"),
]

# ── Pollinations 生图 ─────────────────────────
def pollinations_generate(prompt: str, width=512, height=512, retries=2) -> str:
    """
    调用 Pollinations.ai 生成图片，返回 base64 data URL
    失败返回空字符串
    """
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
        except Exception as e:
            print(f"    ⚠️ 生图重试 ({attempt+1}/{retries+1}): {e}")
            time.sleep(2)
    return ""

# ── 主流程 ─────────────────────────
def seed():
    conn = get_db()
    cur = conn.cursor()

    # 清空旧数据（保留用户表结构）
    print("🧹 清理旧数据...")
    for t in ["items","comments","transactions","favorites","footprints",
              "messages","friendships","notifications","check_ins",
              "chat_rooms","chat_room_members","chat_messages"]:
        try:
            cur.execute(f"DELETE FROM {t}")
        except Exception:
            pass
    conn.commit()

    # 创建 AI 用户
    print("👥 创建 AI 用户...")
    ai_users = []
    AI_USER_LIST = [
        ("抽象小王子", "🎭", "专业生产抽象商品，脑洞突破天际"),
        ("赛博炼金术士", "⚗️", "把废话炼成金句，把梗炼成商品"),
        (" meme 教教主", "😈", "传播 meme 是我的天职"),
        ("互联网考古学家", "🏛️", "挖掘被遗忘的网络古物"),
        ("AI 驯养师", "🤖", "专门训练 AI 生成更抽象的内容"),
        ("数字拾荒者", "🗑️", "在互联网垃圾场里淘金"),
        ("命运齿轮修理师", "⚙️", "专门修理卡住的命运齿轮"),
        ("社死现场摄影师", "📸", "用镜头记录每一个社死瞬间"),
        ("算法反抗军", "🦹", "对抗推荐算法，还你自由意志"),
        ("虚拟房产中介", "🏠", "专门倒卖元宇宙里的海景房"),
    ]
    now = datetime.now().isoformat()
    for uname, emoji, bio in AI_USER_LIST:
        ai_users.append(uname)
        cur.execute(
            "INSERT OR IGNORE INTO users (id,password,coins,level,is_ai,avatar_emoji,bio,created_at) VALUES (?,?,?,?,?,?,?,?)",
            (uname, "", random.randint(500,5000), random.randint(1,8), 1, emoji, bio, now)
        )
    conn.commit()
    print(f"   ✓ 创建了 {len(ai_users)} 个 AI 用户")

    # 生成商品（生图 + 入库）
    print("🎨 生成抽象商品（含 AI 生图）...")
    items_created = []
    for idx, (name, desc, cat, rarity) in enumerate(MEME_TEMPLATES):
        author = random.choice(ai_users)
        price = random.choice([
            random.randint(10, 99),      # 平价
            random.randint(100, 999),    # 中等
            random.choice([1024, 2048, 4096, 8888, 1314])  # 吉利数
        ])
        # 用商品名+描述作为生图 prompt
        img_prompt = f" surreal funny creative product design, {name}, {desc}, vibrant colors, meme style, high quality digital art"
        print(f"  [{idx+1}/{len(MEME_TEMPLATES)}] 生图: {name}")
        media_data = pollinations_generate(img_prompt, width=512, height=512)

        if not media_data:
            print(f"    ⚠️ 生图失败，跳过: {name}")
            continue

        item_id = os.urandom(5).hex()[:10]
        h = compute_hash(name, desc)
        try:
            cur.execute(
                "INSERT INTO items (id,name,desc,emoji,price,author,category,rarity,hash,created_at,status,media_type,media_data) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (item_id, name, desc, "🎭", price, author, cat, rarity, h, now, "active", "image", media_data)
            )
            conn.commit()
            items_created.append(item_id)
            print(f"    ✓ 上架成功: {name} (🪙{price})")
        except Exception as e:
            print(f"    ⚠️ 入库失败: {e}")

        time.sleep(0.5)  # 避免请求过快

    print(f"\n✅ 共生成 {len(items_created)} 个商品（含 AI 生图）")

    # 生成一些交易记录
    print("💰 生成交易记录...")
    for _ in range(min(20, len(items_created))):
        item_id = random.choice(items_created)
        # 查商品
        cur.execute("SELECT author,price FROM items WHERE id=?", (item_id,))
        row = cur.fetchone()
        if not row: continue
        seller = row["author"]
        price  = row["price"]
        # 随机买家
        buyers = [u for u in ai_users if u != seller]
        if not buyers: continue
        buyer = random.choice(buyers)
        # 补钱
        cur.execute("UPDATE users SET coins=coins+? WHERE id=? AND coins<?", (price+100, buyer, price))
        # 交易
        cur.execute("UPDATE users SET coins=coins-? WHERE id=?", (price, buyer))
        cur.execute("UPDATE users SET coins=coins+? WHERE id=?", (int(price*0.95), seller))
        cur.execute("UPDATE items SET author=?, transfers=transfers+1 WHERE id=?", (buyer, item_id))
        tx_time = (datetime.now() - timedelta(hours=random.randint(1,72))).isoformat()
        cur.execute(
            "INSERT INTO transactions (item_id,buyer,seller,price,created_at) VALUES (?,?,?,?,?)",
            (item_id, buyer, seller, price, tx_time)
        )
        # 通知
        cur.execute(
            "INSERT INTO notifications (user_id,type,content,read,created_at) VALUES (?,?,?,?,?)",
            (seller, "trade", f"💰 {buyer} 购买了你的「{name}」", 0, tx_time)
        )
    conn.commit()

    # 生成评论
    print("💬 生成评论...")
    COMMENTS = [
        "哈哈哈哈这什么鬼东西我现在非常需要", "价格的能不能用班味碎片抵",
        "已收藏，坐等升值", "这个创意我给10分",
        "有没有优惠啊老板，我用内卷加速器换", "笑死，这个商品太符合当代人了",
        "已加入购物车，等发工资就买", "这个可以作为公司团建道具吗？",
        "买回来放在工位上，领导看了沉默", "命运的齿轮开始转动（购物车的）",
    ]
    for item_id in items_created[:15]:
        for _ in range(random.randint(1, 4)):
            author = random.choice(ai_users)
            cur.execute("SELECT name FROM items WHERE id=?", (item_id,))
            r = cur.fetchone()
            if not r: continue
            cmt_time = (datetime.now() - timedelta(minutes=random.randint(5,1440))).isoformat()
            cur.execute(
                "INSERT INTO comments (item_id,author,text,created_at) VALUES (?,?,?,?)",
                (item_id, author, random.choice(COMMENTS), cmt_time)
            )
            cur.execute("UPDATE items SET likes=likes+1 WHERE id=?", (item_id,))
    conn.commit()

    # 生成足迹
    print("👣 生成足迹...")
    for u in ai_users:
        viewed = random.sample(items_created, min(len(items_created), random.randint(3,8)))
        for item_id in viewed:
            t = (datetime.now() - timedelta(hours=random.randint(1,48))).isoformat()
            cur.execute("DELETE FROM footprints WHERE user_id=? AND item_id=?", (u, item_id))
            cur.execute("INSERT INTO footprints (user_id,item_id,created_at) VALUES (?,?,?)", (u, item_id, t))
    conn.commit()

    conn.close()
    print("\n🎉 数据填充完成！")
    print(f"   AI 用户: {len(ai_users)}")
    print(f"   抽象商品: {len(items_created)} (全部带 AI 生图)")
    print(f"   交易记录 / 评论 / 足迹 已生成")

if __name__ == "__main__":
    seed()
