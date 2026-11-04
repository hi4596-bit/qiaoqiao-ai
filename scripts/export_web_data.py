# -*- coding: utf-8 -*-
"""把本机真实 skills 数据导出成 web/data/app-data.js（含真实业务，已被 .gitignore 排除）。
用 JS 赋值而非 json，避免 file:// 打开时的 CORS 拦截，双击即可用。"""
import json
from pathlib import Path

SKILLS = Path.home() / ".agents" / "skills"
ROOT = Path(__file__).resolve().parent.parent

def load_card(name):
    p = SKILLS / "qiaoqiao-style" / "learned" / "cards" / (name + ".md")
    return p.read_text(encoding="utf-8") if p.exists() else ""

kb_path = SKILLS / "qiaoqiao-kb" / "kb" / "kb.json"
kb = json.loads(kb_path.read_text(encoding="utf-8")) if kb_path.exists() else {"招生简章": []}

styles_path = SKILLS / "qiaoqiao-style" / "learned" / "styles.json"
styles = json.loads(styles_path.read_text(encoding="utf-8")).get("styles", []) if styles_path.exists() else []

app = {
    "kb": kb.get("招生简章", []),
    "degree": kb.get("学位申请条件", []) + kb.get("学位英语报考条件", []) + kb.get("本科论文与延毕", []),
    "affiliation": kb.get("备案教学点", []),
    "cards": [{"name": s["name"], "owner": s.get("owner", ""), "text": load_card(s["id"])} for s in styles],
}
out = ROOT / "web" / "data" / "app-data.js"
out.write_text("window.APP_DATA = " + json.dumps(app, ensure_ascii=False) + ";\n", encoding="utf-8")
print("已导出 %d 简章 / %d 政策 / %d 风格卡 → %s" % (
    len(app["kb"]), len(app["degree"]), len(app["cards"]), out))
