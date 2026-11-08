// Vyrenderuje celou mapu po dlaždicích v headless Chromiu a uloží je do build/tiles/
import { chromium } from 'playwright';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const args = Object.fromEntries(process.argv.slice(2).map((a) => a.split('=')));
const mpp = args.mpp || '0.4', tile = args.tile || '1024';
const outDir = path.join(ROOT, args.out || 'build/tiles');
fs.mkdirSync(outDir, { recursive: true });

const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.png': 'image/png' };
const server = http.createServer((req, res) => {
  const p = path.join(ROOT, decodeURIComponent(new URL(req.url, 'http://x').pathname));
  if (!p.startsWith(ROOT + path.sep)) { res.writeHead(403); res.end(); return; }   // jen soubory projektu
  fs.readFile(p, (err, data) => {
    if (err) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { 'content-type': MIME[path.extname(p)] || 'application/octet-stream' });
    res.end(data);
  });
}).listen(0, '127.0.0.1');   // jen z tohoto počítače, ne z celé sítě
await new Promise((r) => server.once('listening', r));
const port = server.address().port;

// Mac: Metal, Windows: Direct3D 11, Linux: HW GPU přes EGL (pokud je v /dev/dri a WebGL není jen SW rasterizer), jinak SwiftShader
const SWIFTSHADER = ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'];
const linuxExe = process.platform === 'linux' && ['/opt/pw-browsers/chromium-1194/chrome-linux/chrome', '/ms-playwright/chromium-1194/chrome-linux/chrome', '/opt/pw-browsers/chromium'].find((p) => fs.existsSync(p));
const launch = (args) => chromium.launch({ ...(linuxExe ? { executablePath: linuxExe } : {}), args });
let browser, page;
if (process.platform === 'linux') {
  let hasDri = false;
  try { hasDri = fs.existsSync('/dev/dri') && fs.readdirSync('/dev/dri').some((f) => f.startsWith('renderD')); }
  catch { console.warn('GPU: nelze přečíst /dev/dri, zkouším SwiftShader'); }
  if (hasDri) {
    try {
      browser = await launch(['--no-sandbox', '--use-gl=angle', '--use-angle=gl-egl', '--enable-gpu', '--ignore-gpu-blocklist']);
      page = await browser.newPage();
      const gpu = await page.evaluate(() => {
        const gl = document.createElement('canvas').getContext('webgl2');
        const dbg = gl?.getExtension('WEBGL_debug_renderer_info');
        return gl ? String(gl.getParameter(dbg ? dbg.UNMASKED_RENDERER_WEBGL : gl.RENDERER)) : '';
      });
      if (!gpu || /swiftshader|llvmpipe|softpipe|swrast|lavapipe/i.test(gpu)) { await browser.close(); browser = page = null; }
      else console.log('GPU:', gpu);
    } catch { await browser?.close().catch(() => {}); browser = page = null; }
  }
  if (!browser) { console.log('GPU: SwiftShader (fallback)'); browser = await launch(SWIFTSHADER); page = await browser.newPage(); }
} else {
  browser = await launch(process.platform === 'darwin'
    ? ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist']
    : ['--use-angle=d3d11', '--enable-gpu', '--ignore-gpu-blocklist']);
  page = await browser.newPage();
}
page.on('console', (m) => console.log('[page]', m.text()));
page.on('requestfailed', (r) => console.log('[rf]', r.url(), r.failure()?.errorText));
page.on('pageerror', (e) => { console.log('[pageerror]', e.message); process.exit(1); });
const t0 = Date.now();
await page.goto(`http://127.0.0.1:${port}/render.html?mpp=${mpp}&tile=${tile}&season=${args.season || 'autumn'}&mode=${args.mode || 'day'}&dir=${args.dir || 'build'}&alpha=${args.alpha || '0'}${args.skirt ? `&skirt=${args.skirt}` : ''}${args.gx0 ? `&gx0=${args.gx0}&gy1=${args.gy1}` : ''}${args.relief ? `&relief=${args.relief}` : ''}`);
await page.waitForFunction(() => window.READY === true, null, { timeout: 240000, polling: 1000 });
const info = await page.evaluate(() => window.INFO);
console.log('scéna připravena za', (Date.now() - t0) / 1000, 's', info);
fs.writeFileSync(path.join(outDir, 'info.json'), JSON.stringify(info));
if (args.stromy) {                             // jen kresby stromů pro prohlížeč: node render.mjs stromy=site/stromy season=summer
  const t = await page.evaluate(() => window.TREE_EXPORT());
  fs.mkdirSync(path.join(ROOT, args.stromy), { recursive: true });
  fs.writeFileSync(path.join(ROOT, args.stromy, `${args.season}.png`), Buffer.from(t.url.split(',')[1], 'base64'));
  delete t.url; fs.writeFileSync(path.join(ROOT, args.stromy, `${args.season}.json`), JSON.stringify(t));
  await browser.close(); server.close(); process.exit(0);
}
const only = args.only ? args.only.split(',').map(Number) : null;
const list = args.tiles ? new Set(args.tiles.split(';')) : null;
for (let j = 0; j < info.rows; j++) for (let i = 0; i < info.cols; i++) {
  if (only && (only[0] !== i || only[1] !== j)) continue;
  if (list && !list.has(`${i}_${j}`)) continue;
  const t = Date.now();
  const url = await page.evaluate(([a, b]) => window.renderTile(a, b), [i, j]);
  fs.writeFileSync(path.join(outDir, `${i}_${j}.png`), Buffer.from(url.split(',')[1], 'base64'));
  console.log(`dlaždice ${i},${j}`, (Date.now() - t) / 1000, 's');
}
await browser.close();
server.close();
