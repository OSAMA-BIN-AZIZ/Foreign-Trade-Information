# wx-auto-publisher

微信公众号自动发布系统（草稿优先 + 可选自动发布）。

## 功能
- 每日聚合日期/农历、汇率、新闻摘要。
- Jinja2 + Markdown -> HTML 渲染。
- 上传封面图与正文图（正文图支持替换）。
- 创建草稿，支持 `draft_only / auto_publish / safe_auto`。
- SQLite 幂等：同日同内容不重复创建。
- CLI + APScheduler + pytest。

## 公众号后台准备事项
1. 打开开发者模式。
2. 获取 AppID / AppSecret。
3. 配置接口调用 IP 白名单（否则常见 token / publish 调用失败）。

## 配置
1. 复制 `.env.example` 为 `.env`。
2. 填写微信配置、发布模式、定时表达式等。


## 运行环境
- 支持 Python 版本：**3.10 / 3.11 / 3.14**。
- 推荐本地开发默认使用 Python 3.11（当前仓库 `.python-version` 示例为 `3.11.14`）。

## 本地运行
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.cli build-only
python -m app.cli run-once
```

## CLI（主要命令说明）
```bash
python -m app.cli run-once
# 执行一次完整流程：抓取数据 -> 生成内容 -> 创建草稿（按发布模式可自动发布）

python -m app.cli build-only
# 只抓取并渲染，输出到 data/output，不调用微信接口

python -m app.cli publish-draft --date 2026-04-20
# 按日期发布已有草稿（需该日期草稿已存在）

python -m app.cli check-wechat
# 微信连通性检查（token、素材上传、草稿创建链路）

python -m app.cli backfill --start 2026-04-01 --end 2026-04-20
# 批量回填历史日期内容

python -m app.cli scheduler
# 启动定时任务（按 publish_cron 执行）
```

## 汇率来源说明
- 美元/人民币（USD/CNY）优先来自：`open.er-api` -> `frankfurter` -> `exchangerate-api`。
- 欧元/人民币（EUR/CNY）优先使用 `frankfurter` 的 EUR 基准直出值，失败时再走其他源换算。
- 若实时源不可用，会降级为缓存/演示值，并在正文里标注“非最新”。

## 发布模式
- `draft_only`: 仅创建草稿。
- `auto_publish`: 创建草稿后提交发布，报错即失败。
- `safe_auto`: 默认尝试发布，权限不足时自动降级为草稿并告警。

## 常见错误码
- `40001`: token 失效，系统会自动刷新重试一次。
- `48001 / 85019 / 20012`: 常见权限不足，`safe_auto` 下会降级。

## 已知限制
- 不同公众号主体权限不同，自动发布能力不保证可用。
- 农历当前为占位实现，可替换为真实日历库。
- 汇率默认 `exchange_rate_provider=auto`：优先实时拉取，失败后降级缓存/Mock。
- 新闻 `news_source_mode=rss` 默认拉取外部 RSS，失败时才降级为 Mock。



## 新闻源建议（中文 + 国际）
- 优先配置 `NEWS_CN_RSS_URLS`（国内中文源）和 `NEWS_GLOBAL_RSS_URLS`（国际源）。
- `NEWS_CN_MIN_ITEMS` 可控制最终列表里至少保留多少条中文资讯（默认 4）。
- 若外部源不可用，会在内容中显示降级提示（Mock）。
- 对非中文新闻会自动生成中文标题与中文摘要，适配微信公众号发布。
- 模板按“国内/国际”分区展示，排版更简洁。
- 默认每次尽量保留 20 条高相关资讯（不足时会降级补充并提示）。

## 个人主体账号建议（重点）
- 建议先使用 `WECHAT_USE_DRAFT_ONLY=true`，确保稳定进入草稿箱。
- 若想尝试自动发布，使用 `PUBLISH_MODE=safe_auto`，权限不足时会自动降级为仅草稿。
- 先跑 `python -m app.cli check-wechat --mock false` 做真实连通性检查（token/封面上传/草稿创建）。
- 再跑 `python -m app.cli run-once`，确认 `data/output/` 产物和草稿创建都正常。
