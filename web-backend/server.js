import 'dotenv/config';
import express from 'express';
import cors from 'cors';
import crypto from 'crypto';
import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const ROOT = path.resolve(__dirname, '..');
const HOST = '0.0.0.0';
const PORT = process.env.PORT || 8080;
const PY = process.env.PYTHON || 'python3';           // можно переопределить на "python"
const PY_TARGET = path.join(ROOT, '.pylibs');         // сюда ставим пакеты бота локально

const CORS_ORIGIN = (process.env.CORS_ORIGIN || '*')
  .split(',')
  .map(s => s.trim())
  .filter(Boolean);

const app = express();
app.use(cors({
  origin: (origin, cb) => {
    if (!origin || CORS_ORIGIN.includes('*') || CORS_ORIGIN.includes(origin)) return cb(null, true);
    return cb(new Error('Not allowed by CORS'));
  }
}));
app.use(express.json());

// простые health-эндпоинты (удобны для проверок)
app.get('/', (req, res) => res.send('OK'));
app.get('/health', (req, res) => res.json({ ok: true }));

// --- Telegram WebApp initData validation ---
app.get('/api/validate', (req, res) => {
  try {
    const initData = req.query.initData;
    if (!initData) return res.status(400).json({ ok: false, error: 'no_initData' });

    const params = new URLSearchParams(initData);
    const hash = params.get('hash');
    if (!hash) return res.status(400).json({ ok: false, error: 'no_hash' });

    // data_check_string: sorted "<key>=<value>" joined by "\n", без hash
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

    // опционально: протухание через 24ч
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

// --- утилиты для подготовки python-зависимостей ---
function run(cmd, args, opts = {}) {
  return new Promise((resolve) => {
    const p = spawn(cmd, args, { stdio: 'inherit', ...opts });
    p.on('exit', (code) => resolve(code === 0));
  });
}

async function preparePython() {
  // поднимем pip, если его нет (операция идемпотентна)
  await run(PY, ['-m', 'ensurepip', '--upgrade'], { cwd: ROOT });

  // ставим зависимости бота локально в .pylibs
  const hasReq = fs.existsSync(path.join(ROOT, 'requirements.txt'));
  const args = hasReq
    ? ['-m', 'pip', 'install', '--no-cache-dir', '--upgrade', '-r', 'requirements.txt', '--target', PY_TARGET]
    : ['-m', 'pip', 'install', '--no-cache-dir', '--upgrade', 'aiogram', 'python-dotenv', 'prisma', '--target', PY_TARGET];

  const ok = await run(PY, args, { cwd: ROOT });
  if (!ok) console.error('[pip] install failed (packages may be missing)');
}

// --- запуск бота как подпроцесса ---
function startPythonBot() {
  const env = {
    ...process.env,
    // чтобы python "увидел" локально установленные либы
    PYTHONPATH: [PY_TARGET, process.env.PYTHONPATH || ''].filter(Boolean).join(':')
  };
  const botPath = path.join(ROOT, 'bot.py');

  const child = spawn(PY, [botPath], { cwd: ROOT, env, stdio: 'inherit' });
  console.log(`[bot] started pid=${child.pid}`);

  child.on('exit', (code, signal) => {
    console.log(`[bot] exited code=${code} signal=${signal} -> restart in 5s`);
    setTimeout(startPythonBot, 5000);
  });

  child.on('error', (err) => {
    console.error('[bot] failed to start:', err?.message);
  });
}

// --- запуск: подготовка питона -> бот -> API ---
preparePython()
  .catch(err => console.error('[pip] error:', err?.message))
  .finally(() => {
    startPythonBot();
    app.listen(PORT, HOST, () => console.log(`API listening on ${HOST}:${PORT}`));
  });

// аккуратное завершение
process.on('SIGTERM', () => process.exit(0));
process.on('SIGINT',  () => process.exit(0));
