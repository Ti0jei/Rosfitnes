(function () {
  // Telegram WebApp API (если запущено внутри Telegram)
  const tg = (window.Telegram && window.Telegram.WebApp) ? window.Telegram.WebApp : null;
  const qs = new URLSearchParams(location.search);

  // URL вашего бэкенда (Express из web-backend/server.js)
  const API_BASE = "https://ti0jei-rosfitnes-c178.twc1.net";

  // DOM-узлы
  const envStatus   = document.getElementById('envStatus');
  const greetingEl  = document.getElementById('greeting');
  const tariffEl    = document.getElementById('tariff');
  const themeNameEl = document.getElementById('themeName');

  // Тема из Telegram
  const setCSSFromTheme = (p = {}) => {
    const map = {
      '--bg':     p.bg_color,
      '--text':   p.text_color,
      '--card':   p.secondary_bg_color,
      '--card-2': p.section_bg_color,
    };
    for (const [k, v] of Object.entries(map)) {
      if (v) document.documentElement.style.setProperty(k, v);
    }
  };

  // Алёрты (работают и вне Telegram)
  const showAlert = (msg) => (tg?.showAlert ? tg.showAlert(msg) : alert(msg));

  // Дождаться готовности WebApp (если есть)
  const waitReady = () => { try { tg?.ready?.(); } catch (_) {} };

  // Сбор корректной строки initData:
  // 1) используем tg.initData, если он не пуст;
  // 2) иначе собираем строку из tg.initDataUnsafe (на некоторых клиентах Telegram initData пустой).
  function buildInitData() {
    const raw = (tg && tg.initData) || '';
    if (raw && raw.length > 0) return raw;

    const u = tg?.initDataUnsafe || null;
    if (!u || !u.hash) return ''; // вне Telegram или без подписи — не валидируемся

    const p = new URLSearchParams();
    if (u.query_id)      p.set('query_id', u.query_id);
    if (u.user)          p.set('user', JSON.stringify(u.user));
    if (u.auth_date)     p.set('auth_date', String(u.auth_date));
    if (u.start_param)   p.set('start_param', u.start_param);
    if (u.chat_type)     p.set('chat_type', u.chat_type);
    if (u.chat_instance) p.set('chat_instance', u.chat_instance);
    p.set('hash', u.hash);

    return p.toString();
  }

  // Подтянуть профиль/тариф после успешной валидации
  async function fetchUserAndRender(initData) {
    try {
      const res = await fetch(`${API_BASE}/api/user?initData=${encodeURIComponent(initData)}`);
      const json = await res.json().catch(() => ({}));
      if (!json?.ok) return;

      // Имя в приветствии
      const fn = json.profile?.first_name || json.user?.first_name;
      if (fn) greetingEl.textContent = `Привет, ${fn}!`;

      // Тариф
      const tariff = json.profile?.tariffName || 'не куплен';
      tariffEl.textContent = `Тариф: ${tariff}`;
    } catch (e) {
      // Тихо игнорируем — тариф можно оставить как есть
      console.warn('[user] fetch failed', e);
    }
  }

  async function init() {
    try {
      // Блок Telegram UI/Theme (если открыто в Telegram)
      if (tg) {
        waitReady();
        tg.expand?.();
        setCSSFromTheme(tg.themeParams || {});
        themeNameEl.textContent = `Тема: ${tg.colorScheme || 'system'}`;

        const u = tg.initDataUnsafe?.user;
        if (u?.first_name) greetingEl.textContent = `Привет, ${u.first_name}!`;
      }

      // Временный тариф из query (?tariff=Базовый/Выгодный/Максимум)
      const qpTariff = qs.get('tariff');
      tariffEl.textContent = `Тариф: ${qpTariff || 'неизвестно'}`;

      // Заглушки разделов
      document.querySelectorAll('.tile').forEach(btn => {
        btn.addEventListener('click', () => {
          const action = btn.getAttribute('data-action');
          showAlert(`«${action}» — раздел в разработке`);
        });
      });

      // Проверка доступа и подгрузка тарифа с бэка
      if (API_BASE && tg) {
        envStatus.hidden = false;
        envStatus.textContent = 'Проверка доступа…';

        const initData = buildInitData(); // <-- ключевое отличие
        const res = await fetch(`${API_BASE}/api/validate?initData=${encodeURIComponent(initData)}`);
        const json = await res.json().catch(() => ({}));

        if (json?.ok) {
          envStatus.textContent = 'Доступ подтверждён';
          envStatus.style.color = '#6dd96d';
          // После валидации тянем профиль/тариф
          await fetchUserAndRender(initData);
        } else {
          envStatus.textContent = `Нет доступа: ${json?.error || 'unknown'}`;
          envStatus.style.color = '#ff7a7a';
        }
      }
    } catch (e) {
      console.error(e);
      showAlert('Ошибка инициализации приложения');
    }
  }
// --- DEBUG EXPORTS ---
window.API_BASE = API_BASE;
window.tg = tg;
window.buildInitData = typeof buildInitData === 'function' ? buildInitData : () => (tg?.initData || '');

  init();
})();
