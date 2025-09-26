(function () {
  const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
  const qs = new URLSearchParams(location.search);

  // Пропиши URL бэкенда если поднимешь API (иначе оставь пустым)
  const API_BASE = ""; // например: "https://api.example.com"

  const envStatus = document.getElementById('envStatus');
  const greetingEl = document.getElementById('greeting');
  const tariffEl = document.getElementById('tariff');
  const themeNameEl = document.getElementById('themeName');

  const setCSSFromTheme = (p = {}) => {
    const map = {
      '--bg': p.bg_color,
      '--text': p.text_color,
      '--card': p.secondary_bg_color,
      '--card-2': p.section_bg_color,
    };
    for (const [k, v] of Object.entries(map)) if (v) document.documentElement.style.setProperty(k, v);
  };

  const showAlert = (msg) => { if (tg?.showAlert) tg.showAlert(msg); else alert(msg); };

  const init = async () => {
    try {
      if (tg) {
        tg.ready();
        tg.expand();
        setCSSFromTheme(tg.themeParams || {});
        themeNameEl.textContent = `Тема: ${tg.colorScheme || 'system'}`;
        const u = tg.initDataUnsafe?.user;
        if (u?.first_name) greetingEl.textContent = `Привет, ${u.first_name}!`;
      }

      // Тариф из query (?tariff=Базовый/Выгодный/Максимум) — временно
      const qpTariff = qs.get('tariff');
      tariffEl.textContent = `Тариф: ${qpTariff || 'неизвестно'}`;

      // Кнопки-заглушки
      document.querySelectorAll('.tile').forEach(btn => {
        btn.addEventListener('click', () => {
          const action = btn.getAttribute('data-action');
          showAlert(`«${action}» — раздел в разработке`);
        });
      });

      // Проверка initData на бэкенде (опционально)
      if (tg && API_BASE) {
        envStatus.hidden = false;
        envStatus.textContent = 'Проверка доступа…';
        const res = await fetch(`${API_BASE}/api/validate?initData=${encodeURIComponent(tg.initData || '')}`);
        const json = await res.json().catch(() => ({}));
        if (json.ok) { envStatus.textContent = 'Доступ подтверждён'; envStatus.style.color = '#6dd96d'; }
        else { envStatus.textContent = `Нет доступа: ${json.error || 'unknown'}`; envStatus.style.color = '#ff7a7a'; }
      }
    } catch (e) {
      console.error(e);
      showAlert('Ошибка инициализации приложения');
    }
  };

  init();
})();
