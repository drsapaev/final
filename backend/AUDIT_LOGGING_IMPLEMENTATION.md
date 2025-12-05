# Реализация Audit Logging (Шаг A)

## ✅ Выполнено

### 1. Обновлена модель UserAuditLog
- Добавлено поле `request_id` (String(64), index=True) - UUID запроса для трассировки
- Добавлено поле `diff_hash` (String(32)) - хеш различий для быстрого сравнения
- Обновлены индексы для оптимизации запросов

### 2. Создан модуль `app/core/audit.py`
- `log_critical_change()` - основная функция для логирования критичных изменений
- `log_audit_event()` - низкоуровневая функция создания audit log
- `extract_model_changes()` - извлечение изменений между экземплярами моделей
- `calculate_diff_hash()` - вычисление хеша различий
- `get_client_ip()`, `get_user_agent()` - получение контекста запроса
- `CRITICAL_TABLES` - список критичных таблиц для аудита

### 3. Создан middleware `app/middleware/audit_middleware.py`
- `AuditMiddleware` - устанавливает `request_id` в каждом запросе
- Добавляет `X-Request-ID` в заголовки ответа

### 4. Добавлено аудит-логирование в endpoints
- **patients.py**: CREATE, UPDATE, DELETE операции логируются
- Примеры использования добавлены в критичные endpoints

### 5. Созданы тесты `tests/test_audit_logs.py`
- Тест создания пациента
- Тест обновления пациента
- Тест удаления пациента
- Тест критичных таблиц
- Тест request_id
- Тест вычисления хеша различий

## 📋 Использование

### В endpoint (пример):

```python
from fastapi import Request
from app.core.audit import log_critical_change, extract_model_changes

@router.post("/patients/")
def create_patient(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    patient_in: PatientCreate,
):
    # Создаем пациента
    patient = patient_crud.create(db=db, obj_in=patient_in)
    
    # ✅ AUDIT LOG: Логируем создание
    _, new_data = extract_model_changes(None, patient)
    log_critical_change(
        db=db,
        user_id=current_user.id,
        action="CREATE",
        table_name="patients",
        row_id=patient.id,
        old_data=None,
        new_data=new_data,
        request=request,
        description=f"Создан пациент: {patient.last_name}",
    )
    db.commit()
    
    return patient
```

### Критичные таблицы (автоматически логируются):
- `patients`
- `visits`
- `payments`
- `emr`
- `files`
- `appointments`
- `prescriptions`
- `lab_results`

## 🔄 Следующие шаги

1. **Добавить аудит-логирование в остальные критичные endpoints:**
   - `visits.py` - CREATE, UPDATE, DELETE
   - `payments.py` - CREATE, UPDATE, DELETE
   - `emr.py` - CREATE, UPDATE, DELETE
   - `files.py` - CREATE, UPDATE, DELETE

2. **Применить миграцию:**
   ```powershell
   alembic upgrade head
   ```

3. **Запустить тесты:**
   ```powershell
   python -m pytest tests/test_audit_logs.py -k audit -v
   ```

4. **Проверить вручную:**
   ```powershell
   sqlite3 backend/clinic.db "SELECT * FROM user_audit_logs ORDER BY created_at DESC LIMIT 5;"
   ```

## ⚠️ Важные замечания

1. **Request dependency**: Все endpoints, которые логируют аудит, должны принимать `Request` как dependency
2. **Commit**: После `log_critical_change()` нужно вызвать `db.commit()` для сохранения audit log
3. **Performance**: Audit logging выполняется синхронно, что может замедлить запросы. В будущем можно вынести в background task
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
    "created_at": "2025-12-03T18:00:00Z"
}
```

