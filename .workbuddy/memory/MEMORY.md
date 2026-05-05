# 2026-05-05 工作日志

## abstract-trade 牛只交易平台 - 已部署上线

- GitHub: https://github.com/tian3014868710-hub/abstract-trade
- 生产地址: https://abstract-trade.onrender.com
- 技术栈: FastAPI + SQLite/Turso (libSQL) + 纯静态 HTML 前端
- 数据库: Turso libSQL，免费5GB存储
- 部署: Render (render.yaml配置，push到GitHub自动部署)

### 完成的功能
- 密码注册/登录（PBKDF2-SHA256加盐）
- 商品上架/购买（图片base64存储）
- 评论系统
- 私信/群聊/好友申请
- 通知中心
- 收藏/足迹/签到领金币
- 游戏化UI（等级/稀有度/富豪榜）
- Turso数据库（libsql://格式，需要TURSO_AUTH_TOKEN认证）

### 本轮迭代（2026-05-05下午）
**UI大厂质感优化 (static/index.html)**
- 卡片悬停：translateY(-8px) + scale(1.02) + 金色阴影层次
- 图片区域：hover时scale(1.08)放大 + 渐变遮罩.img-overlay
- 价格标签：#c9a84c金色渐变背景 + 悬停动效
- legendary稀有度：legendaryGlow脉冲发光动画
- 标题hover变粉色，交互感更强
- 三处卡片渲染函数统一升级

**Pollinations.ai免费生图API (main.py)**
- GET /api/generate-image：完全免费，无需API Key
- 自动跟随重定向获取真实图片URL
- 返回base64 data URL，与media_data字段兼容
- 尺寸支持256/512/1024，model=flux

**AI商品生成改进 (seed_data.py + ai_simulate.py + main.py)**
- 抽象热梗商品：特朗普的假发、AI的灵魂碎片、小丑的安慰奖杯等25个
- 全部商品用Pollinations.ai生成真实512x512图片
- AI用户每5~15分钟自动创作并上架新商品
- 后台线程do_create_product()支持生图创作

### GitHub操作注意事项
- 该环境Windows ACP模式无法运行git命令，需要用户在本地CMD执行
- 新建文件后需要手动在GitHub网页编辑（如render.yaml已存在）

### Render + Turso 配置要点
- TURSO_DATABASE_URL = libsql://xxx.turso.io（不是https://）
- TURSO_AUTH_TOKEN = ndx_xxxxxxxx...（需要从Turso Create Token生成）
- Render自动从GitHub部署，push后约2分钟生效
