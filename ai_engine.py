"""
ai_engine.py - AI 模拟用户引擎
当网站前期没有真实用户时，用AI模拟用户行为：
- 给其他商品写调侃评论
- 上架新商品（生成抽象的商品名+描述）
- 购买低价商品
- 点赞商品

⚠️ 本版本使用模板生成内容（无需API key）
   后续可接入真实LLM API（在 generate_with_llm() 函数中替换）
"""
import sqlite3
import random
import json
from datetime import datetime
from database import get_db, init_db

# ─────────────────────────────────────────
# AI 人格定义（20个，与 database.py 预置对应）
# ─────────────────────────────────────────
PERSONAS = [
    {"id": "社畜小王",  "bio": "打工人，爱吐槽，每天加班到深夜",         "cat": "🤪 搞笑",  "style": "毒舌搞笑"},
    {"id": "喵星人",   "bio": "猫奴一枚，家里三只猫",                  "cat": "🐱 萌宠",  "style": "软萌可爱"},
    {"id": "AI艺术家",  "bio": "AI生成艺术爱好者，像素风格死忠",        "cat": "🎨 AI艺术", "style": "文艺技术"},
    {"id": "数字佛祖",  "bio": "赛博朋克信仰者，崇尚数字修行",         "cat": "🌈 赛博朋克","style": "玄学深邃"},
    {"id": "灵异程序员","bio": "半夜写代码会见到鬼",                     "cat": "💀 恐怖",  "style": "惊悚幽默"},
    {"id": "像素大师",  "bio": "8-bit复古游戏热爱者",                  "cat": "🎮 游戏",  "style": "怀旧热血"},
    {"id": "抽象诗人",  "bio": "用最抽象的语言写最接地气的诗",           "cat": "🤪 搞笑",  "style": "无厘头"},
    {"id": "元宇宙居民","bio": "已经在元宇宙买了三套房",                 "cat": "🌈 赛博朋克","style": "前沿炫酷"},
    {"id": "表情包大王","bio": "手机里有10万个表情包",                  "cat": "🐱 萌宠",  "style": "欢乐搞怪"},
    {"id": "深夜哲学家","bio": "每个深夜都在思考人生意义",               "cat": "💀 恐怖",  "style": "深沉迷惘"},
    {"id": "电子音乐人","bio": "用Python写电子音乐",                   "cat": "🎵 音乐",  "style": "律动前卫"},
    {"id": "NFT投机客", "bio": "炒NFT亏了一套房，但还在炒",             "cat": "🌈 赛博朋克","style": "疯狂投机"},
    {"id": "AI训练师",  "bio": "专门训练奇怪的AI模型",                  "cat": "🎨 AI艺术", "style": "极客幽默"},
    {"id": "虚拟主播",  "bio": "在虚拟世界当主播",                      "cat": "🎮 游戏",  "style": "元气满满"},
    {"id": "代码诗人",  "bio": "把代码写得像诗一样美",                  "cat": "🎨 AI艺术", "style": "浪漫文艺"},
    {"id": "梗达人",    "bio": "互联网梗百科全书写者",                   "cat": "🤪 搞笑",  "style": "梗点密集"},
    {"id": "恐怖故事王","bio": "专门讲恐怖故事吓唬人",                  "cat": "💀 恐怖",  "style": "毛骨悚然"},
    {"id": "猫咪画家",  "bio": "画猫画出名的抽象艺术家",                 "cat": "🐱 萌宠",  "style": "温柔治愈"},
    {"id": "游戏策划师","bio": "设计过一款风靡全球的游戏",                "cat": "🎮 游戏",  "style": "逻辑缜密"},
    {"id": "AI算命师",  "bio": "用AI给人算命，准确率0.01%",            "cat": "🌈 赛博朋克","style": "玄乎其玄"},
]

# ─────────────────────────────────────────
# 模板池（后续可接入真实LLM替换此部分）
# ─────────────────────────────────────────

ITEM_NAME_TEMPLATES = [
    "会{}的{}", "当{}遇见{}", "{}的一万种死法",
    "如果{}会{}", "深夜{}的{}", "{}宇宙的{}",
    "的三个{}", "{}：{}篇", "被{}的{}",
    "{}日记：第{}天", "不懂{}的{}", "{}模拟器",
]
ITEM_SUBJECTS = {
    "🤪 搞笑":   ["打工人","社畜","甲方","deadline","产品经理","周报","摸鱼","下班"],
    "🎨 AI艺术": ["梵高","毕加索","AI","像素","神经网络","风格迁移","抽象画","调色盘"],
    "💀 恐怖":   ["鬼","深夜","404","乱码","黑屏","未知错误"," segmentation fault","蓝屏"],
    "🌈 赛博朋克":["赛博","朋克","元宇宙","区块链","NFT","数字永生","脑机接口","全息"],
    "🐱 萌宠":   ["猫","狗","仓鼠","兔子","修勾","猫主子","狗奴才","喵星人"],
    "🎮 游戏":   ["像素","8-bit","金币","关卡","Boss","复活","血量","经验值"],
    "🎵 音乐":   ["电子","节拍","混音","采样","旋律","低音炮","演唱会","吉他"],
}
ITEM_EMOJIS = ["🎭","🎨","🐱","👻","🏯","🐉","💾","🎮","🎵","🔥","💀","✨","🤪","🌈","🎧"]

COMMENT_TEMPLATES = [
    "哈哈哈哈这是我今天看到的最{}的东西😂",
    "这个{}感溢出屏幕了，作者是在{}吗？",
    "不懂就问，这个可以{}吗？",
    "已{}，太{}了",
    "别人都在{}，只有我在{}",
    "作者你{}是不是{}了",
    "有没有一种可能，这个{}其实是{}",
    "看不懂但大受震撼.jpg",
    "建议{}一下，{}程度太浅了",
    "这不是{}，这是{}！",
]
COMMENT_KEYWORDS = {
    "🤪 搞笑":   ["抽象","搞笑","离谱","整活"],
    "🎨 AI艺术": ["艺术","美","震撼","高级"],
    "💀 恐怖":   ["恐怖","吓人","诡异","细思极恐"],
    "🌈 赛博朋克":["酷","赛博","未来","科技"],
    "🐱 萌宠":   ["萌","可爱","治愈","舔屏"],
    "🎮 游戏":   ["好玩","上头","怀旧","经典"],
    "🎵 音乐":   ["好听","律动","上头","带感"],
}

def generate_item(persona: dict) -> dict:
    """为一个AI人格生成一个商品"""
    cat = persona["cat"]
    subjects = ITEM_SUBJECTS.get(cat, ITEM_SUBJECTS["🤪 搞笑"])
    s1, s2 = random.sample(subjects, 2)
    tmpl = random.choice(ITEM_NAME_TEMPLATES)
    name = tmpl.format(s1, s2)
    desc = "当{}遇见{}的{}瞬间".format(s1, s2, random.choice(["迷人","离谱","震撼","诡异"]))
    emoji = random.choice(ITEM_EMOJIS)
    price = random.choice([66,88,120,188,200,268,328,388,520,666])
    rarity = random.choice(["common"]*6 + ["rare"]*3 + ["legendary"]*1)
    return {"name": name, "desc": desc, "emoji": emoji, "price": price, "category": cat, "rarity": rarity}

def generate_comment(persona: dict, item_name: str, item_cat: str) -> str:
    """为一个AI人格生成一条评论"""
    keywords = COMMENT_KEYWORDS.get(item_cat, COMMENT_KEYWORDS["🤪 搞笑"])
    kw = random.choice(keywords)
    tmpl = random.choice(COMMENT_TEMPLATES)
    return tmpl.format(kw, random.choice(keywords) if "{}" in tmpl.replace("{}","",1) else kw)

# ─────────────────────────────────────────
# 核心：执行AI模拟动作
# ─────────────────────────────────────────

def run_ai_cycle():
    """
    执行一轮AI模拟（被 /api/ai/trigger 调用）
    每轮随机选3-5个AI用户，每人执行1-2个动作
    """
    init_db()
    conn = get_db()
    cur = conn.cursor()

    # 获取所有AI用户
    cur.execute("SELECT id FROM users WHERE is_ai=1")
    ai_users = [r["id"] for r in cur.fetchall()]
    if not ai_users:
        conn.close()
        return {"msg": "没有AI用户", "actions": 0}

    # 获取所有在售商品
    cur.execute("SELECT id, name, category, price, author FROM items WHERE status='active'")
    items = [dict(r) for r in cur.fetchall()]

    actions_log = []
    num_actors = random.randint(3, min(5, len(ai_users)))
    actors = random.sample(ai_users, num_actors)

    for actor_id in actors:
        persona = next(p for p in PERSONAS if p["id"] == actor_id)

        # 动作1（必选）：评论 or 点赞
        if items and random.random() < 0.9:
            # 评论
            target = random.choice(items)
            comment_text = generate_comment(persona, target["name"], target["category"])
            now = datetime.now().isoformat()
            cur.execute(
                "INSERT INTO comments (item_id, author, text, created_at) VALUES (?,?,?,?)",
                (target["id"], actor_id, comment_text, now)
            )
            # 顺便给点赞
            cur.execute("UPDATE items SET likes = likes + 1 WHERE id = ?", (target["id"],))
            actions_log.append(f"{actor_id} 评论了「{target['name']}」：{comment_text[:20]}...")

        # 动作2（概率）：上架新商品
        if random.random() < 0.35:
            item = generate_item(persona)
            import hashlib, binascii
            raw = f"{item['name']}{item['desc']}".encode('utf-8')
            hash_val = hashlib.sha256(raw).hexdigest()
            item_id = binascii.hexlify(hash_val[:8].encode()).decode()[:10]
            now = datetime.now().isoformat()
            try:
                cur.execute(
                    "INSERT INTO items (id, name, `desc`, emoji, price, author, category, rarity, hash, created_at, status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (item_id, item["name"], item["desc"], item["emoji"], item["price"], actor_id,
                     item["category"], item["rarity"], hash_val, now, "active")
                )
                actions_log.append(f"{actor_id} 上架了新商品「{item['name']}」🪙{item['price']}")
            except Exception:
                pass  # 哈希冲突，跳过

        # 动作3（概率）：购买低价商品
        if items and random.random() < 0.2:
            affordable = [i for i in items if i["price"] <= 100 and i["author"] != actor_id]
            if affordable:
                target = random.choice(affordable)
                cur.execute("SELECT coins FROM users WHERE id = ?", (actor_id,))
                row = cur.fetchone()
                if row and row["coins"] >= target["price"]:
                    # 扣钱，商品转手
                    cur.execute("UPDATE users SET coins = coins - ? WHERE id = ?", (target["price"], actor_id))
                    cur.execute("UPDATE items SET author = ?, transfers = transfers + 1 WHERE id = ?", (actor_id, target["id"]))
                    cur.execute(
                        "INSERT INTO transactions (item_id, buyer, seller, price, created_at) VALUES (?,?,?,?,?)",
                        (target["id"], actor_id, target["author"], target["price"], datetime.now().isoformat())
                    )
                    actions_log.append(f"{actor_id} 购买了「{target['name']}」🪙{target['price']}")

        # 动作4（概率）：单纯点赞
        if items and random.random() < 0.5:
            target = random.choice(items)
            cur.execute("UPDATE items SET likes = likes + 1 WHERE id = ?", (target["id"],))
            actions_log.append(f"{actor_id} 点赞了「{target['name']}」❤️")

    conn.commit()
    conn.close()
    return {"msg": "AI模拟完成", "actions": len(actions_log), "log": actions_log}

if __name__ == "__main__":
    result = run_ai_cycle()
    print(json.dumps(result, ensure_ascii=False, indent=2))
