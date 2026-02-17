# Настройка автоматической эволюции лора через Google Cloud Scheduler

## Проблема
Текущая реализация обновления лора (Lore Evolution) работает через внутренний планировщик `APScheduler` внутри бота (`src/main.py`).
Это имеет ряд недостатков:
1. **Редкость обновлений:** Настроено на раз в неделю (понедельник, 00:30).
2. **Зависимость от аптайма:** Если бот перезагружается или падает в момент срабатывания таймера, обновление пропускается.
3. **Зависимость от памяти:** Эволюция требует наличия "воспоминаний" (memories), которые создаются ежедневным анализом. Если ежедневный анализ не прошел, эволюция не сработает.

## Решение
Перенос запуска эволюции лора на внешний планировщик **Google Cloud Scheduler**. Это гарантирует выполнение задачи по расписанию через HTTP-вызов.

---

## Шаг 1: Добавление API Endpoint

В файл `src/main.py` необходимо добавить новый маршрут для принудительного запуска эволюции лора.

```python
# src/main.py

@app.post("/evolve_lore")
async def evolve_lore_endpoint(request: Request, auth=Depends(verify_jwt)):
    """
    Эндпоинт для триггера эволюции лора из Google Cloud Scheduler.
    """
    data = await request.json()
    chat_id = data.get("chat_id")
    
    if not chat_id:
        raise HTTPException(status_code=400, detail="Missing chat_id")
        
    logging.info(f"Manual lore evolution triggered for chat {chat_id}")
    
    try:
        # Запускаем эволюцию (это может занять время, лучше делать в фоне, 
        # но для Cloud Scheduler синхронный ответ тоже допустим, если уложимся в таймаут)
        await LoreService.evolve_lore(int(chat_id))
        return {"status": "evolution_completed", "chat_id": chat_id}
    except Exception as e:
        logging.error(f"Lore evolution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

## Шаг 2: Настройка Google Cloud Scheduler

1. Перейдите в [Google Cloud Console -> Cloud Scheduler](https://console.cloud.google.com/cloudscheduler).
2. Нажмите **Create Job**.

### Конфигурация задачи:

*   **Name:** `snitch-lore-evolution`
*   **Region:** Выберите регион вашего приложения (например, `europe-west1` или `us-central1`).
*   **Description:** `Daily lore evolution trigger`
*   **Frequency:** `0 2 * * *` 
    *   *Это 02:00 ночи. Важно запускать ПОСЛЕ ежедневного анализа (обычно в 00:00 или 01:00), чтобы были свежие воспоминания.*
*   **Timezone:** `Europe/Moscow` (или ваш часовой пояс).

### Конфигурация выполнения (Target):

*   **Target type:** `HTTP`
*   **URL:** `https://<ВАШ_ДОМЕН_БОТА>/evolve_lore`
    *   *Например: `https://snitch-bot-r423.a.run.app/evolve_lore`*
*   **HTTP Method:** `POST`
*   **Body:**
    ```json
    {
      "chat_id": -1001234567890 
    }
    ```
    *   *Замените `-1001234567890` на ID вашего основного чата.*

*   **Auth Header:** `Add headers`
    *   **Header name:** `X-Secret-Token`
    *   **Header value:** `<ВАШ_SECRET_TOKEN_ИЗ_ENV>`
    *   *Или используйте OIDC token, если сервис закрыт IAM, но текущая реализация бота использует кастомный токен `X-Secret-Token`.*

## Шаг 3: Проверка

1. В консоли Cloud Scheduler нажмите кнопку **Run now** (Force run).
2. Проверьте логи бота (через Cloud Logging или `docker logs`), вы должны увидеть:
   *   `INFO: Manual lore evolution triggered for chat ...`
   *   `INFO: Lore evolution completed successfully ...`
3. Проверьте Firestore: в коллекции `chats/{chat_id}/lore/current` поле `updated_at` должно обновиться.

---

## Примечание по таймаутам
Процесс эволюции лора включает вызовы к Vertex AI и может занимать 10-30 секунд. Google Cloud Scheduler имеет таймаут по умолчанию (обычно 10-30 минут), так что операция успеет завершиться. Если бот деплоится на Cloud Run, убедитесь, что таймаут запроса в Cloud Run не слишком короткий (обычно по умолчанию 300с, чего достаточно).
