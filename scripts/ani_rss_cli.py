#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ani-rss-cli — ANI-RSS 番剧订阅命令行工具

对已部署的 ani-rss 实例（Spring Boot，默认 7789 端口 /api 前缀）通过 REST API
实现搜番、预览、订阅、管理。零第三方依赖，仅用 Python 标准库。

用法：
    ani_rss_cli.py config init --base-url http://127.0.0.1:7789 --auth apikey --api-key xxx
    ani_rss_cli.py ping
    ani_rss_cli.py mikan search "葬送的芙莉莲"
    ani_rss_cli.py mikan groups https://mikanani.me/Home/Bangumi/3828
    ani_rss_cli.py subscribe --url "https://mikanani.me/RSS/Bangumi?bangumiId=3828&subgroupid=370" \
        --title "葬送的芙莉莲" --subgroup 动漫国 --match 1080P --match HEVC --preview
    ani_rss_cli.py list
    ani_rss_cli.py disable <id>

配置存放：~/.config/ani_rss_cli/config.json
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

VERSION = "1.0.0"
UA = "ani-rss-cli/{version}".format(version=VERSION)

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "ani_rss_cli")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

OK_CODE = 200

STATE = {
    "debug": False,
    "timeout": 60,
}


class CliError(Exception):
    pass


# ---------------------------------------------------------------- config ---

def default_config():
    return {
        "base_url": "http://127.0.0.1:7789",
        "auth": "apikey",          # apikey | login
        "apikey": "",
        "username": "",
        "password": "",
        "token": "",               # login 模式缓存令牌
    }


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return default_config()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        raise CliError("读取配置文件失败 {}: {}".format(CONFIG_FILE, e))
    merged = default_config()
    merged.update(cfg)
    return merged


def save_config(cfg):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        raise CliError("写入配置文件失败 {}: {}".format(CONFIG_FILE, e))


def effective_config(args):
    cfg = load_config()
    if getattr(args, "base_url", None):
        cfg["base_url"] = args.base_url
    if getattr(args, "api_key", None):
        cfg["apikey"] = args.api_key
        cfg["auth"] = "apikey"
    if getattr(args, "auth", None):
        cfg["auth"] = args.auth
    if getattr(args, "username", None):
        cfg["username"] = args.username
    if getattr(args, "password", None):
        cfg["password"] = args.password
    return cfg


MASKS = ("apikey", "password", "token")


def masked(cfg, key):
    v = cfg.get(key, "")
    return "***" if key in MASKS and v else v


# ------------------------------------------------------------ http helpers --

def _api_url(cfg, path, params=None):
    base = cfg["base_url"].rstrip("/")
    url = base + "/api" + (path if path.startswith("/") else "/" + path)
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    return url


def _make_headers(cfg):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": UA,
    }
    if cfg["auth"] == "apikey":
        if cfg["apikey"]:
            headers["api-key"] = cfg["apikey"]
        else:
            raise CliError("未配置 API Key，请先执行 config init 或 config set apikey <key>")
    elif cfg["auth"] == "login":
        headers["Authorization"] = _login_token(cfg)
    else:
        raise CliError("未知鉴权方式: {}".format(cfg["auth"]))
    return headers


def _login_token(cfg):
    if cfg.get("token"):
        return cfg["token"]
    if not cfg.get("username") or not cfg.get("password"):
        raise CliError("未配置登录账号，请执行 config init --auth login --username <u> --password <p>")
    body = {"username": cfg["username"], "password": cfg["password"]}
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(_api_url(cfg, "/login"), data=payload, method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=STATE["timeout"]) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise CliError("登录失败 HTTP {}: {}".format(e.code, _safe_read(e)))
    except urllib.error.URLError as e:
        raise CliError("无法连接 ani-rss: {}".format(e.reason))
    if result.get("code") != OK_CODE or not result.get("data"):
        raise CliError("登录失败: {}".format(result.get("message", "未知错误")))
    token = result["data"]
    cfg["token"] = token
    save_config(cfg)
    return token


def _safe_read(err):
    try:
        return err.read().decode("utf-8", "replace")[:500]
    except Exception:
        return ""


def api_call(cfg, method, path, params=None, body=None, retry=True):
    """发起请求并返回 Result 的 data 字段；code!=200 抛 CliError。"""
    url = _api_url(cfg, path, params)
    headers = _make_headers(cfg)
    payload = None
    if body is not None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")

    if STATE["debug"]:
        dbg(">>> {} {}".format(method, url))
        if body is not None:
            dbg(">>> body: {}".format(payload.decode("utf-8")))

    req = urllib.request.Request(url, data=payload, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=STATE["timeout"]) as resp:
            raw = resp.read().decode("utf-8")
            if STATE["debug"]:
                dbg("<<< HTTP {}: {}".format(resp.status, raw[:1000]))
            return _parse_result(raw)
    except urllib.error.HTTPError as e:
        raw = _safe_read(e)
        if STATE["debug"]:
            dbg("<<< HTTPError {}: {}".format(e.code, raw))
        if cfg["auth"] == "login" and e.code in (401, 403) and retry:
            cfg["token"] = ""
            save_config(cfg)
            return api_call(cfg, method, path, params, body, retry=False)
        try:
            result = json.loads(raw)
            msg = result.get("message") if isinstance(result, dict) else raw
        except Exception:
            msg = raw or "HTTP {}".format(e.code)
        raise CliError("请求失败 ({}): {}".format(e.code, msg))
    except urllib.error.URLError as e:
        raise CliError("无法连接 ani-rss {}: {}".format(cfg["base_url"], e.reason))


def _parse_result(raw):
    try:
        result = json.loads(raw)
    except Exception:
        raise CliError("返回内容不是 JSON: {}".format(raw[:300]))
    if not isinstance(result, dict):
        raise CliError("返回结构异常")
    if result.get("code") != OK_CODE:
        raise CliError(result.get("message", "请求失败"))
    return result.get("data")


def dbg(msg):
    if STATE["debug"]:
        print(msg, file=sys.stderr)


# ------------------------------------------------------------- formatting --

def fmt_season(n):
    """1/2/3/4 -> 冬/春/夏/秋；20263 -> 2026夏"""
    qn = ["", "冬", "春", "夏", "秋"]
    if not n:
        return "-"
    n = int(n)
    if 1 <= n <= 4:
        return qn[n]
    year = n // 10
    q = n % 10
    return "{}{}".format(year, qn[q] if 1 <= q <= 4 else "")


def fmt_bool(v, true_str="✔", false_str="✘"):
    return true_str if v else false_str


def print_json(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------- commands --

def cmd_config(args):
    sub = args.config_sub
    if sub == "init":
        cfg = load_config()
        if args.base_url:
            cfg["base_url"] = args.base_url.rstrip("/")
        if args.auth:
            cfg["auth"] = args.auth
        if args.api_key:
            cfg["apikey"] = args.api_key
            cfg["username"] = cfg["password"] = cfg["token"] = ""
        if args.username:
            cfg["username"] = args.username
            cfg["token"] = ""
        if args.password:
            cfg["password"] = args.password
            cfg["token"] = ""
        if not sys.stdin.isatty():
            # 非交互环境不询问，保留已有/默认值
            pass
        else:
            if not args.base_url:
                v = input("base_url (默认 {}): ".format(cfg["base_url"])).strip()
                if v:
                    cfg["base_url"] = v.rstrip("/")
            if not args.auth:
                v = input("鉴权方式 apikey / login (默认 {}): ".format(cfg["auth"])).strip()
                if v:
                    cfg["auth"] = v
            if cfg["auth"] == "apikey" and not cfg["apikey"]:
                cfg["apikey"] = input("api-key: ").strip()
            elif cfg["auth"] == "login":
                if not cfg["username"]:
                    cfg["username"] = input("用户名: ").strip()
                if not cfg["password"]:
                    cfg["password"] = input("密码: ").strip()
                cfg["token"] = ""
        save_config(cfg)
        print("配置已保存: {}".format(CONFIG_FILE))
        cmd_config_status(args)
        return
    if sub == "set":
        key, value = args.key, args.value
        allowed = dict(base_url=str, auth=str, apikey=str, username=str, password=str)
        if key not in allowed:
            raise CliError("不支持的配置项 {}，可用: {}".format(key, ", ".join(allowed)))
        cfg = load_config()
        cfg[key] = value.rstrip("/") if key == "base_url" else value
        if key in ("username", "password"):
            cfg["token"] = ""
        save_config(cfg)
        print("已设置 {}={}".format(key, masked(cfg, key)))
        return
    if sub == "get":
        cfg = load_config()
        if args.key:
            if args.key in MASKS and cfg.get(args.key):
                print("***")
            else:
                print(cfg.get(args.key, ""))
        else:
            for k in cfg:
                print("{} = {}".format(k, masked(cfg, k)))
        return
    if sub == "path":
        print(CONFIG_FILE)
        return
    if sub == "status":
        cmd_config_status(args)
        return
    raise CliError("未知 config 子命令")


def cmd_config_status(args):
    cfg = effective_config(args)
    auth = cfg["auth"]
    print("配置文件 : {}".format(CONFIG_FILE))
    print("base_url : {}".format(cfg["base_url"]))
    print("auth     : {} (apikey={})".format(auth, masked(cfg, "apikey")))
    if auth == "login":
        print("login    : {} token={}".format(cfg.get("username", ""), "已缓存" if cfg.get("token") else "未缓存"))
    try:
        Health = cmd_ping(args, return_data=True)
        print("连通性   : 正常  {} / {}".format(Health.get("version", "-"), Health.get("latest", "-")))
    except CliError as e:
        print("连通性   : 不可用 ({})".format(e))


def cmd_ping(args, return_data=False):
    cfg = effective_config(args)
    if args.json:
        return_data = True
    url = cfg["base_url"].rstrip("/") + "/"
    if STATE["debug"]:
        dbg(">>> GET {}".format(url))
    try:
        with urllib.request.urlopen(url, timeout=STATE["timeout"]) as resp:
            status = resp.status
    except urllib.error.HTTPError as e:
        status = e.code
    except urllib.error.URLError as e:
        raise CliError("无法连接 ani-rss {}: {}".format(cfg["base_url"], e.reason))
    info = {"reachable": True, "http_status": status, "url": cfg["base_url"]}
    try:
        about = api_call(cfg, "POST", "/about")
        if isinstance(about, dict):
            info["version"] = about.get("version")
            info["latest"] = about.get("latest")
            info["update"] = about.get("update")
    except CliError as e:
        dbg("about 需要鉴权: {}".format(e))
    if args.json or return_data:
        if return_data:
            return info
        print_json(info)
        return
    print("ani-rss 连通正常: {} (HTTP {})".format(cfg["base_url"], status))
    if info.get("version"):
        line = "当前版本 {}，最新版本 {}，{}更新".format(
            info["version"], info["latest"], "需要" if info.get("update") else "无需")
        print(line)


def _mikan_season(args):
    season = {}
    if getattr(args, "year", None):
        season["year"] = int(args.year)
    if getattr(args, "season", None):
        season["season"] = args.season
    return season


def cmd_mikan(args):
    cfg = effective_config(args)
    data = api_call(cfg, "POST", "/mikan", params={"text": args.text}, body=_mikan_season(args))
    if args.json:
        print_json(data)
        return
    seasons = data.get("seasons") or []
    if seasons:
        current = [s.get("seasonLabel") for s in seasons if s.get("select")]
        print("季度: {}".format(" | ".join(current) if current else ", ".join(
            "{}".format(s.get("seasonLabel")) for s in seasons)))
    for week in data.get("weeks") or []:
        label = week.get("weekLabel")
        items = week.get("items") or []
        if not items:
            continue
        print("=== {} ({} 部) ===".format(label, len(items)))
        for it in items:
            score = it.get("score")
            score_str = "{:.1f}".format(score) if isinstance(score, (int, float)) and score else "-"
            flag = "已订阅" if it.get("exists") else "-"
            title = it.get("title") or "-"
            url = it.get("url") or ""
            bgm = it.get("bgmUrl") or ""
            tail = "  " + bgm if bgm else ""
            print("  [{:>4}] {:>4}  {}".format(score_str, flag, title))
            print("          url: {}".format("{}".format(url) + tail))
    print("共 {} 部".format(data.get("totalItem", 0)))


def cmd_mikan_groups(args):
    cfg = effective_config(args)
    data = api_call(cfg, "POST", "/mikanGroup", params={"url": args.url})
    if args.json:
        print_json(data)
        return
    groups = data if isinstance(data, list) else []
    if not groups:
        print("未获取到字幕组")
        return
    print("共 {} 个字幕组：".format(len(groups)))
    for g in groups:
        label = g.get("label") or "-"
        day = g.get("updateDay") or "-"
        rss = g.get("rss") or ""
        bgm = g.get("bgmUrl") or ""
        n_items = len(g.get("items") or [])
        print("== {}  [更新 {}] [{} 条]".format(label, day, n_items))
        if bgm:
            print("   BGM: {}".format(bgm))
        print("   RSS: {}".format(rss))
        regex = g.get("groupRegex")
        if isinstance(regex, dict):
            rx = regex.get("regex") or ""
            if rx:
                print("   匹配正则: {}".format(rx))
        if args.items:
            print("   版本标题: ")
            for it in g.get("items") or []:
                t = it.get("title") or "-"
                sz = it.get("formatSize") or ""
                print("     - {}  {}".format(t, sz))


def cmd_anibt(args):
    cfg = effective_config(args)
    body = {}
    if getattr(args, "season", None):
        body["season"] = args.season
    if getattr(args, "bgm_url", None):
        body["bgmUrl"] = args.bgm_url
    if getattr(args, "title", None):
        body["title"] = args.title
    data = api_call(cfg, "POST", "/aniBT", body=body)
    if args.json:
        print_json(data)
        return
    # AniBT 结构：weeks 列表，weekLabel + items
    for week in data.get("weeks") or []:
        label = week.get("weekLabel")
        items = week.get("items") or []
        if not items:
            continue
        print("=== {} ({} 部) ===".format(label, len(items)))
        for it in items:
            title = it.get("title") or "-"
            bgm_id = it.get("bgmId") or it.get("bgmURL") or "-"
            print("  " + title)
            print("     bgmId: {}  年份: {}".format(bgm_id, it.get("year") or "-"))


def cmd_anibt_groups(args):
    cfg = effective_config(args)
    data = api_call(cfg, "POST", "/aniBTGroup", params={"bgmId": args.bgm_id})
    if args.json:
        print_json(data)
        return
    for g in data if isinstance(data, list) else []:
        print("== {}".format(g.get("label") or "-"))
        if g.get("bgmUrl"):
            print("   BGM: {}".format(g["bgmUrl"]))
        print("   RSS: {}".format(g.get("rss") or ""))


def cmd_garden_list(args):
    cfg = effective_config(args)
    params = {"bgmUrl": args.bgm_url or ""}
    data = api_call(cfg, "POST", "/animeGardenList", params=params)
    if args.json:
        print_json(data)
        return
    for week in data if isinstance(data, list) else []:
        label = week.get("weekLabel")
        items = week.get("items") or []
        if not items:
            continue
        print("=== {} ===".format(label))
        for it in items:
            print("  {}  bgmId: {}".format(it.get("title") or "-", it.get("bgmId") or "-"))


def cmd_garden_groups(args):
    cfg = effective_config(args)
    data = api_call(cfg, "POST", "/animeGardenGroup", params={"bgmId": args.bgm_id})
    if args.json:
        print_json(data)
        return
    for g in data if isinstance(data, list) else []:
        print("== {}".format(g.get("label") or "-"))
        print("   RSS: {}".format(g.get("rss") or ""))


def cmd_bgm(args):
    cfg = effective_config(args)
    data = api_call(cfg, "POST", "/searchBgm", params={"name": args.name})
    if args.json:
        print_json(data)
        return
    items = data if isinstance(data, list) else []
    if not items:
        print("未搜索到 BGM 条目")
        return
    print("共 {} 条： (可用 bgm to-ani <id> 转成订阅配置)".format(len(items)))
    for it in items:
        name = it.get("nameCn") or it.get("name") or "-"
        bid = it.get("id") or "-"
        eps = it.get("eps")
        date = (it.get("date") or "")[:10]
        score = it.get("rating", {})
        score = score.get("score") if isinstance(score, dict) else None
        score_s = "{:.1f}".format(score) if isinstance(score, (int, float)) else "-"
        print("  [{}] {}  评分 {}  集数 {}  {}".format(bid, name, score_s, eps or "-", date))
        if it.get("url"):
            print("       {}".format(it.get("url")))


def cmd_bgm_to_ani(args):
    cfg = effective_config(args)
    data = api_call(cfg, "POST", "/getAniBySubjectId", params={"id": args.subject_id})
    if args.json:
        print_json(data)
        return
    print("bgmId={} 已转换为订阅配置，可用 --patch 方式传入 subscribe：".format(args.subject_id))
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _build_ani(args, cfg):
    """根据参数构造 Ani 配置（优先 rssToAni 解析，可再覆盖）。"""
    if getattr(args, "url", None):
        dto = {"url": args.url, "type": args.type or "mikan"}
        if args.bgm_url:
            dto["bgmUrl"] = args.bgm_url
        if args.subgroup:
            dto["subgroup"] = args.subgroup
        enable = getattr(args, "enable", None)
        if enable is not None:
            dto["enable"] = enable
        ani = api_call(cfg, "POST", "/rssToAni", body=dto)
    else:
        raise CliError("缺少 --url（RSS 地址）")
    if not isinstance(ani, dict):
        raise CliError("RSS 解析结果异常")

    ani = dict(ani)
    if getattr(args, "title", None):
        ani["title"] = args.title
    if getattr(args, "season", None):
        ani["season"] = int(args.season)
    if getattr(args, "offset", None):
        ani["offset"] = int(args.offset)
    if getattr(args, "download_new", False):
        ani["downloadNew"] = True
    if getattr(args, "match", None):
        ani["match"] = list(args.match)
    for kv in getattr(args, "set_fields", None) or []:
        if kv.count("=") != 1:
            raise CliError("--set 参数格式应为 key=value: {}".format(kv))
        k, v = kv.split("=", 1)
        v = v.strip()
        if v.lower() in ("true", "false"):
            v = bool(v.lower() == "true")
        elif v.isdigit():
            v = int(v)
        ani[k] = v
    ani["enable"] = not bool(getattr(args, "disable", False))
    return ani


def _show_preview(args, cfg, ani):
    data = api_call(cfg, "POST", "/previewAni", body=ani)
    if args.json:
        return data
    print("下载目录 : {}".format(data.get("downloadPath", "-")))
    items = data.get("items") or []
    omit = data.get("omitList") or []
    msg = "命中 {} 条".format(len(items))
    if omit:
        msg += "，遗漏检测列表: {}".format(omit)
    print(msg)
    for it in items:
        ep = it.get("episode")
        ep_s = "第{}集".format(int(ep)) if isinstance(ep, (int, float)) else "-"
        done = "已下载" if it.get("hasDownloaded") else "未下载"
        title = it.get("title") or "-"
        size = it.get("formatSize") or "-"
        print("  {}  [{} / {}]  {}".format(ep_s, done, size, title))
    return data


def cmd_preview(args):
    cfg = effective_config(args)
    ani = _build_ani(args, cfg)
    if args.json:
        data = _show_preview(args, cfg, ani)
        print_json(data)
        return
    print("== 订阅配置 ==")
    print("标题     : {}".format(ani.get("title", "-")))
    print("RSS      : {}".format(ani.get("url", "-")))
    print("类型     : {}  字幕组: {}".format(ani.get("type", "-"), ani.get("subgroup", "-")))
    match_list = ani.get("match")
    if match_list:
        print("标题匹配 : {}".format(", ".join(match_list)))
    if ani.get("bgmUrl"):
        print("BGM      : {}".format(ani["bgmUrl"]))
    print("== 预览命中 ==")
    _show_preview(args, cfg, ani)


def cmd_subscribe(args):
    cfg = effective_config(args)
    ani = _build_ani(args, cfg)
    if getattr(args, "preview", False) and not args.json:
        print("== 预览命中 ==")
        _show_preview(args, cfg, ani)
        print()
    if args.json:
        data = api_call(cfg, "POST", "/addAni", body=ani)
        print_json(data)
        return
    print("即将添加订阅：")
    print("  标题 : {}".format(ani.get("title", "-")))
    print("  RSS  : {}".format(ani.get("url", "-")))
    print("  字幕组: {}  启用: {}".format(ani.get("subgroup", "-"), fmt_bool(ani.get("enable", True))))
    match_list = ani.get("match")
    if match_list:
        print("  标题匹配: {}".format(", ".join(match_list)))
    if args.dry_run:
        print("(--dry-run) 未实际添加，生成的订阅配置：")
        print_json(ani)
        return
    if not args.no_confirm:
        answer = input("确认添加该订阅? [Y/n] ").strip().lower()
        if answer in ("n", "no"):
            print("已取消")
            return
    data = api_call(cfg, "POST", "/addAni", body=ani)
    print("已添加订阅: {}".format(ani.get("title", "-")))
    if isinstance(data, dict) and data.get("id"):
        print("订阅 id  : {}".format(data["id"]))


def cmd_list(args):
    cfg = effective_config(args)
    data = api_call(cfg, "POST", "/listAni")
    if args.json:
        print_json(data)
        return
    week_list = data.get("weekList") or []
    all_ani = []
    for week in week_list:
        all_ani.extend(week.get("items") or [])
    total = data.get("total")
    print("订阅总数: {}（page 仅一页，--json 可看全量）".format(total if total is not None else len(all_ani)))
    if args.enabled:
        enabled_f = True
    elif args.disabled:
        enabled_f = False
    else:
        enabled_f = None
    for week in week_list:
        items = [it for it in (week.get("items") or []) if
                 (enabled_f is None or it.get("enable") == enabled_f)]
        if not items:
            continue
        print("=== {} ({}) ===".format(week.get("weekLabel"), len(items)))
        for it in items:
            aid = it.get("id") or "-"
            title = it.get("title") or "-"
            season = fmt_season(it.get("season"))
            ep = "{}/{}".format(it.get("currentEpisodeNumber") or 0, it.get("totalEpisodeNumber") or 0)
            en = "启用" if it.get("enable") else "停用"
            sub = it.get("subgroup") or "-"
            cur = "{}-{}".format(aid[:8], aid[-8:]) if aid and isinstance(aid, str) and len(aid) > 16 else aid
            print("  [{}]  {}  [{}]  {}/{}集  {}  {}".format(cur, title, season, ep.split("/")[0], ep.split("/")[1], en, sub))


def cmd_enable(args):
    cmd_batch_enable(args, True)


def cmd_disable(args):
    cmd_batch_enable(args, False)


def cmd_batch_enable(args, value):
    cfg = effective_config(args)
    ids = args.ids
    api_call(cfg, "POST", "/batchEnable", params={"value": str(value).lower()}, body=ids)
    print("已{} {} 个订阅".format("启用" if value else "停用", len(ids)))


def cmd_delete(args):
    cfg = effective_config(args)
    api_call(cfg, "POST", "/deleteAni", params={"deleteFiles": str(args.delete_files).lower()},
             body=args.ids)
    print("已删除 {} 个订阅 (同时删除文件: {})".format(len(args.ids), "是" if args.delete_files else "否"))


def cmd_set(args):
    cfg = effective_config(args)
    aid = args.id
    data = api_call(cfg, "POST", "/listAni")
    ani = None
    for week in (data.get("weekList") or []):
        for it in (week.get("items") or []):
            if it.get("id") == aid:
                ani = it
                break
    if ani is None:
        raise CliError("未找到订阅 id={}（可用 list 查看 id）".format(aid))
    ani = dict(ani)
    if getattr(args, "url", None):
        ani["url"] = args.url
    if getattr(args, "type", None):
        ani["type"] = args.type
    if getattr(args, "bgm_url", None):
        ani["bgmUrl"] = args.bgm_url
    if getattr(args, "subgroup", None):
        ani["subgroup"] = args.subgroup
    if getattr(args, "title", None):
        ani["title"] = args.title
    if getattr(args, "season", None):
        ani["season"] = int(args.season)
    if getattr(args, "enable", False):
        ani["enable"] = True
    if getattr(args, "disable", False):
        ani["enable"] = False
    if getattr(args, "match", None):
        ani["match"] = list(args.match)
    for kv in getattr(args, "set_fields", None) or []:
        if kv.count("=") != 1:
            raise CliError("--set 参数格式应为 key=value: {}".format(kv))
        k, v = kv.split("=", 1)
        v = v.strip()
        if v.lower() in ("true", "false"):
            v = bool(v.lower() == "true")
        elif v.isdigit():
            v = int(v)
        ani[k] = v
    if getattr(args, "dry_run", False):
        print("(--dry-run) 将更新的订阅配置：")
        print_json(ani)
        return
    params = {"move": str(getattr(args, "move", False)).lower()}
    api_call(cfg, "POST", "/setAni", params=params, body=ani)
    print("已更新订阅: {}  url={}  subgroup={}".format(ani.get("title", aid), ani.get("url", "-"),
                                                    ani.get("subgroup", "-")))


def cmd_refresh(args):
    cfg = effective_config(args)
    if args.all:
        api_call(cfg, "POST", "/refreshAll")
        print("已开始刷新全部订阅")
        return
    if not args.ids:
        raise CliError("需要指定订阅 id 或使用 --all")
    for aid in args.ids:
        api_call(cfg, "POST", "/refreshAni", body={"id": aid})
    print("已开始刷新 {} 个订阅".format(len(args.ids)))


def cmd_import(args):
    cfg = effective_config(args)
    if args.file == "-":
        raw = sys.stdin.read()
    else:
        with open(args.file, "r", encoding="utf-8") as f:
            raw = f.read()
    try:
        ani_list = json.loads(raw)
    except Exception as e:
        raise CliError("导入文件不是合法 JSON: {}".format(e))
    if not isinstance(ani_list, list):
        raise CliError("导入 JSON 应为 Ani 对象数组")
    conflict = args.conflict.upper()
    body = {"filename": args.filename or os.path.basename(args.file), "conflict": conflict,
            "aniList": ani_list}
    api_call(cfg, "POST", "/importAni", body=body)
    print("已导入 {} 个订阅 (冲突策略: {})".format(len(ani_list), conflict))


# ------------------------------------------------------------------ main --

def build_parser():
    p = argparse.ArgumentParser(prog="ani-rss-cli", description="ANI-RSS 番剧订阅命令行工具")
    p.add_argument("--config", metavar="FILE", help="配置文件路径（默认 ~/.config/ani_rss_cli/config.json）")
    p.add_argument("--base-url", metavar="URL", help="临时指定 ani-rss 地址（不写入配置）")
    p.add_argument("--auth", choices=["apikey", "login"], help="临时指定鉴权方式")
    p.add_argument("--api-key", metavar="KEY", help="临时指定 API Key")
    p.add_argument("--username", metavar="U", help="临时指定登录用户名")
    p.add_argument("--password", metavar="P", help="临时指定登录密码")
    p.add_argument("--timeout", type=int, default=60, help="请求超时秒数")
    p.add_argument("--debug", action="store_true", help="打印 HTTP 请求/响应")
    p.add_argument("--version", action="version", version="ani-rss-cli {}".format(VERSION))

    sub = p.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", dest="json", action="store_true", default=argparse.SUPPRESS,
                        help="输出原始 JSON")

    # config
    pc = sub.add_parser("config", help="配置管理")
    pc_sub = pc.add_subparsers(dest="config_sub", required=True)
    pc_init = pc_sub.add_parser("init", help="初始化配置")
    pc_init.add_argument("--base-url")
    pc_init.add_argument("--auth", choices=["apikey", "login"])
    pc_init.add_argument("--api-key")
    pc_init.add_argument("--username")
    pc_init.add_argument("--password")
    pc_init.set_defaults(func=cmd_config)
    pc_set = pc_sub.add_parser("set", help="设置单一项")
    pc_set.add_argument("key")
    pc_set.add_argument("value")
    pc_set.set_defaults(func=cmd_config)
    pc_get = pc_sub.add_parser("get", help="查看配置")
    pc_get.add_argument("key", nargs="?")
    pc_get.set_defaults(func=cmd_config)
    pc_path = pc_sub.add_parser("path", help="打印配置路径")
    pc_path.set_defaults(func=cmd_config)
    pc_status = pc_sub.add_parser("status", help="查看配置与连通性")
    pc_status.set_defaults(func=cmd_config)

    p.add_argument("--json", dest="json", action="store_true", help="输出原始 JSON")
    pping = sub.add_parser("ping", parents=[common], help="连通性检测")
    pping.set_defaults(func=cmd_ping)

    # mikan
    pm = sub.add_parser("mikan", help="Mikan 搜索")
    pm_sub = pm.add_subparsers(dest="mikan_sub", required=True)
    pm_s = pm_sub.add_parser("search", parents=[common], help="搜索番剧")
    pm_s.add_argument("text", nargs="?", default="")
    pm_s.add_argument("--year", type=int, help="季度年份，如 2026")
    pm_s.add_argument("--season", choices=["春", "夏", "秋", "冬"], help="季度")
    pm_s.set_defaults(func=cmd_mikan)
    pm_g = pm_sub.add_parser("groups", parents=[common], help="获取字幕组 RSS")
    pm_g.add_argument("url", help="Mikan 番剧页面 URL")
    pm_g.add_argument("--items", action="store_true", help="同时列出该字幕组上传的版本标题")
    pm_g.set_defaults(func=cmd_mikan_groups)

    # anibt
    pb = sub.add_parser("anibt", help="AniBT")
    pb_sub = pb.add_subparsers(dest="anibt_sub", required=True)
    pb_l = pb_sub.add_parser("list", parents=[common], help="番剧列表")
    pb_l.add_argument("--season")
    pb_l.add_argument("--bgm-url")
    pb_l.add_argument("--title")
    pb_l.set_defaults(func=cmd_anibt)
    pb_g = pb_sub.add_parser("groups", parents=[common], help="字幕组 RSS")
    pb_g.add_argument("bgm_id")
    pb_g.set_defaults(func=cmd_anibt_groups)

    # anime garden
    pg = sub.add_parser("garden", help="AnimeGarden")
    pg_sub = pg.add_subparsers(dest="garden_sub", required=True)
    pg_l = pg_sub.add_parser("list", parents=[common], help="番剧列表")
    pg_l.add_argument("--bgm-url", default="")
    pg_l.set_defaults(func=cmd_garden_list)
    pg_g = pg_sub.add_parser("groups", parents=[common], help="字幕组 RSS")
    pg_g.add_argument("bgm_id")
    pg_g.set_defaults(func=cmd_garden_groups)

    # bgm
    pb2 = sub.add_parser("bgm", help="Bangumi 搜索")
    pb2_sub = pb2.add_subparsers(dest="bgm_sub", required=True)
    pb2_s = pb2_sub.add_parser("search", parents=[common], help="搜索 BGM 条目")
    pb2_s.add_argument("name")
    pb2_s.set_defaults(func=cmd_bgm)
    pb2_a = pb2_sub.add_parser("to-ani", parents=[common], help="按 BGM subject id 转换订阅配置")
    pb2_a.add_argument("subject_id")
    pb2_a.set_defaults(func=cmd_bgm_to_ani)

    def add_ani_args(sp):
        sp.add_argument("--url", help="RSS 地址")
        sp.add_argument("--type", choices=["mikan", "ani-bt", "anime-garden", "other"], help="RSS 类型")
        sp.add_argument("--bgm-url")
        sp.add_argument("--subgroup", help="字幕组名")
        sp.add_argument("--enable", action="store_true", help="启用订阅")
        sp.add_argument("--disable", action="store_true", help="停用订阅")
        sp.add_argument("--title", help="覆盖标题")
        sp.add_argument("--season", type=int, help="覆盖季度（如 20263）")
        sp.add_argument("--offset", type=int, help="集数偏移")
        sp.add_argument("--download-new", action="store_true", help="只下载最新集")
        sp.add_argument("--match", dest="match", action="append", metavar="关键词", help="标题关键词匹配（正则，可重复），用于筛选同一字幕组内的不同版本，仅命中全部关键词的资源才下载")
        sp.add_argument("--set", dest="set_fields", action="append", metavar="k=v", help="覆盖任意 Ani 字段")

    pp = sub.add_parser("preview", parents=[common], help="预览订阅命中")
    add_ani_args(pp)
    pp.set_defaults(func=cmd_preview)

    ps = sub.add_parser("subscribe", parents=[common], help="添加订阅")
    add_ani_args(ps)
    ps.add_argument("--preview", action="store_true", help="先预览命中")
    ps.add_argument("--dry-run", action="store_true", help="只生成配置不添加")
    ps.add_argument("--no-confirm", action="store_true", help="跳过确认")
    ps.set_defaults(func=cmd_subscribe)

    pl = sub.add_parser("list", parents=[common], help="订阅列表")
    pl.add_argument("--enabled", dest="enabled", action="store_true", help="只显示启用")
    pl.add_argument("--disabled", dest="disabled", action="store_true", help="只显示停用")
    pl.set_defaults(func=cmd_list)

    pe = sub.add_parser("enable", parents=[common], help="启用订阅")
    pe.add_argument("ids", nargs="+")
    pe.set_defaults(func=cmd_enable)
    pd = sub.add_parser("disable", parents=[common], help="停用订阅")
    pd.add_argument("ids", nargs="+")
    pd.set_defaults(func=cmd_disable)
    pdel = sub.add_parser("delete", parents=[common], help="删除订阅")
    pdel.add_argument("--delete-files", action="store_true", help="同时删除下载文件")
    pdel.add_argument("ids", nargs="+")
    pdel.set_defaults(func=cmd_delete)

    ps = sub.add_parser("set", parents=[common], help="修改订阅字段")
    ps.add_argument("id", help="订阅 id（用 list --json 查看）")
    ps.add_argument("--url", help="RSS 地址")
    ps.add_argument("--type", help="下载类型")
    ps.add_argument("--bgm-url", help="bangumi 页面地址")
    ps.add_argument("--subgroup", help="字幕组名称")
    ps.add_argument("--title", help="标题")
    ps.add_argument("--season", help="季度（整数字符串）")
    ps.add_argument("--enable", action="store_true", help="启用")
    ps.add_argument("--disable", action="store_true", help="停用")
    ps.add_argument("--move", action="store_true", help="同步移动已下载文件到新目录")
    ps.add_argument("--match", dest="match", action="append", metavar="关键词", help="标题关键词匹配（正则，可重复），覆盖订阅的标题匹配列表")
    ps.add_argument("--set", dest="set_fields", action="append", metavar="k=v", help="直接设置任意字段")
    ps.add_argument("--dry-run", action="store_true", help="只打印将写入的配置，不调用")
    ps.set_defaults(func=cmd_set)

    pr = sub.add_parser("refresh", parents=[common], help="刷新 RSS")
    pr.add_argument("--all", action="store_true", help="刷新全部")
    pr.add_argument("ids", nargs="*")
    pr.set_defaults(func=cmd_refresh)

    pi = sub.add_parser("import", parents=[common], help="批量导入订阅")
    pi.add_argument("file", help="Ani JSON 数组文件，或 - 表示 stdin")
    pi.add_argument("--conflict", choices=["REPLACE", "SKIP"], default="SKIP", help="冲突策略")
    pi.add_argument("--filename", help="导入文件名")
    pi.set_defaults(func=cmd_import)

    return p


def main():
    global CONFIG_FILE, STATE
    args = build_parser().parse_args()
    if args.config:
        CONFIG_FILE = os.path.abspath(args.config)
    STATE["debug"] = args.debug
    STATE["timeout"] = args.timeout
    try:
        args.func(args)
    except CliError as e:
        print("错误: {}".format(e), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n已取消", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()