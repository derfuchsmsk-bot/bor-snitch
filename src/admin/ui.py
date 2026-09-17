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
                <option value="elevenlabs">ElevenLabs (Ультра-реализм, эмоции)</option>
                <option value="google">Google Cloud TTS (Нативный Wavenet)</option>
              </select>
            </div>

            <div>
              <label class="block text-xs font-medium text-slate-400 mb-1">ElevenLabs Voice ID</label>
              <input type="text" id="cfg-ELEVENLABS_VOICE_ID" class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-white font-mono" placeholder="pNInz6obpgDQGcFmaJgB">
              <div class="text-[10px] text-slate-500 mt-1">Adam: pNInz6obpgDQGcFmaJgB | George: JBFqnCBsd6RMkjVDRZzb</div>
            </div>

            <div>
              <label class="block text-xs font-medium text-slate-400 mb-1">Резервный голос (Google Cloud TTS)</label>
              <input type="text" id="cfg-VOICE_DIGEST_VOICE" class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-white font-mono" placeholder="ru-RU-Wavenet-D">
              <div class="text-[10px] text-slate-500 mt-1">Используется, если ElevenLabs недоступен или кончилась квота</div>
            </div>
          </div>

          <!-- Card: Context & Agreements -->
          <div class="bg-[#111827] border border-slate-800 rounded-2xl p-5 space-y-4 md:col-span-2 lg:col-span-3">
            <h3 class="text-sm font-bold text-sky-400 uppercase tracking-wider flex items-center gap-2">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
              Контекст, Лимиты и Слово Пацана (Договоренности)
            </h3>

            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
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
                <label class="block text-xs font-medium text-slate-400 mb-1">Лимит контекста репорта (сообщ.)</label>
                <input type="number" id="cfg-REPORT_CONTEXT_LIMIT" class="w-full px-3 py-2 bg-[#1a2333] border border-slate-700 rounded-xl text-xs text-white font-mono">
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

      <!-- ================= TAB: ACTIONS ================= -->
      <section id="tab-content-actions" class="tab-pane hidden space-y-6">
        <div class="bg-[#111827] p-5 rounded-2xl border border-slate-800">
          <h2 class="text-lg font-bold text-white flex items-center gap-2">
            <span>⚡</span> Процедуры и Действия в 1 клик
          </h2>
          <p class="text-xs text-slate-400">Ручной запуск регулярных заданий и служебных алгоритмов</p>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-6">
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
      config: {},
      defaults: {}
    };

    // --- Helpers: Toast Notifications ---
    function showToast(message, type = 'success') {
      const container = document.getElementById('toast-container');
      const toast = document.createElement('div');
      const colorClass = type === 'success' 
        ? 'bg-emerald-950/90 border-emerald-500 text-emerald-200' 
        : 'bg-rose-950/90 border-rose-500 text-rose-200';
      toast.className = `pointer-events-auto flex items-center gap-2 px-4 py-3 rounded-xl border shadow-xl text-xs font-medium transition-all duration-300 opacity-0 translate-y-2 ${colorClass}`;
      toast.innerHTML = `<span>${type === 'success' ? '✓' : '⚠️'}</span><span>${message}</span>`;
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
      const res = await fetch(endpoint, options);
      if (res.status === 401) {
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
      try {
        await apiRequest('/api/admin/login', {
          method: 'POST',
          body: JSON.stringify({ password: pwd })
        });
        showToast('Успешный вход в систему');
        showDashboard();
      } catch (err) {
        errBox.textContent = err.message;
        errBox.classList.remove('hidden');
      }
    }

    async function handleLogout() {
      try {
        await apiRequest('/api/admin/logout', { method: 'POST' });
      } catch (e) {}
      showLogin();
    }

    // --- Initialization & Chat Selection ---
    async function initializeApp() {
      await loadChats();
      await loadConfig();
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
      if (state.activeTab === 'users') loadUsers();
      if (state.activeTab === 'lore') loadFactsAndLore();
      if (state.activeTab === 'agreements') loadAgreements();
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

      if (tabId === 'config') loadConfig();
      if (tabId === 'prompts') loadPrompts();
      if (tabId === 'users') loadUsers();
      if (tabId === 'lore') loadFactsAndLore();
      if (tabId === 'agreements') loadAgreements();
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
        const username = u.username ? `@${u.username}` : (u.full_name || `ID ${u.user_id}`);

        const tr = document.createElement('tr');
        tr.className = 'hover:bg-slate-800/40 transition';
        tr.innerHTML = `
          <td class="py-3 px-4">
            <div class="font-bold text-white text-xs">${u.full_name || username}</div>
            <div class="text-[10px] text-slate-400 font-mono">${username} <span class="text-slate-600">(${u.user_id})</span></div>
          </td>
          <td class="py-3 px-4 text-center">
            <span class="inline-block px-2.5 py-0.5 rounded-full text-xs font-mono font-bold ${points > 200 ? 'bg-rose-500/20 text-rose-300' : 'bg-slate-800 text-slate-300'}">
              ${points}
            </span>
          </td>
          <td class="py-3 px-4">
            <span class="text-xs">${rank}</span>
          </td>
          <td class="py-3 px-4">
            <div class="flex flex-wrap gap-1 max-w-xs">
              ${achievements.length > 0 
                ? achievements.map(a => `<span class="px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 text-[10px] border border-amber-500/20 truncate">${typeof a === 'string' ? a : (a.title || 'Ачивка')}</span>`).join('')
                : '<span class="text-slate-600 italic text-[10px]">Нет</span>'}
            </div>
          </td>
          <td class="py-3 px-4 text-right">
            <div class="inline-flex items-center gap-1">
              <button onclick="quickAdjustPoints('${u.user_id}', 25)" title="+25 очков (Токсичность)"
                      class="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-rose-400 font-mono text-[11px] font-bold">+25</button>
              <button onclick="quickAdjustPoints('${u.user_id}', -25)" title="-25 очков"
                      class="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-emerald-400 font-mono text-[11px] font-bold">-25</button>
              <button onclick="openPointsModal('${u.user_id}', '${username.replace(/'/g, "\\'")}', ${points})" title="Кастомные очки"
                      class="p-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs">✏️</button>
              <button onclick="openAchievementsModal('${u.user_id}', '${username.replace(/'/g, "\\'")}', ${encodeURIComponent(JSON.stringify(achievements))})" title="Ачивки"
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

    function openPointsModal(userId, username, currentPoints) {
      state.selectedUserForPoints = userId;
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

    function openAchievementsModal(userId, username, achJsonEncoded) {
      state.selectedUserForAchievements = userId;
      const achs = JSON.parse(decodeURIComponent(achJsonEncoded));
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
            <td class="py-2.5 px-3 font-mono text-[10px] text-slate-400">${ev.week_key || '—'}</td>
            <td class="py-2.5 px-3 font-mono text-[11px]">${ev.user_id}</td>
            <td class="py-2.5 px-3 text-center font-mono font-bold ${delta > 0 ? 'text-rose-400' : 'text-emerald-400'}">${delta > 0 ? '+' : ''}${delta}</td>
            <td class="py-2.5 px-3 text-[11px]"><span class="text-slate-400">${ev.event_type || ''}:</span> ${ev.reason || ''}</td>
            <td class="py-2.5 px-3 text-right">
              <button onclick="revertLedgerEvent('${ev.id}')" class="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 hover:bg-rose-500/30 text-[10px] font-medium">Откатить</button>
            </td>
          `;
          tbody.appendChild(tr);
        });
      } catch (err) {
        tbody.innerHTML = `<tr><td colspan="5" class="py-4 text-center text-rose-400">${err.message}</td></tr>`;
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
              <div class="text-slate-200 font-medium">${f.text}</div>
              <div class="text-[10px] text-slate-500 font-mono">${f.username ? '@' + f.username : ''} ${f.added_by ? '• ' + f.added_by : ''}</div>
            </div>
            <button onclick="deleteFact('${f.id}')" title="Удалить факт" class="text-slate-500 hover:text-rose-400 p-1 transition">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
            </button>
          `;
          container.appendChild(div);
        });
      } catch (err) {
        container.innerHTML = `<div class="text-xs text-rose-400 py-4 text-center">Ошибка: ${err.message}</div>`;
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
            <td class="py-3 px-4 font-medium text-white">${ag.text || '—'}</td>
            <td class="py-3 px-4 font-mono text-[11px] text-slate-300">${users}</td>
            <td class="py-3 px-4 text-center">${statusBadge}</td>
            <td class="py-3 px-4 text-[10px] text-slate-400 font-mono">${ag.expires_at ? new Date(ag.expires_at).toLocaleString() : '—'}</td>
            <td class="py-3 px-4 text-right">
              <div class="inline-flex items-center gap-1">
                <button onclick="setAgreementStatus('${ag.id}', 'fulfilled')" title="Исполнена" class="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-sky-300 text-[10px]">✓</button>
                <button onclick="setAgreementStatus('${ag.id}', 'disputed')" title="Оспорить" class="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-amber-300 text-[10px]">⚠️</button>
                <button onclick="deleteAgreement('${ag.id}')" title="Удалить" class="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-rose-400 text-[10px]">✕</button>
              </div>
            </td>
          `;
          tbody.appendChild(tr);
        });
      } catch (err) {
        tbody.innerHTML = `<tr><td colspan="5" class="py-8 text-center text-rose-400">Ошибка: ${err.message}</td></tr>`;
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

    // Auto-check auth on page load
    checkAuth();
  </script>
</body>
</html>
"""
