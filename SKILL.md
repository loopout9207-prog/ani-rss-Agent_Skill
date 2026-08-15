---
name: ani-rss-Agent_Skill
description: 通过 ani-rss-Agent_Skill（基于 ANI-RSS REST API 的命令行工具）自动追番、订阅番剧。当用户想订阅/添加番剧、搜索 Mikan/AniBT/AnimeGarden 资源、管理 ani-rss 订阅（查看/启用/停用/删除/刷新/批量导入）、预览番剧订阅命中、切换下载版本/强制重新下载时，使用此 skill。
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

> - 在 WSL / Linux 下常见路径：`/mnt/c/Users/<用户名>/.agents/skills/ani-rss-Agent_Skill/scripts/ani_rss_cli.py`
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
#    加 --items 可同时列出每个字幕组已上传资源的标题，便于挑选同一字幕组内的不同版本（如 720P/1080P、HEVC 等）
python3 "$CLI" mikan groups "https://mikanani.me/Home/Bangumi/3828" --items

# 3) 预览订阅命中（确认会下载哪些集、下载目录）
python3 "$CLI" preview --url "https://mikanani.me/RSS/Bangumi?bangumiId=3828&subgroupid=370" \
    --type mikan --bgm-url "https://bgm.tv/subject/544109" --subgroup 动漫国 --enable

# 4) 添加订阅
python3 "$CLI" subscribe --url "https://mikanani.me/RSS/Bangumi?bangumiId=3828&subgroupid=370" \
    --type mikan --title "葬送的芙莉莲" --preview --no-confirm
```

### 筛选同一字幕组内的不同版本（标题关键词匹配）

同一个字幕组可能同时上传多个版本（如 720P、1080P、4K，或 x264/x265/HEVC 压制）。选定字幕组后，可用 `--match` 按标题关键词精确筛选，只下载命中全部关键词的版本：

```bash
# 1) 先看字幕组上传了哪些版本（挑出版本特征关键词）
python3 "$CLI" mikan groups "https://mikanani.me/Home/Bangumi/3828" --items

# 2) 用 --match 过滤预览（只命中 1080P 和 HEVC 的资源才会显示并下载）
python3 "$CLI" preview --url "https://mikanani.me/RSS/Bangumi?bangumiId=3828&subgroupid=370" \
    --type mikan --subgroup 动漫国 --match 1080P --match HEVC --enable

# 3) 确认无误后同样带上 --match 添加订阅
python3 "$CLI" subscribe --url "https://mikanani.me/RSS/Bangumi?bangumiId=3828&subgroupid=370" \
    --type mikan --title "葬送的芙莉莲" --subgroup 动漫国 --match 1080P --match HEVC \
    --preview --no-confirm
```

要点：

- `--match` 支持正则，默认区分大小写（项目用 `ReUtil.contains` 匹配标题），可重复指定多个，命中规则为"全部命中"。
- 关键词提取示例：`1080P`、`HEVC`、`x265`、`WebRip`、`BDRip`；若字幕组版本间差异在文件名末尾（如 `-v2`），直接写特征片段即可。
- 只做预览不落库用 `preview`；已添加的订阅可用 `set <id> --match 1080P` 追加覆盖匹配列表（`--match` 会整体替换原列表，空列表传 `--set match=[]` 可清空）。
- `--exclude`（排除关键词）仍可配合使用：同一字幕组内想排除某版本时，用 `--set exclude=["720P","合集"]`。

可选的高级参数（订阅时可覆盖生成配置）：

- `--title <标题>` 覆盖番剧标题
- `--season <季度>` 覆盖季度（如 `20263`）
- `--offset <n>` 集数偏移
- `--download-new` 只下载最新集
- `--enable` / `--disable` 是否启用
- `--match <关键词>` 可重复，按标题关键词（正则）过滤同一字幕组内的不同版本，**只有命中全部关键词的资源才会下载**（例：`--match 1080P --match HEVC` 只下 1080P+HEVC 的压制版）
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
python3 "$CLI" set <id> --match 1080P --match HEVC  # 覆盖标题匹配关键词（可重复）
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

## 切换下载版本 / 强制重新下载

> 适用场景：某番已下载过，但想换成指定字幕组/版本（如 `Baha`/`HEVC`/`1080P`）重新下载。单靠 `set --match` + 删文件 + `refresh` **常常无效**，原因见下方去重机制。本流程在实操中已验证（Windows PowerShell + plink 管理远端 Docker 部署）。

### 为什么改了 match、删了文件还不重新下载（三层去重）

ani-rss 对每个 RSS 命中项按顺序做"是否已下载"判断，**任一命中即跳过**：

1. **已保存的种子记录**：`TorrentUtil.getTorrent()` 检查 `{config}/torrents/{pinyin首字母}/{title}/Season {season}/{infoHash}.torrent`（config 即 docker 挂载到 `/config` 的目录）。存在则跳过，且**只打 debug 日志**——表现为"删了文件、刷新后没有任何反应"。
2. **qBittorrent 已有同名任务**：`itemDownloaded()` 按重命名后的任务名匹配。因重命名模板 `[${subgroup}] ${title} S${seasonFormat}E${episodeFormat}` 不含版本信息，**同集不同版本会重命名为同名**，旧版本任务会挡住新版本 → 日志 `已存在下载任务`。
3. **下载目录已有该集视频** → 日志 `本地已存在`。

### 强制重下 / 切换版本流程

```bash
# 1) 加版本过滤（--match 整体替换原列表；--set match=[] 可清空）
wsl python3 <CLI> set <id> --match Baha

# 2) 删除已下载视频文件（宿主机路径 = docker 挂载源）
#    （如 /mnt/MediaDown/media/番剧/<标题>/Season 1/*.mkv）

# 3) 清 qBittorrent 旧任务（含文件）——注意 deleteFiles 参数不可省略
#    POST http://<host>:8080/api/v2/torrents/delete  hashes=a|b|c  deleteFiles=true

# 4) 删 ani-rss 保存的种子记录（必须！否则步骤 5 无任何输出）
#    rm -rf <config>/torrents/<pinyin首字母>/<标题>/Season <n>/

# 5) 刷新并验证
wsl python3 <CLI> refresh <id>
#    容器日志出现 "添加下载" + "重命名 [组] ... (Baha ...) ==> ..." 即为成功
sudo -n docker logs --tail 60 ani-rss | grep <标题关键词>
```

- 种子记录目录名用**标题拼音首字母**（如 `遭到流放...` → `Z/遭到流放.../Season 1`），两套命名都查一下：`{config}/torrents/{标题}/Season {season}` 或 `{config}/torrents/{pinyin}/{标题}/Season {season}`。
- 若换的是**整个源**（而非同一字幕组内的版本），先用 `set <id> --url <RSS> --subgroup <组名>` 换源，再走步骤 2-5。
- 远端 SSH/plink、Docker 命令、qBittorrent WebUI API、PowerShell-WSL 引号陷阱等底层操作，见文末「附录：远端服务器上的 ani-rss 运维」。

## 常见问题

| 现象 | 处理 |
|---|---|
| `无法连接 ani-rss ... Connection refused` | 实例未启动或地址/端口不对，先 `ping` 确认；CLI 不负责部署 |
| `未配置 API Key` / `未配置登录账号` | 执行 `config init` 或 `config set` 补齐鉴权 |
| 鉴权返回 `登录已失效` | login 模式会自动重登；确认用户名密码正确；api-key 模式下确认 apiKey 与 ani-rss 配置一致 |
| `RSS解析失败` | RSS 地址不属于所选 `--type`，或用 `mikan groups` 重新获取规范 RSS 地址 |
| 找不到番剧 | 加 `--year --season` 限定季度，或换 `bgm search` / `anibt list` 搜 |
| 订阅后下载的不是想要的版本 | 用 `--match` 加标题关键词过滤（如 `1080P`、`HEVC`），先 `preview` 确认命中再订阅 |
| `--match` 一个都没命中 | 关键词是正则且需全部命中，先 `mikan groups --items` 看实际标题，写版本特征片段 |
| 改了 `--match` 或删了文件，刷新却不重新下载 | 三层去重：① 删 `{config}/torrents/{pinyin}/{title}/Season {n}/` 种子记录；② 清 qBittorrent 同名旧任务（`deleteFiles=true`）；③ 删下载目录视频；再 `refresh`（详见"切换下载版本 / 强制重新下载"） |
| 想换另一个字幕组/版本重新下载 | `set <id> --match <版本关键词>`（换整个源则 `--url/--subgroup`），再按"强制重新下载"流程清理后刷新 |
| Windows 下报 `python3 找不到` | 用 `wsl` 调用：`wsl python3 /mnt/c/.../ani_rss_cli.py <命令>` |

## 附录：远端服务器上的 ani-rss 运维（Windows 侧）

> 专用于管理**部署在远端（如 Docker）的 ani-rss 实例及其下载器 qBittorrent** 的底层操作。以下命令在 Windows PowerShell 中执行。

### SSH 登录（plink）

- Windows 自带 OpenSSH 不支持非交互式传密码，用 plink：`https://the.earth.li/~sgtatham/putty/latest/w64/plink.exe`
- **首次连接必须用 `-hostkey` 指定服务器指纹**（从报错 `Cannot confirm a host key in batch mode` 里取 SHA256），否则中断。
- 模板（密码占位，向用户索取）：

```powershell
& "C:\...\plink.exe" -batch -ssh dietpi@<host> -hostkey "SHA256:..." -pw "<密码>" "<远程命令>"
```

### Docker 命令（dietpi 用户需 `sudo -n`）

```bash
sudo -n docker ps
sudo -n docker inspect ani-rss --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{println}}{{end}}'
sudo -n docker logs --tail 60 ani-rss        # 看下载日志（"添加下载" / "重命名 ..." / "本地已存在"）
```

- ani-rss 容器挂载：`/mnt/MediaDown/media -> /Media`（番剧视频下载目录的宿主机路径）、`/mnt/Appdata/ani-rss -> /config`（**种子记录在 `/config/torrents/...`**）。
- qbittorrent 容器与 ani-rss 共享 `/Media` 挂载（文件互通），WebUI 端口 8080。

### qBittorrent WebUI API（ani-rss 的下载器）

```bash
# 登录拿 cookie（用户名密码从服务器 qBittorrent WebUI 配置读取）
curl -s -c qbt.cookies -d 'username=<用户名>&password=<密码>' 'http://<host>:8080/api/v2/auth/login'
# 列表（ani-rss 任务都在 category=ani-rss；magnet_uri 的 dn= 是原始种子名，需 URL 解码）
curl -s -b qbt.cookies 'http://<host>:8080/api/v2/torrents/info?category=ani-rss'
# 删除：hashes 用 | 分隔，且【必须带 deleteFiles】，否则报"缺少必需参数：deleteFiles"
curl -s -b qbt.cookies -X POST --data-urlencode 'hashes=<hash1|hash2>' --data-urlencode 'deleteFiles=true' 'http://<host>:8080/api/v2/torrents/delete'
```

### PowerShell 调用 WSL 的坑

- `wsl bash -c '...'` 内层单引号、`|` 管道、`>` 重定向、`&&` 会被 PowerShell 抢先解析 → **多步/含管道重定向的命令写成脚本文件放 WSL home 再 `wsl bash <script>` 执行**。
- `wsl cmd > file` 的重定向会落到 Windows 侧；要写 WSL 内文件须在 WSL 内重定向（脚本内）。
- 单条无重定向命令可直接 `wsl python3 /mnt/c/.../ani_rss_cli.py <命令>`（WSL 可访问 `/mnt/c/Users/...`）。
