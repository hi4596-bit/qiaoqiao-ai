# -*- coding: utf-8 -*-
"""
乔侨爱学习 · 业务知识库构建器 (build_kb.py)
把《班主任工具清单》这类"官方事实底表"结构化抽取成可查询的知识库。
这不是口播稿，不做风格训练；抽的是：各校招生简章/学费、学位申请条件、
学位英语报考条件、备案教学点、好评/协议 SOP、工具清单。

输出：
  kb.json   —— 结构化事实（机器可读，写稿/答问前查用）
  kb.md     —— 人读索引（关键数字 + 学校政策速查）
  kb_raw.md —— 每个 sheet 的逐行原文（兜底，结构化漏了的在这里找）

用法：
  python build_kb.py [表格.xlsx] [--out 目录]
"""
import argparse
import io
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
except Exception:
    pass

import openpyxl

SCHOOL_HINT = ("大学", "学院", "学校", "开放大学", "医学院", "职业", "校区", "分校", "中心")


def clean(v):
    return "" if v is None else str(v).strip()


def is_num(s):
    return bool(re.match(r"^\d+$", (s or "").strip()))


def load(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    return [(ws.title, [[clean(c) for c in r] for r in ws.iter_rows(values_only=True)])
            for ws in wb.worksheets]


def first_header(rows, *aliases):
    for i, r in enumerate(rows):
        joined = "".join(r)
        if all(any(a in (r[j] or "") for j in range(len(r))) for a in aliases if a):
            if any(a in joined for a in aliases):
                return i
    return None


def find_col(header_row, *aliases):
    results = []
    for j, c in enumerate(header_row):
        for a in aliases:
            if a and a in (c or ""):
                results.append((j, c or ""))
                break
    if not results:
        return None
    # 优先精确匹配（如「专业」不抢「专业代码」那一列）
    for j, v in results:
        if v in aliases:
            return j
    # 否则取表头文字最短的那个（同样避免抢到「代码」列）
    return min(results, key=lambda x: len(x[1]))[0]


# ---------------------------------------------------------------- 招生简章（成考/国开/自考）

def parse_chengkao(rows, label):
    """成考三张表：块头是 col0=院校名 + col1=简介，然后表头行，再数据行。"""
    recs = []
    school = ""
    hi = None
    for i, r in enumerate(rows):
        if r[0] and not is_num(r[0]) and "序号" not in "".join(r) and "专业" not in r[0]:
            school = r[0]
            continue
        if "序号" in "".join(r) and "专业" in "".join(r):
            hi = i
            continue
        if hi is None:
            continue
        if is_num(r[0]):
            hdr = rows[hi]
            major = r[find_col(hdr, "专业名称", "招生专业", "专业") or 1]
            if not major or major in ("专业名称", "招生专业", "专业"):
                continue
            recs.append({
                "类型": label,
                "院校": school,
                "层次": r[find_col(hdr, "层次") or 2] or "",
                "专业": major,
                "学制": r[find_col(hdr, "学制") or 3] or "",
                "学费": r[find_col(hdr, "学费") or 4] or "",
                "考试科目": r[find_col(hdr, "考试科目", "考试科类") or 5] or "",
            })
    return recs


def parse_guokai(rows):
    """国开简章：col0=院校/分校名，col1=简介，表头行，数据行。"""
    recs = []
    school = ""
    hi = None
    for i, r in enumerate(rows):
        if r[0] and not is_num(r[0]) and "序号" not in "".join(r) and "专业" not in r[0]:
            school = r[0]
            continue
        if "序号" in "".join(r) and "专业" in "".join(r):
            hi = i
            continue
        if hi is None:
            continue
        if is_num(r[0]):
            hdr = rows[hi]
            major = r[find_col(hdr, "专业") or 2]
            if not major or major == "专业":
                continue
            recs.append({
                "类型": "国开",
                "院校": school,
                "类别": r[find_col(hdr, "类别") or 1] or "",
                "专业": major,
                "层次": r[find_col(hdr, "层次") or 3] or "",
                "学习形式": r[find_col(hdr, "学习形式") or 4] or "",
                "学制": r[find_col(hdr, "学制") or 5] or "",
                "第一学年学费": r[find_col(hdr, "第一学年学费") or 6] or "",
                "第二学年学费": r[find_col(hdr, "第二学年学费") or 7] or "",
                "教材费": r[find_col(hdr, "教材费") or 8] or "",
            })
    return recs


def parse_zikao(rows):
    """自考招生简章：院校是 col1（数据行内），无块头。"""
    recs = []
    hi = first_header(rows, "院校", "专业名称") if first_header(rows, "院校") is not None else None
    if hi is None:
        return recs
    hdr = rows[hi]
    for r in rows[hi + 1:]:
        school = r[find_col(hdr, "院校") or 1]
        major = r[find_col(hdr, "专业名称", "专业") or 4]
        if not school and not major:
            continue
        if major in ("专业名称（点击跳转科目表）", "专业名称", "专业"):
            continue
        if not school:
            continue
        recs.append({
            "类型": "自考",
            "院校": school,
            "层次": r[find_col(hdr, "层次") or 2] or "",
            "专业代码": r[find_col(hdr, "专业代码") or 3] or "",
            "专业": major,
            "学费": r[find_col(hdr, "学费") or 5] or "",
            "教材费": r[find_col(hdr, "教材费") or 6] or "",
            "备注": r[find_col(hdr, "备注") or 7] or "",
        })
    return recs


def parse_guangkai(rows):
    """广开简章：单一院校，表头行，数据行（专业列可能多值堆叠）。学费单列。"""
    recs = []
    hi = first_header(rows, "专业代码", "收费标准") if first_header(rows, "专业") is not None else None
    if hi is None:
        return recs
    hdr = rows[hi]
    school = "广东开放大学"
    for r in rows[hi + 1:]:
        if not is_num(r[0]):
            continue
        majors = re.split(r"[\n\r]+", r[find_col(hdr, "专业") or 3] or "")
        majors = [m.strip() for m in majors if m.strip()]
        recs.append({
            "类型": "广开",
            "院校": school,
            "招生层次": (r[find_col(hdr, "招生层次") or 1] or "").replace("\n", "/"),
            "专业代码": r[find_col(hdr, "专业代码") or 2] or "",
            "专业列表": majors,
            "收费标准": r[find_col(hdr, "收费标准") or 4] or "",
            "第一次收费": r[find_col(hdr, "第一次收费") or 5] or "",
            "第二次收费": r[find_col(hdr, "第二次收费") or 6] or "",
            "第三次收费": r[find_col(hdr, "第三次收费") or 7] or "",
        })
    return recs


# ---------------------------------------------------------------- 政策表（按学校归并）

def parse_by_school(rows, field_cols):
    """通用：学校名在 col1（块首行单独一行，或夹在第一条数据行里），其余列是 项目/要求。
    子行（c0 空、c1 空但 c2+ 有内容）沿用当前学校。"""
    recs = []
    school = ""
    hi = None
    for r in rows:
        joined = "".join(r)
        if "序号" in joined and any(k in joined for k in field_cols):
            hi = 0
            continue
        if hi is None:
            continue
        c0 = r[0] if len(r) > 0 else ""
        c1 = r[1] if len(r) > 1 else ""
        if c1 and not is_num(c1):
            school = c1
            if c0 and is_num(c0):          # 学校名夹在第一条数据行
                rec = {"学校": school}
                for name, idx in field_cols.items():
                    rec[name] = r[idx] if idx < len(r) else ""
                recs.append(rec)
            continue                       # 纯块头行：跳过
        has_field = any((r[idx] if idx < len(r) else "") for idx in field_cols.values())
        if (c0 and is_num(c0)) or (c1 == "" and has_field):
            rec = {"学校": school}
            for name, idx in field_cols.items():
                rec[name] = r[idx] if idx < len(r) else ""
            recs.append(rec)
    return recs


# ---------------------------------------------------------------- 简单表

def parse_affiliation(rows):
    recs = []
    for r in rows[2:]:
        if is_num(r[0]) and r[1]:
            recs.append({"序号": r[0], "单位名称": r[1], "高校": r[2]})
    return recs


def parse_tools(rows):
    recs = []
    for r in rows[3:]:
        if (r[0] and is_num(r[0])) or (r[1] and "项目" not in r[1]):
            detail = " ".join([c for c in r[2:] if c]).strip()
            if r[1] or detail:
                recs.append({"序号": r[0], "项目": r[1], "子项目": r[2], "详细内容": detail})
    return recs


def parse_sop(rows):
    hdr = rows[1] if len(rows) > 1 else []
    steps = []
    if len(rows) > 2:
        for j, name in enumerate(hdr):
            val = rows[2][j] if j < len(rows[2]) else ""
            if name and val:
                steps.append({"步骤": name, "内容": val})
    return steps


# ---------------------------------------------------------------- 原文

def sheet_raw(rows):
    out = []
    for i, r in enumerate(rows, 1):
        cells = [c for c in r]
        line = " | ".join(cells).rstrip(" |")
        if line.strip():
            out.append("  R%-2d: %s" % (i, line))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("table", nargs="?", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    here = Path(__file__).resolve().parent.parent
    src = Path(args.table) if args.table else (here / "sources" / "班主任工具清单.xlsx")
    if not src.exists():
        src = list(here.glob("sources/*.xlsx"))
        src = src[0] if src else None
    if not src or not Path(src).exists():
        raise SystemExit("找不到业务表：请把班主任工具清单.xlsx 放到 sources/ 或传 --table")
    out = Path(args.out) if args.out else (here / "kb")
    out.mkdir(parents=True, exist_ok=True)

    sheets = load(src)
    by = {title: rows for title, rows in sheets}
    kb = {"_meta": {"source": Path(src).name, "sheets": len(sheets)},
          "招生简章": [], "学位申请条件": [], "学位英语报考条件": [],
          "本科论文与延毕": [], "备案教学点": [], "工具清单": [], "操作SOP": {}}

    # 招生简章
    if "成考简章" in by:
        kb["招生简章"] += parse_chengkao(by["成考简章"], "成考-专升本/综合")
    if "成考-高升专、高升本" in by:
        kb["招生简章"] += parse_chengkao(by["成考-高升专、高升本"], "成考-高升专高升本")
    if "成考-专升本" in by:
        kb["招生简章"] += parse_chengkao(by["成考-专升本"], "成考-专升本")
    if "国开简章" in by:
        kb["招生简章"] += parse_guokai(by["国开简章"])
    if "广开简章" in by:
        kb["招生简章"] += parse_guangkai(by["广开简章"])
    if "自考招生简章" in by:
        kb["招生简章"] += parse_zikao(by["自考招生简章"])

    if "学位申请条件" in by:
        kb["学位申请条件"] = parse_by_school(by["学位申请条件"],
            {"项目": 2, "要求": 3, "注意事项": 4})
    if "学位英语、PETS、CET-4和CET-6等报考条件" in by:
        kb["学位英语报考条件"] = parse_by_school(by["学位英语、PETS、CET-4和CET-6等报考条件"],
            {"学位英语": 2, "自考英语二": 3, "PETS": 4, "校内英语四级": 5,
             "校内英语八级": 6, "TEM4": 7, "TEM8": 8, "其他": 9})
    if "本科论文、实践报告及最后休学、延毕要求" in by:
        kb["本科论文与延毕"] = parse_by_school(by["本科论文、实践报告及最后休学、延毕要求"],
            {"本科学位论文": 2, "可写作次数": 3, "普通论文": 4, "实践报告": 5,
             "保留学位论文成绩申请延毕": 6, "休学": 7, "休学限制": 8, "学籍年限": 9, "备注": 10})
    if "26备案截图（已更新" in by:
        kb["备案教学点"] = parse_affiliation(by["26备案截图（已更新"])
    if "汇总清单" in by:
        kb["工具清单"] = parse_tools(by["汇总清单"])
    if "成考辅导班电子协议操作" in by:
        kb["操作SOP"]["成考辅导班电子协议"] = parse_sop(by["成考辅导班电子协议操作"])
    if "美团、大众点评评论步骤" in by:
        kb["操作SOP"]["美团大众点评好评"] = parse_sop(by["美团、大众点评评论步骤"])

    (out / "kb.json").write_text(json.dumps(kb, ensure_ascii=False, indent=2), encoding="utf-8")

    # 人读索引
    md = ["# 乔侨爱学习 · 业务知识库（官方口径底表）", "",
          "> 来源：`%s`（%d 个 sheet）。本库是**官方事实来源**：写稿/答问时，凡是学费、学制、学位条件、备案关系，以这里为准，不要沿用成稿里数出来的「观察值」。" % (Path(src).name, len(sheets)), ""]
    md.append("## 招生简章（按类型+院校+专业）— 共 %d 条" % len(kb["招生简章"]))
    md.append("")
    for t in ["成考-专升本/综合", "成考-高升专高升本", "成考-专升本", "国开", "广开", "自考"]:
        sub = [r for r in kb["招生简章"] if r.get("类型") == t]
        if not sub:
            continue
        md.append("### %s（%d 条）" % (t, len(sub)))
        for r in sub[:40]:
            if t == "广开":
                majors = "、".join(r.get("专业列表", [])[:12])
                md.append("- %s｜%s｜收费%s｜分收 %s/%s/%s" % (
                    r.get("招生层次", ""), majors, r.get("收费标准", ""),
                    r.get("第一次收费", ""), r.get("第二次收费", ""), r.get("第三次收费", "")))
            elif t == "国开":
                md.append("- %s｜%s｜%s｜%s｜年费%s/%s｜教材%s" % (
                    r.get("类别", ""), r.get("专业", ""), r.get("层次", ""), r.get("学制", ""),
                    r.get("第一学年学费", ""), r.get("第二学年学费", ""), r.get("教材费", "")))
            else:
                md.append("- %s｜%s｜%s｜%s｜%s" % (
                    r.get("院校", ""), r.get("层次", ""), r.get("专业", ""),
                    r.get("学制", ""), r.get("学费", "") or r.get("考试科目", "")))
        if len(sub) > 40:
            md.append("- …（其余 %d 条见 kb.json）" % (len(sub) - 40))
        md.append("")
    for key, title in [("学位申请条件", "学位申请条件"), ("学位英语报考条件", "学位英语/PETS/CET 报考条件"),
                      ("本科论文与延毕", "本科论文、实践报告与延毕/休学"), ("备案教学点", "备案教学点（教学中心↔高校）"),
                      ("工具清单", "班主任工具清单")]:
        items = kb[key]
        md.append("## %s — 共 %d 条" % (title, len(items)))
        md.append("")
        for it in items[:60]:
            bits = ["%s：%s" % (k, v) for k, v in it.items() if k != "学校" and v]
            md.append("- **%s** %s" % (it.get("学校", ""), "；".join(bits)))
        if len(items) > 60:
            md.append("- …（其余见 kb.json）")
        md.append("")
    md.append("## 操作 SOP")
    for name, steps in kb["操作SOP"].items():
        md.append("### %s" % name)
        for s in steps:
            md.append("- %s：%s" % (s["步骤"], s["内容"][:200]))
    (out / "kb.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    # 原文兜底
    raw = ["# 班主任工具清单 · 逐 sheet 原文（结构化漏了的在这里查）", ""]
    for title, rows in sheets:
        raw.append("## %s" % title)
        raw.append(sheet_raw(rows))
        raw.append("")
    (out / "kb_raw.md").write_text("\n".join(raw), encoding="utf-8")

    print("已构建知识库：")
    for k, v in [("招生简章", kb["招生简章"]), ("学位申请条件", kb["学位申请条件"]),
                 ("学位英语报考条件", kb["学位英语报考条件"]), ("本科论文与延毕", kb["本科论文与延毕"]),
                 ("备案教学点", kb["备案教学点"]), ("工具清单", kb["工具清单"])]:
        print("  %-10s %d 条" % (k, len(v)))
    print("输出目录：%s" % out.resolve())


if __name__ == "__main__":
    main()
