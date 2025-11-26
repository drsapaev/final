# Руководство по интеграции с медицинским оборудованием

## Обзор

Система интеграции с медицинским оборудованием позволяет подключать и управлять различными медицинскими устройствами, выполнять измерения и сохранять результаты. Система поддерживает различные протоколы связи и типы устройств.

## Поддерживаемые типы устройств

### 1. Тонометр (Blood Pressure Monitor)
- **Назначение**: Измерение артериального давления
- **Параметры**: Систолическое давление, диастолическое давление, пульс
- **Протоколы**: Serial, TCP, HTTP, Mock

### 2. Пульсоксиметр (Pulse Oximeter)
- **Назначение**: Измерение сатурации кислорода и пульса
- **Параметры**: SpO2, частота пульса
- **Протоколы**: Serial, TCP, HTTP, Mock

### 3. Глюкометр (Glucometer)
- **Назначение**: Измерение уровня глюкозы в крови
- **Параметры**: Уровень глюкозы (ммоль/л)
- **Протоколы**: Serial, TCP, HTTP, Mock

### 4. Термометр (Thermometer)
- **Назначение**: Измерение температуры тела
- **Параметры**: Температура (°C)
- **Протоколы**: Serial, TCP, HTTP, Mock

### 5. Медицинские весы (Scale)
- **Назначение**: Измерение массы тела
- **Параметры**: Вес (кг)
- **Протоколы**: Serial, TCP, HTTP, Mock

### 6. ЭКГ аппарат (ECG)
- **Назначение**: Электрокардиография
- **Параметры**: ЭКГ данные, ритм, интервалы
- **Протоколы**: Serial, TCP, HTTP

### 7. УЗИ аппарат (Ultrasound)
- **Назначение**: Ультразвуковое исследование
- **Параметры**: Изображения, измерения
- **Протоколы**: TCP, HTTP

### 8. Рентген аппарат (X-Ray)
- **Назначение**: Рентгенография
- **Параметры**: Изображения, параметры съемки
- **Протоколы**: TCP, HTTP

### 9. Биохимический анализатор (Analyzer)
- **Назначение**: Анализ биологических образцов
- **Параметры**: Результаты анализов
- **Протоколы**: Serial, TCP, HTTP

### 10. Спирометр (Spirometer)
- **Назначение**: Исследование функции внешнего дыхания
- **Параметры**: Объемы, потоки, графики
- **Протоколы**: Serial, TCP, HTTP

### 11. Ростомер (Height Meter)
- **Назначение**: Измерение роста
- **Параметры**: Рост (см)
- **Протоколы**: Serial, TCP, Mock

## Протоколы подключения

### 1. Serial (COM порт)
- **Описание**: Последовательное подключение через COM порт
- **Параметры**: port, baudrate, bytesize, parity, stopbits, timeout
- **Использование**: Старые устройства, простые протоколы

### 2. TCP/IP
- **Описание**: Сетевое подключение по TCP
- **Параметры**: host, port, timeout
- **Использование**: Современные сетевые устройства

### 3. UDP
- **Описание**: Сетевое подключение по UDP
- **Параметры**: host, port, timeout
- **Использование**: Быстрая передача данных

### 4. HTTP API
- **Описание**: REST API подключение
- **Параметры**: base_url, auth, timeout
- **Использование**: Современные устройства с веб-интерфейсом

### 5. Bluetooth
- **Описание**: Беспроводное подключение
- **Параметры**: device_address, service_uuid
- **Использование**: Портативные устройства

### 6. USB
- **Описание**: USB подключение
- **Параметры**: vendor_id, product_id
- **Использование**: Прямое подключение к компьютеру

### 7. Mock
- **Описание**: Тестовое подключение
- **Параметры**: Нет
- **Использование**: Демонстрация и тестирование

## API Endpoints

### Устройства

#### Получить все устройства
```http
GET /api/v1/medical-equipment/devices
Authorization: Bearer <token>
```

**Ответ**:
```json
{
  "success": true,
  "devices": [
    {
      "id": "bp-001",
      "name": "Тонометр OMRON",
      "device_type": "blood_pressure",
      "manufacturer": "OMRON",
      "model": "M3 Comfort",
      "serial_number": "BP001234",
      "firmware_version": "1.2.3",
      "connection_type": "mock",
      "status": "online",
      "location": "Кабинет 101",
      "last_seen": "2024-01-15T10:30:00Z",
      "last_measurement": "2024-01-15T09:45:00Z",
      "calibration_date": "2024-01-01T08:00:00Z",
      "maintenance_date": null
    }
  ],
  "total_count": 5
}
```

#### Получить устройство по ID
```http
GET /api/v1/medical-equipment/devices/{device_id}
Authorization: Bearer <token>
```

#### Получить устройства по типу
```http
GET /api/v1/medical-equipment/devices/type/{device_type}
Authorization: Bearer <token>
```

### Подключение и управление

#### Подключиться к устройству
```http
POST /api/v1/medical-equipment/devices/{device_id}/connect
Authorization: Bearer <token>
```

#### Отключиться от устройства
```http
POST /api/v1/medical-equipment/devices/{device_id}/disconnect
Authorization: Bearer <token>
```

#### Получить статус устройства
```http
GET /api/v1/medical-equipment/devices/{device_id}/status
Authorization: Bearer <token>
```

### Измерения

#### Выполнить измерение
```http
POST /api/v1/medical-equipment/measurements
Authorization: Bearer <token>
Content-Type: application/json

{
  "device_id": "bp-001",
  "patient_id": "patient-123"
}
```

**Ответ**:
```json
{
  "device_id": "bp-001",
  "device_type": "blood_pressure",
  "timestamp": "2024-01-15T10:30:00Z",
  "patient_id": "patient-123",
  "measurements": {
    "sys": 120,
    "dia": 80,
    "pulse": 72
  },
  "raw_data": "SYS:120,DIA:80,PULSE:72",
  "quality_score": 0.95,
  "notes": null
}
```

#### Получить измерения
```http
GET /api/v1/medical-equipment/measurements?device_id=bp-001&limit=50
Authorization: Bearer <token>
```

### Калибровка и диагностика

#### Калибровать устройство
```http
POST /api/v1/medical-equipment/devices/{device_id}/calibrate
Authorization: Bearer <token>
```

#### Запустить диагностику
```http
POST /api/v1/medical-equipment/devices/{device_id}/diagnostics
Authorization: Bearer <token>
```

**Ответ**:
```json
{
  "device_id": "bp-001",
  "timestamp": "2024-01-15T10:30:00Z",
  "success": true,
  "tests": {
    "connection": {
      "passed": true,
      "message": "Подключение успешно"
    },
    "status": {
      "passed": true,
      "status": "online",
      "message": "Статус: online"
    },
    "measurement": {
      "passed": true,
      "message": "Тестовое измерение выполнено",
      "data": {...}
    }
  },
  "error": null
}
```

### Конфигурация

#### Обновить конфигурацию устройства
```http
PUT /api/v1/medical-equipment/devices/{device_id}/config
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Новое название",
  "location": "Кабинет 102",
  "connection_params": {
    "port": "COM2",
    "baudrate": 19200
  },
  "maintenance_date": "2024-02-01T08:00:00Z"
}
```

### Статистика

#### Получить статистику устройства
```http
GET /api/v1/medical-equipment/devices/{device_id}/statistics
Authorization: Bearer <token>
```

#### Получить общую статистику
```http
GET /api/v1/medical-equipment/statistics/overview
Authorization: Bearer <token>
```

### Экспорт

#### Экспорт измерений
```http
GET /api/v1/medical-equipment/measurements/export?format=csv&device_id=bp-001
Authorization: Bearer <token>
```

### Быстрые действия

#### Быстрое измерение
```http
POST /api/v1/medical-equipment/quick-measurement/{device_type}?patient_id=patient-123
Authorization: Bearer <token>
```

### Информация о системе

#### Получить типы устройств
```http
GET /api/v1/medical-equipment/device-types
Authorization: Bearer <token>
```

#### Получить типы подключения
```http
GET /api/v1/medical-equipment/connection-types
Authorization: Bearer <token>
```

## Статусы устройств

### Статусы
- `online` - Устройство в сети и готово к работе
- `offline` - Устройство не в сети
- `error` - Ошибка устройства
- `busy` - Устройство занято выполнением операции
- `maintenance` - Устройство на обслуживании
- `calibrating` - Выполняется калибровка

## Качество измерений

Система автоматически оценивает качество измерений по шкале от 0.0 до 1.0:

- **1.0** - Отличное качество
- **0.8-0.9** - Хорошее качество
- **0.6-0.7** - Удовлетворительное качество
- **0.4-0.5** - Низкое качество
- **0.0-0.3** - Очень низкое качество

Факторы, влияющие на оценку:
- Успешность парсинга данных
- Соответствие значений нормальным диапазонам
- Стабильность сигнала
- Отсутствие артефактов

## Интеграция с клиникой

### Интеграция с электронными медицинскими картами
```python
# Сохранение измерения в карту пациента
measurement = await equipment_service.take_measurement(
    device_id="bp-001",
    patient_id=patient.id
)

if measurement:
    # Создаем запись в медицинской карте
    medical_record = MedicalRecord(
        patient_id=patient.id,
        doctor_id=current_user.id,
        measurement_type=measurement.device_type,
        measurement_data=measurement.measurements,
        measurement_date=measurement.timestamp,
        quality_score=measurement.quality_score
    )
    db.add(medical_record)
    db.commit()
```

### Интеграция с системой уведомлений
```python
# Отправка уведомления при критических значениях
if measurement.device_type == DeviceType.BLOOD_PRESSURE:
    sys_pressure = measurement.measurements.get('sys', 0)
    if sys_pressure > 180:  # Критическое давление
        await notification_service.send_alert(
            recipient=doctor.email,
            message=f"Критическое давление у пациента {patient.name}: {sys_pressure}/{measurement.measurements.get('dia', 0)}",
            priority="high"
        )
```

### Интеграция с системой очередей
```python
# Автоматическое измерение при вызове пациента
@router.post("/queue/call-patient")
async def call_patient(patient_id: str, queue_id: str):
    # Вызываем пациента
    await queue_service.call_patient(queue_id, patient_id)
    
    # Автоматически выполняем базовые измерения
    await equipment_service.take_measurement("th-001", patient_id)  # Температура
    await equipment_service.take_measurement("sc-001", patient_id)  # Вес
```

## Настройка устройств

### Конфигурация Serial устройства
```python
device_config = {
    "id": "bp-serial-001",
    "name": "Тонометр Serial",
    "device_type": DeviceType.BLOOD_PRESSURE,
    "manufacturer": "OMRON",
    "model": "M6 Comfort",
    "serial_number": "SN123456",
    "firmware_version": "2.1.0",
    "connection_type": ConnectionType.SERIAL,
    "connection_params": {
        "port": "COM1",
        "baudrate": 9600,
        "bytesize": 8,
        "parity": "N",
        "stopbits": 1,
        "timeout": 2
    },
    "location": "Кабинет врача"
}
```

### Конфигурация TCP устройства
```python
device_config = {
    "id": "analyzer-tcp-001",
    "name": "Анализатор TCP",
    "device_type": DeviceType.ANALYZER,
    "manufacturer": "Roche",
    "model": "Cobas 6000",
    "connection_type": ConnectionType.TCP,
    "connection_params": {
        "host": "192.168.1.100",
        "port": 8080,
        "timeout": 10
    },
    "location": "Лаборатория"
}
```

### Конфигурация HTTP устройства
```python
device_config = {
    "id": "ultrasound-http-001",
    "name": "УЗИ HTTP",
    "device_type": DeviceType.ULTRASOUND,
    "manufacturer": "GE Healthcare",
    "model": "LOGIQ E10",
    "connection_type": ConnectionType.HTTP,
    "connection_params": {
        "base_url": "http://192.168.1.200:8080/api",
        "auth": {
            "username": "admin",
            "password": "password"
        },
        "timeout": 30
    },
    "location": "Кабинет УЗИ"
}
```

## Протоколы данных

### Serial протокол (пример для тонометра)
```
Команды:
- STATUS\r\n - получить статус
- MEASURE\r\n - выполнить измерение
- CALIBRATE\r\n - калибровка

Ответы:
- OK\r\n - команда выполнена
- ERROR\r\n - ошибка
- SYS:120,DIA:80,PULSE:72\r\n - результат измерения
```

### TCP протокол (пример JSON)
```json
{
  "command": "measure",
  "patient_id": "patient-123",
  "timestamp": "2024-01-15T10:30:00Z"
}

{
  "status": "success",
  "measurements": {
    "glucose": 5.6,
    "unit": "mmol/L"
  },
  "quality": 0.95,
  "timestamp": "2024-01-15T10:30:15Z"
}
```

### HTTP API протокол
```http
POST /api/measure
Content-Type: application/json
Authorization: Basic YWRtaW46cGFzc3dvcmQ=

{
  "patient_id": "patient-123"
}

HTTP/1.1 200 OK
Content-Type: application/json

{
  "success": true,
  "measurements": {
    "temperature": 36.6,
    "unit": "celsius"
  },
  "quality_score": 0.98,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Безопасность

### Авторизация
- Все endpoints требуют JWT токен
- Роли: ADMIN (полный доступ), DOCTOR (измерения, калибровка), REGISTRAR (просмотр, измерения)

### Валидация данных
- Проверка корректности параметров подключения
- Валидация результатов измерений
- Проверка качества данных

### Логирование
- Все операции с устройствами логируются
- Отслеживание пользователей и времени операций
- Аудит изменений конфигурации

## Мониторинг и обслуживание

### Мониторинг устройств
- Автоматическая проверка статуса устройств
- Уведомления о сбоях и ошибках
- Статистика использования

### Калибровка
- Регулярная калибровка устройств
- Отслеживание дат калибровки
- Напоминания о необходимости калибровки

### Обслуживание
- Планирование технического обслуживания
- Отслеживание дат обслуживания
- Ведение истории ремонтов

## Устранение неполадок

### Проблемы подключения

**Serial устройства**:
- Проверьте правильность COM порта
- Убедитесь в корректности параметров (baudrate, parity)
- Проверьте кабель и драйверы

**TCP устройства**:
- Проверьте сетевое подключение
- Убедитесь в доступности IP адреса и порта
- Проверьте настройки firewall

**HTTP устройства**:
- Проверьте URL и доступность API
- Убедитесь в правильности аутентификации
- Проверьте SSL сертификаты

### Проблемы измерений

**Низкое качество данных**:
- Проверьте калибровку устройства
- Убедитесь в правильности подключения датчиков
- Проверьте условия измерения

**Ошибки парсинга**:
- Проверьте формат данных от устройства
- Убедитесь в соответствии протокола
- Обновите драйвер устройства

## Расширение системы

### Добавление нового типа устройства

1. **Добавьте тип в enum**:
```python
class DeviceType(str, Enum):
    # ... существующие типы
    NEW_DEVICE = "new_device"
```

2. **Создайте драйвер**:
```python
class NewDeviceDriver(BaseDeviceDriver):
    async def take_measurement(self, patient_id: Optional[str] = None) -> Optional[MeasurementData]:
        # Реализация измерения для нового устройства
        pass
```

3. **Добавьте парсинг данных**:
```python
def _parse_measurement_data(self, raw_data: str) -> Dict[str, Any]:
    if self.device_info.device_type == DeviceType.NEW_DEVICE:
        # Парсинг данных нового устройства
        return {"value": parsed_value}
```

### Добавление нового протокола

1. **Добавьте тип подключения**:
```python
class ConnectionType(str, Enum):
    # ... существующие типы
    NEW_PROTOCOL = "new_protocol"
```

2. **Создайте драйвер**:
```python
class NewProtocolDriver(BaseDeviceDriver):
    async def connect(self) -> bool:
        # Реализация подключения
        pass
```

3. **Зарегистрируйте драйвер**:
```python
def _create_driver(self, device_info: DeviceInfo) -> Optional[BaseDeviceDriver]:
    if device_info.connection_type == ConnectionType.NEW_PROTOCOL:
        return NewProtocolDriver(device_info)
```

## Заключение

Система интеграции с медицинским оборудованием предоставляет гибкое и масштабируемое решение для подключения различных медицинских устройств. Она поддерживает множество протоколов связи, обеспечивает качественную обработку данных и интегрируется с основными функциями клиники.

Для получения дополнительной помощи обратитесь к документации API или свяжитесь с командой разработки.

