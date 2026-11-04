#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
乔侨爱学习 · 风格自训练脚本 (qiaoqiao.py)

把业务表格喂进来，自动拆出「每个人 / 每个账号」的口播风格卡 + 语料库。
纯本地抽取与统计：不联网、不调模型、不改原表、不编造任何数字。

用法：
  python qiaoqiao.py learn  <表格.xlsx> [--style 名字] [--owner 归属人] [--sheet 名] [--replace]
  python qiaoqiao.py list
  python qiaoqiao.py show   <风格名>
  python qiaoqiao.py topics <风格名>
  python qiaoqiao.py check  <草稿.txt> --style <风格名>
  python qiaoqiao.py forget <风格名>

训练成果默认写在技能目录的 learned/ 下（可用 --out 指定别处）。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import statistics
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "learned"
TZ = timezone(timedelta(hours=8))

# ---------------------------------------------------------------- 表头识别

CANON = {
    "序号": ["序号", "编号", "no", "index", "#"],
    "选题方向": ["选题方向", "选题", "方向", "主题", "角度"],
    "3秒爆点开头": ["3秒爆点开头", "3秒开头", "爆点开头", "涉爆点开头", "开头", "钩子", "hook"],
    "完整口播脚本": ["完整口播脚本", "完整口播稿", "口播脚本", "口播稿", "完整脚本", "正文", "脚本", "body"],
    "抖音标题": ["抖音标题", "抖音", "douyin"],
    "小红书标题": ["小红书标题", "小红书", "xhs"],
    "视频号标题": ["视频号标题", "视频号", "shipinhao"],
    "发布文案": ["发布文案", "发布", "文案", "caption"],
    "话题标签": ["话题标签", "标签", "hashtag", "tags"],
    "生成日期": ["生成日期", "日期", "date"],
    "提词器直接复制版": ["提词器直接复制版", "提词器版", "提词器"],
}
BODY_KEYS = ("完整口播脚本",)
META_LABELS = {
    "平台", "账号名称", "运营人", "口播方", "垂直内容", "认证", "备注", "主体",
    "负责人", "出镜", "账号", "风格", "定位", "人群", "地区", "认证/实名/主体备注（原文）",
}
PLATFORM_LABELS = {"抖音", "小红书", "视频号", "快手", "b站", "B站", "公众号"}

BANNED = {
    "承诺类": ["包过", "保过", "稳过", "免考", "不过退款", "保证拿证", "直接拿证", "替考",
             "托管代刷", "一年拿证", "一年半拿证", "内部指标"],
    "绝对化（广告法）": ["最好", "最佳", "唯一", "顶级", "国家级", "绝对", "100%", "无门槛",
                    "必过", "第一品牌", "最权威", "最低价"],
    "挂靠类": ["官方指定", "唯一官方渠道", "国家承认的正规学历", "包分配", "学历=落户", "学历=入户"],
}
ENTITY_WORDS = [
    "国家开放大学", "广东开放大学", "国开", "广开", "畜牧兽医", "成人高考", "成考",
    "自学考试", "自考", "小自考", "大自考", "专本套读", "学位证", "学信网",
    "华南理工", "华工", "华南农业大学", "华农", "广东外语外贸大学", "广外", "广州大学", "广大",
    "岭南师范学院", "岭师", "桂林电子科技大学", "桂电", "广东财经大学", "广财",
    "广东工业大学", "广工", "执业兽医", "助学加分", "视觉传达设计", "工商管理", "法学",
]
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF]")
TAG_RE = re.compile(r"#[^\s#，,。、]+")
NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
SENT_SPLIT = re.compile(r"[。！？!?\n]+")


def norm(s) -> str:
    return re.sub(r"[\s\u3000]+", "", str(s or "")).strip().lower()


def clean(s) -> str:
    return "" if s is None else str(s).strip()


def canon_map(header_row) -> dict:
    """返回 {规范列名: 列下标}；要求必须能定位到口播正文列。"""
    cells = [norm(c) for c in header_row]
    found = {}
    for key, aliases in CANON.items():
        for i, cell in enumerate(cells):
            if not cell:
                continue
            for alias in aliases:
                if cell == norm(alias) or (len(alias) >= 3 and norm(alias) in cell):
                    if key not in found:
                        found[key] = i
                    break
    if not any(k in found for k in BODY_KEYS):
        return {}
    return found


def load_table(path: Path):
    """-> [(sheet名, rows:list[list[str]]), ...]"""
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xlsm"):
        import openpyxl
        wb = openpyxl.load_workbook(path, data_only=True)
        out = []
        for ws in wb.worksheets:
            rows = [[clean(c) for c in r] for r in ws.iter_rows(values_only=True)]
            out.append((ws.title, rows))
        return out
    if suffix in (".csv", ".tsv"):
        delim = "\t" if suffix == ".tsv" else ","
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            rows = [[clean(c) for c in r] for r in csv.reader(f, delimiter=delim)]
        return [(path.stem, rows)]
    if suffix == ".jsonl":
        with path.open("r", encoding="utf-8-sig") as f:
            objs = [json.loads(l) for l in f if l.strip()]
        if not objs:
            return [(path.stem, [])]
        keys = list(objs[0].keys())
        rows = [keys] + [[clean(o.get(k, "")) for k in keys] for o in objs]
        return [(path.stem, rows)]
    if suffix == ".xls":
        raise SystemExit(
            "读不了 .xls（老版二进制格式）。请另存为 .xlsx 再喂给我，或用 Excel 打开后「另存为 → Excel 工作簿(.xlsx)」。"
        )
    raise SystemExit("不支持的文件类型：%s（支持 .xlsx/.xlsm/.csv/.tsv/.jsonl）" % suffix)


def parse_sheet(rows):
    """定位表头、抽元数据与记录。返回 (meta, records, schema_note)。"""
    best_i, best_map = None, {}
    for i, row in enumerate(rows[:60]):
        m = canon_map(row)
        if len(m) > len(best_map):
            best_i, best_map = i, m
    if best_i is None:
        # 兜底：没有标准表头时，把「平均文本最长」的列当正文
        if not rows:
            return {}, [], "generic/empty"
        width = max(len(r) for r in rows)
        scores = []
        for col in range(width):
            texts = [clean(r[col]) if col < len(r) else "" for r in rows]
            scores.append(statistics.mean([len(t) for t in texts]) if texts else 0)
        body_col = max(range(width), key=lambda c: scores[c])
        recs = []
        for r in rows:
            body = clean(r[body_col]) if body_col < len(r) else ""
            if len(body) >= 40:
                recs.append({"完整口播脚本": body, "序号": clean(r[0]) if r else ""})
        return {}, recs, "generic/最长文本列当正文（未识别到标准表头，风格卡的部分字段会留空）"

    meta = {}
    for r in rows[:best_i]:
        cells = [clean(c) for c in r]
        first = cells[0] if cells else ""
        if not first and not any(cells):
            continue
        title_accounts = TAG_RE  # keep alias unused
        accs = re.findall(r"「([^」]+)」", " ".join(cells))
        if accs:
            meta.setdefault("三号同发", " ｜ ".join(accs))
            meta.setdefault("组标题", " ".join(cells)[:200])
        label = first.replace(":", "").replace("：", "").strip()
        value = " ".join([c for c in cells[1:] if c])[:200]
        if label in META_LABELS or label in PLATFORM_LABELS:
            if value and not (label == "平台" and "账号名称" in value):
                meta[label] = value
        elif re.match(r"^运营|^口播|^垂直", label):
            meta[label] = value

    width = max((len(r) for r in rows), default=0)
    recs = []
    auto_seq = 0
    for r in rows[best_i + 1:]:
        cells = list(r) + [""] * (width - len(r))
        rec = {k: clean(cells[i]) if i < len(cells) else "" for k, i in best_map.items()}
        body = rec.get("完整口播脚本", "")
        if len(body) < 40:
            continue
        auto_seq += 1
        if not rec.get("序号"):
            rec["序号"] = str(auto_seq)
        recs.append(rec)
    return meta, recs, "standard/识别到表头：%s" % "、".join(best_map.keys())


# ---------------------------------------------------------------- 风格统计

def first_sentence(text: str, limit=48) -> str:
    parts = [p.strip() for p in SENT_SPLIT.split(text) if p.strip()]
    s = parts[0] if parts else text[:limit]
    return s[:limit]


def last_sentence(text: str, limit=48) -> str:
    parts = [p.strip() for p in SENT_SPLIT.split(text) if p.strip()]
    s = parts[-1] if parts else text[-limit:]
    return s[-limit:]


def body_hash(text: str) -> str:
    return hashlib.md5(re.sub(r"\s+", "", text).encode("utf-8")).hexdigest()


def analyze(recs, meta, sources, meta_schema=""):
    bodies = [r["完整口播脚本"] for r in recs]
    length = [len(b) for b in bodies]
    full = "\n".join(bodies)
    n = max(len(recs), 1)

    person_counts = {k: full.count(k) for k in ["老师", "同学们", "我们", "你们", "你", "我不允许", "我"]}
    if person_counts["老师"] >= n and person_counts["我"] < person_counts["老师"] * 0.6:
        voice = "第三人称「老师」口播（老师讲给同学听），不是第一人称自述"
    elif person_counts["我不允许"] or person_counts["我"] > person_counts["老师"]:
        voice = "第一人称「我/我们」直呼式口播"
    else:
        voice = "混合人称，以语料为准"

    hooks = [first_sentence(b) for b in bodies]
    hook_prefix = Counter(h[:4] for h in hooks if h)
    structure_markers = ["第一，", "第二，", "第三，", "第四步", "第三步", "第二步", "第一步",
                         "最后", "先说", "再说", "首先", "其次", "第一句", "第二句", "第三句",
                         "第一段", "第二段", "第一个", "第二个", "第三个"]
    marker_counts = {m: full.count(m) for m in structure_markers}
    marker_counts = {k: v for k, v in marker_counts.items() if v}

    punct = {p: full.count(p) for p in ["!", "！", "~", "～", ",", "，", "？", "?", "；", "：", "、"]}
    para_counts = [len([p for p in b.split("\n\n") if p.strip()]) for b in bodies]

    endings = [last_sentence(b) for b in bodies]
    ending_types = Counter()
    for e in endings:
        if any(w in e for w in ["留言", "收藏", "关注", "问", "了解"]):
            ending_types["引导互动（留言/收藏/咨询）"] += 1
        elif any(w in e for w in ["吗", "？", "?"]):
            ending_types["反问收尾"] += 1
        elif any(w in e for w in ["规划", "准备", "开始", "别", "一定要", "记牢"]):
            ending_types["行动建议/提醒"] += 1
        elif any(w in e for w in ["适合", "关键", "重点", "才是", "就是"]):
            ending_types["观点落点"] += 1
        else:
            ending_types["陈述收尾"] += 1

    titles = {}
    for key in ["抖音标题", "小红书标题", "视频号标题"]:
        vals = [clean(r.get(key)) for r in recs if clean(r.get(key))]
        if vals:
            titles[key] = {
                "篇数": len(vals),
                "平均字数": round(statistics.mean([len(v) for v in vals]), 1),
                "带emoji": sum(bool(EMOJI_RE.search(v)) for v in vals),
                "带数字": sum(bool(re.search(r"\d", v)) for v in vals),
            }

    tag_text = "\n".join([clean(r.get("话题标签")) + " " + clean(r.get("发布文案")) for r in recs])
    tags = Counter(TAG_RE.findall(tag_text))

    numbers = Counter(t for t in NUM_RE.findall(full) if len(t.replace(",", "")) >= 2)
    entities = Counter({w: full.count(w) for w in ENTITY_WORDS if full.count(w)})
    topics = [clean(r["选题方向"]) for r in recs if clean(r.get("选题方向"))]
    banned_hits = {}
    for cat, words in BANNED.items():
        hits = {w: full.count(w) for w in words if full.count(w)}
        if hits:
            banned_hits[cat] = hits

    return {
        "语料篇数": n,
        "字数": {
            "最短": min(length) if length else 0,
            "最长": max(length) if length else 0,
            "平均": round(statistics.mean(length), 1) if length else 0,
            "中位数": round(statistics.median(length), 1) if length else 0,
        },
        "估算时长_按300字每分钟": {
            "最短分钟": round(min(length) / 300, 2) if length else 0,
            "最长分钟": round(max(length) / 300, 2) if length else 0,
        },
        "人称": {"判定": voice, "词频": person_counts},
        "钩子": {
            "前4字高频": hook_prefix.most_common(12),
            "样例": hooks[:5],
        },
        "结构": {
            "分点标记词频": dict(Counter(marker_counts).most_common()),
            "双换行分段数_平均": round(statistics.mean(para_counts), 1) if para_counts else 0,
        },
        "标点": punct,
        "结尾": {"类型分布": dict(ending_types.most_common()), "样例": endings[:5]},
        "标题": titles,
        "话题标签Top": tags.most_common(12),
        "高频数字": numbers.most_common(20),
        "业务实体词频": entities.most_common(20),
        "选题库": topics,
        "禁用词语料命中": banned_hits,
        "来源": sources,
        "配置": meta,
        "表头识别": meta_schema,
        "指纹": hashlib.sha256("\n".join(sorted(body_hash(b) for b in bodies)).encode()).hexdigest()[:16],
    }


def md_table(pairs):
    out = ["| 项 | 值 |", "|---|---|"]
    for k, v in pairs:
        out.append("| %s | %s |" % (k, str(v).replace("|", "\\|").replace("\n", " ")))
    return "\n".join(out)


def render_card(name, owner, a, style_id):
    s = []
    s.append("# 风格卡：%s" % name)
    s.append("")
    s.append("> 由「乔侨爱学习」脚本自动训练生成 · 风格ID `%s` · 语料 %d 篇 · 归属人 %s" %
             (style_id, a["语料篇数"], owner or "未指定"))
    s.append("> 本卡只描述**怎么写**（语感/结构/体例），**不授权数字**：里面的数字是语料观察值，写新稿必须用当次官方表核对。")
    if "generic/" in a.get("表头识别", ""):
        s.append("> ⚠️ **表头降级**：%s —— 标题/标签/选题等字段会留空，补齐标准表头能学到更全的风格。" % a["表头识别"])
    s.append("")
    s.append("## 1. 账号 / 身份配置")
    s.append("")
    s.append(md_table(list(a["配置"].items())) if a["配置"] else "_（表格里没有账号配置区）_")
    s.append("")
    s.append("## 2. 语料与体量")
    s.append("")
    s.append(md_table([
        ("语料篇数", a["语料篇数"]),
        ("字数 最短/中位/平均/最长", "%s / %s / %s / %s" % (
            a["字数"]["最短"], a["字数"]["中位数"], a["字数"]["平均"], a["字数"]["最长"])),
        ("估算时长（300字/分钟）", "%s–%s 分钟" % (
            a["估算时长_按300字每分钟"]["最短分钟"], a["估算时长_按300字每分钟"]["最长分钟"])),
        ("语料指纹", a["指纹"]),
        ("来源文件", "；".join(a["来源"])),
    ]))
    s.append("")
    s.append("## 3. 人称与口播身份")
    s.append("")
    s.append("- **判定**：%s" % a["人称"]["判定"])
    s.append("- **词频**：%s" % "、".join("%s×%d" % (k, v) for k, v in a["人称"]["词频"].items()))
    s.append("")
    s.append("## 4. 3秒爆点开头（钩子）")
    s.append("")
    s.append("- 开头前4字高频：%s" % "、".join("%s(%d)" % (k, v) for k, v in a["钩子"]["前4字高频"]))
    for i, h in enumerate(a["钩子"]["样例"], 1):
        s.append("- 样例%d：%s" % (i, h))
    s.append("")
    s.append("## 5. 正文结构")
    s.append("")
    s.append("- 分点标记词频：%s" % ("、".join("%s×%d" % (k, v) for k, v in a["结构"]["分点标记词频"].items()) or "（无明显分点词，靠段落推进）"))
    s.append("- 双换行分段数（平均）：%s 段" % a["结构"]["双换行分段数_平均"])
    s.append("")
    s.append("## 6. 语气与标点")
    s.append("")
    s.append("- 全语料标点计数：%s" % "、".join("%s×%d" % (k, v) for k, v in a["标点"].items()))
    mixed = sum(a["标点"].get(k, 0) for k in ["!", "！", "~", "～", ","])
    if mixed > 0:
        s.append("- 存在混排口语标点（! ~ , 共 %d 处）：写新稿保留口语感，不要统一改成书面标点。" % mixed)
    else:
        s.append("- 该风格**通篇中文标点**（无 ! ~ 半角逗号混排），写新稿也用规范中文标点；口语感靠句式和「老师／你」的对话推进，不靠标点花活。")
    s.append("")
    s.append("## 7. 结尾方式")
    s.append("")
    s.append("- 类型分布：%s" % "、".join("%s %d篇" % (k, v) for k, v in a["结尾"]["类型分布"].items()))
    for i, e in enumerate(a["结尾"]["样例"], 1):
        s.append("- 样例%d：…%s" % (i, e))
    s.append("")
    s.append("## 8. 三平台标题")
    s.append("")
    if a["标题"]:
        s.append("| 平台 | 篇数 | 平均字数 | 带emoji | 带数字 |")
        s.append("|---|---|---|---|---|")
        for k, v in a["标题"].items():
            s.append("| %s | %s | %s | %s | %s |" % (k, v["篇数"], v["平均字数"], v["带emoji"], v["带数字"]))
    else:
        s.append("_（语料没有标题列）_")
    s.append("")
    s.append("## 9. 话题标签")
    s.append("")
    s.append(" ".join("%s(%d)" % (k, v) for k, v in a["话题标签Top"]) or "_（无）_")
    s.append("")
    s.append("## 10. 选题库（写新稿前必须查重）")
    s.append("")
    for i, t in enumerate(dict.fromkeys(a["选题库"]), 1):
        s.append("%d. %s" % (i, t))
    if not a["选题库"]:
        s.append("_（语料没有选题方向列）_")
    s.append("")
    s.append("## 11. 事实口径观察值（**非官方口径，仅供参考**）")
    s.append("")
    s.append("- 语料高频数字：%s" % ("、".join("%s×%d" % (k, v) for k, v in a["高频数字"]) or "无"))
    s.append("- 业务实体词频：%s" % ("、".join("%s×%d" % (k, v) for k, v in a["业务实体词频"]) or "无"))
    s.append("- ⚠️ 这些数字是从成稿里数出来的，可能含旧口径/作废数字。**写新稿时一律以用户当次给的官方收费表为准**，不要照抄本段。")
    s.append("")
    s.append("## 12. 禁用词在语料里的既有命中（写新稿时避免）")
    s.append("")
    if a["禁用词语料命中"]:
        for cat, hits in a["禁用词语料命中"].items():
            s.append("- %s：%s" % (cat, "、".join("%s×%d" % (k, v) for k, v in hits.items())))
        s.append("- 老稿里出现不等于新稿能写；否定句里出现也算命中。")
    else:
        s.append("- 语料零命中，保持。")
    s.append("")
    s.append("## 写稿要点（自动归纳，按此卡出稿）")
    s.append("")
    s.append("1. 用「%s」；开口第一句就是钩子，正文不要重复钩子。" % a["人称"]["判定"])
    s.append("2. 正文约 %s 字（区间 %s–%s），按 %s 段推进，分点用该风格惯用标记。" % (
        a["字数"]["中位数"], a["字数"]["最短"], a["字数"]["最长"], a["结构"]["双换行分段数_平均"]))
    s.append("3. 三平台标题按第8节的字数/emoji习惯写；话题标签沿用第9节固定标签。")
    s.append("4. 选题先对第10节查重；数字先对当次官方表核对；写完跑 `qiaoqiao.py check` 自检。")
    s.append("")
    return "\n".join(s)


# ---------------------------------------------------------------- 索引与落盘

def now():
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S%z")


def slug(name: str) -> str:
    s = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", name).strip()
    return s[:80] or "unnamed"


def load_index(out: Path):
    p = out / "styles.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"version": 1, "updatedAt": "", "styles": []}


def save_index(out: Path, idx):
    idx["updatedAt"] = now()
    (out / "styles.json").write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_dirs(out: Path):
    for d in [out, out / "cards", out / "corpus"]:
        d.mkdir(parents=True, exist_ok=True)


def append_log(out: Path, event: dict):
    with (out / "learn-log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(dict(时间=now(), **event), ensure_ascii=False) + "\n")


def find_style(idx, name):
    key = name.strip()
    hits = [s for s in idx["styles"] if s["name"] == key or s["id"] == key]
    if hits:
        return hits[0]
    hits = [s for s in idx["styles"] if key in s["name"] or key in s["id"]]
    return hits[0] if len(hits) == 1 else None


def write_overview(out: Path, idx):
    s = ["# 乔侨爱学习 · 已训练风格总览", "", "更新时间：%s" % now(), "",
         "| 风格名 | 归属人 | 语料篇数 | 语料中位字数 | 来源 | 卡片 |", "|---|---|---|---|---|---|"]
    for st in idx["styles"]:
        card = (out / st["card"]).as_posix()
        s.append("| %s | %s | %s | %s | %s | [%s](%s) |" % (
            st["name"], st.get("owner", ""), st.get("rows", ""), st.get("medianLen", ""),
            "；".join(st.get("sources", []))[:80], st["name"], st["card"]))
    if len(idx["styles"]) == 0:
        s.append("| _（还没有风格，先跑 learn）_ | | | | | |")
    s += ["", "## 怎么加自己的风格", "",
          "1. 准备一张业务表（.xlsx，8列或11列体例；或者直接一列口播全文）。",
          "2. `python qiaoqiao.py learn 你的表.xlsx --style 你的风格名 --owner 你的名字`",
          "3. `python qiaoqiao.py list` 确认，`python qiaoqiao.py show 你的风格名` 看风格卡。",
          "4. 写稿前读该风格卡 + 选题库；写完用 `check` 自检。",
          "",
          "> 默认每个 sheet 训练成一个独立风格；加 `--style` 则把整张表的所有 sheet 合并成**一个**人的风格。"]
    (out / "overview.md").write_text("\n".join(s) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- 命令

def cmd_learn(args):
    path = Path(args.table).expanduser().resolve()
    if not path.exists():
        raise SystemExit("找不到表格：%s" % path)
    out = Path(args.out).expanduser().resolve() if args.out else DEFAULT_OUT
    ensure_dirs(out)
    idx = load_index(out)
    sheets = load_table(path)
    if args.sheet:
        wanted = set(args.sheet)
        sheets = [s for s in sheets if s[0] in wanted]
        if not sheets:
            raise SystemExit("没有匹配的 sheet：%s（可用：%s）" % (args.sheet, [s[0] for s in load_table(path)]))

    parsed = []
    for sheet_name, rows in sheets:
        meta, recs, schema = parse_sheet(rows)
        if not recs:
            print("  · 跳过 sheet「%s」：没抽到口播正文（%s）" % (sheet_name, schema))
            continue
        parsed.append((sheet_name, meta, recs, schema))
    if not parsed:
        raise SystemExit("整张表都没抽到口播正文，训练中止（原表未改动）。")

    groups = []
    if args.style:
        meta, recs, schemas = {}, [], []
        for sheet_name, m, rs, schema in parsed:
            for k, v in m.items():
                meta.setdefault("sheet:" + sheet_name + "/" + k, v)
            for r in rs:
                r = dict(r)
                r["_sheet"] = sheet_name
                recs.append(r)
            schemas.append("%s→%s" % (sheet_name, schema))
        groups.append((args.style, meta, recs, "；".join(schemas)))
    else:
        for sheet_name, m, rs, schema in parsed:
            groups.append((sheet_name, m, rs, schema))

    for name, meta, recs, schema in groups:
        sid = slug(name)
        existing = next((s for s in idx["styles"] if s["id"] == sid), None)
        src = "%s%s" % (path.name, ("#" + "/".join(args.sheet)) if args.sheet else "")
        if existing and not args.replace:
            old = []
            cp = out / existing["corpus"]
            if cp.exists():
                for line in cp.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        old.append(json.loads(line))
            seen = {body_hash(o["完整口播脚本"]) for o in old}
            added = [r for r in recs if body_hash(r["完整口播脚本"]) not in seen]
            all_recs = old + added
            sources = list(dict.fromkeys(existing.get("sources", []) + [src]))
            merged_meta = dict(existing.get("config", {}))
            merged_meta.update(meta)
            meta = merged_meta
            action = "增量合并：+%d 篇（去重后共 %d 篇）" % (len(added), len(all_recs))
        else:
            all_recs, sources = list(recs), [src]
            action = "新建：%d 篇" % len(all_recs)

        a = analyze(all_recs, meta, sources, schema)
        card_rel = "cards/%s.md" % sid
        corpus_rel = "corpus/%s.jsonl" % sid
        (out / card_rel).write_text(render_card(name, args.owner or (existing or {}).get("owner", ""), a, sid), encoding="utf-8")
        with (out / corpus_rel).open("w", encoding="utf-8") as f:
            for r in all_recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        entry = {
            "id": sid, "name": name, "owner": args.owner or (existing or {}).get("owner", ""),
            "rows": len(all_recs), "medianLen": a["字数"]["中位数"],
            "sources": sources, "card": card_rel, "corpus": corpus_rel,
            "schema": schema, "fingerprint": a["指纹"], "trainedAt": now(),
        }
        if existing:
            idx["styles"][idx["styles"].index(existing)] = entry
        else:
            idx["styles"].append(entry)
        append_log(out, {"动作": "learn", "风格": name, "归属人": entry["owner"],
                         "结果": action, "来源": src, "表头": schema})
        print("✓ [%s] %s → %s" % (name, action, card_rel))

    save_index(out, idx)
    write_overview(out, idx)
    print("\n共 %d 个风格，索引：%s" % (len(idx["styles"]), out / "styles.json"))


def cmd_list(args):
    out = Path(args.out).expanduser().resolve() if args.out else DEFAULT_OUT
    idx = load_index(out)
    if not idx["styles"]:
        print("（还没有风格）先跑：python qiaoqiao.py learn 你的表.xlsx --style 名字 --owner 你")
        return
    print("已训练 %d 个风格：\n" % len(idx["styles"]))
    for s in idx["styles"]:
        print("  %-24s 归属:%-10s %3d 篇  中位%s字  %s" % (
            s["name"], s.get("owner", "-"), s["rows"], s.get("medianLen", "-"), ", ".join(s["sources"])))
    print("\n详情：python qiaoqiao.py show <风格名>")


def cmd_show(args):
    out = Path(args.out).expanduser().resolve() if args.out else DEFAULT_OUT
    st = find_style(load_index(out), args.name)
    if not st:
        raise SystemExit("找不到风格「%s」。用 list 看全部。" % args.name)
    print((out / st["card"]).read_text(encoding="utf-8"))


def cmd_topics(args):
    out = Path(args.out).expanduser().resolve() if args.out else DEFAULT_OUT
    st = find_style(load_index(out), args.name)
    if not st:
        raise SystemExit("找不到风格「%s」" % args.name)
    topics = []
    for line in (out / st["corpus"]).read_text(encoding="utf-8").splitlines():
        if line.strip():
            t = clean(json.loads(line).get("选题方向"))
            if t and t not in topics:
                topics.append(t)
    print("# %s · 选题库（%d 条，写新稿前查重）\n" % (st["name"], len(topics)))
    for i, t in enumerate(topics, 1):
        print("%d. %s" % (i, t))


def cmd_check(args):
    out = Path(args.out).expanduser().resolve() if args.out else DEFAULT_OUT
    st = find_style(load_index(out), args.style)
    if not st:
        raise SystemExit("找不到风格「%s」" % args.style)
    draft = Path(args.draft).expanduser().resolve().read_text(encoding="utf-8-sig")
    corpus = [json.loads(l) for l in (out / st["corpus"]).read_text(encoding="utf-8").splitlines() if l.strip()]
    lens = [len(c["完整口播脚本"]) for c in corpus]
    n = len(draft)
    warns, oks = [], []
    if lens:
        med = statistics.median(lens)
        lo, hi = int(med * 0.75), int(med * 1.25)
        if lo <= n <= hi:
            oks.append("字数 %d 在语料中位±25%% 区间 %d–%d 内（语料中位 %d、实测最短/最长 %d/%d）" % (n, lo, hi, int(med), min(lens), max(lens)))
        elif n < lo:
            warns.append("字数 %d 偏短：语料中位 %d、最短 %d，建议补到 %d 以上，贴近该账号长口播风格" % (n, int(med), min(lens), lo))
        else:
            warns.append("字数 %d 偏长：语料中位 %d、最长 %d，超了 %d 字，建议压一压" % (n, int(med), max(lens), hi))
    else:
        oks.append("字数 %d（语料为空，未做区间校验）" % n)
    for cat, words in BANNED.items():
        for w in words:
            if w in draft:
                warns.append("禁用词[%s]：%s（否定句里也算命中）" % (cat, w))
    if not any(w in draft for w in ["同学们", "老师", "同学", "你"]):
        warns.append("开头可能缺少称呼/对话感，检查 3 秒钩子")
    seen_nums = set()
    for l in (out / st["corpus"]).read_text(encoding="utf-8").splitlines():
        if l.strip():
            seen_nums.update(NUM_RE.findall(json.loads(l).get("完整口播脚本", "")))
    new_nums = sorted({x for x in NUM_RE.findall(draft) if len(x) >= 2 and x not in seen_nums})
    if new_nums:
        warns.append("出现语料里没有的数字 %s → 必须回官方表核对，不要直接沿用旧稿" % "、".join(new_nums[:15]))
    hook = first_sentence(draft)
    oks.append("首句钩子：%s" % hook)
    print("=== 自检：%s ===" % st["name"])
    for o in oks:
        print("  OK  %s" % o)
    for w in warns:
        print("  !!  %s" % w)
    print("\n结论：%s" % ("通过（仍须人工核对事实口径）" if not warns else "%d 项待改/待核" % len(warns)))
    append_log(out, {"动作": "check", "风格": st["name"], "草稿": Path(args.draft).name,
                     "字数": n, "告警数": len(warns)})
    return 1 if warns else 0


def cmd_forget(args):
    out = Path(args.out).expanduser().resolve() if args.out else DEFAULT_OUT
    idx = load_index(out)
    st = find_style(idx, args.name)
    if not st:
        raise SystemExit("找不到风格「%s」" % args.name)
    for rel in [st["card"], st["corpus"]]:
        p = out / rel
        if p.exists():
            p.unlink()
    idx["styles"].remove(st)
    save_index(out, idx)
    write_overview(out, idx)
    append_log(out, {"动作": "forget", "风格": st["name"]})
    print("已删除风格「%s」及其卡片/语料（原表不受影响）。" % st["name"])


def main():
    ap = argparse.ArgumentParser(description="乔侨爱学习 · 风格自训练")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("learn", help="喂一张业务表，训练风格卡")
    p.add_argument("table")
    p.add_argument("--style", help="把整张表合成一个风格（不填则每个 sheet 各成一个风格）")
    p.add_argument("--owner", default="", help="归属人 / 谁的风格")
    p.add_argument("--sheet", action="append", help="只训练指定 sheet，可重复")
    p.add_argument("--replace", action="store_true", help="同名风格重建（默认增量合并去重）")
    p.add_argument("--out", help="训练成果目录，默认技能内 learned/")
    p.set_defaults(func=cmd_learn)

    p = sub.add_parser("list", help="列出已训练风格")
    p.add_argument("--out")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("show", help="打印风格卡")
    p.add_argument("name")
    p.add_argument("--out")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("topics", help="打印选题库（查重用）")
    p.add_argument("name")
    p.add_argument("--out")
    p.set_defaults(func=cmd_topics)

    p = sub.add_parser("check", help="草稿自检（字数/禁用词/新数字）")
    p.add_argument("draft")
    p.add_argument("--style", required=True)
    p.add_argument("--out")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("forget", help="删除某个风格")
    p.add_argument("name")
    p.add_argument("--out")
    p.set_defaults(func=cmd_forget)

    args = ap.parse_args()
    rc = args.func(args)
    sys.exit(rc or 0)


if __name__ == "__main__":
    main()
