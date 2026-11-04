#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成一张空白的「自己风格」业务表模板（.xlsx），同事填完成稿即可 learn。"""
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill

HEADERS = ["序号", "选题方向", "3秒爆点开头", "完整口播脚本",
           "抖音标题", "小红书标题", "视频号标题", "发布文案"]
EXAMPLE = [
    "1", "（选题方向，10字内，写新稿前查重用）",
    "（钩子：开口第一句就能直接念）",
    "（完整口播正文，建议 500–750 字；只填真实成稿，数字以当次官方表为准）",
    "（抖音标题：短、带冲突或数字）", "（小红书标题：稍长、可带 emoji）",
    "（视频号标题：平实一点）", "（发布文案：学校口吻的补充说明，别跟口播重复）",
]

def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("我的风格-模板.xlsx")
    sheet = sys.argv[2] if len(sys.argv) > 2 else "我的风格"
    if out.exists():
        raise SystemExit("文件已存在，不覆盖：%s" % out)
    wb = Workbook()
    ws = wb.active
    ws.title = sheet[:31]
    ws.merge_cells("A1:H1")
    c = ws.cell(1, 1, "组X · 三号同发：抖音「你的账号」｜小红书「你的账号」｜视频号「你的账号」")
    c.font = Font(bold=True, size=12)
    c.fill = PatternFill("solid", fgColor="FFF2CC")
    for row_i, (label, value) in enumerate([
        ("运营人", "（你的名字）"), ("口播方", "（成考 / 自考 / 国开 / 广开 …）"),
        ("垂直内容", "（你这个账号专讲什么）"),
    ], start=3):
        ws.cell(row_i, 1, label).font = Font(bold=True)
        ws.cell(row_i, 2, value)
        ws.merge_cells(start_row=row_i, start_column=2, end_row=row_i, end_column=8)
    hrow = 8
    for i, h in enumerate(HEADERS, 1):
        cell = ws.cell(hrow, i, h)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.fill = PatternFill("solid", fgColor="D9E1F2")
    for i, v in enumerate(EXAMPLE, 1):
        cell = ws.cell(hrow + 1, i, v)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        cell.font = Font(color="808080", italic=True)
    widths = [8, 32, 42, 80, 26, 30, 30, 46]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[chr(64 + i)].width = w
    ws.freeze_panes = "A9"
    ws.row_dimensions[hrow + 1].height = 60
    wb.save(out)
    print("已生成模板：%s" % out.resolve())
    print("填法：一个 sheet = 一个人的风格；从第 %d 行开始，一行一篇成稿，示例行可直接删。" % (hrow + 1))
    print("填完跑：python qiaoqiao.py learn \"%s\" --owner 你的名字" % out.name)

if __name__ == "__main__":
    main()
