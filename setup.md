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
*   `SECRET_TOKEN`: Придумайте любую секретную строку (для защиты эндпоинтов от посторонних).

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

4.  Обновите `WEBHOOK_URL` в файле `.env` и перезапустите бота, ИЛИ вручную установите вебхук:
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

### 4. Настройка Cloud Scheduler

Бот использует **Cloud Scheduler** для запуска периодических задач, так как Cloud Run может "засыпать".

> **Важно:** Поскольку бот не хранит список чатов в памяти для шедулера, вам нужно создать отдельные задачи (Jobs) для **каждого** активного чата.

#### А. Ежедневный анализ (Daily Analysis)
Триггерит анализ за прошедший день.

*   **Имя:** `daily-analysis-CHATID`
*   **Частота:** `50 23 * * *` (каждый день в 23:50).
*   **URL:** `https://YOUR-SERVICE-URL.run.app/analyze_daily`
*   **HTTP метод:** POST
*   **Заголовки:** `X-Secret-Token: ВАШ_SECRET_TOKEN`
*   **Тело (Body):**
    ```json
    {"chat_id": "123456789"}
    ```

#### Б. Еженедельная амнистия (Weekly Decay)
Делит очки пополам каждое воскресенье.

*   **Имя:** `weekly-decay-CHATID`
*   **Частота:** `59 23 * * 0` (каждое воскресенье в 23:59).
*   **URL:** `https://YOUR-SERVICE-URL.run.app/weekly_decay`
*   **HTTP метод:** POST
*   **Заголовки:** `X-Secret-Token: ВАШ_SECRET_TOKEN`
*   **Тело (Body):**
    ```json
    {"chat_id": "123456789"}
    ```
