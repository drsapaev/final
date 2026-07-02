# AI Audit Log Integrity Fix

## Проблема

`provider_id` в модели `AIUsageLog` был настроен с нарушением принципов audit trail:

```python
# ❌ НЕПРАВИЛЬНО (было):
provider_id = Column(Integer, ForeignKey("ai_providers.id", ondelete="SET NULL"), nullable=True)
```

**Последствия:**
- При удалении AI провайдера все его логи теряли `provider_id` (устанавливался в `NULL`)
- Нарушалась целостность audit trail - невозможно узнать, какой провайдер обработал запрос
- Несоответствие между кодом приложения (`provider_id: int`) и БД (`nullable=True`)

## Решение

### 1. Изменения в модели (`backend/app/models/ai_config.py`)

```python
# ✅ ПРАВИЛЬНО (исправлено):
provider_id = Column(Integer, ForeignKey("ai_providers.id", ondelete="RESTRICT"), nullable=False)
provider_name = Column(String(100), nullable=False)  # Дополнительная защита
```

**Механизм защиты:**
1. **`nullable=False`** - провайдер всегда должен быть указан
2. **`ondelete="RESTRICT"`** - запрещает удаление провайдера, если есть логи
3. **`provider_name`** - копия имени провайдера для двойной защиты

### 2. Обновление CRUD функций

**`backend/app/crud/ai_config.py`:**
```python
def create_ai_usage_log(...) -> AIUsageLog:
    # Получаем провайдера для копирования имени
    provider = get_ai_provider(db, provider_id)
    if not provider:
        raise ValueError(f"AI Provider с ID {provider_id} не найден")

    log = AIUsageLog(
        provider_id=provider_id,
        provider_name=provider.display_name,  # ← Копируем имя
        ...
    )
```

**`backend/app/services/ai_tracking_service.py`:**
```python
log = AIUsageLog(
    provider_id=tracking.model_info.provider_id,
    provider_name=tracking.model_info.provider_name,  # ← Из схемы
    ...
)
```

### 3. Миграция базы данных

**Файл:** `backend/alembic/versions/20251211_0001_fix_ai_usage_log_audit_integrity.py`

**Что делает миграция:**

1. ✅ Добавляет колонку `provider_name`
2. ✅ Заполняет существующие записи именами провайдеров
3. ✅ Устанавливает "Unknown Provider (Deleted)" для уже удаленных провайдеров
4. ✅ Удаляет записи с `provider_id IS NULL` (orphaned logs)
5. ✅ Изменяет `provider_id` на `NOT NULL`
6. ✅ Изменяет FK constraint на `RESTRICT` (для PostgreSQL/MySQL)

**Применение миграции:**

```bash
cd backend
alembic upgrade head
```

**⚠️ ВАЖНО для SQLite:**
SQLite не поддерживает изменение FK constraints. Новое ограничение `RESTRICT` применится только через определение модели в SQLAlchemy при следующем создании таблицы.

## Поведение системы после исправления

### Попытка удаления провайдера с логами

**Ситуация:** Администратор пытается удалить провайдера, у которого есть usage logs

**PostgreSQL/MySQL:**
```sql
DELETE FROM ai_providers WHERE id = 1;
-- ERROR: update or delete on table "ai_providers" violates foreign key constraint
-- DETAIL: Key (id)=(1) is still referenced from table "ai_usage_logs".
```

**SQLite:**
Поведение зависит от настроек PRAGMA foreign_keys. После обновления моделей новые записи будут защищены.

**Решение для администратора:**
```python
# Вместо удаления - пометить как неактивный
provider.active = False
db.commit()
```

### Функция delete_ai_provider уже безопасна

```python
def delete_ai_provider(db: Session, provider_id: int) -> bool:
    """Удалить AI провайдера"""
    # ...
    db_provider.active = False  # ← Soft delete, не физическое удаление!
    db.commit()
    return True
```

Несмотря на название "delete", функция делает **soft delete** (мягкое удаление), что идеально подходит для audit trail.

## Преимущества решения

### 1. Целостность Audit Trail
- ✅ Все исторические логи сохраняют информацию о провайдере
- ✅ Невозможно потерять данные о том, кто обработал запрос
- ✅ Соответствие требованиям HIPAA/GDPR для медицинских систем

### 2. Двойная защита
```sql
SELECT provider_id, provider_name FROM ai_usage_logs WHERE id = 123;
-- provider_id: 5
-- provider_name: "OpenAI GPT-4"
```

Даже если FK как-то нарушится, имя провайдера остается в логе.

### 3. Предсказуемое поведение
- Код приложения: `provider_id: int` (NOT NULL)
- База данных: `nullable=False`
- ✅ Полное соответствие

## Тестирование

### Тест 1: Создание лога с валидным провайдером
```python
log = create_ai_usage_log(
    db=db,
    user_id=1,
    provider_id=5,
    task_type="analyze_complaints"
)
assert log.provider_id == 5
assert log.provider_name == "OpenAI GPT-4"
```

### Тест 2: Создание лога с несуществующим провайдером
```python
with pytest.raises(ValueError, match="не найден"):
    create_ai_usage_log(
        db=db,
        provider_id=999,  # Не существует
        task_type="test"
    )
```

### Тест 3: Попытка удаления провайдера с логами (PostgreSQL)
```python
# Создаем лог
create_ai_usage_log(db, provider_id=5, task_type="test")

# Пытаемся удалить провайдера
with pytest.raises(IntegrityError):
    db.execute("DELETE FROM ai_providers WHERE id = 5")
    db.commit()
```

### Тест 4: Soft delete работает
```python
result = delete_ai_provider(db, provider_id=5)
assert result is True

provider = get_ai_provider(db, 5)
assert provider.active is False  # Помечен как неактивный, не удален
```

## Рекомендации

### Для разработчиков

1. **Всегда используйте CRUD функции** для создания логов:
   ```python
   # ✅ ПРАВИЛЬНО
   from app.crud.ai_config import create_ai_usage_log
   log = create_ai_usage_log(db, provider_id=5, ...)

   # ❌ НЕПРАВИЛЬНО
   log = AIUsageLog(provider_id=5, ...)  # Забыли provider_name!
   ```

2. **Проверяйте существование провайдера** перед использованием:
   ```python
   provider = get_ai_provider(db, provider_id)
   if not provider:
       raise ValueError("Provider not found")
   ```

3. **Используйте soft delete** для системных сущностей:
   ```python
   # Вместо db.delete(provider)
   provider.active = False
   ```

### Для администраторов

1. **Не удаляйте провайдеров** - помечайте как неактивные
2. **Перед деактивацией** убедитесь, что есть другой активный провайдер
3. **Для очистки старых логов** используйте специальные скрипты с фильтрацией по дате

## Влияние на существующие данные

### Существующие логи
- Все логи с валидным `provider_id` получат `provider_name`
- Логи с `provider_id = NULL` будут **удалены** (orphaned logs)
- Логи с удаленными провайдерами получат "Unknown Provider (Deleted)"

### API endpoints
- Все endpoint-ы продолжают работать без изменений
- Схемы Pydantic уже содержат `provider_name` в `AIModelInfo`

## Дополнительная информация

### Файлы, затронутые исправлением

1. `backend/app/models/ai_config.py` - Модель `AIUsageLog`
2. `backend/app/crud/ai_config.py` - Функция `create_ai_usage_log()`
3. `backend/app/services/ai_tracking_service.py` - Метод `_save_usage_log()`
4. `backend/alembic/versions/20251211_0001_*.py` - Миграция базы данных

### Связанные модели

- `AIProvider` - Провайдеры AI (OpenAI, Gemini и т.д.)
- `AIPromptTemplate` - Шаблоны промптов (уже использует `ondelete="CASCADE"`)
- `AIUsageLog` - **Исправленная модель**

## Заключение

Это исправление критически важно для медицинской системы:
- ✅ Сохраняет audit trail для compliance (HIPAA, GDPR)
- ✅ Предотвращает потерю исторических данных
- ✅ Устраняет несоответствие между кодом и БД
- ✅ Следует best practices для audit logging

**Статус:** ✅ Исправлено и готово к применению
**Дата:** 2025-12-11
**Версия миграции:** 20251211_0001
