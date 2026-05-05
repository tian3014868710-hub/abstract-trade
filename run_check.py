import sys, os
sys.path.insert(0, r'C:\Users\ManTo\WorkBuddy\2026-05-05-task-1')
from database import get_db
conn = get_db()
cur = conn.cursor()
tables = ['users', 'items', 'transactions', 'friendships', 'messages', 'notifications', 'comments', 'favorites']
for t in tables:
    try:
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        print(f'{t}: {cur.fetchone()[0]}')
    except Exception as e:
        print(f'{t}: ERROR {e}')
conn.close()
