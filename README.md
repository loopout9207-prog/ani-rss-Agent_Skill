# ani-rss-cli

基于 [ANI-RSS](https://github.com/HisAtri/AniRss) REST API 的番剧订阅命令行工具（Python 3，零第三方依赖）。

通过已部署的 ani-rss 实例（Spring Boot，默认 `7789` 端口，REST API 位于 `/api`）实现搜番、预览命中、订阅与管理。本工具**只负责调用实例，不负责部署 ani-rss**。

## 功能

- **搜索**：Mikan / AniBT / AnimeGarden / Bangumi 四源搜番
- **字幕组**：按番剧页面/ BGM ID 获取字幕组 RSS
- **预览**：订阅前预览命中条目与下载目录
- **订阅**：添加 / 启停 / 删除 / 刷新 / 修改字段
- **导入**：从 Ani JSON 数组批量导入（REPLACE / SKIP 冲突策略）
- **鉴权**：API Key 或 用户名密码登录（登录令牌自动缓存与失效重登）
- **MCP**：内置 ani-rss MCP 接入规则（见 `SKILL.md`）

## 安装

无需安装依赖，直接运行脚本：

```bash
python3 scripts/ani_rss_cli.py --help
```

可选：软链到 PATH

```bash
ln -s "$(pwd)/scripts/ani_rss_cli.py" ~/.local/bin/ani-rss
```

## 快速开始

```bash
# 1) 初始化配置（二选一鉴权方式）
python3 scripts/ani_rss_cli.py config init --base-url http://<host>:7789 --auth apikey --api-key <你的apiKey>
python3 scripts/ani_rss_cli.py config init --base-url http://<host>:7789 --auth login --username <用户名> --password <密码>

# 2) 连通性检查
python3 scripts/ani_rss_cli.py ping

# 3) 搜索番剧
python3 scripts/ani_rss_cli.py mikan search "葬送的芙莉莲"

# 4) 预览命中后添加订阅
python3 scripts/ani_rss_cli.py preview --url "https://mikanani.me/RSS/Bangumi?bangumiId=3828&subgroupid=370" \
    --type mikan --bgm-url "https://bgm.tv/subject/544109" --subgroup 动漫国 --enable
python3 scripts/ani_rss_cli.py subscribe --url "https://mikanani.me/RSS/Bangumi?bangumiId=3828&subgroupid=370" \
    --type mikan --title "葬送的芙莉莲" --preview --no-confirm

# 5) 管理订阅
python3 scripts/ani_rss_cli.py list
python3 scripts/ani_rss_cli.py enable <id>
python3 scripts/ani_rss_cli.py disable <id>
python3 scripts/ani_rss_cli.py refresh --all
```

## 配置

配置文件位于 `~/.config/ani_rss_cli/config.json`（自动创建）。包含 `base_url`、鉴权方式、API Key / 用户名密码 / 缓存令牌。

**安全**：本文件含敏感凭据，已被 `.gitignore` 排除，切勿提交到 git。可用 `config get` 查看（敏感项以 `***` 掩码）。

## 完整文档

详细命令树、订阅流程与 MCP 接入规则见 [SKILL.md](SKILL.md)。
