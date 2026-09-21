from fastapi.responses import HTMLResponse

def get_admin_html() -> str:
    return r"""<!DOCTYPE html>
<html lang="ru" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Bor Snitch CMS — Панель Управления</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            snitch: {
              50: '#f0fdf4',
              100: '#dcfce7',
              500: '#22c55e',
              600: '#16a34a',
              900: '#14532d',
              dark: '#0b0f17',
              panel: '#111827',
              border: '#1f2937',
              input: '#1f2937',
              card: '#151d2c'
            }
          }
        }
      }
    }
  </script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    body {
      font-family: 'Plus Jakarta Sans', sans-serif;
      background-color: #090d16;
      color: #e2e8f0;
    }
    code, pre, .font-mono {
      font-family: 'JetBrains Mono', monospace;
    }
    /* Custom scrollbar */
    ::-webkit-scrollbar {
      width: 8px;
      height: 8px;
    }
    ::-webkit-scrollbar-track {
      background: #0d131f;
    }
    ::-webkit-scrollbar-thumb {
      background: #253349;
      border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
      background: #374b6a;
    }
  </style>
</head>
<body class="min-h-screen flex flex-col bg-[#090d16] text-slate-200">

  <!-- Toast Notification Container -->
  <div id="toast-container" class="fixed top-4 right-4 z-50 flex flex-col space-y-2 pointer-events-none"></div>

  <!-- LOGIN SCREEN (shown when unauthenticated) -->
  <div id="login-view" class="flex-1 flex items-center justify-center p-4">
    <div class="w-full max-w-md bg-[#111827] border border-slate-800 rounded-2xl p-8 shadow-2xl relative overflow-hidden">
      <div class="absolute -top-24 -right-24 w-48 h-48 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none"></div>
      <div class="text-center mb-8">
        <div class="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-3xl mb-4">
          🏆🐀
        </div>
        <h1 class="text-2xl font-bold text-white tracking-tight">Bor Snitch CMS</h1>
        <p class="text-sm text-slate-400 mt-1">Центр управления ботом, базой и промптами</p>
      </div>

      <form id="login-form" onsubmit="handleLogin(event)" class="space-y-5">
        <div>
          <label class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Пароль Администратора</label>
          <input type="password" id="login-password" required autocomplete="current-password"
                 class="w-full px-4 py-3 bg-[#1a2333] border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition font-mono text-sm"
                 placeholder="Введите пароль из .env...">
        </div>
        <div id="login-error" class="hidden p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs font-medium"></div>
        <button type="submit" id="login-submit-btn"
                class="w-full py-3.5 px-4 bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 text-white font-semibold rounded-xl transition duration-150 shadow-lg shadow-emerald-900/30 flex items-center justify-center gap-2">
          <span>Войти в систему</span>
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"/></svg>
        </button>
      </form>
    </div>
  </div>

  <!-- DASHBOARD APP (shown when authenticated) -->
  <div id="app-view" class="hidden flex-1 flex flex-col">
    <!-- Top Navigation Header -->
    <header class="bg-[#101726] border-b border-slate-800 sticky top-0 z-30">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex items-center justify-between h-16">
          <div class="flex items-center gap-3">
            <span class="text-2xl">🏆🐀</span>
            <div>
              <div class="flex items-center gap-2">
                <span class="font-bold text-white text-base tracking-tight">Bor Snitch</span>
                <span class="text-xs px-2 py-0.5 rounded-full font-mono bg-slate-800 text-slate-400 border border-slate-700">CMS</span>
              </div>
            </div>
          </div>

          <!-- Quick Bot Status Indicator & Global Switch -->
          <div class="flex items-center gap-4">
            <div id="bot-status-badge" class="flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              <span id="bot-status-text">Бот активен</span>
            </div>

            <button onclick="toggleBotQuickly()" id="quick-bot-toggle-btn"
                    class="text-xs font-medium px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition flex items-center gap-1.5">
              <span id="quick-bot-toggle-label">Остановить</span>
            </button>

            <!-- Active Chat Selector -->
            <div class="flex items-center gap-1.5">
              <span class="text-xs text-slate-400 hidden sm:inline">Чат:</span>
              <select id="global-chat-select" onchange="onChatChanged()"
                      class="bg-[#1a2333] border border-slate-700 text-xs rounded-lg px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-emerald-500">
                <option value="">Загрузка чатов...</option>
              </select>
            </div>

            <!-- Logout Button -->
            <button onclick="handleLogout()" title="Выйти"
                    class="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/></svg>
            </button>
          </div>
        </div>

        <!-- Navigation Tabs -->
        <nav class="flex space-x-1 sm:space-x-4 overflow-x-auto border-t border-slate-800/60 py-1.5 text-sm">
          <button onclick="switchTab('config')" data-tab="config"
                  class="tab-btn px-3 py-1.5 rounded-lg font-medium text-xs sm:text-sm whitespace-nowrap transition text-slate-400 hover:text-white hover:bg-slate-800/60">
            ⚙️ Настройки бота
          </button>
          <button onclick="switchTab('prompts')" data-tab="prompts"
                  class="tab-btn px-3 py-1.5 rounded-lg font-medium text-xs sm:text-sm whitespace-nowrap transition text-slate-400 hover:text-white hover:bg-slate-800/60">
            🧠 Студия промптов
          </button>
          <button onclick="switchTab('chat')" data-tab="chat"
                  class="tab-btn px-3 py-1.5 rounded-lg font-medium text-xs sm:text-sm whitespace-nowrap transition text-slate-400 hover:text-white hover:bg-slate-800/60 flex items-center gap-1.5">
            <span>💬</span> <span>Чат</span>
          </button>
          <button onclick="switchTab('users')" data-tab="users"
                  class="tab-btn px-3 py-1.5 rounded-lg font-medium text-xs sm:text-sm whitespace-nowrap transition text-slate-400 hover:text-white hover:bg-slate-800/60">
            👥 Участники и Очки
          </button>
          <button onclick="switchTab('lore')" data-tab="lore"
                  class="tab-btn px-3 py-1.5 rounded-lg font-medium text-xs sm:text-sm whitespace-nowrap transition text-slate-400 hover:text-white hover:bg-slate-800/60">
            📜 Лор и Факты
          </button>
          <button onclick="switchTab('agreements')" data-tab="agreements"
                  class="tab-btn px-3 py-1.5 rounded-lg font-medium text-xs sm:text-sm whitespace-nowrap transition text-slate-400 hover:text-white hover:bg-slate-800/60">
            🤝 Договоренности
          </button>
          <button onclick="switchTab('lessons')" data-tab="lessons"
                  class="tab-btn px-3 py-1.5 rounded-lg font-medium text-xs sm:text-sm whitespace-nowrap transition text-slate-400 hover:text-white hover:bg-slate-800/60">
            🎓 Уроки и Обучение
          </button>
          <button onclick="switchTab('actions')" data-tab="actions"
                  class="tab-btn px-3 py-1.5 rounded-lg font-medium text-xs sm:text-sm whitespace-nowrap transition text-slate-400 hover:text-white hover:bg-slate-800/60">
            ⚡ Операции
          </button>
        </nav>
      </div>
    </header>

    <!-- MAIN CONTENT AREA -->
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 w-full flex-1">

      <!-- ================= TAB: CONFIG ================= -->
      <section id="tab-content-config" class="tab-pane hidden space-y-6">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-[#111827] p-5 rounded-2xl border border-slate-800">
          <div>
            <h2 class="text-lg font-bold text-white flex items-center gap-2">
              <span>⚙️</span> Рабочие параметры бота
            </h2>
            <p class="text-xs text-slate-400">Изменения сохраняются в Firestore и применяются ботом на лету без перезапуска</p>
          </div>
          <div class="flex items-center gap-2">
            <button onclick="resetConfigToDefaults()"
                    class="px-3 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-rose-300 border border-slate-700 transition">
              Сбросить к дефолту
            </button>
            <button onclick="saveConfigForm()"
                    class="px-4 py-2 rounded-xl text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-900/30 transition flex items-center gap-1.5">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
              <span>Сохранить настройки</span>
            </button>
          </div>
        </div>

        <form id="config-form" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">

          <!-- Card: Bot State & AI Models -->
          <div class="bg-[#111827] border border-slate-800 rounded-2xl p-5 space-y-4">
            <h3 class="text-sm font-bold text-emerald-400 uppercase tracking-wider flex items-center gap-2">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>
              Режим & Модели AI
            </h3>

            <div>
              <label class="flex items-center justify-between p-3 rounded-xl bg-[#162032] border border-slate-800 cursor-pointer">
                <div>
                  <div class="text-sm font-semibold text-white">Отключить бота</div>
                  <div class="text-xs text-slate-400">Бот игнорирует сообщения и команды</div>
                </div>
                <input type="checkbox" id="cfg-BOT_DISABLED" class="w-5 h-5 accent-rose-500 rounded cursor-pointer">
              </label>
            </div>

            <div>
              <label class="block text-xs font-medium text-slate-400 mb-1">Модель для анализа (Daily & Report)</label>
              <input type="text" id="cfg-AI_MODEL_ANALYSIS"
                     class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-white font-mono focus:outline-none focus:border-emerald-500">
              <div class="text-[10px] text-slate-500 mt-1">Пример: gemini-3.8-flash, gemini-2.0-flash</div>
            </div>

            <div>
              <label class="block text-xs font-medium text-slate-400 mb-1">Модель для комментатора & мультимодал</label>
              <input type="text" id="cfg-AI_MODEL_MULTIMODAL"
                     class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-white font-mono focus:outline-none focus:border-emerald-500">
            </div>

            <div>
              <label class="block text-xs font-medium text-slate-400 mb-1">Таймзона (Часовой пояс)</label>
              <input type="number" id="cfg-TIMEZONE_OFFSET"
                     class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-white font-mono focus:outline-none focus:border-emerald-500">
              <div class="text-[10px] text-slate-500 mt-1">3 = МСК (UTC+3)</div>
            </div>
          </div>

          <!-- Card: Points Rules -->
          <div class="bg-[#111827] border border-slate-800 rounded-2xl p-5 space-y-4">
            <h3 class="text-sm font-bold text-amber-400 uppercase tracking-wider flex items-center gap-2">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
              Тарифная сетка (Очки)
            </h3>

            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-xs font-medium text-slate-400 mb-1">Токсичность</label>
                <input type="number" id="cfg-POINTS_TOXICITY" class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-white font-mono">
              </div>
              <div>
                <label class="block text-xs font-medium text-slate-400 mb-1">Снитчевание/Игнор</label>
                <input type="number" id="cfg-POINTS_SNITCHING" class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-white font-mono">
              </div>
              <div>
                <label class="block text-xs font-medium text-slate-400 mb-1">AFK База (3 дня)</label>
                <input type="number" id="cfg-POINTS_AFK_BASE" class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-white font-mono">
              </div>
              <div>
                <label class="block text-xs font-medium text-slate-400 mb-1">AFK в день</label>
                <input type="number" id="cfg-POINTS_AFK_DAILY" class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-white font-mono">
              </div>
              <div>
                <label class="block text-xs font-medium text-slate-400 mb-1">Нытье (0=откл)</label>
                <input type="number" id="cfg-POINTS_WHINING" class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-white font-mono">
              </div>
              <div>
                <label class="block text-xs font-medium text-slate-400 mb-1">Духота (0=откл)</label>
                <input type="number" id="cfg-POINTS_STIFFNESS" class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-white font-mono">
              </div>
            </div>

            <div class="pt-2 border-t border-slate-800">
              <label class="block text-xs font-medium text-slate-400 mb-1">Штраф за ложный донос (/report)</label>
              <input type="number" id="cfg-FALSE_REPORT_PENALTY" class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-white font-mono">
            </div>
          </div>

          <!-- Card: Casino & Cynical Comments -->
          <div class="bg-[#111827] border border-slate-800 rounded-2xl p-5 space-y-4">
            <h3 class="text-sm font-bold text-purple-400 uppercase tracking-wider flex items-center gap-2">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.828 14.828a4 4 0 01-5.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
              Казино & Комментатор
            </h3>

            <div>
              <div class="flex justify-between items-center mb-1">
                <label class="text-xs font-medium text-slate-400">Шанс победы в /casino</label>
                <span id="label-GAMBLE_WIN_CHANCE" class="text-xs font-mono text-purple-400 font-bold">50%</span>
              </div>
              <input type="range" id="cfg-GAMBLE_WIN_CHANCE" min="0" max="1" step="0.05" oninput="updateRangeLabel(this, '%')"
                     class="w-full accent-purple-500 cursor-pointer">
            </div>

            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-xs font-medium text-slate-400 mb-1">Списание очков (Win)</label>
                <input type="number" id="cfg-GAMBLE_WIN_POINTS" class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-white font-mono">
              </div>
              <div>
                <label class="block text-xs font-medium text-slate-400 mb-1">Штраф (Loss)</label>
                <input type="number" id="cfg-GAMBLE_LOSS_POINTS" class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-white font-mono">
              </div>
            </div>

            <div class="pt-2 border-t border-slate-800">
              <div class="flex justify-between items-center mb-1">
                <label class="text-xs font-medium text-slate-400">Шанс циничного коммента</label>
                <span id="label-CYNICAL_COMMENT_CHANCE" class="text-xs font-mono text-purple-400 font-bold">0.2%</span>
              </div>
              <input type="range" id="cfg-CYNICAL_COMMENT_CHANCE" min="0" max="0.05" step="0.001" oninput="updateRangeLabel(this, '%', 100)"
                     class="w-full accent-purple-500 cursor-pointer">
            </div>

            <div>
              <label class="block text-xs font-medium text-slate-400 mb-1">Кулдаун комментария (сек)</label>
              <input type="number" id="cfg-CYNICAL_COMMENT_COOLDOWN_SECONDS" class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-white font-mono">
            </div>

            <div>
              <label class="block text-xs font-medium text-slate-400 mb-1">Разрыв сессии чата (часов)</label>
              <input type="number" id="cfg-SESSION_TIMEOUT_HOURS" class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-white font-mono">
            </div>

            <div class="pt-3 border-t border-slate-800 space-y-3">
              <label class="flex items-center justify-between p-3 rounded-xl bg-[#162032] border border-slate-800 cursor-pointer">
                <div>
                  <div class="text-xs font-semibold text-white">Спонтанное правосудие (ИИ)</div>
                  <div class="text-[10px] text-slate-400">Бот сам начисляет очки за масть/людское в диалоге</div>
                </div>
                <input type="checkbox" id="cfg-SPONTANEOUS_JUDGMENT_ENABLED" class="w-5 h-5 accent-purple-500 rounded cursor-pointer">
              </label>

              <div>
                <label class="block text-xs font-medium text-slate-400 mb-1">Кулдаун спонтанных вердиктов (сек)</label>
                <input type="number" id="cfg-SPONTANEOUS_JUDGMENT_COOLDOWN_SECONDS" class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-white font-mono">
              </div>
            </div>
          </div>

          <!-- Card: Automatic Emoji Reactions -->
          <div class="bg-[#111827] border border-slate-800 rounded-2xl p-5 space-y-4">
            <h3 class="text-sm font-bold text-amber-400 uppercase tracking-wider flex items-center gap-2">
              <span class="text-base">🎭</span>
              Циничные Эмодзи-Реакции
            </h3>

            <div>
              <label class="flex items-center justify-between p-3 rounded-xl bg-[#162032] border border-slate-800 cursor-pointer">
                <div>
                  <div class="text-sm font-semibold text-white">Включить реакции</div>
                  <div class="text-xs text-slate-400">Бот ставит эмодзи на сообщения в чате</div>
                </div>
                <input type="checkbox" id="cfg-REACTIONS_ENABLED" class="w-5 h-5 accent-amber-500 rounded cursor-pointer">
              </label>
            </div>

            <div>
              <div class="flex justify-between items-center mb-1">
                <label class="text-xs font-medium text-slate-400">Шанс реакции (на сообщение)</label>
                <span id="label-REACTION_CHANCE" class="text-xs font-mono text-amber-400 font-bold">2.0%</span>
              </div>
              <input type="range" id="cfg-REACTION_CHANCE" min="0" max="0.10" step="0.005" oninput="updateRangeLabel(this, '%', 100)"
                     class="w-full accent-amber-500 cursor-pointer">
            </div>

            <div>
              <label class="block text-xs font-medium text-slate-400 mb-1">Кулдаун реакций (сек)</label>
              <input type="number" id="cfg-REACTION_COOLDOWN_SECONDS" class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-white font-mono">
            </div>

            <div>
              <label class="block text-xs font-medium text-slate-400 mb-1">Разрешенные эмодзи</label>
              <input type="text" id="cfg-REACTION_ALLOWED_EMOJIS" class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-white font-mono">
              <div class="text-[10px] text-slate-500 mt-1">Эмодзи через пробел (🤡 🗿 🚽 👑 🍿 👀 🔥 👌)</div>
            </div>
          </div>

          <!-- Card: Voice Digest (Криминальная хроника) -->
          <div class="bg-[#111827] border border-slate-800 rounded-2xl p-5 space-y-4">
            <h3 class="text-sm font-bold text-rose-400 uppercase tracking-wider flex items-center gap-2">
              <span class="text-base">🎙️</span>
              Голосовая Сводка (Хроника)
            </h3>

            <div>
              <label class="flex items-center justify-between p-3 rounded-xl bg-[#162032] border border-slate-800 cursor-pointer">
                <div>
                  <div class="text-sm font-semibold text-white">Включить голосовые сводки</div>
                  <div class="text-xs text-slate-400">2 раза в день бот присылает войс с итогами</div>
                </div>
                <input type="checkbox" id="cfg-VOICE_DIGEST_ENABLED" class="w-5 h-5 accent-rose-500 rounded cursor-pointer">
              </label>
            </div>

            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-xs font-medium text-slate-400 mb-1">Выпуск 1 (МСК)</label>
                <input type="text" id="cfg-VOICE_DIGEST_TIME_1" class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-white font-mono" placeholder="14:00">
                <div class="text-[10px] text-slate-500 mt-1">Обеденная сводка</div>
              </div>
              <div>
                <label class="block text-xs font-medium text-slate-400 mb-1">Выпуск 2 (МСК)</label>
                <input type="text" id="cfg-VOICE_DIGEST_TIME_2" class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-white font-mono" placeholder="22:00">
                <div class="text-[10px] text-slate-500 mt-1">Вечерний приговор</div>
              </div>
            </div>

            <div>
              <label class="block text-xs font-medium text-slate-400 mb-1">Движок озвучки (TTS Provider)</label>
              <select id="cfg-TTS_PROVIDER" class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-white">
                <option value="gemini">Google Cloud Gemini 3.1 Flash TTS (Стиль, Бесплатно)</option>
                <option value="elevenlabs">ElevenLabs (Adam)</option>
                <option value="google">Google Wavenet</option>
              </select>
            </div>

            <div>
              <label class="block text-xs font-medium text-slate-400 mb-1">Голос (Gemini TTS Voice)</label>
              <input type="text" id="cfg-GOOGLE_TTS_VOICE" class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-white font-mono" placeholder="Sadaltager">
              <div class="text-[10px] text-slate-500 mt-1">Sadaltager (мужской, солидный) | Puck | Zephyr</div>
            </div>

            <div>
              <label class="block text-xs font-medium text-slate-400 mb-1">Инструкция по стилю речи (Style Instructions)</label>
              <textarea id="cfg-GOOGLE_TTS_STYLE" rows="2" class="w-full p-2.5 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-slate-200 font-mono focus:outline-none focus:border-rose-500"></textarea>
              <div class="text-[10px] text-slate-500 mt-1">Управляет интонацией в Gemini 3.1 Flash TTS</div>
            </div>
          </div>

          <!-- Card: Context & Agreements -->
          <div class="bg-[#111827] border border-slate-800 rounded-2xl p-5 space-y-4 md:col-span-2 lg:col-span-3">
            <h3 class="text-sm font-bold text-sky-400 uppercase tracking-wider flex items-center gap-2">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
              Контекст, Лимиты и Слово Пацана (Договоренности)
            </h3>

            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
              <div>
                <label class="flex items-center justify-between p-3 rounded-xl bg-[#162032] border border-slate-800 cursor-pointer h-full">
                  <div>
                    <div class="text-xs font-semibold text-white">Модуль договоренностей</div>
                    <div class="text-[10px] text-slate-400">Команды /agreements и /dispute</div>
                  </div>
                  <input type="checkbox" id="cfg-ENABLE_AGREEMENTS" class="w-5 h-5 accent-sky-500 rounded cursor-pointer">
                </label>
              </div>

              <div>
                <label class="flex items-center justify-between p-3 rounded-xl bg-[#162032] border border-slate-800 cursor-pointer h-full">
                  <div>
                    <div class="text-xs font-semibold text-white">Учет долгов (Сплитвил)</div>
                    <div class="text-[10px] text-slate-400">Команда /debts и парсинг переводов</div>
                  </div>
                  <input type="checkbox" id="cfg-ENABLE_DEBTS" class="w-5 h-5 accent-emerald-500 rounded cursor-pointer">
                </label>
              </div>

              <div>
                <label class="block text-xs font-medium text-slate-400 mb-1">Контекст до репорта (сообщ.)</label>
                <input type="number" id="cfg-REPORT_CONTEXT_LIMIT" class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-white font-mono">
              </div>

              <div>
                <label class="block text-xs font-medium text-slate-400 mb-1">Контекст после репорта (сообщ.)</label>
                <input type="number" id="cfg-REPORT_NEXT_CONTEXT_LIMIT" class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-white font-mono">
              </div>

              <div>
                <label class="block text-xs font-medium text-slate-400 mb-1">Окно оспаривания (минут)</label>
                <input type="number" id="cfg-AGREEMENT_DISPUTE_WINDOW_MINUTES" class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-white font-mono">
              </div>

              <div>
                <label class="block text-xs font-medium text-slate-400 mb-1">Время жизни договоренности (ч)</label>
                <input type="number" id="cfg-AGREEMENT_DEFAULT_LIFESPAN_HOURS" class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-white font-mono">
              </div>
            </div>
          </div>
        </form>
      </section>

      <!-- ================= TAB: PROMPTS ================= -->
      <section id="tab-content-prompts" class="tab-pane hidden space-y-6">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-[#111827] p-5 rounded-2xl border border-slate-800">
          <div>
            <h2 class="text-lg font-bold text-white flex items-center gap-2">
              <span>🧠</span> Студия системных промптов
            </h2>
            <p class="text-xs text-slate-400">Редактируйте инструкции Gemini без необходимости повторного деплоя</p>
          </div>
          <div class="flex items-center gap-2">
            <button onclick="resetSelectedPrompt()"
                    class="px-3 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-rose-300 border border-slate-700 transition">
              Сбросить этот промпт
            </button>
            <button onclick="saveSelectedPrompt()"
                    class="px-4 py-2 rounded-xl text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-900/30 transition flex items-center gap-1.5">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
              <span>Сохранить промпт</span>
            </button>
          </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <!-- Prompts list navigation -->
          <div class="bg-[#111827] border border-slate-800 rounded-2xl p-4 space-y-2 lg:col-span-1">
            <div class="text-xs font-bold text-slate-400 uppercase tracking-wider px-2 mb-2">Шаблоны промптов</div>
            <div id="prompts-list-container" class="space-y-1">
              <!-- Dynamically populated -->
            </div>
          </div>

          <!-- Prompt Editor -->
          <div class="bg-[#111827] border border-slate-800 rounded-2xl p-5 lg:col-span-3 flex flex-col space-y-4">
            <div>
              <div class="flex items-center justify-between">
                <h3 id="current-prompt-title" class="text-base font-bold text-white">Промпт</h3>
                <span id="current-prompt-badge" class="text-[11px] px-2.5 py-0.5 rounded-full font-mono bg-slate-800 text-slate-400 border border-slate-700">Оригинал</span>
              </div>
              <p id="current-prompt-desc" class="text-xs text-slate-400 mt-1"></p>
            </div>

            <!-- Available Variables / Placeholders Tags -->
            <div>
              <div class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5">Доступные переменные (нажмите для вставки):</div>
              <div id="current-prompt-placeholders" class="flex flex-wrap gap-1.5">
                <!-- Dynamically populated -->
              </div>
            </div>

            <!-- Editor Textarea -->
            <div class="flex-1 flex flex-col">
              <textarea id="prompt-editor-textarea" rows="20"
                        class="w-full flex-1 p-4 bg-[#0c121e] border border-slate-700 rounded-xl text-slate-100 font-mono text-xs leading-relaxed focus:outline-none focus:border-emerald-500 transition resize-y"></textarea>
              <div class="flex justify-between items-center text-[11px] text-slate-500 mt-2 px-1">
                <span id="prompt-char-count">0 символов</span>
                <span>Формат: Markdown / Text</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- ================= TAB: USERS & POINTS ================= -->
      <section id="tab-content-users" class="tab-pane hidden space-y-6">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-[#111827] p-5 rounded-2xl border border-slate-800">
          <div>
            <h2 class="text-lg font-bold text-white flex items-center gap-2">
              <span>👥</span> Участники чата и Очки
            </h2>
            <p class="text-xs text-slate-400">Управление рангами, балансом очков и выдача ачивок участникам</p>
          </div>
          <div class="flex items-center gap-2">
            <button onclick="loadUsers()"
                    class="px-3 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition flex items-center gap-1.5">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
              <span>Обновить</span>
            </button>
            <button onclick="showLedgerModal()"
                    class="px-3 py-2 rounded-xl text-xs font-semibold bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 transition flex items-center gap-1.5">
              <span>📋 Аудит очков (Ledger)</span>
            </button>
          </div>
        </div>

        <!-- Search Bar -->
        <div class="flex gap-4">
          <input type="text" id="user-search-input" oninput="filterUsersTable()"
                 placeholder="🔍 Поиск по нику или имени..."
                 class="w-full sm:max-w-md px-4 py-2.5 bg-[#111827] border border-slate-800 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500">
        </div>

        <!-- Users Table -->
        <div class="bg-[#111827] border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs">
              <thead class="bg-[#162032] text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-800">
                <tr>
                  <th class="py-3 px-4">Пользователь</th>
                  <th class="py-3 px-4 text-center">Очки</th>
                  <th class="py-3 px-4">Масть (Ранг)</th>
                  <th class="py-3 px-4">Ачивки</th>
                  <th class="py-3 px-4 text-right">Действия с очками</th>
                </tr>
              </thead>
              <tbody id="users-table-body" class="divide-y divide-slate-800/60 text-slate-300">
                <tr>
                  <td colspan="5" class="py-8 text-center text-slate-500">Загрузка участников...</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <!-- ================= TAB: LORE & FACTS ================= -->
      <section id="tab-content-lore" class="tab-pane hidden space-y-6">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-[#111827] p-5 rounded-2xl border border-slate-800">
          <div>
            <h2 class="text-lg font-bold text-white flex items-center gap-2">
              <span>📜</span> Лор и База фактов чата
            </h2>
            <p class="text-xs text-slate-400">Просмотр и редактирование подтвержденных фактов и глобального лора</p>
          </div>
          <div class="flex items-center gap-2">
            <button onclick="loadFactsAndLore()"
                    class="px-3 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition">
              Обновить
            </button>
          </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <!-- Facts Box -->
          <div class="bg-[#111827] border border-slate-800 rounded-2xl p-5 space-y-4 flex flex-col">
            <div class="flex items-center justify-between">
              <h3 class="text-sm font-bold text-emerald-400 uppercase tracking-wider flex items-center gap-1.5">
                <span>📌</span> Подтвержденные факты (<span id="facts-count">0</span>)
              </h3>
              <button onclick="showAddFactModal()"
                      class="px-2.5 py-1 rounded-lg text-xs font-medium bg-emerald-600 hover:bg-emerald-500 text-white transition flex items-center gap-1">
                <span>+ Добавить факт</span>
              </button>
            </div>

            <div id="facts-list-container" class="space-y-2 flex-1 max-h-[500px] overflow-y-auto pr-1">
              <!-- Dynamically populated -->
            </div>
          </div>

          <!-- Lore JSON Editor -->
          <div class="bg-[#111827] border border-slate-800 rounded-2xl p-5 space-y-4 flex flex-col">
            <div class="flex items-center justify-between">
              <h3 class="text-sm font-bold text-indigo-400 uppercase tracking-wider flex items-center gap-1.5">
                <span>📖</span> Ядро Лора (JSON)
              </h3>
              <button onclick="saveLoreJson()"
                      class="px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg transition">
                Сохранить Лор
              </button>
            </div>

            <div class="flex-1 flex flex-col">
              <textarea id="lore-json-textarea" rows="18"
                        class="w-full flex-1 p-3 bg-[#0c121e] border border-slate-700 rounded-xl text-indigo-200 font-mono text-xs leading-relaxed focus:outline-none focus:border-indigo-500 transition resize-y"></textarea>
              <div class="text-[11px] text-slate-500 mt-2">Редактируйте персонажей (characters), концепции (concepts) и словарь сленга (dictionary)</div>
            </div>
          </div>
        </div>
      </section>

      <!-- ================= TAB: AGREEMENTS ================= -->
      <section id="tab-content-agreements" class="tab-pane hidden space-y-6">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-[#111827] p-5 rounded-2xl border border-slate-800">
          <div>
            <h2 class="text-lg font-bold text-white flex items-center gap-2">
              <span>🤝</span> Слово Пацана (Договоренности)
            </h2>
            <p class="text-xs text-slate-400">Мониторинг обязательств, споров и статусов договоренностей участников</p>
          </div>
          <div class="flex items-center gap-2">
            <button onclick="runWeeklyAgreementsScan(false)" id="btn-scan-agreements"
                    class="px-3 py-2 rounded-xl text-xs font-semibold bg-sky-600 hover:bg-sky-500 text-white shadow-lg shadow-sky-900/30 transition flex items-center gap-1.5">
              <span>🔍 Просканировать за неделю</span>
            </button>
            <button onclick="loadAgreements()"
                    class="px-3 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition">
              Обновить
            </button>
          </div>
        </div>

        <div class="bg-[#111827] border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs">
              <thead class="bg-[#162032] text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-800">
                <tr>
                  <th class="py-3 px-4">Текст договоренности</th>
                  <th class="py-3 px-4">Участники</th>
                  <th class="py-3 px-4 text-center">Статус</th>
                  <th class="py-3 px-4">Истекает</th>
                  <th class="py-3 px-4 text-right">Действия</th>
                </tr>
              </thead>
              <tbody id="agreements-table-body" class="divide-y divide-slate-800/60 text-slate-300">
                <tr>
                  <td colspan="5" class="py-8 text-center text-slate-500">Загрузка договоренностей...</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <!-- ================= TAB: LESSONS ================= -->
      <section id="tab-content-lessons" class="tab-pane hidden space-y-6">
        <!-- Top Banner -->
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-[#111827] p-5 rounded-2xl border border-slate-800">
          <div>
            <h2 class="text-lg font-bold text-white flex items-center gap-2">
              <span>🎓</span> Самообучение и Уроки бота (Lessons)
            </h2>
            <p class="text-xs text-slate-400">Автономное извлечение уроков из реакций чата на вердикты бота, база правил поведения и адаптация промптов.</p>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <button onclick="showAddLessonModal()"
                    class="px-3 py-2 rounded-xl text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-900/30 transition flex items-center gap-1.5">
              <span>+ Добавить урок</span>
            </button>
            <button onclick="showFeedbackAnalysisModal()"
                    class="px-3 py-2 rounded-xl text-xs font-semibold bg-purple-600 hover:bg-purple-500 text-white shadow-lg shadow-purple-900/30 transition flex items-center gap-1.5">
              <span>🤖 Анализ фидбека</span>
            </button>
            <button onclick="loadLessons()"
                    class="px-3 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition">
              Обновить
            </button>
          </div>
        </div>

        <!-- Metrics Cards -->
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div class="bg-[#111827] border border-slate-800 p-4 rounded-2xl">
            <div class="text-slate-400 text-xs font-medium uppercase tracking-wider">Всего уроков</div>
            <div id="stat-lessons-total" class="text-2xl font-bold text-white mt-1">0</div>
          </div>
          <div class="bg-[#111827] border border-slate-800 p-4 rounded-2xl">
            <div class="text-emerald-400 text-xs font-medium uppercase tracking-wider">🟢 Активны (В промпте)</div>
            <div id="stat-lessons-active" class="text-2xl font-bold text-emerald-400 mt-1">0</div>
          </div>
          <div class="bg-[#111827] border border-slate-800 p-4 rounded-2xl">
            <div class="text-slate-400 text-xs font-medium uppercase tracking-wider">📦 В архиве</div>
            <div id="stat-lessons-archived" class="text-2xl font-bold text-slate-400 mt-1">0</div>
          </div>
          <div class="bg-[#111827] border border-slate-800 p-4 rounded-2xl">
            <div class="text-rose-400 text-xs font-medium uppercase tracking-wider">⚠️ Ошибки бота</div>
            <div id="stat-lessons-mistakes" class="text-2xl font-bold text-rose-400 mt-1">0</div>
          </div>
        </div>

        <!-- Filter & Search Controls -->
        <div class="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-[#111827] p-4 rounded-2xl border border-slate-800">
          <div class="flex flex-wrap items-center gap-2">
            <span class="text-xs text-slate-400 font-medium mr-1">Статус:</span>
            <button onclick="setLessonsFilter('all')" id="filter-btn-all" class="px-3 py-1 rounded-lg text-xs font-semibold bg-slate-800 text-emerald-400 transition">Все</button>
            <button onclick="setLessonsFilter('active')" id="filter-btn-active" class="px-3 py-1 rounded-lg text-xs font-medium text-slate-400 hover:text-white transition">Только активные</button>
            <button onclick="setLessonsFilter('archived')" id="filter-btn-archived" class="px-3 py-1 rounded-lg text-xs font-medium text-slate-400 hover:text-white transition">В архиве</button>
          </div>
          <div class="flex items-center gap-2">
            <select id="lessons-verdict-filter" onchange="onLessonsVerdictChanged()" class="px-3 py-1.5 bg-[#1a2333] border border-slate-700 rounded-xl text-white text-xs">
              <option value="all">Все вердикты</option>
              <option value="fair">✓ Справедливо</option>
              <option value="mistake">⚠️ Ошибка бота</option>
              <option value="unclear">? Непонятно</option>
            </select>
            <input type="text" id="lessons-search" oninput="onLessonsSearchChanged()" placeholder="Поиск по правилу или причине..."
                   class="px-3 py-1.5 bg-[#1a2333] border border-slate-700 rounded-xl text-white placeholder-slate-500 text-xs w-full sm:w-64 focus:outline-none focus:border-purple-500">
          </div>
        </div>

        <!-- Lessons Container -->
        <div id="lessons-list-container" class="space-y-3">
          <div class="py-12 text-center text-slate-500 text-xs">Загрузка уроков...</div>
        </div>
      </section>

      <!-- ================= TAB: ACTIONS ================= -->
      <section id="tab-content-actions" class="tab-pane hidden space-y-6">
        <div class="bg-[#111827] p-5 rounded-2xl border border-slate-800">
          <h2 class="text-lg font-bold text-white flex items-center gap-2">
            <span>⚡</span> Процедуры и Действия в 1 клик
          </h2>
          <p class="text-xs text-slate-400">Ручной запуск регулярных заданий и служебных алгоритмов</p>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-6">
          <!-- Action: Daily Analysis -->
          <div class="bg-[#111827] border border-slate-800 rounded-2xl p-5 space-y-4 flex flex-col justify-between">
            <div>
              <div class="text-2xl mb-2">🔍</div>
              <h3 class="text-sm font-bold text-white">Дневной анализ чата</h3>
              <p class="text-xs text-slate-400 mt-1">Запускает Gemini для чтения сообщений за день, выбора Снитча дня и начисления очков.</p>
            </div>
            <button onclick="runDailyAnalysisAction()" id="btn-action-analysis"
                    class="w-full py-2.5 px-4 bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 text-white text-xs font-semibold rounded-xl transition flex items-center justify-center gap-2 shadow-lg shadow-emerald-900/30">
              <span>Запустить анализ</span>
            </button>
          </div>

          <!-- Action: Agreement Scan -->
          <div class="bg-[#111827] border border-slate-800 rounded-2xl p-5 space-y-4 flex flex-col justify-between">
            <div>
              <div class="text-2xl mb-2">🤝</div>
              <h3 class="text-sm font-bold text-white">Поиск договоренностей</h3>
              <p class="text-xs text-slate-400 mt-1">Сканирует переписку за последние 7 дней на предмет обещаний («Слово Пацана») и записывает их.</p>
            </div>
            <button onclick="runWeeklyAgreementsScan(true)" id="btn-action-agreements-scan"
                    class="w-full py-2.5 px-4 bg-sky-600 hover:bg-sky-500 active:bg-sky-700 text-white text-xs font-semibold rounded-xl transition flex items-center justify-center gap-2 shadow-lg shadow-sky-900/30">
              <span>Просканировать</span>
            </button>
          </div>

          <!-- Action: Voice Digest -->
          <div class="bg-[#111827] border border-slate-800 rounded-2xl p-5 space-y-4 flex flex-col justify-between">
            <div>
              <div class="text-2xl mb-2">🎙️</div>
              <h3 class="text-sm font-bold text-white">Голосовая хроника</h3>
              <p class="text-xs text-slate-400 mt-1">Озвучивает сводку событий чата через Google Cloud TTS и шлет войс в чат.</p>
            </div>
            <div class="flex gap-2">
              <button onclick="runVoiceDigestAction('Дневной выпуск (14:00)')" id="btn-action-voice-day"
                      class="flex-1 py-2 px-1 bg-rose-600/80 hover:bg-rose-500 text-white text-[11px] font-semibold rounded-xl transition shadow-lg text-center">
                14:00
              </button>
              <button onclick="runVoiceDigestAction('Вечерний выпуск (22:00)')" id="btn-action-voice-eve"
                      class="flex-1 py-2 px-1 bg-purple-600/80 hover:bg-purple-500 text-white text-[11px] font-semibold rounded-xl transition shadow-lg text-center">
                22:00
              </button>
            </div>
          </div>

          <!-- Action: Weekly Amnesty -->
          <div class="bg-[#111827] border border-slate-800 rounded-2xl p-5 space-y-4 flex flex-col justify-between">
            <div>
              <div class="text-2xl mb-2">🧹</div>
              <h3 class="text-sm font-bold text-white">Еженедельная амнистия</h3>
              <p class="text-xs text-slate-400 mt-1">Делит очки за текущую неделю пополам и отправляет объявление об амнистии в чат.</p>
            </div>
            <button onclick="runWeeklyAmnestyAction()" id="btn-action-amnesty"
                    class="w-full py-2.5 px-4 bg-amber-600 hover:bg-amber-500 active:bg-amber-700 text-white text-xs font-semibold rounded-xl transition flex items-center justify-center gap-2 shadow-lg shadow-amber-900/30">
              <span>Применить амнистию</span>
            </button>
          </div>

          <!-- Action: Lore Evolution -->
          <div class="bg-[#111827] border border-slate-800 rounded-2xl p-5 space-y-4 flex flex-col justify-between">
            <div>
              <div class="text-2xl mb-2">🧬</div>
              <h3 class="text-sm font-bold text-white">Эволюция Лора</h3>
              <p class="text-xs text-slate-400 mt-1">Обобщает накопленные факты о людях и обновляет карточки персонажей в ядре лора.</p>
            </div>
            <button onclick="runLoreEvolutionAction()" id="btn-action-evolution"
                    class="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white text-xs font-semibold rounded-xl transition flex items-center justify-center gap-2 shadow-lg shadow-indigo-900/30">
              <span>Запустить эволюцию</span>
            </button>
          </div>

          <!-- Action: Forget Memory -->
          <div class="bg-[#111827] border border-rose-900/30 rounded-2xl p-5 space-y-4 flex flex-col justify-between relative overflow-hidden">
            <div class="absolute inset-0 bg-gradient-to-br from-rose-500/5 to-transparent pointer-events-none"></div>
            <div class="relative">
              <div class="text-2xl mb-2">🔥</div>
              <h3 class="text-sm font-bold text-rose-400">Сброс памяти (Forget)</h3>
              <p class="text-xs text-slate-400 mt-1">Полностью удаляет лор и текущий контекст чата (эквивалент /forget). Решает проблему зацикливания.</p>
            </div>
            <button onclick="runForgetAction()" id="btn-action-forget"
                    class="w-full py-2.5 px-4 bg-rose-600 hover:bg-rose-500 active:bg-rose-700 text-white text-xs font-semibold rounded-xl transition flex items-center justify-center gap-2 shadow-lg shadow-rose-900/30 relative">
              <span>Очистить память чата</span>
            </button>
          </div>

          <!-- Action: Feedback Analysis / Self-Learning -->
          <div class="bg-[#111827] border border-slate-800 rounded-2xl p-5 space-y-4 flex flex-col justify-between">
            <div>
              <div class="text-2xl mb-2">🎓</div>
              <h3 class="text-sm font-bold text-white">Анализ фидбека (Обучение)</h3>
              <p class="text-xs text-slate-400 mt-1">Анализирует реакцию участников на вердикты бота за выбранную дату и формулирует обучающие правила.</p>
            </div>
            <button onclick="showFeedbackAnalysisModal()" id="btn-action-feedback-analysis"
                    class="w-full py-2.5 px-4 bg-purple-600 hover:bg-purple-500 active:bg-purple-700 text-white text-xs font-semibold rounded-xl transition flex items-center justify-center gap-2 shadow-lg shadow-purple-900/30">
              <span>Запустить анализ</span>
            </button>
          </div>
        </div>

        <!-- Live Output Log Console -->
        <div class="bg-[#111827] border border-slate-800 rounded-2xl p-5 space-y-3">
          <div class="flex items-center justify-between">
            <h3 class="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5 font-mono">
              <span>🖥️</span> Консоль результатов выполнения
            </h3>
            <button onclick="clearConsoleLog()" class="text-slate-500 hover:text-slate-300 text-xs font-mono">Очистить</button>
          </div>
          <pre id="actions-console-log" class="p-4 bg-[#0c121e] border border-slate-800 rounded-xl text-slate-300 font-mono text-xs overflow-x-auto max-h-72 leading-relaxed">Готов к выполнению операций...</pre>
        </div>
      </section>

      <!-- ================= TAB: CHAT ================= -->
      <section id="tab-content-chat" class="tab-pane hidden space-y-4">
        <!-- Chat Header Card -->
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-[#111827] p-4 sm:p-5 rounded-2xl border border-slate-800">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-purple-600/20 border border-purple-500/30 flex items-center justify-center text-xl">
              💬
            </div>
            <div>
              <h2 class="text-base sm:text-lg font-bold text-white flex items-center gap-2">
                <span>Прямой эфир чата</span>
                <span id="chat-live-badge" class="px-2 py-0.5 rounded-full text-[10px] font-mono bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center gap-1">
                  <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span> LIVE
                </span>
              </h2>
              <p class="text-xs text-slate-400">Переписка в реальном времени и отправка сообщений от лица Снитч-бота</p>
            </div>
          </div>
          <div class="flex items-center gap-3">
            <label class="flex items-center gap-2 text-xs text-slate-300 cursor-pointer bg-[#162032] px-3 py-2 rounded-xl border border-slate-700 select-none">
              <input type="checkbox" id="chat-auto-refresh" checked class="w-4 h-4 accent-purple-500 rounded cursor-pointer">
              <span>Автообновление (5с)</span>
            </label>
            <button onclick="loadChatMessages(true)" id="btn-refresh-chat"
                    class="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-xs font-semibold border border-slate-700 transition flex items-center gap-1.5">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
              <span>Обновить</span>
            </button>
          </div>
        </div>

        <!-- Chat Container -->
        <div class="bg-[#111827] border border-slate-800 rounded-2xl flex flex-col h-[650px] shadow-2xl overflow-hidden">
          <!-- Messages Scroll Area -->
          <div id="chat-messages-container" class="flex-1 p-4 sm:p-5 overflow-y-auto space-y-3 bg-[#0d1424]">
            <div class="py-12 text-center text-slate-500 text-xs">Загрузка сообщений...</div>
          </div>

          <!-- Reply Banner (Hidden by default) -->
          <div id="chat-reply-banner" class="hidden px-4 py-2 bg-[#162032] border-t border-slate-800 flex items-center justify-between text-xs text-slate-300">
            <div class="flex items-center gap-2 truncate">
              <span class="text-purple-400 font-bold">↩️ Ответ на:</span>
              <span id="chat-reply-author" class="font-semibold text-white"></span>
              <span id="chat-reply-preview" class="text-slate-400 truncate italic"></span>
            </div>
            <button onclick="cancelChatReply()" class="text-slate-400 hover:text-white text-xs px-2 py-0.5 rounded hover:bg-slate-700">✕ Отмена</button>
          </div>

          <!-- Message Composer Area -->
          <div class="p-3 sm:p-4 bg-[#111827] border-t border-slate-800 space-y-2">
            <!-- Quick Chips & Options -->
            <div class="flex items-center justify-between gap-2 overflow-x-auto pb-1 text-[11px]">
              <div class="flex items-center gap-1.5 flex-nowrap">
                <span class="text-slate-500 text-[10px] uppercase font-semibold">Шаблоны:</span>
                <button type="button" onclick="insertChatTemplate('⚖️ Масть зафиксирована: ')"
                        class="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-rose-300 border border-slate-700 whitespace-nowrap">⚖️ Масть</button>
                <button type="button" onclick="insertChatTemplate('👑 По-людски: ')"
                        class="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-emerald-300 border border-slate-700 whitespace-nowrap">👑 Людское</button>
                <button type="button" onclick="insertChatTemplate('📣 Сайонара сбор! ')"
                        class="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-sky-300 border border-slate-700 whitespace-nowrap">📣 Сбор</button>
                <button type="button" onclick="insertChatTemplate('🤡 ')"
                        class="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-amber-300 border border-slate-700 whitespace-nowrap">🤡</button>
              </div>
              <div class="flex items-center gap-2">
                <label class="text-[10px] text-slate-400">Формат:</label>
                <select id="chat-parse-mode" class="bg-[#1a2333] border border-slate-700 text-white rounded px-2 py-0.5 text-[11px] focus:outline-none">
                  <option value="HTML">HTML</option>
                  <option value="Markdown">Markdown</option>
                  <option value="none">Обычный текст</option>
                </select>
              </div>
            </div>

            <!-- Input Bar -->
            <div class="flex gap-2 items-end">
              <textarea id="chat-input-text" rows="2"
                        placeholder="Напишите сообщение в чат от имени бота... (Ctrl+Enter для отправки)"
                        onkeydown="handleChatInputKeydown(event)"
                        class="flex-1 p-3 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 font-sans resize-none"></textarea>
              <button onclick="sendChatMessageFromAdmin()" id="btn-send-chat"
                      class="px-4 py-3 bg-purple-600 hover:bg-purple-500 active:bg-purple-700 text-white rounded-xl text-xs font-semibold shadow-lg shadow-purple-900/40 flex items-center gap-1.5 transition whitespace-nowrap h-full">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/></svg>
                <span class="hidden sm:inline">Отправить</span>
              </button>
            </div>
          </div>
        </div>
      </section>

    </main>
  </div>

  <!-- MODAL: Adjust Points -->
  <div id="modal-points" class="hidden fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
    <div class="bg-[#111827] border border-slate-800 rounded-2xl p-6 max-w-md w-full shadow-2xl space-y-4">
      <div class="flex justify-between items-center">
        <h3 class="text-base font-bold text-white">Изменение очков</h3>
        <button onclick="closeModal('modal-points')" class="text-slate-400 hover:text-white">✕</button>
      </div>
      <div>
        <div class="text-xs text-slate-400">Пользователь:</div>
        <div id="modal-points-user" class="text-sm font-bold text-emerald-400 font-mono"></div>
      </div>
      <div class="space-y-3">
        <div>
          <label class="block text-xs font-medium text-slate-400 mb-1">Дельта очков (+начислить, -списать)</label>
          <input type="number" id="modal-points-delta" class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-white font-mono" placeholder="Например: 50 или -25">
        </div>
        <div>
          <label class="block text-xs font-medium text-slate-400 mb-1">Или задать точное число очков</label>
          <input type="number" id="modal-points-exact" class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-white font-mono" placeholder="Оставьте пустым, если используете дельту">
        </div>
        <div>
          <label class="block text-xs font-medium text-slate-400 mb-1">Причина</label>
          <input type="text" id="modal-points-reason" class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-white" value="Ручная корректировка администратора">
        </div>
      </div>
      <div class="flex justify-end gap-2 pt-2">
        <button onclick="closeModal('modal-points')" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs">Отмена</button>
        <button onclick="submitPointsAdjust()" class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-xl text-xs shadow-lg">Применить</button>
      </div>
    </div>
  </div>

  <!-- MODAL: Achievements Management -->
  <div id="modal-achievements" class="hidden fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
    <div class="bg-[#111827] border border-slate-800 rounded-2xl p-6 max-w-lg w-full shadow-2xl space-y-4">
      <div class="flex justify-between items-center">
        <h3 class="text-base font-bold text-white">Достижения (Ачивки)</h3>
        <button onclick="closeModal('modal-achievements')" class="text-slate-400 hover:text-white">✕</button>
      </div>
      <div>
        <div class="text-xs text-slate-400">Пользователь:</div>
        <div id="modal-achievements-user" class="text-sm font-bold text-amber-400 font-mono"></div>
      </div>
      <div>
        <label class="block text-xs font-medium text-slate-400 mb-1">Список ачивок (каждая с новой строки или JSON)</label>
        <textarea id="modal-achievements-text" rows="8"
                  class="w-full p-3 bg-[#0c121e] border border-slate-700 rounded-xl text-slate-100 font-mono text-xs leading-relaxed"></textarea>
        <div class="text-[10px] text-slate-500 mt-1">Пример: Король Стукачей 👑 | Обиженный года 🚽</div>
      </div>
      <div class="flex justify-end gap-2 pt-2">
        <button onclick="closeModal('modal-achievements')" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs">Отмена</button>
        <button onclick="submitAchievementsUpdate()" class="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white font-semibold rounded-xl text-xs shadow-lg">Сохранить ачивки</button>
      </div>
    </div>
  </div>

  <!-- MODAL: Add Fact -->
  <div id="modal-fact" class="hidden fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
    <div class="bg-[#111827] border border-slate-800 rounded-2xl p-6 max-w-md w-full shadow-2xl space-y-4">
      <div class="flex justify-between items-center">
        <h3 class="text-base font-bold text-white">Добавить подтвержденный факт</h3>
        <button onclick="closeModal('modal-fact')" class="text-slate-400 hover:text-white">✕</button>
      </div>
      <div class="space-y-3">
        <div>
          <label class="block text-xs font-medium text-slate-400 mb-1">Текст факта</label>
          <textarea id="modal-fact-text" rows="4" class="w-full p-3 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-white" placeholder="Например: @andrey купил новую машину..."></textarea>
        </div>
        <div>
          <label class="block text-xs font-medium text-slate-400 mb-1">Username (необязательно)</label>
          <input type="text" id="modal-fact-username" class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-white" placeholder="@username">
        </div>
      </div>
      <div class="flex justify-end gap-2 pt-2">
        <button onclick="closeModal('modal-fact')" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs">Отмена</button>
        <button onclick="submitAddFact()" class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-xl text-xs shadow-lg">Добавить факт</button>
      </div>
    </div>
  </div>

  <!-- MODAL: Points Audit Ledger -->
  <div id="modal-ledger" class="hidden fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
    <div class="bg-[#111827] border border-slate-800 rounded-2xl p-6 max-w-3xl w-full shadow-2xl space-y-4 max-h-[85vh] flex flex-col">
      <div class="flex justify-between items-center">
        <h3 class="text-base font-bold text-white flex items-center gap-2">
          <span>📋</span> Аудит начислений очков (Points Ledger)
        </h3>
        <button onclick="closeModal('modal-ledger')" class="text-slate-400 hover:text-white">✕</button>
      </div>
      <p class="text-xs text-slate-400">Последние начисления. Клик по кнопке «Откатить» отменяет начисление и списывает/возвращает очки.</p>
      
      <div class="flex-1 overflow-y-auto border border-slate-800 rounded-xl">
        <table class="w-full text-left text-xs">
          <thead class="bg-[#162032] text-slate-400 uppercase font-semibold sticky top-0">
            <tr>
              <th class="py-2.5 px-3">Дата</th>
              <th class="py-2.5 px-3">User ID</th>
              <th class="py-2.5 px-3 text-center">Дельта</th>
              <th class="py-2.5 px-3">Тип & Причина</th>
              <th class="py-2.5 px-3 text-right">Действие</th>
            </tr>
          </thead>
          <tbody id="ledger-table-body" class="divide-y divide-slate-800 text-slate-300">
            <tr>
              <td colspan="5" class="py-4 text-center text-slate-500">Загрузка истории...</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- MODAL: Add/Edit Lesson -->
  <div id="modal-lesson" class="hidden fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
    <div class="bg-[#111827] border border-slate-800 rounded-2xl p-6 max-w-lg w-full shadow-2xl space-y-4">
      <div class="flex justify-between items-center border-b border-slate-800 pb-3">
        <h3 id="modal-lesson-title" class="text-base font-bold text-white flex items-center gap-2">
          <span>🎓</span> <span>Добавить урок</span>
        </h3>
        <button onclick="closeModal('modal-lesson')" class="text-slate-400 hover:text-white">✕</button>
      </div>
      <input type="hidden" id="modal-lesson-id">
      <div class="space-y-3 text-xs">
        <div>
          <label class="block font-medium text-slate-300 mb-1">Сформулированное правило поведения (learned_rule) *</label>
          <textarea id="modal-lesson-rule" rows="3" required
                    class="w-full p-3 bg-[#1a2333] border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 font-sans text-xs"
                    placeholder="Например: Не зацикливаться на времени суток и призывах «идти спать» в каждом ответе."></textarea>
        </div>
        <div>
          <label class="block font-medium text-slate-300 mb-1">Обоснование / Причина (reasoning)</label>
          <textarea id="modal-lesson-reasoning" rows="2"
                    class="w-full p-3 bg-[#1a2333] border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 font-sans text-xs"
                    placeholder="Почему бот решил выучить это правило..."></textarea>
        </div>
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block font-medium text-slate-300 mb-1">Вердикт</label>
            <select id="modal-lesson-verdict" class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-white focus:outline-none focus:border-purple-500 text-xs">
              <option value="fair">fair (Справедливо)</option>
              <option value="mistake">mistake (Ошибка бота)</option>
              <option value="unclear">unclear (Непонятно)</option>
            </select>
          </div>
          <div>
            <label class="block font-medium text-slate-300 mb-1">Статус</label>
            <select id="modal-lesson-status" class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-white focus:outline-none focus:border-purple-500 text-xs">
              <option value="active">active (Активен в промпте)</option>
              <option value="archived">archived (В архиве)</option>
            </select>
          </div>
        </div>
        <div>
          <label class="block font-medium text-slate-300 mb-1">Дата события (YYYY-MM-DD)</label>
          <input type="text" id="modal-lesson-date" class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-white font-mono text-xs" placeholder="2026-09-18">
        </div>
        <div id="modal-lesson-context-box" class="hidden">
          <label class="block font-medium text-slate-400 mb-1">Контекст триггера (исходные сообщения)</label>
          <pre id="modal-lesson-context" class="p-2.5 bg-[#0d1424] border border-slate-800 rounded-xl text-[11px] text-slate-400 font-mono max-h-28 overflow-y-auto whitespace-pre-wrap"></pre>
        </div>
      </div>
      <div class="flex justify-end gap-2 pt-2 border-t border-slate-800">
        <button onclick="closeModal('modal-lesson')" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold">Отмена</button>
        <button onclick="saveLessonForm()" class="px-4 py-2 bg-purple-600 hover:bg-purple-500 active:bg-purple-700 text-white rounded-xl text-xs font-semibold shadow-lg shadow-purple-900/30">Сохранить</button>
      </div>
    </div>
  </div>

  <!-- MODAL: Feedback Analysis On-Demand -->
  <div id="modal-feedback-analysis" class="hidden fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
    <div class="bg-[#111827] border border-slate-800 rounded-2xl p-6 max-w-lg w-full shadow-2xl space-y-4">
      <div class="flex justify-between items-center border-b border-slate-800 pb-3">
        <h3 class="text-base font-bold text-white flex items-center gap-2">
          <span>🤖</span> <span>Анализ обратной связи (Самообучение)</span>
        </h3>
        <button onclick="closeModal('modal-feedback-analysis')" class="text-slate-400 hover:text-white">✕</button>
      </div>
      <div class="space-y-3 text-xs">
        <p class="text-slate-400">
          Gemini проанализирует сообщения в чате (реплаи и упоминания бота) за выбранную дату, оценит справедливость действий и при необходимости сформулирует новое обучающее правило.
        </p>
        <div>
          <label class="block font-medium text-slate-300 mb-1">Дата для анализа (YYYY-MM-DD):</label>
          <input type="date" id="feedback-analysis-date" class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-white font-mono text-xs">
        </div>
        <div id="feedback-analysis-result-container" class="hidden p-4 bg-[#0d1424] border border-slate-800 rounded-xl space-y-2">
          <div class="font-bold text-sm text-purple-400 flex items-center gap-1.5">
            <span>✨</span> <span id="feedback-result-title">Результат анализа</span>
          </div>
          <div id="feedback-result-body" class="text-slate-300 text-xs leading-relaxed whitespace-pre-wrap font-mono"></div>
        </div>
      </div>
      <div class="flex justify-end gap-2 pt-2 border-t border-slate-800">
        <button onclick="closeModal('modal-feedback-analysis')" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold">Закрыть</button>
        <button onclick="executeFeedbackAnalysis()" id="btn-submit-feedback-analysis"
                class="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-purple-900/30 flex items-center gap-1.5">
          <span>🚀 Запустить анализ</span>
        </button>
      </div>
    </div>
  </div>

  <!-- CLIENT-SIDE LOGIC -->
  <script>
    let state = {
      activeTab: 'config',
      chats: [],
      currentChatId: '',
      prompts: [],
      selectedPromptKey: 'system_prompt',
      users: [],
      selectedUserForPoints: null,
      selectedUserForAchievements: null,
      lessons: [],
      lessonsFilter: 'all',
      lessonsVerdictFilter: 'all',
      lessonsSearch: '',
      editingLessonId: null,
      chatMessages: [],
      chatReplyToMessageId: null,
      chatAutoRefreshInterval: null,
      config: {},
      defaults: {}
    };

    // --- HTML Sanitization Helper to Prevent XSS ---
    function escapeHtml(str) {
      if (str === null || str === undefined) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    // --- Helpers: Toast Notifications ---
    function showToast(message, type = 'success') {
      const container = document.getElementById('toast-container');
      const toast = document.createElement('div');
      const colorClass = type === 'success' 
        ? 'bg-emerald-950/90 border-emerald-500 text-emerald-200' 
        : 'bg-rose-950/90 border-rose-500 text-rose-200';
      toast.className = `pointer-events-auto flex items-center gap-2 px-4 py-3 rounded-xl border shadow-xl text-xs font-medium transition-all duration-300 opacity-0 translate-y-2 ${colorClass}`;
      toast.innerHTML = `<span>${type === 'success' ? '✓' : '⚠️'}</span><span>${escapeHtml(message)}</span>`;
      container.appendChild(toast);
      requestAnimationFrame(() => {
        toast.classList.remove('opacity-0', 'translate-y-2');
      });
      setTimeout(() => {
        toast.classList.add('opacity-0', '-translate-y-2');
        setTimeout(() => toast.remove(), 300);
      }, 3500);
    }

    function closeModal(id) {
      document.getElementById(id).classList.add('hidden');
    }
    function openModal(id) {
      document.getElementById(id).classList.remove('hidden');
    }

    // --- API Fetch Wrapper ---
    async function apiRequest(endpoint, options = {}) {
      options.credentials = 'same-origin';
      options.headers = {
        'Content-Type': 'application/json',
        ...(options.headers || {})
      };
      const token = localStorage.getItem('admin_token');
      if (token) {
        options.headers['Authorization'] = 'Bearer ' + token;
      }
      const res = await fetch(endpoint, options);
      if (res.status === 401) {
        localStorage.removeItem('admin_token');
        showLogin();
        throw new Error('Сессия истекла. Войдите снова.');
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || 'Ошибка запроса');
      }
      return res.json();
    }

    // --- Auth Flow ---
    async function checkAuth() {
      try {
        await apiRequest('/api/admin/me');
        showDashboard();
      } catch (e) {
        localStorage.removeItem('admin_token');
        showLogin();
      }
    }

    function showLogin() {
      document.getElementById('login-view').classList.remove('hidden');
      document.getElementById('app-view').classList.add('hidden');
    }

    function showDashboard() {
      document.getElementById('login-view').classList.add('hidden');
      document.getElementById('app-view').classList.remove('hidden');
      initializeApp();
    }

    async function handleLogin(e) {
      e.preventDefault();
      const pwd = document.getElementById('login-password').value;
      const errBox = document.getElementById('login-error');
      errBox.classList.add('hidden');
      const submitBtn = document.getElementById('login-submit-btn');
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.firstElementChild.textContent = 'Проверка...';
      }
      try {
        const data = await apiRequest('/api/admin/login', {
          method: 'POST',
          body: JSON.stringify({ password: pwd })
        });
        if (data && data.token) {
          localStorage.setItem('admin_token', data.token);
        }
        showToast('Успешный вход в систему');
        showDashboard();
      } catch (err) {
        errBox.textContent = err.message;
        errBox.classList.remove('hidden');
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.firstElementChild.textContent = 'Войти в систему';
        }
      }
    }

    async function handleLogout() {
      try {
        await apiRequest('/api/admin/logout', { method: 'POST' });
      } catch (e) {}
      localStorage.removeItem('admin_token');
      showLogin();
    }

    // --- Initialization & Chat Selection ---
    async function initializeApp() {
      await loadChats();
      await loadConfig();
      setupChatAutoRefresh();
      switchTab('config');
    }

    async function loadChats() {
      try {
        const data = await apiRequest('/api/admin/chats');
        state.chats = data.chats || [];
        const select = document.getElementById('global-chat-select');
        select.innerHTML = '';
        state.chats.forEach(c => {
          const opt = document.createElement('option');
          opt.value = c.chat_id;
          opt.textContent = `${c.title} (${c.chat_id})`;
          select.appendChild(opt);
        });
        if (state.chats.length > 0) {
          state.currentChatId = state.chats[0].chat_id;
          select.value = state.currentChatId;
        }
      } catch (err) {
        showToast('Не удалось загрузить список чатов: ' + err.message, 'error');
      }
    }

    function onChatChanged() {
      const select = document.getElementById('global-chat-select');
      state.currentChatId = select.value;
      if (state.activeTab === 'chat') loadChatMessages(true);
      if (state.activeTab === 'users') loadUsers();
      if (state.activeTab === 'lore') loadFactsAndLore();
      if (state.activeTab === 'agreements') loadAgreements();
      if (state.activeTab === 'lessons') loadLessons();
    }

    // --- Tab Navigation ---
    function switchTab(tabId) {
      state.activeTab = tabId;
      document.querySelectorAll('.tab-btn').forEach(btn => {
        if (btn.dataset.tab === tabId) {
          btn.className = 'tab-btn px-3 py-1.5 rounded-lg font-medium text-xs sm:text-sm whitespace-nowrap transition bg-slate-800 text-emerald-400 font-semibold shadow-inner';
        } else {
          btn.className = 'tab-btn px-3 py-1.5 rounded-lg font-medium text-xs sm:text-sm whitespace-nowrap transition text-slate-400 hover:text-white hover:bg-slate-800/60';
        }
      });
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.add('hidden'));
      const activePane = document.getElementById('tab-content-' + tabId);
      if (activePane) activePane.classList.remove('hidden');

      if (tabId === 'chat') loadChatMessages(true);
      if (tabId === 'config') loadConfig();
      if (tabId === 'prompts') loadPrompts();
      if (tabId === 'users') loadUsers();
      if (tabId === 'lore') loadFactsAndLore();
      if (tabId === 'agreements') loadAgreements();
      if (tabId === 'lessons') loadLessons();
    }

    // --- TAB: CHAT & LIVE MESSAGES ---
    async function loadChatMessages(manual = false) {
      if (!state.currentChatId) return;
      try {
        const data = await apiRequest(`/api/admin/chats/${state.currentChatId}/messages?limit=60`);
        state.chatMessages = data.messages || [];
        renderChatMessages(state.chatMessages, manual);
      } catch (err) {
        if (manual) showToast('Ошибка загрузки сообщений: ' + err.message, 'error');
      }
    }

    function renderChatMessages(messages, forceScroll = false) {
      const container = document.getElementById('chat-messages-container');
      if (!container) return;

      const isScrolledToBottom = container.scrollHeight - container.clientHeight <= container.scrollTop + 60;

      if (!messages || messages.length === 0) {
        container.innerHTML = '<div class="py-16 text-center text-slate-500 text-xs">В этом чате пока нет записанных сообщений</div>';
        return;
      }

      container.innerHTML = messages.map(m => {
        const isBot = m.is_bot || m.username === 'YOU (Snitch Bot)';
        const author = escapeHtml(m.username || m.first_name || `ID ${m.user_id}`);
        const text = escapeHtml(m.text || '');
        const msgId = m.message_id;
        const replyTo = m.reply_to;
        const isReported = m.is_reported;
        const points = m.points_awarded || 0;
        const reportReason = escapeHtml(m.report_reason || '');

        let timeStr = '';
        if (m.timestamp) {
          try {
            const dt = new Date(m.timestamp);
            timeStr = dt.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
          } catch (e) {
            timeStr = String(m.timestamp);
          }
        }

        const replyBlock = replyTo ? `
          <div class="mb-1 text-[10px] text-purple-300/80 bg-purple-950/30 px-2 py-0.5 rounded border-l-2 border-purple-500 truncate font-mono">
            ↩️ Ответ на сообщение ID: ${escapeHtml(replyTo)}
          </div>
        ` : '';

        const badgeBlock = (isReported || points > 0) ? `
          <div class="mt-1.5 flex items-center gap-1.5 flex-wrap">
            <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/30">
              ⚖️ ${points > 0 ? `+${points} pts` : 'Репорт'} ${reportReason ? `— ${reportReason}` : ''}
            </span>
          </div>
        ` : '';

        return `
          <div class="group flex gap-2.5 items-start ${isBot ? 'flex-row-reverse' : ''}">
            <div class="w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-bold shrink-0 ${isBot ? 'bg-purple-600 text-white shadow-md shadow-purple-900/50' : 'bg-slate-800 text-slate-300 border border-slate-700'}">
              ${isBot ? '🤖' : author.charAt(0).toUpperCase()}
            </div>
            <div class="max-w-[85%] sm:max-w-md ${isBot ? 'bg-purple-950/40 border border-purple-800/40' : 'bg-[#162032] border border-slate-800'} rounded-2xl px-3.5 py-2.5 shadow-md space-y-1">
              <div class="flex items-center justify-between gap-3 text-[11px]">
                <div class="flex items-center gap-1.5 font-semibold ${isBot ? 'text-purple-300' : 'text-slate-200'}">
                  <span>${author}</span>
                  ${isBot ? '<span class="px-1 rounded bg-purple-500/20 text-purple-300 text-[9px] font-mono">БОТ</span>' : ''}
                </div>
                <div class="flex items-center gap-1.5 text-slate-500 text-[10px]">
                  <span>${timeStr}</span>
                  <button type="button" onclick="setChatReply('${escapeHtml(msgId)}', '${escapeHtml(author)}', '${escapeHtml(text.slice(0, 30))}')"
                          class="opacity-0 group-hover:opacity-100 transition px-1 py-0.5 rounded hover:bg-slate-700/60 text-purple-300 text-[10px]" title="Ответить на это сообщение">
                    ↩️
                  </button>
                </div>
              </div>
              ${replyBlock}
              <div class="text-xs text-slate-200 leading-relaxed whitespace-pre-wrap break-words">${text}</div>
              ${badgeBlock}
            </div>
          </div>
        `;
      }).join('');

      if (forceScroll || isScrolledToBottom) {
        container.scrollTop = container.scrollHeight;
      }
    }

    function setChatReply(msgId, author, textPreview) {
      state.chatReplyToMessageId = msgId;
      document.getElementById('chat-reply-author').textContent = author;
      document.getElementById('chat-reply-preview').textContent = `"${textPreview}..."`;
      document.getElementById('chat-reply-banner').classList.remove('hidden');
      document.getElementById('chat-input-text').focus();
    }

    function cancelChatReply() {
      state.chatReplyToMessageId = null;
      document.getElementById('chat-reply-banner').classList.add('hidden');
    }

    function insertChatTemplate(templateText) {
      const input = document.getElementById('chat-input-text');
      input.value = templateText + input.value;
      input.focus();
    }

    function handleChatInputKeydown(e) {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        sendChatMessageFromAdmin();
      }
    }

    async function sendChatMessageFromAdmin() {
      const textEl = document.getElementById('chat-input-text');
      const text = textEl.value.trim();
      if (!text) return;

      if (!state.currentChatId) {
        showToast('Чат не выбран', 'error');
        return;
      }

      const parseMode = document.getElementById('chat-parse-mode').value;
      const sendBtn = document.getElementById('btn-send-chat');
      sendBtn.disabled = true;

      try {
        await apiRequest(`/api/admin/chats/${state.currentChatId}/messages`, {
          method: 'POST',
          body: JSON.stringify({
            text: text,
            parse_mode: parseMode,
            reply_to_message_id: state.chatReplyToMessageId ? parseInt(state.chatReplyToMessageId) : null
          })
        });

        textEl.value = '';
        cancelChatReply();
        showToast('Сообщение отправлено в Telegram!', 'success');
        await loadChatMessages(true);
      } catch (err) {
        showToast('Ошибка отправки: ' + err.message, 'error');
      } finally {
        sendBtn.disabled = false;
      }
    }

    function setupChatAutoRefresh() {
      if (state.chatAutoRefreshInterval) {
        clearInterval(state.chatAutoRefreshInterval);
      }
      state.chatAutoRefreshInterval = setInterval(() => {
        if (state.activeTab === 'chat') {
          const autoRefreshChecked = document.getElementById('chat-auto-refresh')?.checked;
          if (autoRefreshChecked) {
            loadChatMessages(false);
          }
        }
      }, 5000);
    }

    // --- TAB: CONFIG ---
    async function loadConfig() {
      try {
        const data = await apiRequest('/api/admin/config');
        state.config = data.config;
        state.defaults = data.defaults;
        renderConfigForm(data.config);
        updateBotStatusUI(data.config.BOT_DISABLED);
      } catch (err) {
        showToast('Ошибка загрузки конфигурации: ' + err.message, 'error');
      }
    }

    function renderConfigForm(cfg) {
      for (const [key, val] of Object.entries(cfg)) {
        const el = document.getElementById('cfg-' + key);
        if (!el) continue;
        if (key === 'REACTION_ALLOWED_EMOJIS') {
          el.value = Array.isArray(val) ? val.join(' ') : (val || '');
        } else if (el.type === 'checkbox') {
          el.checked = !!val;
        } else if (el.type === 'range') {
          el.value = val;
          const unit = key.includes('CHANCE') ? '%' : '';
          const label = document.getElementById('label-' + key);
          if (label) label.textContent = `${(val * 100).toFixed(1)}%`;
        } else {
          el.value = val;
        }
      }
    }

    function updateRangeLabel(input, unit = '%', multiplier = 100) {
      const key = input.id.replace('cfg-', '');
      const label = document.getElementById('label-' + key);
      if (label) {
        const val = parseFloat(input.value) * 100;
        label.textContent = `${val.toFixed(1)}${unit}`;
      }
    }

    function updateBotStatusUI(isDisabled) {
      const badge = document.getElementById('bot-status-badge');
      const text = document.getElementById('bot-status-text');
      const btn = document.getElementById('quick-bot-toggle-btn');
      const btnLabel = document.getElementById('quick-bot-toggle-label');

      if (isDisabled) {
        badge.className = 'flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20';
        badge.firstElementChild.className = 'w-2 h-2 rounded-full bg-rose-500';
        text.textContent = 'Бот отключен';
        btnLabel.textContent = 'Включить';
      } else {
        badge.className = 'flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20';
        badge.firstElementChild.className = 'w-2 h-2 rounded-full bg-emerald-500 animate-pulse';
        text.textContent = 'Бот активен';
        btnLabel.textContent = 'Остановить';
      }
    }

    async function toggleBotQuickly() {
      try {
        const res = await apiRequest('/api/admin/actions/toggle_bot', { method: 'POST' });
        state.config.BOT_DISABLED = res.bot_disabled;
        updateBotStatusUI(res.bot_disabled);
        const el = document.getElementById('cfg-BOT_DISABLED');
        if (el) el.checked = res.bot_disabled;
        showToast(res.bot_disabled ? 'Бот успешно отключен' : 'Бот успешно включен');
      } catch (err) {
        showToast('Ошибка переключения бота: ' + err.message, 'error');
      }
    }

    async function saveConfigForm() {
      const updates = {};
      for (const [key, defaultVal] of Object.entries(state.defaults || {})) {
        const el = document.getElementById('cfg-' + key);
        if (!el) continue;
        if (key === 'REACTION_ALLOWED_EMOJIS') {
          updates[key] = el.value.replace(/,/g, ' ').split(/\s+/).filter(Boolean);
        } else if (el.type === 'checkbox') {
          updates[key] = el.checked;
        } else if (typeof defaultVal === 'number') {
          updates[key] = parseFloat(el.value);
        } else {
          updates[key] = el.value;
        }
      }

      try {
        const res = await apiRequest('/api/admin/config', {
          method: 'PUT',
          body: JSON.stringify(updates)
        });
        state.config = res.config;
        updateBotStatusUI(res.config.BOT_DISABLED);
        showToast('Параметры бота успешно обновлены!');
      } catch (err) {
        showToast('Ошибка сохранения настроек: ' + err.message, 'error');
      }
    }

    async function resetConfigToDefaults() {
      if (!confirm('Сбросить ВСЕ параметры бота к заводским значениям?')) return;
      try {
        const res = await apiRequest('/api/admin/config/reset', { method: 'POST' });
        state.config = res.config;
        renderConfigForm(res.config);
        updateBotStatusUI(res.config.BOT_DISABLED);
        showToast('Настройки сброшены к дефолту');
      } catch (err) {
        showToast('Ошибка сброса: ' + err.message, 'error');
      }
    }

    // --- TAB: PROMPTS ---
    async function loadPrompts() {
      try {
        const data = await apiRequest('/api/admin/prompts');
        state.prompts = data.prompts || [];
        renderPromptsList();
        selectPrompt(state.selectedPromptKey);
      } catch (err) {
        showToast('Ошибка загрузки промптов: ' + err.message, 'error');
      }
    }

    function renderPromptsList() {
      const container = document.getElementById('prompts-list-container');
      container.innerHTML = '';
      state.prompts.forEach(p => {
        const btn = document.createElement('button');
        const isSelected = p.key === state.selectedPromptKey;
        btn.className = `w-full text-left px-3 py-2.5 rounded-xl transition text-xs flex flex-col gap-0.5 ${
          isSelected ? 'bg-emerald-600/20 text-emerald-300 border border-emerald-500/30' : 'text-slate-300 hover:bg-slate-800'
        }`;
        btn.onclick = () => selectPrompt(p.key);
        btn.innerHTML = `
          <div class="flex items-center justify-between">
            <span class="font-semibold">${p.name}</span>
            ${p.is_modified ? '<span class="text-[9px] px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-400 font-mono">Изменен</span>' : ''}
          </div>
          <span class="text-[10px] text-slate-500 truncate">${p.key}</span>
        `;
        container.appendChild(btn);
      });
    }

    function selectPrompt(key) {
      state.selectedPromptKey = key;
      renderPromptsList();
      const prompt = state.prompts.find(p => p.key === key);
      if (!prompt) return;

      document.getElementById('current-prompt-title').textContent = prompt.name;
      document.getElementById('current-prompt-desc').textContent = prompt.description;
      const badge = document.getElementById('current-prompt-badge');
      if (prompt.is_modified) {
        badge.className = 'text-[11px] px-2.5 py-0.5 rounded-full font-mono bg-amber-500/10 text-amber-400 border border-amber-500/20';
        badge.textContent = 'Модифицирован';
      } else {
        badge.className = 'text-[11px] px-2.5 py-0.5 rounded-full font-mono bg-slate-800 text-slate-400 border border-slate-700';
        badge.textContent = 'Оригинальный шаблон';
      }

      // Render placeholders
      const phContainer = document.getElementById('current-prompt-placeholders');
      phContainer.innerHTML = '';
      if (!prompt.placeholders || prompt.placeholders.length === 0) {
        phContainer.innerHTML = '<span class="text-xs text-slate-600 italic">Нет переменных</span>';
      } else {
        prompt.placeholders.forEach(ph => {
          const tag = document.createElement('button');
          tag.className = 'text-[11px] font-mono px-2 py-0.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-emerald-400 border border-slate-700 transition cursor-pointer';
          tag.textContent = `{${ph}}`;
          tag.title = 'Нажмите, чтобы вставить переменную в текст';
          tag.onclick = () => insertVariableAtCursor(`{${ph}}`);
          phContainer.appendChild(tag);
        });
      }

      const textarea = document.getElementById('prompt-editor-textarea');
      textarea.value = prompt.current_template;
      updateCharCount(textarea.value);
    }

    function insertVariableAtCursor(variable) {
      const textarea = document.getElementById('prompt-editor-textarea');
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      const val = textarea.value;
      textarea.value = val.substring(0, start) + variable + val.substring(end);
      textarea.selectionStart = textarea.selectionEnd = start + variable.length;
      textarea.focus();
      updateCharCount(textarea.value);
    }

    function updateCharCount(val) {
      document.getElementById('prompt-char-count').textContent = `${val.length} символов (~${Math.round(val.length / 4)} токенов)`;
    }

    document.getElementById('prompt-editor-textarea').addEventListener('input', (e) => {
      updateCharCount(e.target.value);
    });

    async function saveSelectedPrompt() {
      const key = state.selectedPromptKey;
      const textarea = document.getElementById('prompt-editor-textarea');
      try {
        await apiRequest(`/api/admin/prompts/${key}`, {
          method: 'PUT',
          body: JSON.stringify({ template: textarea.value })
        });
        showToast(`Промпт "${key}" сохранен и активен!`);
        await loadPrompts();
      } catch (err) {
        showToast('Ошибка сохранения промпта: ' + err.message, 'error');
      }
    }

    async function resetSelectedPrompt() {
      const key = state.selectedPromptKey;
      if (!confirm(`Сбросить промпт "${key}" к оригинальному системному тексту?`)) return;
      try {
        await apiRequest(`/api/admin/prompts/${key}/reset`, { method: 'POST' });
        showToast(`Промпт "${key}" сброшен к дефолту`);
        await loadPrompts();
      } catch (err) {
        showToast('Ошибка сброса: ' + err.message, 'error');
      }
    }

    // --- TAB: USERS & POINTS ---
    async function loadUsers() {
      if (!state.currentChatId) return;
      const tbody = document.getElementById('users-table-body');
      tbody.innerHTML = '<tr><td colspan="5" class="py-8 text-center text-slate-500">Загрузка...</td></tr>';
      try {
        const data = await apiRequest(`/api/admin/chats/${state.currentChatId}/users`);
        state.users = data.users || [];
        renderUsersTable(state.users);
      } catch (err) {
        tbody.innerHTML = `<tr><td colspan="5" class="py-8 text-center text-rose-400">Ошибка: ${err.message}</td></tr>`;
      }
    }

    function renderUsersTable(usersList) {
      const tbody = document.getElementById('users-table-body');
      tbody.innerHTML = '';
      if (!usersList || usersList.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="py-8 text-center text-slate-500">В этом чате еще нет зарегистрированных участников</td></tr>';
        return;
      }

      usersList.forEach(u => {
        const stats = u.stats || {};
        const points = stats.total_points || 0;
        const rank = stats.current_rank || 'Порядочный 😐';
        const achievements = stats.achievements || [];
        const falseReports = stats.false_report_count || 0;
        const username = u.username ? `@${u.username}` : (u.full_name || `ID ${u.user_id}`);

        const tr = document.createElement('tr');
        tr.className = 'hover:bg-slate-800/40 transition';
        tr.innerHTML = `
          <td class="py-3 px-4">
            <div class="font-bold text-white text-xs flex items-center gap-2">
              <span>${escapeHtml(u.full_name || username)}</span>
              ${falseReports > 0 ? `<span class="px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300 text-[10px] font-mono border border-rose-500/30 cursor-pointer" title="Ложных доносов: ${falseReports}. Нажмите для сброса" onclick="resetFalseReports('${escapeHtml(u.user_id)}')">⚠️ ${falseReports} страйк</span>` : ''}
            </div>
            <div class="text-[10px] text-slate-400 font-mono">${escapeHtml(username)} <span class="text-slate-600">(${escapeHtml(u.user_id)})</span></div>
          </td>
          <td class="py-3 px-4 text-center">
            <span class="inline-block px-2.5 py-0.5 rounded-full text-xs font-mono font-bold ${points > 200 ? 'bg-rose-500/20 text-rose-300' : 'bg-slate-800 text-slate-300'}">
              ${points}
            </span>
          </td>
          <td class="py-3 px-4">
            <span class="text-xs">${escapeHtml(rank)}</span>
          </td>
          <td class="py-3 px-4">
            <div class="flex flex-wrap gap-1 max-w-xs">
              ${achievements.length > 0 
                ? achievements.map(a => `<span class="px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 text-[10px] border border-amber-500/20 truncate">${escapeHtml(typeof a === 'string' ? a : (a.title || 'Ачивка'))}</span>`).join('')
                : '<span class="text-slate-600 italic text-[10px]">Нет</span>'}
            </div>
          </td>
          <td class="py-3 px-4 text-right">
            <div class="inline-flex items-center gap-1">
              ${falseReports > 0 ? `
              <button onclick="resetFalseReports('${escapeHtml(u.user_id)}')" title="Сбросить страйки (${falseReports})"
                      class="px-2 py-1 rounded bg-rose-950/60 hover:bg-rose-900 border border-rose-800/50 text-rose-300 font-mono text-[11px] font-bold">Сброс страйков</button>
              ` : ''}
              <button onclick="quickAdjustPoints('${escapeHtml(u.user_id)}', 25)" title="+25 очков (Токсичность)"
                      class="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-rose-400 font-mono text-[11px] font-bold">+25</button>
              <button onclick="quickAdjustPoints('${escapeHtml(u.user_id)}', -25)" title="-25 очков"
                      class="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-emerald-400 font-mono text-[11px] font-bold">-25</button>
              <button onclick="openPointsModal('${escapeHtml(u.user_id)}')" title="Кастомные очки"
                      class="p-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs">✏️</button>
              <button onclick="openAchievementsModal('${escapeHtml(u.user_id)}')" title="Ачивки"
                      class="p-1 rounded bg-slate-800 hover:bg-slate-700 text-amber-400 text-xs">🏅</button>
            </div>
          </td>
        `;
        tbody.appendChild(tr);
      });
    }

    function filterUsersTable() {
      const q = document.getElementById('user-search-input').value.toLowerCase();
      const filtered = state.users.filter(u => {
        const name = (u.full_name || '').toLowerCase();
        const username = (u.username || '').toLowerCase();
        const uid = String(u.user_id);
        return name.includes(q) || username.includes(q) || uid.includes(q);
      });
      renderUsersTable(filtered);
    }

    async function quickAdjustPoints(userId, delta) {
      try {
        await apiRequest(`/api/admin/chats/${state.currentChatId}/users/${userId}/points`, {
          method: 'POST',
          body: JSON.stringify({
            points_delta: delta,
            reason: delta > 0 ? 'Административный штраф' : 'Административное поощрение'
          })
        });
        showToast(`Очки обновлены (${delta > 0 ? '+' : ''}${delta})`);
        await loadUsers();
      } catch (err) {
        showToast('Ошибка: ' + err.message, 'error');
      }
    }

    async function resetFalseReports(userId) {
      if (!confirm('Сбросить счетчик ложных доносов для этого пользователя до 0?')) return;
      try {
        await apiRequest(`/api/admin/chats/${state.currentChatId}/users/${userId}/reset_false_reports`, {
          method: 'POST'
        });
        showToast('Страйки ложных доносов сброшены!', 'success');
        await loadUsers();
      } catch (err) {
        showToast('Ошибка: ' + err.message, 'error');
      }
    }

    function openPointsModal(userId) {
      const u = state.users.find(x => String(x.user_id) === String(userId));
      if (!u) return;
      state.selectedUserForPoints = userId;
      const username = u.username ? `@${u.username}` : (u.full_name || `ID ${u.user_id}`);
      const currentPoints = (u.stats && u.stats.total_points) || 0;
      document.getElementById('modal-points-user').textContent = `${username} (Текущие: ${currentPoints})`;
      document.getElementById('modal-points-delta').value = '';
      document.getElementById('modal-points-exact').value = '';
      openModal('modal-points');
    }

    async function submitPointsAdjust() {
      const deltaVal = document.getElementById('modal-points-delta').value;
      const exactVal = document.getElementById('modal-points-exact').value;
      const reason = document.getElementById('modal-points-reason').value;

      const body = { reason };
      if (exactVal !== '') {
        body.exact_points = parseInt(exactVal, 10);
      } else if (deltaVal !== '') {
        body.points_delta = parseInt(deltaVal, 10);
      } else {
        showToast('Укажите дельту или точное количество очков', 'error');
        return;
      }

      try {
        await apiRequest(`/api/admin/chats/${state.currentChatId}/users/${state.selectedUserForPoints}/points`, {
          method: 'POST',
          body: JSON.stringify(body)
        });
        closeModal('modal-points');
        showToast('Очки успешно обновлены!');
        await loadUsers();
      } catch (err) {
        showToast('Ошибка: ' + err.message, 'error');
      }
    }

    function openAchievementsModal(userId) {
      const u = state.users.find(x => String(x.user_id) === String(userId));
      if (!u) return;
      state.selectedUserForAchievements = userId;
      const username = u.username ? `@${u.username}` : (u.full_name || `ID ${u.user_id}`);
      const achs = (u.stats && u.stats.achievements) || [];
      document.getElementById('modal-achievements-user').textContent = username;
      const textLines = achs.map(a => typeof a === 'string' ? a : JSON.stringify(a)).join('\\n');
      document.getElementById('modal-achievements-text').value = textLines;
      openModal('modal-achievements');
    }

    async function submitAchievementsUpdate() {
      const rawText = document.getElementById('modal-achievements-text').value;
      const lines = rawText.split('\\n').map(l => l.trim()).filter(Boolean);
      const parsedAchievements = lines.map(l => {
        try {
          return JSON.parse(l);
        } catch (e) {
          return l;
        }
      });

      try {
        await apiRequest(`/api/admin/chats/${state.currentChatId}/users/${state.selectedUserForAchievements}/achievements`, {
          method: 'POST',
          body: JSON.stringify({ achievements: parsedAchievements })
        });
        closeModal('modal-achievements');
        showToast('Ачивки сохранены');
        await loadUsers();
      } catch (err) {
        showToast('Ошибка сохранения ачивок: ' + err.message, 'error');
      }
    }

    async function showLedgerModal() {
      openModal('modal-ledger');
      const tbody = document.getElementById('ledger-table-body');
      tbody.innerHTML = '<tr><td colspan="5" class="py-4 text-center text-slate-500">Загрузка журнала...</td></tr>';
      try {
        const data = await apiRequest(`/api/admin/chats/${state.currentChatId}/points_ledger`);
        const events = data.events || [];
        tbody.innerHTML = '';
        if (events.length === 0) {
          tbody.innerHTML = '<tr><td colspan="5" class="py-4 text-center text-slate-500">История пуста</td></tr>';
          return;
        }
        events.forEach(ev => {
          const delta = ev.points_delta || 0;
          const tr = document.createElement('tr');
          tr.className = 'hover:bg-slate-800/40';
          tr.innerHTML = `
            <td class="py-2.5 px-3 font-mono text-[10px] text-slate-400">${escapeHtml(ev.week_key || '—')}</td>
            <td class="py-2.5 px-3 font-mono text-[11px]">${escapeHtml(ev.user_id)}</td>
            <td class="py-2.5 px-3 text-center font-mono font-bold ${delta > 0 ? 'text-rose-400' : 'text-emerald-400'}">${delta > 0 ? '+' : ''}${delta}</td>
            <td class="py-2.5 px-3 text-[11px]"><span class="text-slate-400">${escapeHtml(ev.event_type || '')}:</span> ${escapeHtml(ev.reason || '')}</td>
            <td class="py-2.5 px-3 text-right">
              <button onclick="revertLedgerEvent('${escapeHtml(ev.id)}')" class="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 hover:bg-rose-500/30 text-[10px] font-medium">Откатить</button>
            </td>
          `;
          tbody.appendChild(tr);
        });
      } catch (err) {
        tbody.innerHTML = `<tr><td colspan="5" class="py-4 text-center text-rose-400">${escapeHtml(err.message)}</td></tr>`;
      }
    }

    async function revertLedgerEvent(eventId) {
      if (!confirm('Откатить это начисление очков и вернуть баланс?')) return;
      try {
        await apiRequest(`/api/admin/chats/${state.currentChatId}/points_ledger/${eventId}`, { method: 'DELETE' });
        showToast('Событие успешно отменено!');
        showLedgerModal();
        loadUsers();
      } catch (err) {
        showToast('Ошибка отката: ' + err.message, 'error');
      }
    }

    // --- TAB: LORE & FACTS ---
    async function loadFactsAndLore() {
      if (!state.currentChatId) return;
      loadFacts();
      loadLoreJson();
    }

    async function loadFacts() {
      const container = document.getElementById('facts-list-container');
      container.innerHTML = '<div class="text-xs text-slate-500 py-4 text-center">Загрузка фактов...</div>';
      try {
        const data = await apiRequest(`/api/admin/chats/${state.currentChatId}/facts`);
        const facts = data.facts || [];
        document.getElementById('facts-count').textContent = facts.length;
        container.innerHTML = '';
        if (facts.length === 0) {
          container.innerHTML = '<div class="text-xs text-slate-500 py-4 text-center">Нет фактов. Добавьте первый факт!</div>';
          return;
        }
        facts.forEach(f => {
          const div = document.createElement('div');
          div.className = 'p-3 rounded-xl bg-[#162032] border border-slate-800 flex items-start justify-between gap-3 text-xs';
          div.innerHTML = `
            <div class="space-y-1">
              <div class="text-slate-200 font-medium">${escapeHtml(f.text)}</div>
              <div class="text-[10px] text-slate-500 font-mono">${f.username ? '@' + escapeHtml(f.username) : ''} ${f.added_by ? '• ' + escapeHtml(f.added_by) : ''}</div>
            </div>
            <button onclick="deleteFact('${escapeHtml(f.id)}')" title="Удалить факт" class="text-slate-500 hover:text-rose-400 p-1 transition">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
            </button>
          `;
          container.appendChild(div);
        });
      } catch (err) {
        container.innerHTML = `<div class="text-xs text-rose-400 py-4 text-center">Ошибка: ${escapeHtml(err.message)}</div>`;
      }
    }

    function showAddFactModal() {
      document.getElementById('modal-fact-text').value = '';
      document.getElementById('modal-fact-username').value = '';
      openModal('modal-fact');
    }

    async function submitAddFact() {
      const text = document.getElementById('modal-fact-text').value.trim();
      const username = document.getElementById('modal-fact-username').value.trim();
      if (!text) {
        showToast('Введите текст факта', 'error');
        return;
      }
      try {
        await apiRequest(`/api/admin/chats/${state.currentChatId}/facts`, {
          method: 'POST',
          body: JSON.stringify({ text, username })
        });
        closeModal('modal-fact');
        showToast('Факт добавлен!');
        loadFacts();
      } catch (err) {
        showToast('Ошибка добавления факта: ' + err.message, 'error');
      }
    }

    async function deleteFact(factId) {
      if (!confirm('Удалить этот факт из базы?')) return;
      try {
        await apiRequest(`/api/admin/chats/${state.currentChatId}/facts/${factId}`, { method: 'DELETE' });
        showToast('Факт удален');
        loadFacts();
      } catch (err) {
        showToast('Ошибка: ' + err.message, 'error');
      }
    }

    async function loadLoreJson() {
      const textarea = document.getElementById('lore-json-textarea');
      try {
        const data = await apiRequest(`/api/admin/chats/${state.currentChatId}/lore`);
        textarea.value = JSON.stringify(data.lore || {}, null, 2);
      } catch (err) {
        textarea.value = 'Ошибка загрузки лора: ' + err.message;
      }
    }

    async function saveLoreJson() {
      const textarea = document.getElementById('lore-json-textarea');
      let parsed;
      try {
        parsed = JSON.parse(textarea.value);
      } catch (e) {
        showToast('Невалидный JSON! Проверьте синтаксис.', 'error');
        return;
      }

      try {
        await apiRequest(`/api/admin/chats/${state.currentChatId}/lore`, {
          method: 'PUT',
          body: JSON.stringify({ lore: parsed })
        });
        showToast('Ядро Лора успешно сохранено!');
      } catch (err) {
        showToast('Ошибка сохранения лора: ' + err.message, 'error');
      }
    }

    // --- TAB: AGREEMENTS ---
    async function loadAgreements() {
      if (!state.currentChatId) return;
      const tbody = document.getElementById('agreements-table-body');
      tbody.innerHTML = '<tr><td colspan="5" class="py-8 text-center text-slate-500">Загрузка договоренностей...</td></tr>';
      try {
        const data = await apiRequest(`/api/admin/chats/${state.currentChatId}/agreements`);
        const ags = data.agreements || [];
        tbody.innerHTML = '';
        if (ags.length === 0) {
          tbody.innerHTML = '<tr><td colspan="5" class="py-8 text-center text-slate-500">Договоренностей в этом чате нет</td></tr>';
          return;
        }

        ags.forEach(ag => {
          const status = ag.status || 'active';
          let statusBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-500/20 text-emerald-300">Активна</span>';
          if (status === 'disputed') statusBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-mono bg-amber-500/20 text-amber-300">Оспорена</span>';
          if (status === 'fulfilled') statusBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-mono bg-sky-500/20 text-sky-300">Исполнена</span>';
          if (status === 'cancelled') statusBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-700 text-slate-400">Отменена</span>';

          const users = (ag.users || []).join(', ') || '—';
          const tr = document.createElement('tr');
          tr.className = 'hover:bg-slate-800/40 transition';
          tr.innerHTML = `
            <td class="py-3 px-4 font-medium text-white">${escapeHtml(ag.text || '—')}</td>
            <td class="py-3 px-4 font-mono text-[11px] text-slate-300">${escapeHtml(users)}</td>
            <td class="py-3 px-4 text-center">${statusBadge}</td>
            <td class="py-3 px-4 text-[10px] text-slate-400 font-mono">${ag.expires_at ? escapeHtml(new Date(ag.expires_at).toLocaleString()) : '—'}</td>
            <td class="py-3 px-4 text-right">
              <div class="inline-flex items-center gap-1">
                <button onclick="setAgreementStatus('${escapeHtml(ag.id)}', 'fulfilled')" title="Исполнена" class="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-sky-300 text-[10px]">✓</button>
                <button onclick="setAgreementStatus('${escapeHtml(ag.id)}', 'disputed')" title="Оспорить" class="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-amber-300 text-[10px]">⚠️</button>
                <button onclick="deleteAgreement('${escapeHtml(ag.id)}')" title="Удалить" class="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-rose-400 text-[10px]">✕</button>
              </div>
            </td>
          `;
          tbody.appendChild(tr);
        });
      } catch (err) {
        tbody.innerHTML = `<tr><td colspan="5" class="py-8 text-center text-rose-400">Ошибка: ${escapeHtml(err.message)}</td></tr>`;
      }
    }

    async function setAgreementStatus(agId, newStatus) {
      try {
        await apiRequest(`/api/admin/chats/${state.currentChatId}/agreements/${agId}/status`, {
          method: 'POST',
          body: JSON.stringify({ status: newStatus })
        });
        showToast(`Статус изменен на "${newStatus}"`);
        loadAgreements();
      } catch (err) {
        showToast('Ошибка: ' + err.message, 'error');
      }
    }

    async function deleteAgreement(agId) {
      if (!confirm('Удалить эту договоренность?')) return;
      try {
        await apiRequest(`/api/admin/chats/${state.currentChatId}/agreements/${agId}`, { method: 'DELETE' });
        showToast('Договоренность удалена');
        loadAgreements();
      } catch (err) {
        showToast('Ошибка: ' + err.message, 'error');
      }
    }

    // --- TAB: LESSONS ---
    async function loadLessons() {
      if (!state.currentChatId) return;
      const container = document.getElementById('lessons-list-container');
      container.innerHTML = '<div class="py-12 text-center text-slate-500 text-xs">Загрузка уроков...</div>';
      try {
        const data = await apiRequest(`/api/admin/chats/${state.currentChatId}/lessons`);
        state.lessons = data.lessons || [];
        renderLessons();
      } catch (err) {
        container.innerHTML = `<div class="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs">Ошибка загрузки уроков: ${escapeHtml(err.message)}</div>`;
      }
    }

    function renderLessons() {
      const container = document.getElementById('lessons-list-container');
      if (!container) return;

      const lessons = state.lessons || [];
      const total = lessons.length;
      const active = lessons.filter(l => (l.status || 'active') === 'active').length;
      const archived = lessons.filter(l => l.status === 'archived').length;
      const mistakes = lessons.filter(l => l.verdict === 'mistake' || l.verdict === 'ошибка').length;

      const statTotal = document.getElementById('stat-lessons-total');
      const statActive = document.getElementById('stat-lessons-active');
      const statArchived = document.getElementById('stat-lessons-archived');
      const statMistakes = document.getElementById('stat-lessons-mistakes');

      if (statTotal) statTotal.textContent = total;
      if (statActive) statActive.textContent = active;
      if (statArchived) statArchived.textContent = archived;
      if (statMistakes) statMistakes.textContent = mistakes;

      // Filter by status
      let filtered = lessons;
      if (state.lessonsFilter === 'active') {
        filtered = filtered.filter(l => (l.status || 'active') === 'active');
      } else if (state.lessonsFilter === 'archived') {
        filtered = filtered.filter(l => l.status === 'archived');
      }

      // Filter by verdict
      if (state.lessonsVerdictFilter && state.lessonsVerdictFilter !== 'all') {
        filtered = filtered.filter(l => (l.verdict || 'fair').toLowerCase() === state.lessonsVerdictFilter.toLowerCase());
      }

      // Filter by search query
      if (state.lessonsSearch) {
        const q = state.lessonsSearch;
        filtered = filtered.filter(l => {
          const rule = (l.learned_rule || '').toLowerCase();
          const reason = (l.reasoning || '').toLowerCase();
          const date = (l.date_key || '').toLowerCase();
          const ctx = (l.trigger_context || '').toLowerCase();
          return rule.includes(q) || reason.includes(q) || date.includes(q) || ctx.includes(q);
        });
      }

      container.innerHTML = '';
      if (filtered.length === 0) {
        container.innerHTML = '<div class="py-12 text-center text-slate-500 text-xs">Уроков не найдено (попробуйте сбросить фильтры или запустите анализ фидбека).</div>';
        return;
      }

      filtered.forEach(lesson => {
        const status = lesson.status || 'active';
        const verdict = (lesson.verdict || 'fair').toLowerCase();

        let verdictBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">✓ Справедливо</span>';
        if (verdict === 'mistake' || verdict === 'ошибка') {
          verdictBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-mono bg-rose-500/20 text-rose-300 border border-rose-500/30">⚠️ Ошибка бота</span>';
        } else if (verdict === 'unclear' || verdict === 'непонятно') {
          verdictBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-mono bg-amber-500/20 text-amber-300 border border-amber-500/30">? Непонятно</span>';
        }

        const dateStr = lesson.date_key || (lesson.created_at ? new Date(lesson.created_at).toLocaleDateString() : '—');
        const card = document.createElement('div');
        card.className = `bg-[#111827] border ${status === 'active' ? 'border-emerald-500/30' : 'border-slate-800'} rounded-2xl p-5 space-y-3 hover:border-slate-700 transition`;

        card.innerHTML = `
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div class="flex flex-wrap items-center gap-2">
              ${status === 'active' 
                ? '<span class="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">🟢 В промпте (Active)</span>' 
                : '<span class="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-slate-700/50 text-slate-400 border border-slate-700">📦 В архиве</span>'}
              ${verdictBadge}
              <span class="text-[11px] font-mono text-slate-400 bg-slate-800/80 px-2 py-0.5 rounded">${escapeHtml(dateStr)}</span>
            </div>
            <div class="flex items-center gap-1.5">
              <button onclick="toggleLessonStatus('${escapeHtml(lesson.id)}', '${escapeHtml(status)}')"
                      class="px-2.5 py-1 rounded-lg text-xs font-medium ${status === 'active' ? 'bg-slate-800 hover:bg-slate-700 text-slate-300' : 'bg-emerald-600/80 hover:bg-emerald-500 text-white'} transition">
                ${status === 'active' ? 'В архив' : 'Активировать'}
              </button>
              <button onclick="openEditLessonModal('${escapeHtml(lesson.id)}')" title="Редактировать"
                      class="px-2 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-sky-400 text-xs transition">✏️</button>
              <button onclick="deleteLesson('${escapeHtml(lesson.id)}')" title="Удалить"
                      class="px-2 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-rose-400 text-xs transition">🗑️</button>
            </div>
          </div>

          <div class="text-sm font-semibold text-white leading-relaxed">
            ${escapeHtml(lesson.learned_rule || '—')}
          </div>

          ${lesson.reasoning ? `
            <div class="text-xs text-slate-300 bg-slate-900/60 p-3 rounded-xl border border-slate-800/60">
              <span class="text-slate-500 font-semibold uppercase text-[10px] block mb-1">Обоснование вердикта:</span>
              ${escapeHtml(lesson.reasoning)}
            </div>
          ` : ''}

          ${lesson.trigger_context ? `
            <details class="text-[11px] text-slate-400 bg-[#0c121e] rounded-xl p-2.5 border border-slate-800/60">
              <summary class="cursor-pointer hover:text-slate-200 font-medium select-none">Показать исходные сообщения из чата (контекст)</summary>
              <pre class="mt-2 text-[10px] font-mono text-slate-400 whitespace-pre-wrap max-h-36 overflow-y-auto leading-normal">${escapeHtml(lesson.trigger_context)}</pre>
            </details>
          ` : ''}
        `;
        container.appendChild(card);
      });
    }

    function setLessonsFilter(filterType) {
      state.lessonsFilter = filterType;
      ['all', 'active', 'archived'].forEach(f => {
        const btn = document.getElementById(`filter-btn-${f}`);
        if (!btn) return;
        if (f === filterType) {
          btn.className = 'px-3 py-1 rounded-lg text-xs font-semibold bg-slate-800 text-emerald-400 transition shadow-inner';
        } else {
          btn.className = 'px-3 py-1 rounded-lg text-xs font-medium text-slate-400 hover:text-white transition';
        }
      });
      renderLessons();
    }

    function onLessonsVerdictChanged() {
      const select = document.getElementById('lessons-verdict-filter');
      state.lessonsVerdictFilter = select.value;
      renderLessons();
    }

    function onLessonsSearchChanged() {
      const input = document.getElementById('lessons-search');
      state.lessonsSearch = (input.value || '').toLowerCase().trim();
      renderLessons();
    }

    function showAddLessonModal() {
      state.editingLessonId = null;
      document.getElementById('modal-lesson-title').innerHTML = '<span>🎓</span> <span>Добавить урок</span>';
      document.getElementById('modal-lesson-id').value = '';
      document.getElementById('modal-lesson-rule').value = '';
      document.getElementById('modal-lesson-reasoning').value = '';
      document.getElementById('modal-lesson-verdict').value = 'fair';
      document.getElementById('modal-lesson-status').value = 'active';
      document.getElementById('modal-lesson-date').value = new Date().toISOString().split('T')[0];
      document.getElementById('modal-lesson-context-box').classList.add('hidden');
      openModal('modal-lesson');
    }

    function openEditLessonModal(lessonId) {
      const lesson = (state.lessons || []).find(l => l.id === lessonId);
      if (!lesson) return;
      state.editingLessonId = lessonId;
      document.getElementById('modal-lesson-title').innerHTML = '<span>✏️</span> <span>Редактировать урок</span>';
      document.getElementById('modal-lesson-id').value = lesson.id;
      document.getElementById('modal-lesson-rule').value = lesson.learned_rule || '';
      document.getElementById('modal-lesson-reasoning').value = lesson.reasoning || '';
      document.getElementById('modal-lesson-verdict').value = lesson.verdict || 'fair';
      document.getElementById('modal-lesson-status').value = lesson.status || 'active';
      document.getElementById('modal-lesson-date').value = lesson.date_key || '';
      if (lesson.trigger_context) {
        document.getElementById('modal-lesson-context').textContent = lesson.trigger_context;
        document.getElementById('modal-lesson-context-box').classList.remove('hidden');
      } else {
        document.getElementById('modal-lesson-context-box').classList.add('hidden');
      }
      openModal('modal-lesson');
    }

    async function saveLessonForm() {
      const rule = document.getElementById('modal-lesson-rule').value.trim();
      const reasoning = document.getElementById('modal-lesson-reasoning').value.trim();
      const verdict = document.getElementById('modal-lesson-verdict').value;
      const status = document.getElementById('modal-lesson-status').value;
      const dateKey = document.getElementById('modal-lesson-date').value.trim();

      if (!rule) {
        showToast('Правило урока не может быть пустым', 'error');
        return;
      }

      try {
        if (state.editingLessonId) {
          await apiRequest(`/api/admin/chats/${state.currentChatId}/lessons/${state.editingLessonId}`, {
            method: 'PUT',
            body: JSON.stringify({
              learned_rule: rule,
              reasoning: reasoning,
              verdict: verdict,
              status: status
            })
          });
          showToast('Урок успешно обновлен');
        } else {
          await apiRequest(`/api/admin/chats/${state.currentChatId}/lessons`, {
            method: 'POST',
            body: JSON.stringify({
              learned_rule: rule,
              reasoning: reasoning,
              verdict: verdict,
              status: status,
              date_key: dateKey || undefined
            })
          });
          showToast('Новый урок добавлен');
        }
        closeModal('modal-lesson');
        loadLessons();
      } catch (err) {
        showToast('Ошибка сохранения: ' + err.message, 'error');
      }
    }

    async function toggleLessonStatus(lessonId, currentStatus) {
      const newStatus = currentStatus === 'active' ? 'archived' : 'active';
      try {
        await apiRequest(`/api/admin/chats/${state.currentChatId}/lessons/${lessonId}/status`, {
          method: 'POST',
          body: JSON.stringify({ status: newStatus })
        });
        showToast(`Урок переведен в статус "${newStatus}"`);
        loadLessons();
      } catch (err) {
        showToast('Ошибка изменения статуса: ' + err.message, 'error');
      }
    }

    async function deleteLesson(lessonId) {
      if (!confirm('Удалить этот урок?')) return;
      try {
        await apiRequest(`/api/admin/chats/${state.currentChatId}/lessons/${lessonId}`, { method: 'DELETE' });
        showToast('Урок удален');
        loadLessons();
      } catch (err) {
        showToast('Ошибка удаления: ' + err.message, 'error');
      }
    }

    function showFeedbackAnalysisModal() {
      const dateInput = document.getElementById('feedback-analysis-date');
      if (dateInput) {
        dateInput.value = new Date().toISOString().split('T')[0];
      }
      const resultBox = document.getElementById('feedback-analysis-result-container');
      if (resultBox) resultBox.classList.add('hidden');
      openModal('modal-feedback-analysis');
    }

    async function executeFeedbackAnalysis() {
      const dateInput = document.getElementById('feedback-analysis-date');
      const dateVal = dateInput ? dateInput.value : '';
      const btn = document.getElementById('btn-submit-feedback-analysis');
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span>⏳ Выполняется анализ...</span>';
      }
      const resultBox = document.getElementById('feedback-analysis-result-container');
      const resultBody = document.getElementById('feedback-result-body');
      const resultTitle = document.getElementById('feedback-result-title');

      appendConsole(`Запуск анализа обратной связи (дата: ${dateVal || 'сегодня'}, чат: ${state.currentChatId})...`);

      try {
        const res = await apiRequest('/api/admin/actions/analyze_feedback', {
          method: 'POST',
          body: JSON.stringify({
            chat_id: state.currentChatId,
            date_key: dateVal || undefined
          })
        });

        if (resultBox && resultBody) {
          resultBox.classList.remove('hidden');
          if (res.result) {
            const r = res.result;
            resultTitle.textContent = r.learned_rule ? '🎉 Извлечен новый урок!' : 'ℹ️ Анализ завершен';
            resultBody.textContent = `Вердикт: ${r.verdict}\nОбоснование: ${r.reasoning}\n${r.learned_rule ? `Правило: ${r.learned_rule}` : 'Новое правило не потребовалось.'}`;
          } else {
            resultTitle.textContent = 'ℹ️ Сообщений обратной связи не найдено';
            resultBody.textContent = res.message || 'За выбранный период пользователи не обсуждали работу бота.';
          }
        }

        appendConsole(`Анализ фидбека завершен: ${JSON.stringify(res)}`);
        showToast('Анализ фидбека завершен!');
        loadLessons();
      } catch (err) {
        if (resultBox && resultBody) {
          resultBox.classList.remove('hidden');
          resultTitle.textContent = '❌ Ошибка';
          resultBody.textContent = err.message;
        }
        appendConsole(`ОШИБКА анализа фидбека: ${err.message}`);
        showToast('Ошибка анализа: ' + err.message, 'error');
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '<span>🚀 Запустить анализ</span>';
        }
      }
    }

    // --- TAB: ACTIONS ---
    function appendConsole(msg) {
      const el = document.getElementById('actions-console-log');
      const time = new Date().toLocaleTimeString();
      el.textContent += `\\n[${time}] ${msg}`;
      el.scrollTop = el.scrollHeight;
    }

    function clearConsoleLog() {
      document.getElementById('actions-console-log').textContent = 'Консоль очищена.';
    }

    async function runDailyAnalysisAction() {
      if (!confirm(`Запустить дневной анализ для чата ${state.currentChatId}?`)) return;
      const btn = document.getElementById('btn-action-analysis');
      btn.disabled = true;
      btn.textContent = '⏳ Выполняется анализ...';
      appendConsole(`Запуск дневного анализа для чата ${state.currentChatId}...`);
      try {
        const res = await apiRequest('/api/admin/actions/daily_analysis', {
          method: 'POST',
          body: JSON.stringify({ chat_id: state.currentChatId })
        });
        appendConsole(`Анализ успешно завершен!\\nРезультат: ${JSON.stringify(res.result, null, 2)}`);
        showToast('Дневной анализ выполнен!');
      } catch (err) {
        appendConsole(`ОШИБКА дневного анализа: ${err.message}`);
        showToast('Ошибка анализа: ' + err.message, 'error');
      } finally {
        btn.disabled = false;
        btn.textContent = 'Запустить анализ';
      }
    }

    async function runWeeklyAgreementsScan(notifyTg = false) {
      if (!confirm(`Просканировать сообщения за последние 7 дней на предмет договоренностей в чате ${state.currentChatId}?`)) return;
      const btn1 = document.getElementById('btn-scan-agreements');
      const btn2 = document.getElementById('btn-action-agreements-scan');
      if (btn1) { btn1.disabled = true; btn1.textContent = '⏳ Поиск...'; }
      if (btn2) { btn2.disabled = true; btn2.textContent = '⏳ Поиск...'; }
      appendConsole(`Запуск мониторинга договоренностей за последние 7 дней (чат: ${state.currentChatId})...`);
      try {
        const res = await apiRequest('/api/admin/actions/check_agreements', {
          method: 'POST',
          body: JSON.stringify({ chat_id: state.currentChatId, lookback_days: 7, send_telegram: notifyTg })
        });
        appendConsole(`Мониторинг завершен!\\nОтвет: ${JSON.stringify(res.result, null, 2)}`);
        const count = res.result?.new_agreements?.length || 0;
        showToast(`Поиск завершен. Найдено новых договоренностей: ${count}`);
        loadAgreements();
      } catch (err) {
        appendConsole(`ОШИБКА мониторинга договоренностей: ${err.message}`);
        showToast('Ошибка мониторинга: ' + err.message, 'error');
      } finally {
        if (btn1) { btn1.disabled = false; btn1.textContent = '🔍 Просканировать за неделю'; }
        if (btn2) { btn2.disabled = false; btn2.textContent = 'Просканировать за неделю'; }
      }
    }

    async function runVoiceDigestAction(edition) {
      if (!confirm(`Сгенерировать и отправить ${edition} голосовой сводки в чат ${state.currentChatId}?`)) return;
      appendConsole(`Запуск генерации голосовой сводки (${edition}) для чата ${state.currentChatId}...`);
      try {
        const res = await apiRequest('/api/admin/actions/voice_digest', {
          method: 'POST',
          body: JSON.stringify({ chat_id: state.currentChatId, edition_type: edition, send_telegram: true })
        });
        appendConsole(`Голосовая сводка успешно озвучена и отправлена в чат!\\nСценарий: ${res.result?.script}\\nРазмер аудио: ${res.result?.audio_bytes_length} байт`);
        showToast('Голосовая сводка отправлена в чат!');
      } catch (err) {
        appendConsole(`ОШИБКА генерации голосовой сводки: ${err.message}`);
        showToast('Ошибка генерации войса: ' + err.message, 'error');
      }
    }

    async function runWeeklyAmnestyAction() {
      if (!confirm(`Применить амнистию для чата ${state.currentChatId}? Будут списаны 50% недельных очков.`)) return;
      const btn = document.getElementById('btn-action-amnesty');
      btn.disabled = true;
      btn.textContent = '⏳ Применяется амнистия...';
      appendConsole(`Запуск еженедельной амнистии для чата ${state.currentChatId}...`);
      try {
        const res = await apiRequest('/api/admin/actions/weekly_decay', {
          method: 'POST',
          body: JSON.stringify({ chat_id: state.currentChatId })
        });
        appendConsole(`Амнистия успешно применена! Ответ: ${JSON.stringify(res)}`);
        showToast('Амнистия применена!');
      } catch (err) {
        appendConsole(`ОШИБКА амнистии: ${err.message}`);
        showToast('Ошибка: ' + err.message, 'error');
      } finally {
        btn.disabled = false;
        btn.textContent = 'Применить амнистию';
      }
    }

    async function runLoreEvolutionAction() {
      if (!confirm(`Запустить эволюцию лора для чата ${state.currentChatId}?`)) return;
      const btn = document.getElementById('btn-action-evolution');
      btn.disabled = true;
      btn.textContent = '⏳ Эволюционирует...';
      appendConsole(`Запуск эволюции лора для чата ${state.currentChatId}...`);
      try {
        const res = await apiRequest('/api/admin/actions/lore_evolution', {
          method: 'POST',
          body: JSON.stringify({ chat_id: state.currentChatId })
        });
        appendConsole(`Эволюция лора завершена! Ответ: ${JSON.stringify(res)}`);
        showToast('Эволюция лора завершена!');
      } catch (err) {
        appendConsole(`ОШИБКА эволюции лора: ${err.message}`);
        showToast('Ошибка: ' + err.message, 'error');
      } finally {
        btn.disabled = false;
        btn.textContent = 'Запустить эволюцию';
      }
    }

    async function runForgetAction() {
      if (!confirm(`Вы уверены? Это сотрет ВЕСЬ накопленный лор и контекст для чата ${state.currentChatId}. Действие необратимо!`)) return;
      const btn = document.getElementById('btn-action-forget');
      btn.disabled = true;
      btn.textContent = '⏳ Очистка...';
      appendConsole(`Запуск очистки памяти для чата ${state.currentChatId}...`);
      try {
        const res = await apiRequest('/api/admin/actions/forget', {
          method: 'POST',
          body: JSON.stringify({ chat_id: state.currentChatId })
        });
        appendConsole(`Память чата очищена! Ответ: ${JSON.stringify(res)}`);
        showToast('Память очищена!');
        if (state.activeTab === 'lore') loadLore();
      } catch (err) {
        appendConsole(`ОШИБКА очистки: ${err.message}`);
        showToast('Ошибка: ' + err.message, 'error');
      } finally {
        btn.disabled = false;
        btn.textContent = 'Очистить память чата';
      }
    }

    // Auto-check auth on page load
    checkAuth();
  </script>
</body>
</html>
"""
