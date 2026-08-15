---
name: ani-rss-cli
description: 通过 ani-rss-cli（基于 ANI-RSS REST API 的命令行工具）自动追番、订阅番剧。当用户想订阅/添加番剧、搜索 Mikan/AniBT/AnimeGarden 资源、管理 ani-rss 订阅（查看/启用/停用/删除/刷新/批量导入）、预览番剧订阅命中时，使用此 skill。
---

# ANI-RSS 番剧订阅 CLI

通过 `ani_rss_cli.py` 操作已部署的 ani-rss 实例，完成搜番、订阅、管理与批量导入。

> ani-rss 是一个自托管的"基于 RSS 自动追番/下载/洗版"服务，默认运行在 `7789` 端口，REST API 位于 `/api`。
> 本 CLI 只负责调用已部署的实例，**不负责部署 ani-rss**。

## 第一步：准备 CLI 与运行环境

CLI 是 Python 3 脚本（零第三方依赖），位于本 skill 目录：`scripts/ani_rss_cli.py`。

确认 Python 可用：

```bash
python3 --version
```

定义脚本路径（按当前系统实际路径替换）：

```bash
CLI="<本 skill 目录>/scripts/ani_rss_cli.py"
```

> - 在 WSL / Linux 下常见路径：`/mnt/c/Users/<用户名>/.agents/skills/ani-rss-cli/scripts/ani_rss_cli.py`
> - 在 Windows PowerShell 下执行：`wsl python3 /mnt/c/Users/<用户名>/.../ani_rss_cli.py <命令>`
> - 可选：`ln -s "$CLI" ~/.local/bin/ani-rss` 后可直接用 `ani-rss <命令>`。

查看帮助与命令树：

```bash
python3 "$CLI" --help
```

## 第二步：连接与状态检查

```bash
python3 "$CLI" ping
```

- 提前确认是否有已部署的 ani-rss 实例及它的地址。**如果用户没有实例，不要擅自部署**，先向用户说明：本 CLI 只管理已部署的 ani-rss，请用户自行提供地址（自建/NAS/Docker 均可）。
- 未配置时先引导初始化（二选一鉴权方式，与 ani-rss 配置一致）：

```bash
# 方式一：API Key（需在 ani-rss 配置中设置 apiKey）
python3 "$CLI" config init --base-url http://<host>:7789 --auth apikey --api-key <你的apiKey>

# 方式二：用户名密码登录（ani-rss 默认登录账号）
python3 "$CLI" config init --base-url http://<host>:7789 --auth login --username <用户名> --password <密码>
```

查看连接/鉴权状态：

```bash
python3 "$CLI" config status
```

> 配置保存在 `~/.config/ani_rss_cli/config.json`，登录令牌会自动缓存并在失效时自动重登。可用 `config set <key> <value>` 修改单项，用 `--base-url/--api-key/--username/--password` 临时覆盖。

## 第三步：正常订阅流程

推荐流程：**搜索 → 确认字幕组 → 预览命中 → 添加订阅**。

```bash
# 1) 搜索番剧（Mikan；可用 --year 2026 --season 夏 限定季度）
python3 "$CLI" mikan search "葬送的芙莉莲"

# 2) 查看该番剧的字幕组与 RSS（拿到 RSS 地址用于订阅）
python3 "$CLI" mikan groups "https://mikanani.me/Home/Bangumi/3828"

# 3) 预览订阅命中（确认会下载哪些集、下载目录）
python3 "$CLI" preview --url "https://mikanani.me/RSS/Bangumi?bangumiId=3828&subgroupid=370" \
    --type mikan --bgm-url "https://bgm.tv/subject/544109" --subgroup 动漫国 --enable

# 4) 添加订阅
python3 "$CLI" subscribe --url "https://mikanani.me/RSS/Bangumi?bangumiId=3828&subgroupid=370" \
    --type mikan --title "葬送的芙莉莲" --preview --no-confirm
```

可选的高级参数（订阅时可覆盖生成配置）：

- `--title <标题>` 覆盖番剧标题
- `--season <季度>` 覆盖季度（如 `20263`）
- `--offset <n>` 集数偏移
- `--download-new` 只下载最新集
- `--enable` / `--disable` 是否启用
- `--set 字段=值` 可重复，覆盖任意 Ani 字段（例：`--set omit=true` 开启遗漏检测）
- `--dry-run` 只生成订阅配置不落库；`--json` 输出原始 JSON

其他源（可选）：

```bash
# AniBT / AnimeGarden / Bangumi 搜索
python3 "$CLI" anibt list --title "芙莉莲"
python3 "$CLI" anibt groups <bgmId>
python3 "$CLI" garden list
python3 "$CLI" garden groups <bgmId>
python3 "$CLI" bgm search "芙莉莲"        # Bangumi 条目
python3 "$CLI" bgm to-ani <subjectId>   # 转订阅配置
```

## 第四步：订阅管理

```bash
python3 "$CLI" list                  # 查看全部（标题/季度/集数/启停状态/字幕组）
python3 "$CLI" list --enabled       # 只看启用
python3 "$CLI" list --json          # 原始数据（含完整 id）
python3 "$CLI" enable <id>          # 启用（可多个）
python3 "$CLI" disable <id>         # 停用（可多个）
python3 "$CLI" delete <id> --delete-files   # 删除（可选同删文件）
python3 "$CLI" set <id> --url <RSS> --subgroup <字幕组>  # 修改订阅字段（换字幕组等）
python3 "$CLI" set <id> --set enable=true   # 也可用 --set k=v 设任意字段；--dry-run 预览
python3 "$CLI" refresh --all        # 刷新全部 RSS
python3 "$CLI" refresh <id>         # 刷新单个
```

批量导入（适用于从旧实例导出/脚本批量订阅）：

```bash
# aniList.json 为 Ani 对象数组；冲突策略 REPLACE=覆盖 / SKIP=跳过
python3 "$CLI" import aniList.json --conflict SKIP
```

## 第五步：结果输出与用户友好

- 给用户的推荐链接请用可点击的完整 URL：`https://bgm.tv/subject/<id>`、Mikan 番剧页/字幕组 RSS、`config status` 中的实例地址。
- `list` 输出的短 id（`ani-0001`）可直接用于 enable/disable/delete/refresh。
- **禁止**向用户输出 API Key、密码、登录令牌；`config get` 会默认用 `***` 掩码。
- 命令出错时先看 stderr 的"错误: …"信息，结合 `--debug` 打印实际 HTTP 请求辅助排查。
- 所有写操作命令（subscribe/delete 等）均带确认提示，追加 `--no-confirm` 可跳过。

## MCP 配置规则（供其他 Agent 参考自动配置）

ANI-RSS 已内置 MCP Server，可按以下规则接入 AI 客户端。任何 Agent 依据本规则即可自动完成配置。

### 1. 前提

- ani-rss 启动时启用 MCP：设置环境变量 `MCP_ENABLED=true`（Docker 部署则加 `-e MCP_ENABLED=true`）。
- MCP 端点鉴权走 **API Key**，必须在 ani-rss 配置中设置 `apiKey`，否则 MCP 不可用（`McpEndpointConfig` 校验逻辑）。

### 2. 端点信息

- 端点：`{base_url}/api/mcp`
- 协议：MCP **streamable HTTP**（POST + sse）
- 鉴权头：`api-key: <ani-rss配置的apiKey>`（与 REST 一致，字段 `api-key`/`x-api-key`/`s` 均可）

### 3. 可用工具（9 个，均来自项目 `AniMcpTools`）

| 工具名 | 参数 | 说明 |
|---|---|---|
| `list_subscriptions` | `enabled?`(bool) | 订阅列表，可按启用状态过滤 |
| `search_mikan` | `text?`, `season?`{year,season} | 搜索 Mikan 番剧 |
| `search_anibt` | — | 搜索 AniBT 番剧 |
| `search_anime_garden` | — | 搜索 AnimeGarden 番剧 |
| `get_mikan_groups` | `url` | 按 Mikan 页面 URL 取字幕组 RSS |
| `get_anibt_groups` | `bgmId` | 按 BGM ID 取 AniBT 字幕组 |
| `get_anime_garden_groups` | `bgmId` | 按 BGM ID 取 AnimeGarden 字幕组 |
| `preview_subscription_items` | RssToAni 字段(url/type/bgmUrl/subgroup/enable) | 预览命中条目 |
| `add_subscription` | RssToAni 字段 | 添加订阅（先预览再添加） |

### 4. opencode / 其他 Agent 的 MCP 配置模板

在 opencode（`~/.config/opencode/opencode.jsonc`）中按流式 HTTP 方式注册：

```jsonc
{
  "mcp": {
    "ani-rss": {
      "type": "remote",
      "url": "http://127.0.0.1:7789/api/mcp",
      "headers": { "api-key": "<ani-rss的apiKey>" }
    }
  }
}
```

> 若使用其他 MCP 客户端，等价于注册一个 URL = `http://<host>:7789/api/mcp`、协议 = streamable HTTP、携带 `api-key` 头的 server。

### 5. 注意事项

- MCP 工具集只覆盖「搜索 / 预览 / 添加 / 列举」；**启停、删除、刷新、批量导入等管理能力不存在 MCP 工具**，这类操作请回退到本 CLI（REST API）。
- 鉴权失败（未设 apiKey 或 Key 错误）时 MCP 连接会失败，请先 `config status` 排查 REST 鉴权，再检查 `MCP_ENABLED`。
- 修改 opencode 配置后需重启 opencode 使 MCP 生效；配置语法可参照 `customize-opencode` skill。

## 常见问题

| 现象 | 处理 |
|---|---|
| `无法连接 ani-rss ... Connection refused` | 实例未启动或地址/端口不对，先 `ping` 确认；CLI 不负责部署 |
| `未配置 API Key` / `未配置登录账号` | 执行 `config init` 或 `config set` 补齐鉴权 |
| 鉴权返回 `登录已失效` | login 模式会自动重登；确认用户名密码正确；api-key 模式下确认 apiKey 与 ani-rss 配置一致 |
| `RSS解析失败` | RSS 地址不属于所选 `--type`，或用 `mikan groups` 重新获取规范 RSS 地址 |
| 找不到番剧 | 加 `--year --season` 限定季度，或换 `bgm search` / `anibt list` 搜 |
| Windows 下报 `python3 找不到` | 用 `wsl` 调用：`wsl python3 /mnt/c/.../ani_rss_cli.py <命令>` |
