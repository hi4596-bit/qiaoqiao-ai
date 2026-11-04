# 乔侨爱学习 · 业务 AI 工具（开源版）

把业务表格丢给 AI，让它**学写作风格 + 记官方口径**，然后能按某人的风格写稿、能查学费/学位这类事实。
本仓库是**工具 + 示例数据**；你的真实成稿与底表不进 Git（见 `.gitignore`），本机导出后本地可用。

## 这套东西解决什么
- **风格卡（怎么写）**：喂一批成稿 → 自动总结出某人的口播/文案写法（字数、钩子、人称、结尾、标题习惯）。
- **知识库（写什么数字）**：喂官方底表（招生简章/学费/学位条件）→ 结构化，写稿/问答时精确查用，不靠编。
- **轻量问答网页**：纯前端，问"广开学费多少""按XX风格写"就从资料里检索返回，零成本、数据不出本机。
- **（进阶）接大模型**：仓库结构已为后续接 DeepSeek/通义等留出接口，可升级成真·自由生成 chat。

## 目录
```
skills/        两个通用工具技能（qiaoqiao-style 风格训练 / qiaoqiao-kb 知识库），纯脚本不含业务数据
web/           轻量检索问答网页（纯前端，可 GitHub Pages 部署）
scripts/       export_web_data.py：把本机真实数据导出给网页用
examples/      示例空表 + 示例成稿（教学用）
```

## 快速开始（用工具，不动 Git）
1. 装：把 `skills/` 下两个文件夹复制到 `~/.agents/skills/`（Win: `C:\Users\<你>\.agents\skills\`）。
2. 训练风格：`python skills/qiaoqiao-style/scripts/qiaoqiao.py learn 你的成稿表.xlsx --owner 名字`
3. 建知识库：`python skills/qiaoqiao-kb/scripts/build_kb.py 班主任工具清单.xlsx`
4. 对话用：在 DSH 里说"学习一下这张表""按XX风格写3条""查一下XX学费"。

## 用网页前端（最重要，双击就能用）
直接**双击 `web/index.html`** 即可打开问答界面（数据是内联 JS，不需要起服务器、不会 CORS 报错）。
默认加载 `web/data/sample-data.js` 虚构示例数据。

要用你本机的真实数据：
```bash
python scripts/export_web_data.py   # 生成 web/data/app-data.js（含真实业务，已被 gitignore）
```
然后打开 `web/index.html`，右上角数据源切到「本机真实数据」即可。`app-data.js` 不会进 Git。

## 部署网页（给别人点开用）
- 本仓库已配 GitHub Actions（`.github/workflows/pages.yml`）：push 到 main 自动把 `web/` 发到 **GitHub Pages**。
- 在仓库 Settings → Pages → Source 选「GitHub Actions」即可。别人打开 Pages 链接就是问答界面（用示例数据）。
- 只部署 `web/`；`app-data.js` 含真实业务、已被 gitignore，**不要**提交，否则会公开。
- 也可直接把 `web/` 拖到 Vercel / 任意静态托管，或把 `web/` 整个文件夹发人双击 `index.html`。

## 数据隐私（重要）
- 公开仓库**不含**真实成稿与底表：`learned/`、`kb/`、`sources/*.xlsx` 都在 `.gitignore`。
- 你本机 `web/data/app.json` 含真实业务，已被 gitignore，**提交前请确认它不会随仓库外传**。
- 风格卡只学"怎么写"，知识库只存"官方数字"，AI 不凭记忆编；写新稿数字一律以知识库为准。

## 许可
工具脚本按 MIT 开源；`examples/` 为虚构示例。业务专用技能（含真实口径/样稿）仅在本机使用，未包含在本仓库。

<!-- pages trigger -->
