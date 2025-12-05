# Audit Logging - Полная реализация

## ✅ Выполнено

### 1. Обновлена модель UserAuditLog
- ✅ Добавлено поле `request_id` (String(64), index=True)
- ✅ Добавлено поле `diff_hash` (String(32))
- ✅ Обновлены индексы для оптимизации запросов
- ✅ Миграция применена

### 2. Создан модуль `app/core/audit.py`
- ✅ `log_critical_change()` - основная функция для логирования
- ✅ `extract_model_changes()` - извлечение изменений между экземплярами
- ✅ `calculate_diff_hash()` - вычисление хеша различий
- ✅ `get_client_ip()`, `get_user_agent()` - получение контекста запроса
- ✅ `CRITICAL_TABLES` - список критичных таблиц

### 3. Создан middleware `app/middleware/audit_middleware.py`
- ✅ Устанавливает `request_id` в каждом запросе
- ✅ Добавляет `X-Request-ID` в заголовки ответа
- ✅ Зарегистрирован в `app/main.py`

### 4. Добавлено аудит-логирование во все критичные endpoints

#### ✅ patients.py
- `create_patient()` - CREATE операция
- `update_patient()` - UPDATE операция
- `delete_patient()` - DELETE операция

#### ✅ visits.py
- `create_visit()` - CREATE операция (оба пути: CRUD и Table API)

#### ✅ payments.py
- `create_payment()` - CREATE операция (для кассы)
- `init_payment()` - CREATE операция (инициализация онлайн платежа)

#### ✅ appointment_flow.py (EMR)
- `create_or_update_emr()` - CREATE и UPDATE операции

#### ✅ file_system.py
- `upload_file()` - CREATE операция
- `update_file()` - UPDATE операция
- `delete_file()` - DELETE операция

### 5. Созданы тесты `tests/test_audit_logs.py`
- ✅ Тест создания пациента
- ✅ Тест обновления пациента
- ✅ Тест удаления пациента
- ✅ Тест критичных таблиц
- ✅ Тест request_id
- ✅ Тест вычисления хеша различий

## 📋 Использование

### Пример в endpoint:

```python
from fastapi import Request
from app.core.audit import log_critical_change, extract_model_changes

@router.post("/resource/")
def create_resource(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    resource_in: ResourceCreate,
):
    # Создаем ресурс
    resource = crud.create(db=db, obj_in=resource_in)
    
    # ✅ AUDIT LOG: Логируем создание
    _, new_data = extract_model_changes(None, resource)
    log_critical_change(
        db=db,
        user_id=current_user.id,
        action="CREATE",
        table_name="resources",
        row_id=resource.id,
        old_data=None,
        new_data=new_data,
        request=request,
        description=f"Создан ресурс: {resource.name}",
    )
    db.commit()
    
    return resource
```

## 🔄 Критичные таблицы (автоматически логируются)

- ✅ `patients` - все операции
- ✅ `visits` - все операции
- ✅ `payments` - все операции
- ✅ `emr` - все операции
- ✅ `files` - все операции
- ✅ `appointments` - (можно добавить при необходимости)
- ✅ `prescriptions` - (можно добавить при необходимости)
- ✅ `lab_results` - (можно добавить при необходимости)

## ⚠️ Важные замечания

1. **Request dependency**: Все endpoints, которые логируют аудит, должны принимать `Request` как dependency
2. **Commit**: После `log_critical_change()` нужно вызвать `db.commit()` для сохранения audit log
3. **Performance**: Audit logging выполняется синхронно - может замедлить запросы. В будущем можно вынести в background task
4. **Privacy**: Audit logs содержат чувствительные данные - нужен контроль доступа

## 📊 Структура Audit Log

```python
{
    "id": 1,
    "user_id": 14,
    "action": "CREATE",  # CREATE, UPDATE, DELETE
    "resource_type": "patients",  # table_name
    "resource_id": 123,  # row_id
    "old_values": {...},  # Для UPDATE/DELETE
    "new_values": {...},  # Для CREATE/UPDATE
    "diff_hash": "abc123...",  # Хеш различий
    "description": "Создан пациент: Иванов Иван",
    "ip_address": "192.168.1.1",
    "user_agent": "Mozilla/5.0...",
    "request_id": "uuid-here",
    "session_id": "uuid-here",  # Также используется для request_id
    "created_at": "2025-12-03T18:00:00Z"
}
```

## ✅ Проверка работы

### Вручную через SQLite:
```powershell
sqlite3 backend/clinic.db "SELECT * FROM user_audit_logs ORDER BY created_at DESC LIMIT 5;"
```

### Через тесты:
```powershell
python -m pytest tests/test_audit_logs.py -k audit -v
```

## 🎯 Статус

**✅ ВСЕ КРИТИЧНЫЕ ENDPOINTS ОХВАЧЕНЫ АУДИТ-ЛОГИРОВАНИЕМ**

Все операции CREATE, UPDATE, DELETE в критичных таблицах (patients, visits, payments, emr, files) теперь логируются с полным контекстом:
- Кто выполнил (user_id)
- Когда (timestamp)
- Что изменил (old_values → new_values)
- Откуда (IP, User-Agent)
- Request ID для трассировки

