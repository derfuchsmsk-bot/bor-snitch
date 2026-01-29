# Технический план реализации реворка договоренностей

## 1. База данных (src/services/db.py)
- [ ] Обновить `save_agreement`: добавить поддержку `type`, `expires_at` (Timestamp), `status` (default: 'active'), `can_be_disputed_until` (Timestamp).
- [ ] Добавить `update_agreement_status(chat_id, agreement_id, status, evidence=None)`.
- [ ] Добавить `get_agreement(chat_id, agreement_id)`: получение одной записи.
- [ ] Добавить `delete_agreement(chat_id, agreement_id)`: для полного удаления или пометки как disputed.

## 2. ИИ-Логика (src/utils/prompts.py & src/services/ai.py)
- [ ] **Prompts**: 
    - Обновить описание секции `new_agreements` в `SYSTEM_PROMPT`. Добавить типы (`vow`, `pact`, `public`) и обязательное определение срока (ISO format).
    - Добавить в `SYSTEM_PROMPT` новую секцию вывода: `agreement_updates`.
- [ ] **AI Service**: 
    - В `analyze_daily_logs` передавать список активных договоренностей.

## 3. Обработка результатов (src/main.py)
- [ ] В цикле обработки `ai_result`:
    - При сохранении новых договоренностей выставлять `can_be_disputed_until = now + 15 min`.
    - Обновлять статусы старых.
    - Автоматически закрывать истекшие.

## 4. Сообщения и Интерфейс (src/utils/messages.py & src/bot/handlers.py)
- [ ] **Messages**: 
    - Добавить шаблоны для заголовков и уведомлений о возможности спора.
- [ ] **Handlers**: 
    - Переписать `/agreements`: добавить эмодзи и таймеры.
    - **Реализовать `/dispute [ID]`**:
        - Проверить наличие аргумента.
        - Найти договоренность в БД.
        - Проверить `can_be_disputed_until > now`.
        - Если ОК: изменить статус на `disputed` (или удалить), ответить пользователю "Базар отменен".
        - Если время вышло: ответить "Поздно, слово уже не воробей".

## 5. Тестирование
- [ ] Проверить создание через ИИ.
- [ ] Проверить работу таймера спора (успел/не успел).
- [ ] Проверить жизненный цикл (выполнение/нарушение).
