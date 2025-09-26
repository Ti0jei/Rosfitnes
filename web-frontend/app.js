(function () {
  // Telegram WebApp API (если запущено внутри Telegram)
  const tg = window.Telegram?.WebApp || null;
  const qs = new URLSearchParams(location.search);

  // URL вашего бэкенда (Express из web-backend/server.js)
  const API_BASE = window.ENV?.API_BASE || "";

  // DOM-элементы
  const envStatus   = document.getElementById('envStatus');
  const greetingEl  = document.getElementById('greeting');
  const tariffEl    = document.getElementById('tariff');
  const themeNameEl = document.getElementById('themeName');

  // Установка кастомных CSS-переменных из темы Telegram
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

  // Показывать alert либо системный, либо telegram-овский
  const showAlert = (msg) => (tg?.showAlert ? tg.showAlert(msg) : alert(msg));

  // Telegram WebApp ready
  const waitReady = () => { try { tg?.ready?.(); } catch (_) {} };

  // Строим initData, если не передан как строка (собираем вручную из unsafe)
  function buildInitData() {
    const raw = tg?.initData || '';
    if (raw && raw.length > 0) return raw;

    const u = tg?.initDataUnsafe || null;
    if (!u || !u.hash) return '';

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

  // Получить данные пользователя и тарифа после валидации
  async function fetchUserAndRender(initData) {
    try {
      const res = await fetch(`${API_BASE}/api/user?initData=${encodeURIComponent(initData)}`);
      const json = await res.json().catch(() => ({}));
      if (!json?.ok) return;

      const name = json.profile?.first_name || json.user?.first_name || 'друг';
      const tariff = json.profile?.tariffName || 'неизвестно';

      greetingEl.textContent = `Привет, ${name}!`;
      tariffEl.textContent = `Тариф: ${tariff}`;
      renderTilesByTariff(tariff);
    } catch (e) {
      console.warn('[user] fetch failed', e);
    }
  }
function renderTilesByTariff(tariff) {
  const tiles = document.getElementById("tiles");
  if (!tiles) return;

  tiles.innerHTML = ""; // очищаем

    let actions = [];

  if (tariff === "Базовый") {
    actions = [
      "Тренировки",
      "Дневник тренировок",
      "Дневник питания",
      "Упражнения"
    ];
  } else if (tariff === "Выгодный") {
    actions = [
      "Тренировки",
      "Дневник тренировок",
      "Дневник питания",
      "Упражнения",
      "Связь с куратором"
    ];
  } else {
    actions = [
      "Тренировки",
      "Дневник тренировок",
      "Дневник питания",
      "Упражнения"
    ];
  }


  actions.forEach(label => {
    const tile = document.createElement("button");
    tile.className = "tile";
    tile.dataset.action = label;
    tile.innerHTML = `
      <div class="title">${label}</div>
      <div class="desc">Раздел в разработке</div>
    `;
    tile.addEventListener("click", () => showAlert(`«${label}» — раздел в разработке`));
    tiles.appendChild(tile);
  });
}

  async function init() {
    try {
      if (tg) {
        waitReady();
        tg.expand?.();
        setCSSFromTheme(tg.themeParams || {});
        themeNameEl.textContent = `Тема: ${tg.colorScheme || 'system'}`;

        const u = tg.initDataUnsafe?.user;
        if (u?.first_name) greetingEl.textContent = `Привет, ${u.first_name}!`;
      }

      const qpTariff = qs.get('tariff');
      tariffEl.textContent = `Тариф: ${qpTariff || 'неизвестно'}`;

      // Кнопки-заглушки
      document.querySelectorAll('.tile').forEach(btn => {
        btn.addEventListener('click', () => {
          const action = btn.getAttribute('data-action');
          showAlert(`«${action}» — раздел в разработке`);
        });
      });

      // Валидация initData через бэкенд
      if (API_BASE && tg) {
        envStatus.hidden = false;
        envStatus.textContent = 'Проверка доступа…';

        const initData = buildInitData();
        const res = await fetch(`${API_BASE}/api/validate?initData=${encodeURIComponent(initData)}`);
        const json = await res.json().catch(() => ({}));

        if (json?.ok) {
          envStatus.textContent = 'Доступ подтверждён';
          envStatus.style.color = '#6dd96d';
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
  window.buildInitData = buildInitData;

  console.log("tg.initData:", tg?.initData);
  console.log("tg.initDataUnsafe:", tg?.initDataUnsafe);

  init();
})();
