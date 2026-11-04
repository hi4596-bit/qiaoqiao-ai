'use strict';

function getData() {
  const which = document.getElementById('src').value;
  if (which === 'app') {
    if (typeof window.APP_DATA === 'undefined') {
      document.getElementById('src').value = 'sample';
      return window.SAMPLE_DATA || { kb: [], degree: [], affiliation: [], cards: [] };
    }
    return window.APP_DATA;
  }
  return window.SAMPLE_DATA || { kb: [], degree: [], affiliation: [], cards: [] };
}

function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
function addMsg(role, text, tag) {
  const log = document.getElementById('log');
  const m = document.createElement('div');
  m.className = 'msg ' + role;
  const b = document.createElement('div');
  b.className = 'bubble';
  b.innerHTML = (tag ? '<span class="tag">' + esc(tag) + '</span><br>' : '') +
    esc(text).replace(/\n/g, '<br>');
  m.appendChild(b);
  log.appendChild(m);
  log.scrollTop = log.scrollHeight;
}
function updateStat(D) {
  document.getElementById('stat').textContent =
    '简章 ' + (D.kb || []).length + ' · 政策 ' + (D.degree || []).length + ' · 风格卡 ' + (D.cards || []).length;
}

// ---- 轻量检索：先从资料里找相关事实，再交给 AI（避免 AI 凭空编）----
function tokens(q) {
  const clean = q.replace(/[\s\p{P}]+/gu, '');
  const out = new Set();
  for (let i = 0; i < clean.length; i++)
    for (let n = 2; n <= Math.min(4, clean.length - i); n++) out.add(clean.substr(i, n));
  return [...out];
}
function search(blocks, q, limit) {
  const toks = tokens(q), scored = [];
  for (const b of blocks) {
    const text = typeof b === 'string' ? b : JSON.stringify(b);
    let score = 0;
    for (const t of toks) if (text.includes(t)) score += t.length;
    if (score > 0) scored.push({ b, score });
  }
  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, limit || 4);
}
function blockText(b) {
  if (typeof b === 'string') return b;
  if (b.text) return b.text;
  return Object.entries(b).map(function (kv) { return kv[0] + '：' + kv[1]; }).join('；');
}

// 组装发给服务端的 payload（前端只传明文片段，不碰 key）
function buildPayload(D, q) {
  const blocks = [].concat(D.kb || [], D.degree || [], D.affiliation || []);
  const hits = search(blocks, q, 5);
  const facts = hits.map(function (h) { return '· ' + blockText(h.b).slice(0, 400); }).join('\n')
    || '（本次没有检索到相关资料）';

  let style = '';
  const sm = q.match(/按(.+?)的风格|(.+?)风格写/);
  if (sm) {
    const name = (sm[1] || sm[2] || '').trim();
    const cards = (D.cards || []).filter(function (c) { return !name || c.name.indexOf(name) >= 0; });
    style = cards.slice(0, 1).map(function (c) { return c.text || ''; }).join('\n');
    if (!style && (D.cards || []).length) style = D.cards[0].text || '';
  }
  return { question: q, facts: facts, style: style };
}

function localFallback(payload) {
  let s = 'AI 服务当前不可用，先给你资料检索结果：\n\n' + payload.facts;
  if (payload.style) s += '\n\n（附风格卡写法要点）\n' + payload.style.slice(0, 400);
  return s;
}

// 直连模式（用户自己填 key，仅本机自用；可能被浏览器 CORS 拦）
async function directAsk(payload, key) {
  const r = await fetch('https://api.deepseek.com/chat/completions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key },
    body: JSON.stringify({
      model: 'deepseek-chat',
      messages: [
        { role: 'system', content: '只依据【参考资料】回答，资料里没有的数字一律说「以官方表为准」，绝不编造。有【风格卡】就严格模仿其写法。用中文口语、简洁。' },
        { role: 'user', content: '【参考资料】\n' + payload.facts + '\n\n【风格卡】\n' + payload.style + '\n\n【用户问题】\n' + payload.question }
      ],
      stream: false
    })
  });
  if (!r.ok) throw new Error('直连失败 HTTP ' + r.status + '（多半是浏览器 CORS 限制，建议用 Vercel 部署版）');
  const d = await r.json();
  return d.choices[0].message.content;
}

async function askServer(payload) {
  const r = await fetch('api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const d = await r.json().catch(function () { return {}; });
  if (!r.ok || !d.answer) throw new Error(d.error || ('HTTP ' + r.status));
  return d.answer;
}

async function probe() {
  // 探测后端是否存在（不消耗 key）
  try {
    const r = await fetch('api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: '' }) });
    const d = await r.json().catch(function () { return {}; });
    if (r.status === 503 || r.status === 400) {
      document.getElementById('mode').textContent = 'AI 已接（待填 Key）';
      document.getElementById('keyrow').classList.add('on');
      return 'needkey';
    }
    document.getElementById('mode').textContent = 'AI 已接 ✓';
    return 'ok';
  } catch (e) {
    document.getElementById('mode').textContent = '检索模式（无后端）';
    document.getElementById('keyrow').classList.add('on');
    return 'none';
  }
}

async function send() {
  const q = document.getElementById('q').value.trim();
  if (!q) return;
  document.getElementById('q').value = '';
  addMsg('user', q);
  const D = getData();
  const payload = buildPayload(D, q);
  addMsg('bot', '正在查资料并让 AI 组织回答…');
  // 移除上一条「正在…」占位
  const log = document.getElementById('log');
  const placeholder = log.lastChild;

  try {
    let answer;
    const useMyKey = document.getElementById('usemykey') && document.getElementById('usemykey').checked;
    const myKey = document.getElementById('mykey') ? document.getElementById('mykey').value.trim() : '';
    if (useMyKey && myKey) {
      answer = await directAsk(payload, myKey);
    } else {
      answer = await askServer(payload);
    }
    if (placeholder && placeholder.parentNode) placeholder.parentNode.removeChild(placeholder);
    addMsg('bot', answer, 'DeepSeek');
  } catch (e) {
    if (placeholder && placeholder.parentNode) placeholder.parentNode.removeChild(placeholder);
    addMsg('bot', localFallback(payload) + '\n\n———\n提示：' + e.message, '检索结果');
  }
}

document.getElementById('send').addEventListener('click', send);
document.getElementById('q').addEventListener('keydown', function (e) { if (e.key === 'Enter') send(); });
document.getElementById('src').addEventListener('change', function () { updateStat(getData()); });

updateStat(getData());
addMsg('bot', '你好，我是「乔侨爱学习」AI 问答。\n我会先从业务资料里查事实，再让 AI 照着风格卡回答，数字不瞎编。\n试试：广开土木工程学费多少 / 按示例-文老师的风格写一条。');
probe();

// 便于本地测试暴露
if (typeof global !== 'undefined') {
  global.buildPayload = buildPayload;
  global.tokens = tokens;
  global.search = search;
}
