"""
dedupe.py - 商品查重模块（SHA-256 哈希）
"""
import hashlib

def compute_hash(name: str, desc: str) -> str:
    """计算商品内容的 SHA-256 哈希"""
    raw = f"{name.strip()}{desc.strip()}".encode('utf-8')
    return hashlib.sha256(raw).hexdigest()

def is_duplicate(conn, hash_val: str, exclude_id: str = None) -> bool:
    """检查哈希是否已存在，exclude_id 用于编辑时排除自身"""
    cur = conn.cursor()
    if exclude_id:
        cur.execute("SELECT 1 FROM items WHERE hash = ? AND id != ?", (hash_val, exclude_id))
    else:
        cur.execute("SELECT 1 FROM items WHERE hash = ?", (hash_val,))
    return cur.fetchone() is not None

def check_name_similar(conn, name: str) -> list:
    """模糊查重：查找名称相似的已存在商品（简单包含匹配）"""
    cur = conn.cursor()
    like = f"%{name.strip()}%"
    cur.execute("SELECT id, name, author FROM items WHERE name LIKE ? OR name LIKE ?", (like, f"%{name.strip()}%"))
    return [dict(r) for r in cur.fetchall()]
