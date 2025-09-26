import path from 'path';
import { fileURLToPath } from 'url';

// 1) загружаем .env ИМЕННО из корня
const __filename = fileURLToPath(import.meta.url);
const __dirname  = path.dirname(__filename);
import dotenv from 'dotenv';
dotenv.config({ path: path.resolve(__dirname, '..', '.env') });

// дальше обычные импорты
import express from 'express';
import cors from 'cors';
import crypto from 'crypto';
import { spawn } from 'child_process';
import fs from 'fs';
import https from 'https';
import { PrismaClient } from '@prisma/client';

const ROOT      = path.resolve(__dirname, '..');
const HOST      = '0.0.0.0';
const PORT      = process.env.PORT || 8080;
const PY        = process.env.PYTHON || 'python3';
const PY_TARGET = path.join(ROOT, '.pylibs');          // куда ставим пакеты
const BIN_DIR   = path.join(PY_TARGET, 'bin');         // тут будет prisma-client-py

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

// Prisma client (используем один экземпляр)
const prisma = new PrismaClient();

// health
app.get('/', (_req, res) => res.send('OK'));
app.get('/health', (_req, res) => res.json({ ok: true }));

// validate Telegram initData
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

// ---------- helpers ----------
function run(cmd, args, opts = {}) {
  return new Promise(resolve => {
    const p = spawn(cmd, args, { stdio: 'inherit', ...opts });
    p.on('exit', code => resolve(code === 0));
  });
}

async function ensurePip() {
  // есть ли pip?
  const ok = await run(PY, ['-m', 'pip', '--version'], { cwd: ROOT });
  if (ok) return;

  console.log('[pip] downloading get-pip.py ...');
  const tmp = '/tmp/get-pip.py';
  await new Promise((resolve, reject) => {
    const file = fs.createWriteStream(tmp);
    https.get('https://bootstrap.pypa.io/get-pip.py', res => {
      if (res.statusCode !== 200) return reject(new Error('get-pip http ' + res.statusCode));
      res.pipe(file);
      file.on('finish', () => file.close(resolve));
    }).on('error', reject);
  });

  console.log('[pip] installing via get-pip.py ...');
  await run(PY, [tmp], { cwd: ROOT });
}

async function installPyDeps() {
  const hasReq = fs.existsSync(path.join(ROOT, 'requirements.txt'));
  const args = hasReq
    ? ['-m', 'pip', 'install', '--no-cache-dir', '--upgrade', '-r', 'requirements.txt', '--target', PY_TARGET]
    : ['-m', 'pip', 'install', '--no-cache-dir', '--upgrade', 'aiogram', 'python-dotenv', 'prisma', '--target', PY_TARGET];

  const ok = await run(PY, args, { cwd: ROOT });
  if (!ok) console.error('[pip] install failed (packages may be missing)');
}

async function preparePrisma() {
  const env = {
    ...process.env,
    PYTHONPATH: [PY_TARGET, process.env.PYTHONPATH || ''].filter(Boolean).join(':'), // импорт из .pylibs
    PATH: [BIN_DIR, process.env.PATH || ''].filter(Boolean).join(':'),               // найдётся prisma-client-py
  };

  console.log('[prisma] generate...');
  const okGen = await run(PY, ['-m', 'prisma', 'generate'], { cwd: ROOT, env });
  if (!okGen) console.error('[prisma] generate failed');

  console.log('[prisma] db push...');
  const okPush = await run(PY, ['-m', 'prisma', 'db', 'push', '--accept-data-loss'], { cwd: ROOT, env });
  if (!okPush) console.error('[prisma] db push failed (check DATABASE_URL)');
}

function startPythonBot() {
  const env = {
    ...process.env,
    PYTHONPATH: [PY_TARGET, process.env.PYTHONPATH || ''].filter(Boolean).join(':'),
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

// ---------- boot ----------
(async () => {
  try {
    // 1) pip
    await ensurePip();
    // 2) зависимости
    await installPyDeps();
    // 3) prisma generate + db push
    await preparePrisma();
  } finally {
    // 4) бот + API
    startPythonBot();
    app.listen(PORT, () => {
      console.log(`✅ Server is running on port ${PORT}`);
    });

  }
})();

process.on('SIGTERM', () => process.exit(0));
process.on('SIGINT',  () => process.exit(0));

// ---------------------------
// [GET] /api/user?initData=...
// ---------------------------
app.get('/api/user', async (req, res) => {
  try {
    const initData = req.query.initData;
    if (!initData || typeof initData !== 'string') {
      return res.status(400).json({ ok: false, error: 'no_initData' });
    }

    // 1) валидируем подпись точно так же, как в /api/validate
    const params = new URLSearchParams(initData);
    const hash = params.get('hash');
    if (!hash) return res.status(400).json({ ok: false, error: 'no_hash' });

    const pairs = [];
    for (const [k, v] of params.entries()) if (k !== 'hash') pairs.push(`${k}=${v}`);
    pairs.sort();
    const dataCheckString = pairs.join('\n');

    const botToken = process.env.BOT_TOKEN;
    if (!botToken) return res.status(500).json({ ok: false, error: 'no_bot_token' });

    const secretKey = crypto.createHmac('sha256', 'WebAppData').update(botToken).digest();
    const calcHash  = crypto.createHmac('sha256', secretKey).update(dataCheckString).digest('hex');

    if (calcHash !== hash) return res.status(401).json({ ok: false, error: 'bad_hash' });

    // 2) получаем user из подписанной строки
    const userStr = params.get('user');
    const user = userStr ? JSON.parse(userStr) : null;
    const tg_id = user?.id ? Number(user.id) : null;
    if (!tg_id) return res.status(400).json({ ok: false, error: 'no_tg_id' });

    // 3) подгружаем профиль из Prisma (таблица user — см. schema.prisma)
    let dbUser = null;
    try {
      dbUser = await prisma.user.findUnique({
        where: { tg_id: Number(tg_id) },
      });
    } catch (e) {
      console.error('[prisma] findUnique error', e);
      return res.status(500).json({ ok: false, error: 'db_error' });
    }

    if (!dbUser) {
      // Не найден пользователь в БД — возвращаем минимальные данные (имя из Telegram)
      const profile = {
        first_name: user?.first_name || null,
        tariffName: null
      };
      return res.json({ ok: true, user, profile });
    }

    // 4) Нормализуем профиль для фронта: гарантируем поля first_name и tariffName
    const profile = {
      first_name: dbUser.first_name || dbUser.name || user?.first_name || null,
      tariffName: dbUser.tariffName || dbUser.tariff || null,
      // при желании можно вернуть дополнительные поля:
      // tg_id: dbUser.tg_id, email: dbUser.email, etc.
    };

    return res.json({ ok: true, user, profile });
  } catch (e) {
    console.error('[api/user] error', e);
    res.status(500).json({ ok: false, error: 'server_error' });
  }
});
