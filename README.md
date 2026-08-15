# ani-rss-cli

**给 AI 使用的番剧订阅技能** —— 让 Agent 通过你已部署的 [ANI-RSS](https://github.com/HisAtri/AniRss) 实例（REST API，默认 `7789` 端口）自动搜番、预览命中、添加与管理订阅。

本技能是一份标准 `SKILL.md`（附零依赖 Python 脚本），安装到任意 Agent 的技能目录即可使用。**它只负责调用已部署的 ani-rss，不负责部署 ani-rss**。

## 功能

- **搜番**：Mikan / AniBT / AnimeGarden / Bangumi 四源搜索
- **字幕组**：按番剧页面或 BGM ID 获取字幕组 RSS
- **订阅管理**：添加 / 启用 / 停用 / 删除 / 刷新 / 修改字段 / 批量导入
- **预览**：添加前预览会命中下载哪些集、下载目录
- **鉴权**：API Key 或 用户名密码登录（令牌自动缓存、失效自动重登）
- **MCP 支持**：也可按 `SKILL.md` 中的规则接入 ani-rss 内置 MCP

## 安装为 Agent 技能

仓库根目录即技能目录（含 `SKILL.md` 与 `scripts/`），先克隆到本地：

```bash
git clone https://github.com/loopout9207-prog/ani-rss-cli.git
```

> 仓库当前为**私人**仓库，克隆需要你的 GitHub 账号有访问权限。

### OpenClaw

推荐用官方命令安装（`SKILL.md` 位于仓库根，可直接识别）：

```bash
# 安装到当前 agent 工作区
openclaw skills install git:loopout9207-prog/ani-rss-cli

# 或安装为全局（所有本地 agent 共享）
openclaw skills install git:loopout9207-prog/ani-rss-cli --global
```

验证：

```bash
openclaw skills list
```

### opencode

将克隆下来的 `ani-rss-cli` 目录放进以下任一技能目录：

| 范围 | 路径 |
|---|---|
| 全局技能 | `~/.config/opencode/skills/ani-rss-cli/` |
| 外部自动加载 | `~/.agents/skills/ani-rss-cli/` |

```bash
# 以外部自动加载目录为例
mkdir -p ~/.agents/skills
cp -r ani-rss-cli ~/.agents/skills/
```

或在 `~/.config/opencode/opencode.json` 中显式注册：

```json
{
  "skills": { "paths": ["C:/Users/<你>/ani-rss-cli"] }
}
```

> opencode 配置是启动时加载的，改动后需**重启 opencode** 才会生效。

### 说明

- opencode 与 OpenClaw 都自动扫描 `~/.agents/skills/`，把技能放进该目录即可一份共享、两处生效。
- 目录名须与 `SKILL.md` 中 `name`（`ani-rss-cli`）一致。
- 技能加载后，对话中提及「订阅番剧 / 追番 / 管理 ani-rss」即可自动触发。

## 首次使用：让 AI 自动完成认证与配置

你无需手动敲任何 CLI 命令。安装好技能后，直接把下面任一提示词发给 Agent，它会自行读取 `SKILL.md`、向你询问连接信息、自动完成配置与连通性检测。

### 你只需准备好

- ani-rss 实例地址（如 `http://192.168.1.10:7789`）
- 鉴权信息（二选一）：**API Key**，或 **登录用户名 + 密码**

### 通用提示词（OpenClaw / opencode 均可）

```text
请加载 ani-rss-cli 技能并按照 SKILL.md 的流程工作：
1. 先读取技能目录中的 SKILL.md，了解命令与用法；
2. 询问我 ani-rss 实例的 base_url 与鉴权方式（API Key，或 用户名/密码）；
3. 收到后由你自动执行配置初始化、连通性检测（ping），不要让我自己输入命令；
4. 完成后汇报实例版本与连通状态，并等待我的追番/订阅指令。
```

### opencode 示例

```text
使用 ani-rss-cli 技能帮我配置 ani-rss 连接并订阅番剧。
流程：加载技能 → 读取 SKILL.md → 问我实例地址和 apiKey/账号密码
→ 你自动执行 config init 和 ping 验证 → 汇报结果后等我下指令。
全程由你运行命令，我只提供连接信息。
```

### OpenClaw 示例

```text
请启用 ani-rss-cli 技能。步骤：
1. 阅读技能内的 SKILL.md；
2. 向我询问 ani-rss 的访问地址与鉴权凭据（apiKey 或用户名密码）；
3. 自动完成初始化与连通性测试并给我结论；
4. 之后我提出搜索/订阅请求时，你按技能流程操作，无需我再提供命令。
注意：不要把 apiKey、密码输出到对话中。
```

> 配置会保存在 `~/.config/ani_rss_cli/config.json`，只做一次；之后搜索、订阅、管理只需直接用自然语言下指令。

## 安全说明

- 配置文件 `~/.config/ani_rss_cli/config.json` 含 API Key / 密码 / 登录令牌，**已列入 `.gitignore`，切勿提交到仓库**。
- CLI 输出与提示词都要求掩码敏感字段；如发现问题请提醒 Agent 用 `config get` 自查（敏感项显示为 `***`）。
- 订阅、删除等写操作默认有确认提示，Agent 需要你确认后才执行。

## 完整文档

详细命令树、订阅流程、常见问题与 MCP 接入规则见 [SKILL.md](SKILL.md)。
