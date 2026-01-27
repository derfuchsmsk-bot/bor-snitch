# Руководство по настройке Google Cloud Storage

Это руководство объясняет, как настроить бакет (bucket) в Google Cloud Storage (GCS) для хранения сгенерированных файлов с лором.

## 1. Создание Бакета

1. Перейдите в [Google Cloud Console](https://console.cloud.google.com/).
2. Перейдите в раздел **Cloud Storage** -> **Buckets**.
3. Нажмите **CREATE** (Создать).
4. **Name your bucket (Название бакета)**: Выберите уникальное имя (например, `bor-snitch-lore`).
5. **Choose where to store your data (Где хранить данные)**:
   - **Location type**: Region (Регион).
   - **Location**: Выберите тот же регион, где работает ваш сервис Cloud Run/Vertex AI (например, `us-central1` или `europe-west1`), чтобы минимизировать задержки и расходы.
6. **Choose a storage class (Класс хранилища)**: Standard.
7. **Choose how to control access (Контроль доступа)**: Uniform (рекомендуется) или Fine-grained.
8. Нажмите **CREATE**.

## 2. Настройка Прав Доступа

Сервисному аккаунту (Service Account), который использует ваш бот, нужны права на запись файлов в этот бакет.

1. Перейдите в **IAM & Admin** -> **IAM**.
2. Найдите Service Account вашего бота (обычно выглядит как `compute@developer.gserviceaccount.com` или созданный вами вручную).
3. Нажмите иконку **Редактировать** (карандаш).
4. Добавьте роль: **Storage Object Admin** или **Storage Object Creator**.
   - Это позволит боту загружать файлы в бакет.
5. Сохраните изменения.

## 3. Обновление Конфигурации

Добавьте имя бакета в ваш файл `.env` (или в переменные окружения Cloud Run):

```bash
LORE_BUCKET_NAME=your-bucket-name
```

## 4. Запуск Скрипта

Чтобы сгенерировать лор и загрузить его в бакет, запустите Python скрипт:

```bash
# Убедитесь, что зависимости установлены
pip install -r requirements.txt

# Запустите скрипт (как модуль из корня проекта)
python -m src.scripts.generate_lore
```

Скрипт выполнит следующие действия:
1. Скачает всю историю переписки из Firestore.
2. Отправит её в Gemini AI для анализа.
3. Сгенерирует Markdown файл с описанием лора.
4. Загрузит файл в ваш GCS бакет с именем вида `lore_{chat_id}_{date}.md`.
