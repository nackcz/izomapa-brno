// Volitelný server pro hlášení nepřesností (Cloudflare Worker + databáze D1): statický web ze site/,
// POST /api/report uloží hlášení z mapy, /admin je přehled hlášení. Návod je v README (Hlášení nepřesností).
// /admin a /api/admin/* chrání heslo (HTTP Basic, secret ADMIN_PASSWORD: `npx wrangler secret put ADMIN_PASSWORD`).
// Uživatelské jméno se nekontroluje. Ukládá se jen text hlášení a hash IP adresy (kvůli limitu), ne IP samotná.
const json = (d, s = 200) => new Response(JSON.stringify(d), { status: s, headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' } });

async function sha(s) {
  const b = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s));
  return [...new Uint8Array(b)].slice(0, 12).map((x) => x.toString(16).padStart(2, '0')).join('');
}

function isAdmin(req, env) {
  if (!env.ADMIN_PASSWORD) return false;
  const h = req.headers.get('authorization') || '';
  if (!h.startsWith('Basic ')) return false;
  let dec = ''; try { dec = atob(h.slice(6)); } catch { return false; }
  const pass = dec.slice(dec.indexOf(':') + 1);
  // porovnání v konstantním čase
  if (pass.length !== env.ADMIN_PASSWORD.length) return false;
  let d = 0; for (let i = 0; i < pass.length; i++) d |= pass.charCodeAt(i) ^ env.ADMIN_PASSWORD.charCodeAt(i);
  return d === 0;
}

async function report(req, env) {
  let d; try { d = await req.json(); } catch { return json({ ok: false, err: 'bad json' }, 400); }
  const target = String(d.target || '').slice(0, 80), note = String(d.note || '').trim().slice(0, 500), kind = 'text';
  if (!/^(b:[0-9a-f-]{36}|c-?\d+_-?\d+:\d+|pt:-?[\d.]+,-?[\d.]+)$/.test(target)) return json({ ok: false, err: 'bad input', msg: 'Hlášení nejde přiřadit k místu na mapě.' }, 400);
  if (note.length < 3) return json({ ok: false, err: 'short', msg: 'Napište prosím, co tu nesedí (aspoň pár slov).' }, 400);
  if (env.TURNSTILE_SECRET) {
    const f = new FormData(); f.append('secret', env.TURNSTILE_SECRET); f.append('response', String(d.token || '')); f.append('remoteip', req.headers.get('cf-connecting-ip') || '');
    const r = await (await fetch('https://challenges.cloudflare.com/turnstile/v0/siteverify', { method: 'POST', body: f })).json();
    if (!r.success) return json({ ok: false, err: 'captcha' }, 403);
  }
  const day = new Date().toISOString().slice(0, 10), ip = req.headers.get('cf-connecting-ip') || 'local';
  const who = await sha(ip + '|' + day + '|' + (env.SALT || 'izo'));
  const dev = await sha(ip + '|dev|' + (env.SALT || 'izo'));
  // limit: 3 hlášení za hodinu z jednoho zařízení (IP)
  const recent = await env.DB.prepare("SELECT COUNT(*) n FROM reports WHERE dev = ? AND created > datetime('now', '-1 hour')").bind(dev).first();
  if (recent && recent.n >= 3) return json({ ok: false, err: 'limit', msg: 'Z tohoto zařízení přišla za poslední hodinu už 3 hlášení. Zkuste to prosím později.' }, 429);
  try {
    await env.DB.prepare('INSERT INTO reports (target, title, kind, note, lon, lat, who, dev) VALUES (?, ?, ?, ?, ?, ?, ?, ?)')
      .bind(target, String(d.title || '').slice(0, 120), kind, note, +d.lon || null, +d.lat || null, who, dev).run();
  } catch (e) {
    if (String(e).includes('UNIQUE')) return json({ ok: false, err: 'dup', msg: 'Tohle místo jste dnes už nahlásili, děkuji.' }, 409);
    throw e;
  }
  return json({ ok: true });
}

async function adminList(req, env) {
  const u = new URL(req.url), min = Math.max(1, +u.searchParams.get('min') || 1), st = u.searchParams.get('status') || 'nove';
  const groups = await env.DB.prepare(
    `SELECT target, MAX(title) title, COUNT(*) n, MAX(created) last, AVG(lon) lon, AVG(lat) lat, (SELECT note FROM reports r2 WHERE r2.target = reports.target ORDER BY created DESC LIMIT 1) note
     FROM reports WHERE status = ? GROUP BY target HAVING n >= ? ORDER BY n DESC, last DESC LIMIT 500`).bind(st, min).all();
  return json({ groups: groups.results });
}

async function adminDetail(req, env) {
  const t = new URL(req.url).searchParams.get('target') || '';
  const r = await env.DB.prepare('SELECT id, created, kind, note, status FROM reports WHERE target = ? ORDER BY created DESC').bind(t).all();
  return json({ items: r.results });
}

async function adminSet(req, env) {
  const d = await req.json();
  if (!['nove', 'vyreseno', 'zamitnuto'].includes(d.status)) return json({ ok: false }, 400);
  await env.DB.prepare('UPDATE reports SET status = ? WHERE target = ?').bind(d.status, String(d.target || '')).run();
  return json({ ok: true });
}

export default {
  async fetch(req, env) {
    const p = new URL(req.url).pathname;
    if (p === '/api/report' && req.method === 'POST') return report(req, env);
    if (p.startsWith('/api/admin/') || p === '/admin' || p === '/admin.html') {
      if (!isAdmin(req, env)) return new Response('Přihlášení do administrace', { status: 401, headers: { 'www-authenticate': 'Basic realm="izomapa admin", charset="UTF-8"' } });
      if (p === '/api/admin/list') return adminList(req, env);
      if (p === '/api/admin/detail') return adminDetail(req, env);
      if (p === '/api/admin/status' && req.method === 'POST') return adminSet(req, env);
      if (p === '/admin' || p === '/admin.html') return env.ASSETS.fetch(req);   // assets podávají admin.html na /admin
    }
    return env.ASSETS.fetch(req);
  },
};
