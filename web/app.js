'use strict';

function getData() {
  const which = document.getElementById('src').value;
  if (which === 'app') {
    if (typeof window.APP_DATA === 'undefined') {
      return { error: '还没生成真实数据。请在本机运行 scripts/export_web_data.py，然后刷新页面；当前已切回「示例数据」。' };
    }
    return window.APP_DATA;
  }
  return window.SAMPLE_DATA || { kb: [], degree: [], affiliation: [], cards: [] };
}

function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function addMsg(role, text) {
  const log = document.getElementById('log');
  const m = document.createElement('div');
  m.className = 'msg ' + role;
  const b = document.createElement('div');
  b.className = 'bubble';
  b.innerHTML = esc(text).replace(/\n/g, '<br>');
  m.appendChild(b);
  log.appendChild(m);
  log.scrollTop = log.scrollHeight;
}

function updateStat(DATA) {
  document.getElementById('stat').textContent =
    '资料：简章 ' + (DATA.kb || []).length + ' 条 · 政策 ' + (DATA.degree || []).length +
    ' 条 · 风格卡 ' + (DATA.cards || []).length + ' 张';
}

// 中文检索：2-4 字滑窗分词
function tokens(q) {
  const clean = q.replace(/[\s\p{P}]+/gu, '');
  const out = new Set();
  for (let i = 0; i < clean.length; i++) {
    for (let n = 2; n <= Math.min(4, clean.length - i); n++) {
      out.add(clean.substr(i, n));
    }
  }
  return [...out];
}

function search(blocks, q) {
  const toks = tokens(q);
  const scored = [];
  for (const b of blocks) {
    const text = (typeof b === 'string' ? b : JSON.stringify(b));
    let score = 0;
    for (const t of toks) if (text.includes(t)) score += t.length;
    if (score > 0) scored.push({ b, score });
  }
  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, 4);
}

function blockText(b) {
  if (typeof b === 'string') return b;
  if (b.text) return b.text;
  return Object.entries(b).map(([k, v]) => k + '：' + v).join('；');
}

function answer(DATA, q) {
  // 「有哪些 / 列出」清单类意图
  if (/有哪些|列出|全部|所有|清单|列表/.test(q)) {
    if (/备案|教学点|中心/.test(q) && (DATA.affiliation || []).length) {
      return '备案教学点（共 ' + DATA.affiliation.length + ' 条）：\n\n' +
        DATA.affiliation.map(a => '· ' + blockText(a)).join('\n');
    }
    if (/风格|账号/.test(q) && (DATA.cards || []).length) {
      return '已训练风格卡（共 ' + DATA.cards.length + ' 张）：\n\n' +
        DATA.cards.map(c => '· ' + c.name + (c.owner ? '（' + c.owner + '）' : '')).join('\n');
    }
  }
  // 风格写稿意图
  const styleMatch = q.match(/按(.+?)的风格|(.+?)风格写|写一条|写3条|写三?条/);
  if (styleMatch) {
    const name = (styleMatch[1] || styleMatch[2] || '').trim();
    const cards = (DATA.cards || []).filter(c => !name || c.name.includes(name));
    if (cards.length) {
      let s = '找到 ' + cards.length + ' 张风格卡' + (name ? '（匹配「' + name + '」）' : '') + '：\n\n';
      s += cards.slice(0, 3).map(c => '【' + c.name + '】\n' + (c.text || '').slice(0, 500)).join('\n\n---\n\n');
      s += '\n\n（轻量版展示写法说明；把这段贴给大模型即可照写。接大模型后可自动成稿。）';
      return s;
    }
    return '没有匹配到风格卡。可用的：' + (DATA.cards || []).map(c => c.name).join('、');
  }
  const blocks = [...(DATA.kb || []), ...(DATA.degree || []), ...(DATA.affiliation || [])];
  const hits = search(blocks, q);
  if (!hits.length) {
    return '没在资料里查到相关内容。试试更具体的关键词（学校名+专业/学费/学位/备案）。\n已收录：简章 ' +
      (DATA.kb || []).length + ' 条，政策 ' + (DATA.degree || []).length + ' 条。';
  }
  return '我查到这些（来自业务资料）：\n\n' + hits.map(h => '· ' + blockText(h.b).slice(0, 320)).join('\n\n');
}

function send() {
  const q = document.getElementById('q').value.trim();
  if (!q) return;
  document.getElementById('q').value = '';
  addMsg('user', q);
  const DATA = getData();
  if (DATA.error) {
    document.getElementById('src').value = 'sample';
    addMsg('bot', DATA.error);
    updateStat(getData());
    return;
  }
  setTimeout(() => addMsg('bot', answer(DATA, q)), 120);
}

document.getElementById('send').addEventListener('click', send);
document.getElementById('q').addEventListener('keydown', e => { if (e.key === 'Enter') send(); });
document.getElementById('src').addEventListener('change', () => updateStat(getData()));

// 启动
const boot = getData();
if (boot.error) {
  document.getElementById('src').value = 'sample';
  updateStat(getData());
  addMsg('bot', '你好，我是「乔侨爱学习」问答助手（演示数据）。\n可以问我：广开土木工程学费多少 / 国开畜牧兽医 / 按示例-文老师的风格写一条。\n提示：真实数据需在本机运行 scripts/export_web_data.py 生成。');
} else {
  updateStat(boot);
  addMsg('bot', '你好，我是「乔侨爱学习」问答助手。\n可以问我：广开土木工程学费多少 / 国开畜牧兽医 / 按示例-文老师的风格写一条。');
}
