# 乔侨爱学习 · AI 版部署（接 DeepSeek，别人打开就能用）

## 为什么不能直接在 GitHub Pages 上接
GitHub Pages 只能放静态网页。API Key 只要写进前端，打开网页的人按 F12 就能看到，等于把钥匙贴门上，会被刷爆额度。
所以 AI 版改成：**网页 → 你自己的服务端中转 → DeepSeek**，Key 只存在服务端环境变量里，浏览器永远看不到。

代码已经全部写好并提交到本仓库（`api/chat.js` 中转函数、`web/chat.html` + `web/chat.js` 前端、`vercel.json` 配置）。
**你只需要在 Vercel 点几下**，不需要懂代码。

## 部署步骤（约 3 分钟）

1. 打开 https://vercel.com ，用 **GitHub 账号登录**（就用 `hi4596-bit` 那个）。
2. 点 **Add New… → Project** → 从列表选 **`qiaoqiao-ai`** → Import。
3. Framework Preset 选 **Other**（或保持默认），**不要改 Root Directory**（保持仓库根）。
4. 展开 **Environment Variables**，添加一条：
   - Name：`DEEPSEEK_API_KEY`
   - Value：你的 DeepSeek Key（`sk-…`，在 https://platform.deepseek.com/api_keys 申请）
5. 点 **Deploy**。等 30 秒，Vercel 给你一个网址，例如 `https://qiaoqiao-ai-xxx.vercel.app`。
6. 打开那个网址 → 就是 AI 问答页（根路径自动指向 `chat.html`），别人点开直接能问，**不用自己有 key**。

> `vercel.json` 已配好：静态文件从 `web/` 出，`api/chat.js` 自动成为服务端函数，根路径重写到 `chat.html`。

## 以后改了怎么更新
`git push` 到 GitHub，Vercel 会自动重新部署（和 GitHub Pages 一样）。

## 两个入口别搞混

| 入口 | 地址 | 需要 key | 数据 |
|---|---|---|---|
| **轻量检索版** | https://hi4596-bit.github.io/qiaoqiao-ai/ | 不需要 | 演示数据 |
| **AI 版** | Vercel 给你的网址 | 你在 Vercel 配了就行，访客不需要 | 演示数据 |

## 隐私（重要，再讲一次）

- **公开站点只能用演示数据**。你的真实成稿、学费、政策、62MB 底表全在本机，`.gitignore` 挡着，一个都没进公开仓库。
- 接了大模型 = 用户的问题 + 检索到的资料片段 **会发给 DeepSeek**。用演示数据没问题；**若要接真实业务数据，请改私有仓库 + 只给内部人用**。
- 想在本机用真实数据：跑 `python scripts/export_web_data.py` 生成 `web/data/app-data.js`（不进 Git），打开本地 `web/index.html` 或 `web/chat.html` 切到「本机真实数据」。这份不外发。
- 网页上有个「填自己的 key 直连」开关，仅供你自己本机试用（浏览器直连 DeepSeek 常被 CORS 拦，能用就用，不能用以 Vercel 版为准）。**别在公用电脑填 key**。

## 没 key 也想先看效果
不填 key 直接 Deploy 也能打开页面，会提示「AI 已接（待填 Key）」，问答自动降级成"资料检索结果"，不会白屏。拿到 key 后在 Vercel 环境变量里补上、重新 Deploy 即可。

## 服务端做了哪些防护（`api/chat.js`）
- 只接受 POST；输入长度限制，防滥用；
- Key 只在服务端环境变量，错误信息不回传上游原文（不泄露 key/内部信息）；
- 固定的 system 提示：**资料里没有的数字一律说「以官方表为准」，绝不编造**；有风格卡就严格模仿写法；
- 上游只连 `api.deepseek.com`（或你自设的 `DEEPSEEK_BASE_URL`），不接受前端传任意地址。
