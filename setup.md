# 🛠 Настройка и Запуск Bor Snitch Bot

Этот гайд поможет развернуть бота локально для разработки или задеплоить его в Google Cloud Run.

## 📋 Предварительные требования

*   **Python 3.11+**
*   **Google Cloud SDK** (gcloud CLI)
*   **Docker** (опционально, для контейнеризации)
*   **Ngrok** (для локальной разработки с вебхуками)
*   Аккаунт Google Cloud с активированным биллингом.
*   Токен бота от [@BotFather](https://t.me/BotFather).

---

## 💻 Локальная разработка

### 1. Клонирование и подготовка

```bash
git clone https://github.com/yourusername/bor-snitch.git
cd bor-snitch
```

Создайте виртуальное окружение:

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

Установите зависимости:

```bash
pip install -r requirements.txt
```

### 2. Настройка переменных окружения

Создайте файл `.env` на основе примера:

```bash
cp .env.example .env
```

Отредактируйте `.env`:
*   `TELEGRAM_TOKEN`: Токен вашего бота.
*   `WEBHOOK_URL`: Будет заполнен позже (см. шаг 4).
*   `GCP_PROJECT_ID`: ID вашего проекта в Google Cloud.
*   `GCP_LOCATION`: Регион (например, `us-central1`).
*   `SECRET_TOKEN`: Придумайте любую секретную строку (для защиты эндпоинтов).

### 3. Авторизация в Google Cloud

Для работы с Vertex AI и Firestore локально, используйте Application Default Credentials:

```bash
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

### 4. Запуск с Ngrok (Webhook)

Бот работает через вебхуки (FastAPI), поэтому для локального теста нужен публичный URL.

1.  Запустите бота:
    ```bash
    uvicorn src.main:app --reload
    ```
    Бот запустится на `http://127.0.0.1:8000`.

2.  В другом терминале запустите ngrok:
    ```bash
    ngrok http 8000
    ```

3.  Скопируйте HTTPS URL от ngrok (например, `https://abc1-23-45.ngrok-free.app`).

4.  Обновите `WEBHOOK_URL` в файле `.env` и перезапустите бота, ИЛИ вручную установите вебхук через браузер/curl:
    ```bash
    curl -F "url=https://YOUR_NGROK_URL/webhook" https://api.telegram.org/botYOUR_BOT_TOKEN/setWebhook
    ```

---

## 🐳 Запуск в Docker

1.  **Сборка образа:**
    ```bash
    docker build -t bor-snitch .
    ```

2.  **Запуск контейнера:**
    Вам нужно пробросить переменные окружения и файл с кредами Google Cloud (если запускаете не в GCP среде).

    ```bash
    docker run -p 8000:8080 --env-file .env bor-snitch
    ```

---

## 🚀 Деплой в Google Cloud Run

Бот оптимизирован для Serverless-запуска.

### 1. Подготовка Google Cloud Project

Убедитесь, что API включены:
```bash
gcloud services enable run.googleapis.com \
    firestore.googleapis.com \
    aiplatform.googleapis.com \
    cloudscheduler.googleapis.com
```

### 2. Деплой

```bash
gcloud run deploy bor-snitch \
    --source . \
    --region us-central1 \
    --allow-unauthenticated \
    --set-env-vars TELEGRAM_TOKEN=your_token \
    --set-env-vars GCP_PROJECT_ID=your_project_id \
    --set-env-vars GCP_LOCATION=us-central1 \
    --set-env-vars SECRET_TOKEN=your_secret
```

После успешного деплоя вы получите URL сервиса (например, `https://bor-snitch-xyz.run.app`).

### 3. Установка вебхука

Используйте полученный URL сервиса:

```bash
curl -F "url=https://YOUR_SERVICE_URL/webhook" https://api.telegram.org/botYOUR_BOT_TOKEN/setWebhook
```

### 4. Настройка Cloud Scheduler (через веб-интерфейс)

Бот анализирует чат раз в сутки и проводит "амнистию" раз в неделю. Настройте триггеры через Google Cloud Console.

1.  Перейдите в **Cloud Scheduler**: [console.cloud.google.com/cloudscheduler](https://console.cloud.google.com/cloudscheduler)
2.  Нажмите **Создать задание (Create Job)**.

#### А. Ежедневный анализ (Daily Analysis)

*   **Имя:** `daily-analysis`
*   **Регион:** Выберите тот же, где развернут бот (например, `us-central1`).
*   **Частота:** `50 23 * * *` (каждый день в 23:50).
*   **Часовой пояс:** UTC (или ваш локальный).
*   **Тип назначения (Target type):** HTTP
*   **URL:** `https://YOUR-SERVICE-URL.run.app/analyze_daily`
*   **HTTP метод:** POST
*   **Заголовки (HTTP Headers):**
    *   Добавьте заголовок:
        *   Name: `X-Secret-Token`
        *   Value: `ВАШ_SECRET_TOKEN_ИЗ_ENV`
    *   Content-Type должен быть `application/json` (обычно по умолчанию).
*   **Тело (Body):**
    Вставьте **только** JSON-объект (без слова `json` и кавычек вокруг всего блока):
    ```text
    {"chat_id": "YOUR_TARGET_CHAT_ID"}
    ```
*   Нажмите **Создать**.

#### Б. Еженедельная амнистия (Weekly Decay)

*   **Имя:** `weekly-decay`
*   **Частота:** `59 23 * * 0` (каждое воскресенье в 23:59).
*   **URL:** `https://YOUR-SERVICE-URL.run.app/weekly_decay`
*   **HTTP метод:** POST
*   **Заголовки:** Те же, что и выше (`X-Secret-Token`).
*   **Тело (Body):**
    Вставьте **только** JSON-объект:
    ```text
    {"chat_id": "YOUR_TARGET_CHAT_ID"}
    ```

*Примечание: Вам нужно создать отдельные джобы для каждого активного чата, если их несколько.*
