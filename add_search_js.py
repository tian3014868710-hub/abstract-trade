import re

with open('C:\\Users\\ManTo\\WorkBuddy\\2026-05-05-task-1\\static\\index.html', 'r', encoding='utf-8') as f:
    content = f.read()

search_js = """
// ── 搜索 ─────────────────────────
async function doSearch() {
  const q = document.getElementById('searchInput')?.value?.trim();
  if (!q) { showToast('请输入搜索关键词', 'error'); return; }
  playSound('click');
  const res = await api('/api/search?q=' + encodeURIComponent(q));
  if (!res || res.code !== 0) { showToast(res?.msg||'搜索失败', 'error'); return; }

  const { items, users } = res.data || { items: [], users: [] };

  const qt = document.getElementById('searchQueryText');
  if (qt) qt.textContent = q;
  const stats = document.getElementById('searchStats');
  if (stats) stats.textContent = `找到 ${items.length} 件商品，${users.length} 位用户`;

  // 用户结果
  const userDiv = document.getElementById('searchUserResults');
  if (userDiv) {
    if (users.length === 0) {
      userDiv.innerHTML = '';
    } else {
      userDiv.innerHTML = '<div class="section-header" style="margin-top:24px"><div class="section-title">👤 用户</div></div>' +
        '<div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(200px,1fr))">' +
        users.map(u => {
          const isMe = currentUser && currentUser.id === u.id;
          return '<div class="card" onclick="viewUser(\\'' + esc(u.id) + '\\')">' +
            '<div class="card-img" style="background:linear-gradient(135deg,#1a0a2e,#2d1b69)">' +
            '<div style="font-size:48px">' + escapeHtml(u.avatar_emoji||'👤') + '</div></div>' +
            '<div class="card-body"><div class="card-title">' + escapeHtml(u.id) + '</div>' +
            '<div style="font-size:12px;color:var(--tx3);margin-bottom:8px">' + escapeHtml(u.bio||'') + '</div>' +
            '<div style="font-size:13px;color:var(--acc3);font-weight:700">🪙 ' + (u.coins||0).toLocaleString() + '</div>' +
            (isMe ? '<div style="font-size:11px;color:var(--tx3);margin-top:4px">我自己</div>' : '') + '</div></div>';
        }).join('') + '</div>';
    }
  }

  // 商品结果
  const itemDiv = document.getElementById('searchItemResults');
  if (itemDiv) {
    if (items.length === 0) {
      itemDiv.innerHTML = '<div style="text-align:center;padding:48px;color:var(--tx3)">没有找到相关商品</div>';
    } else {
      itemDiv.innerHTML = '<div class="section-header" style="margin-top:24px"><div class="section-title">🎭 商品</div></div>' +
        '<div class="grid">' +
        items.map((item,i) => {
          const bg = ['linear-gradient(135deg,#1a0a2e,#2d1b69)','linear-gradient(135deg,#0a1a2e,#1b6942)','linear-gradient(135deg,#2e0a0a,#691b1b)'][i%3];
          const rl = {common:'普通',rare:'稀有',legendary:'传说'}[item.rarity]||'普通';
          const imgContent = (item.media_type === 'image' && item.media_data)
            ? '<img src="' + item.media_data + '" style="width:100%;height:100%;object-fit:cover" />'
            : '<div style="font-size:64px">' + escapeHtml(item.emoji||'🎭') + '</div>';
          return '<div class="card" onclick="showDetail(\\'' + esc(item.id) + '\\')" style="animation:pageIn 0.4s ' + (i*0.06) + 's both">' +
            '<div class="card-img" style="background:' + bg + '">' + imgContent + '<div style="position:absolute;bottom:10px;right:10px;background:rgba(0,0,0,0.65);padding:4px 12px;border-radius:999px;font-size:13px;font-weight:700;color:var(--acc3)">🪙 ' + item.price + '</div></div>' +
            '<div class="card-body"><div class="card-title">' + escapeHtml(item.name) + '</div>' +
            '<div class="card-author"><span onclick="event.stopPropagation();viewUser(\\'' + esc(item.author) + '\\')" style="cursor:pointer;text-decoration:underline;color:var(--acc2)">' + escapeHtml(item.author) + '</span></div>' +
            '<div class="card-footer"><div class="card-likes">❤️ ' + (item.likes||0) + '</div>' +
            '<div class="rarity-badge rarity-' + (item.rarity||'common') + '">' + rl + '</div></div></div></div>';
        }).join('') + '</div>';
    }
  }

  sp('search');
}
"""

# Insert before </script>
content = content.replace('</script>', search_js + '\n</script>')

with open('C:\\Users\\ManTo\\WorkBuddy\\2026-05-05-task-1\\static\\index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ doSearch() 函数已添加到 index.html")
panel.plot
