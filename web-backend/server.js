import 'dotenv/config';
import express from 'express';
import cors from 'cors';
import crypto from 'crypto';
import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname  = path.dirname(__filename);

const ROOT      = path.resolve(__dirname, '..');
const HOST      = '0.0.0.0';
const PORT      = process.env.PORT || 8080;
const PY        = process.env.PYTHON || 'python3';
const PY_TARGET = path.join(ROOT, '.pylibs'); // локальный "node_modules" для Python

const CORS_ORIGIN = (process.env.CORS_ORIGIN || '*')
  .split(',').map(s => s.trim()).filter(Boolean);

const app = express();
app.use(cors({
  origin: (origin, cb) => {
    if (!origin || CORS_ORIGIN.includes('*') || CORS_ORIGIN.includes(origin)) return cb(null, true);
    return cb(new Error('Not allowed by CORS'));
  }
}));
app.use(express.json());

// Health
app.get('/', (_req, res) => res.send('OK'));
app.get('/health', (_req, res) => res.json({ ok: true }));

// --- Telegram WebApp initData validation ---
app.get('/api/validate', (req, res) => {
  try {
    const initData = req.query.initData;
    if (!initData) return res.status(400).json({ ok: false, error: 'no_initData' });

    const params = new URLSearchParams(initData);
    const hash = params.get('hash');
    if (!hash) return res.status(400).json({ ok: false, error: 'no_hash' });

    const pairs = [];
    for (const [k, v] of params.entries()) if (k !== 'hash') pairs.push(`${k}=${v}`);
    pairs.sort();
    const dataCheckString = pairs.join('\n');

    const botToken = process.env.BOT_TOKEN;
    if (!botToken) return res.status(500).json({ ok: false, error: 'no_bot_token' });

    // secret_key = HMAC_SHA256(bot_token, key="WebAppData")
    const secretKey = crypto.createHmac('sha256', 'WebAppData').update(botToken).digest();
    const calcHash  = crypto.createHmac('sha256', secretKey).update(dataCheckString).digest('hex');

    if (calcHash !== hash) return res.status(401).json({ ok: false, error: 'bad_hash' });

    const authDate = Number(params.get('auth_date') || 0);
    const age = Math.floor(Date.now() / 1000) - authDate;
    if (authDate && age > 24 * 3600) return res.status(401).json({ ok: false, error: 'expired' });

    const userStr = params.get('user');
    const user = userStr ? JSON.parse(userStr) : null;

    res.json({ ok: true, user });
  } catch (e) {
    console.error(e);
    res.status(500).json({ ok: false, error: 'server_error' });
  }
});
// -------------------------------------------

// ---------- Python bootstrap ----------
function run(cmd, args, opts = {}) {
  return new Promise(resolve => {
    const p = spawn(cmd, args, { stdio: 'inherit', ...opts });
    p.on('exit', code => resolve(code === 0));
  });
}

async function ensurePip() {
  // 1) попробуем pip
  if (await run(PY, ['-m', 'pip', '--version'], { cwd: ROOT })) return true;

  // 2) попробуем ensurepip (если модуль есть)
  if (await run(PY, ['-m', 'ensurepip', '--upgrade'], { cwd: ROOT })) {
    return await run(PY, ['-m', 'pip', '--version'], { cwd: ROOT });
  }

  // 3) жёсткий bootstrap без curl/wget: качаем get-pip.py через urllib и исполняем
  const inline = `
import urllib.request, ssl
url = "https://bootstrap.pypa.io/get-pip.py"
print("[pip] downloading get-pip.py ...")
ctx = None
try:
    ctx = ssl.create_default_context()
except Exception:
    ctx = None
code = urllib.request.urlopen(url, context=ctx).read().decode("utf-8")
print("[pip] installing via get-pip.py ...")
exec(code)
print("[pip] installed")
`;
  if (!await run(PY, ['-c', inline], { cwd: ROOT })) return false;
  return await run(PY, ['-m', 'pip', '--version'], { cwd: ROOT });
}

async function installPyDeps() {
  if (!fs.existsSync(PY_TARGET)) fs.mkdirSync(PY_TARGET, { recursive: true });
  const reqFile = path.join(ROOT, 'requirements.txt');

  // если есть requirements.txt — используем его, иначе ставим минимум
  const args = fs.existsSync(reqFile)
    ? ['-m', 'pip', 'install', '--no-cache-dir', '--upgrade', '-r', 'requirements.txt', '--target', PY_TARGET]
    : ['-m', 'pip', 'install', '--no-cache-dir', '--upgrade', 'aiogram', 'python-dotenv', '--target', PY_TARGET];

  const ok = await run(PY, args, { cwd: ROOT });
  if (!ok) console.error('[pip] install failed (packages may be missing)');
}

async function preparePython() {
  const ok = await ensurePip();
  if (!ok) {
    console.error('[pip] cannot bootstrap pip — Python в образе слишком урезан');
    return;
  }
  await installPyDeps();
}
// ---------------------------------------

// ---------- Bot runner ----------
function startPythonBot() {
  const env = {
    ...process.env,
    PYTHONPATH: [PY_TARGET, process.env.PYTHONPATH || ''].filter(Boolean).join(':'),
    PYTHONNOUSERSITE: '1'
  };
  const botPath = path.join(ROOT, 'bot.py');

  const child = spawn(PY, [botPath], { cwd: ROOT, env, stdio: 'inherit' });
  console.log(`[bot] started pid=${child.pid}`);

  child.on('exit', (code, signal) => {
    console.log(`[bot] exited code=${code} signal=${signal} -> restart in 5s`);
    setTimeout(startPythonBot, 5000);
  });
  child.on('error', err => console.error('[bot] failed to start:', err?.message));
}
// ---------------------------------

// Start sequence: prepare python → bot → API
preparePython()
  .catch(err => console.error('[pip] error:', err?.message))
  .finally(() => {
    startPythonBot();
    app.listen(PORT, HOST, () => console.log(`API listening on ${HOST}:${PORT}`));
  });

process.on('SIGTERM', () => process.exit(0));
process.on('SIGINT',  () => process.exit(0));
