# Руководство по облачной печати

## Обзор

Система облачной печати позволяет печатать документы через облачные сервисы печати, такие как Microsoft Universal Print. Система поддерживает различные типы документов и провайдеров печати.

## Поддерживаемые провайдеры

### 1. Microsoft Universal Print
- **Описание**: Облачный сервис печати от Microsoft
- **Требования**: Azure AD, настроенные принтеры в Universal Print
- **Настройка**: Требуется Tenant ID, Client ID и Client Secret

### 2. Mock Provider
- **Описание**: Тестовый провайдер для разработки и демонстрации
- **Использование**: Автоматически доступен, не требует настройки

## Настройка

### Переменные окружения

```env
# Microsoft Universal Print
MICROSOFT_PRINT_TENANT_ID=your-tenant-id
MICROSOFT_PRINT_CLIENT_ID=your-client-id
MICROSOFT_PRINT_CLIENT_SECRET=your-client-secret

# Общие настройки
CLOUD_PRINTING_ENABLED=true
CLOUD_PRINTING_DEFAULT_PROVIDER=mock
```

### Настройка Microsoft Universal Print

1. **Создание приложения в Azure AD**:
   - Перейдите в Azure Portal → Azure Active Directory → App registrations
   - Создайте новое приложение
   - Скопируйте Application (client) ID и Directory (tenant) ID

2. **Настройка разрешений**:
   - Добавьте API permissions для Microsoft Graph
   - Добавьте разрешения: `PrintJob.Create`, `Printer.Read.All`
   - Предоставьте admin consent

3. **Создание секрета**:
   - В разделе Certificates & secrets создайте новый client secret
   - Скопируйте значение секрета

4. **Настройка принтеров**:
   - Перейдите в Microsoft 365 admin center → Settings → Org settings → Universal Print
   - Добавьте и настройте принтеры

## API Endpoints

### Принтеры

#### Получить все принтеры
```http
GET /api/v1/cloud-printing/printers
Authorization: Bearer <token>
```

**Ответ**:
```json
{
  "success": true,
  "printers": [
    {
      "id": "printer-id",
      "name": "Принтер 1",
      "description": "Описание принтера",
      "status": "online",
      "location": "Кабинет 101",
      "capabilities": {},
      "provider": "microsoft"
    }
  ],
  "total_count": 1,
  "providers": ["microsoft", "mock"]
}
```

#### Получить принтеры провайдера
```http
GET /api/v1/cloud-printing/printers/{provider_name}
Authorization: Bearer <token>
```

#### Получить информацию о принтере
```http
GET /api/v1/cloud-printing/printers/{provider_name}/{printer_id}
Authorization: Bearer <token>
```

### Печать

#### Печать документа
```http
POST /api/v1/cloud-printing/print
Authorization: Bearer <token>
Content-Type: application/json

{
  "provider_name": "microsoft",
  "printer_id": "printer-id",
  "title": "Название документа",
  "content": "<html>...</html>",
  "format": "html",
  "copies": 1,
  "color": false,
  "duplex": false
}
```

**Ответ**:
```json
{
  "success": true,
  "job_id": "job-12345",
  "message": "Документ отправлен на печать"
}
```

#### Печать медицинского документа
```http
POST /api/v1/cloud-printing/print/medical
Authorization: Bearer <token>
Content-Type: application/json

{
  "provider_name": "microsoft",
  "printer_id": "printer-id",
  "document_type": "prescription",
  "patient_data": {
    "patient_name": "Иванов Иван Иванович",
    "age": "35",
    "phone": "+998901234567"
  },
  "template_data": {
    "diagnosis": "ОРВИ",
    "prescription_text": "Парацетамол 500мг по 1 таб. 3 раза в день",
    "doctor_name": "Петров П.П."
  }
}
```

### Управление заданиями

#### Получить статус задания
```http
GET /api/v1/cloud-printing/jobs/{provider_name}/{job_id}/status
Authorization: Bearer <token>
```

**Ответ**:
```json
{
  "job_id": "job-12345",
  "status": "completed",
  "provider_name": "microsoft"
}
```

#### Отменить задание
```http
POST /api/v1/cloud-printing/jobs/{provider_name}/{job_id}/cancel
Authorization: Bearer <token>
```

### Быстрые действия

#### Быстрая печать рецепта
```http
POST /api/v1/cloud-printing/quick-print/prescription?provider_name=microsoft&printer_id=printer-id&patient_name=Иванов&diagnosis=ОРВИ&prescription_text=Лечение&doctor_name=Петров
Authorization: Bearer <token>
```

#### Быстрая печать талона
```http
POST /api/v1/cloud-printing/quick-print/ticket?provider_name=microsoft&printer_id=printer-id&patient_name=Иванов&queue_number=A001&doctor_name=Петров&cabinet=101
Authorization: Bearer <token>
```

### Тестирование

#### Тестовая печать
```http
POST /api/v1/cloud-printing/test/{provider_name}/{printer_id}
Authorization: Bearer <token>
```

### Статистика

#### Получить статистику
```http
GET /api/v1/cloud-printing/statistics
Authorization: Bearer <token>
```

**Ответ**:
```json
{
  "success": true,
  "statistics": {
    "total_printers": 5,
    "online_printers": 3,
    "offline_printers": 2,
    "providers_count": 2,
    "providers": ["microsoft", "mock"]
  }
}
```

## Типы документов

### 1. Рецепт (prescription)
- **Поля**: diagnosis, prescription_text, doctor_name
- **Формат**: HTML с медицинским оформлением
- **Использование**: Выписка лекарств и назначений

### 2. Чек (receipt)
- **Поля**: services (массив услуг с ценами)
- **Формат**: HTML таблица с итоговой суммой
- **Использование**: Оплата медицинских услуг

### 3. Талон (ticket)
- **Поля**: queue_number, doctor_name, cabinet
- **Формат**: HTML с крупным номером очереди
- **Использование**: Система очередей

### 4. Отчет (report)
- **Поля**: examination_results, conclusion, doctor_name
- **Формат**: HTML с медицинским заключением
- **Использование**: Результаты обследований

## Статусы

### Статусы принтеров
- `online` - Принтер в сети и готов к печати
- `offline` - Принтер не в сети
- `busy` - Принтер занят печатью
- `error` - Ошибка принтера
- `out_of_paper` - Закончилась бумага
- `out_of_ink` - Закончились чернила

### Статусы заданий печати
- `pending` - Задание ожидает обработки
- `printing` - Задание печатается
- `completed` - Задание завершено
- `failed` - Задание завершилось с ошибкой
- `cancelled` - Задание отменено

## Форматы документов

### HTML
- **Описание**: Веб-страница с CSS стилями
- **Использование**: Медицинские документы с форматированием
- **Пример**:
```html
<html>
<head>
  <meta charset="utf-8">
  <style>
    body { font-family: Arial, sans-serif; }
    .header { text-align: center; }
  </style>
</head>
<body>
  <div class="header">
    <h2>РЕЦЕПТ</h2>
  </div>
  <p>Пациент: Иванов И.И.</p>
</body>
</html>
```

### PDF
- **Описание**: Готовый PDF документ в base64
- **Использование**: Сложные документы с точным форматированием
- **Пример**: `data:application/pdf;base64,JVBERi0xLjQ...`

### TEXT
- **Описание**: Простой текст
- **Использование**: Простые документы без форматирования

### IMAGE
- **Описание**: Изображение в base64
- **Использование**: Печать изображений, сканов

## Безопасность

### Авторизация
- Все endpoints требуют JWT токен
- Роли: ADMIN, REGISTRAR, DOCTOR (в зависимости от операции)

### Валидация
- Проверка существования принтера перед печатью
- Валидация форматов документов
- Ограничение количества копий (1-10)

### Логирование
- Все операции печати логируются
- Отслеживание пользователей и времени операций
- Логирование ошибок и исключений

## Интеграция с клиникой

### Интеграция с очередями
```python
# Печать талона при создании записи в очередь
await printing_service.print_medical_document(
    provider_name="microsoft",
    printer_id="reception-printer",
    document_type="ticket",
    patient_data={"patient_name": patient.name},
    template_data={
        "queue_number": queue_entry.number,
        "doctor_name": doctor.name,
        "cabinet": doctor.cabinet
    }
)
```

### Интеграция с платежами
```python
# Печать чека после оплаты
await printing_service.print_medical_document(
    provider_name="microsoft",
    printer_id="cashier-printer",
    document_type="receipt",
    patient_data={"patient_name": patient.name},
    template_data={"services": payment.services}
)
```

### Интеграция с врачебными панелями
```python
# Печать рецепта из панели врача
await printing_service.print_medical_document(
    provider_name="microsoft",
    printer_id="doctor-printer",
    document_type="prescription",
    patient_data={"patient_name": patient.name},
    template_data={
        "diagnosis": visit.diagnosis,
        "prescription_text": prescription.text,
        "doctor_name": doctor.name
    }
)
```

## Устранение неполадок

### Проблемы с Microsoft Universal Print

**Ошибка: "Unauthorized"**
- Проверьте правильность Tenant ID, Client ID и Client Secret
- Убедитесь, что приложение имеет необходимые разрешения
- Проверьте, что admin consent предоставлен

**Ошибка: "Printer not found"**
- Убедитесь, что принтер зарегистрирован в Universal Print
- Проверьте статус принтера в admin center
- Обновите список принтеров в приложении

**Ошибка: "Job failed"**
- Проверьте статус принтера
- Убедитесь, что принтер имеет бумагу и чернила
- Проверьте формат документа

### Общие проблемы

**Принтеры не загружаются**
- Проверьте подключение к интернету
- Убедитесь, что провайдер настроен правильно
- Проверьте логи сервера

**Документы не печатаются**
- Проверьте статус принтера
- Убедитесь, что формат документа поддерживается
- Проверьте размер документа (ограничения провайдера)

## Примеры использования

### Frontend (React)
```javascript
// Печать рецепта
const printPrescription = async () => {
  const response = await fetch('/api/v1/cloud-printing/print/medical', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      provider_name: 'microsoft',
      printer_id: 'doctor-printer',
      document_type: 'prescription',
      patient_data: {
        patient_name: 'Иванов И.И.',
        age: '35'
      },
      template_data: {
        diagnosis: 'ОРВИ',
        prescription_text: 'Парацетамол 500мг',
        doctor_name: 'Петров П.П.'
      }
    })
  });
  
  const data = await response.json();
  if (data.success) {
    console.log('Рецепт отправлен на печать:', data.job_id);
  }
};
```

### Backend (Python)
```python
# Использование сервиса в endpoint
@router.post("/print-visit-documents")
async def print_visit_documents(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    visit = db.query(Visit).filter(Visit.id == visit_id).first()
    printing_service = get_cloud_printing_service(db)
    
    # Печать рецепта
    if visit.prescription:
        await printing_service.print_medical_document(
            provider_name="microsoft",
            printer_id="doctor-printer",
            document_type="prescription",
            patient_data={"patient_name": visit.patient.name},
            template_data={
                "diagnosis": visit.diagnosis,
                "prescription_text": visit.prescription,
                "doctor_name": visit.doctor.name
            }
        )
    
    # Печать чека
    if visit.payment_amount:
        await printing_service.print_medical_document(
            provider_name="microsoft",
            printer_id="cashier-printer",
            document_type="receipt",
            patient_data={"patient_name": visit.patient.name},
            template_data={"services": visit.services}
        )
```

## Расширение системы

### Добавление нового провайдера

1. **Создайте класс провайдера**:
```python
class CustomPrintProvider(BasePrintProvider):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # Инициализация провайдера
    
    async def get_printers(self) -> List[Printer]:
        # Реализация получения принтеров
        pass
    
    # Реализация остальных методов...
```

2. **Зарегистрируйте провайдера**:
```python
# В CloudPrintingService._initialize_providers()
if hasattr(settings, 'CUSTOM_PRINT_API_KEY'):
    custom_config = {
        "api_key": getattr(settings, 'CUSTOM_PRINT_API_KEY', '')
    }
    self.providers["custom"] = CustomPrintProvider(custom_config)
```

3. **Добавьте настройки**:
```python
# В config.py
CUSTOM_PRINT_API_KEY: Optional[str] = None
```

### Добавление нового типа документа

1. **Добавьте метод генерации**:
```python
def _generate_custom_document(self, patient_data: Dict[str, Any], template_data: Dict[str, Any]) -> str:
    return f"""
    <html>
    <body>
        <h1>Новый тип документа</h1>
        <p>Пациент: {patient_data.get('patient_name')}</p>
        <!-- Ваш HTML шаблон -->
    </body>
    </html>
    """
```

2. **Обновите метод print_medical_document**:
```python
elif document_type == "custom":
    content = self._generate_custom_document(patient_data, template_data or {})
```

3. **Обновите валидацию в API**:
```python
document_type: str = Field(..., pattern="^(prescription|receipt|ticket|report|custom)$")
```

## Мониторинг и метрики

### Логирование
- Все операции печати логируются с уровнем INFO
- Ошибки логируются с уровнем ERROR
- Включает информацию о пользователе, времени и результате

### Метрики
- Количество заданий печати по провайдерам
- Статистика успешных/неуспешных печатей
- Время выполнения заданий
- Использование принтеров

### Мониторинг
- Проверка доступности провайдеров
- Мониторинг статуса принтеров
- Отслеживание очереди заданий
- Алерты при сбоях

## Заключение

Система облачной печати предоставляет гибкое и масштабируемое решение для печати медицинских документов. Она поддерживает различные провайдеры, типы документов и интегрируется с основными функциями клиники.

Для получения дополнительной помощи обратитесь к документации API или свяжитесь с командой разработки.

