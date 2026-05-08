# Документация по безопасности: Система подтверждения визитов

## Обзор безопасности

Система подтверждения визитов реализует многоуровневую защиту для предотвращения злоупотреблений, спама и несанкционированного доступа.

## Архитектура безопасности

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Rate Limiting │    │ Token Security  │    │ Audit Logging   │
│                 │    │                 │    │                 │
│ • IP-based      │    │ • UUID tokens   │    │ • All attempts  │
│ • User-based    │    │ • TTL expiry    │    │ • Success/fail  │
│ • Channel-based │    │ • Single-use    │    │ • IP tracking   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │ Security Service│
                    │                 │
                    │ • Validation    │
                    │ • Monitoring    │
                    │ • Response      │
                    └─────────────────┘
```

## Компоненты безопасности

### 1. Rate Limiting (Ограничение частоты запросов)

#### Лимиты по типам операций

| Операция | Лимит | Период | Блокировка |
|----------|-------|--------|------------|
| Подтверждение визита | 5 попыток | 1 минута | 15 минут |
| Получение информации | 10 запросов | 1 минуту | 5 минут |
| Неудачные попытки | 3 попытки | 5 минут | 30 минут |

#### Реализация

```python
class RateLimitConfig:
    CONFIRMATION_ATTEMPTS = {
        'limit': 5,
        'window': 60,  # секунд
        'block_duration': 900  # 15 минут
    }
    
    INFO_REQUESTS = {
        'limit': 10,
        'window': 60,
        'block_duration': 300  # 5 минут
    }
    
    FAILED_ATTEMPTS = {
        'limit': 3,
        'window': 300,  # 5 минут
        'block_duration': 1800  # 30 минут
    }
```

#### Алгоритм проверки

1. **Извлечение идентификатора**
   - IP адрес клиента
   - User-Agent (для обнаружения ботов)
   - Telegram User ID (для Telegram запросов)

2. **Проверка лимитов**
   - Подсчет запросов в текущем окне
   - Сравнение с установленным лимитом
   - Проверка статуса блокировки

3. **Применение ограничений**
   - Блокировка при превышении лимита
   - Возврат HTTP 429 с заголовком Retry-After
   - Логирование инцидента

### 2. Token Security (Безопасность токенов)

#### Генерация токенов

```python
import secrets
import uuid
from datetime import datetime, timedelta

def generate_confirmation_token():
    """Генерирует криптографически стойкий токен"""
    return str(uuid.uuid4())

def create_token_hash(token: str) -> str:
    """Создает хеш токена для хранения в БД"""
    return hashlib.sha256(token.encode()).hexdigest()
```

#### Свойства токенов

- **Формат**: UUID v4 (128-bit случайное значение)
- **Энтропия**: 122 бита (достаточно для криптографической стойкости)
- **Время жизни**: 48 часов (настраивается)
- **Одноразовость**: Токен инвалидируется после использования
- **Привязка**: К конкретному визиту и каналу подтверждения

#### Валидация токенов

```python
def validate_token(token: str, visit_id: int) -> TokenValidationResult:
    """
    Проверяет валидность токена подтверждения
    """
    # 1. Проверка формата UUID
    try:
        uuid.UUID(token)
    except ValueError:
        return TokenValidationResult(valid=False, reason="Invalid format")
    
    # 2. Поиск в базе данных
    visit = db.query(Visit).filter(
        Visit.id == visit_id,
        Visit.confirmation_token == token
    ).first()
    
    if not visit:
        return TokenValidationResult(valid=False, reason="Token not found")
    
    # 3. Проверка статуса визита
    if visit.status != "pending_confirmation":
        return TokenValidationResult(valid=False, reason="Already confirmed")
    
    # 4. Проверка срока действия
    if visit.confirmation_expires_at < datetime.utcnow():
        return TokenValidationResult(valid=False, reason="Token expired")
    
    return TokenValidationResult(valid=True)
```

### 3. Channel Security (Безопасность каналов)

#### Telegram Security

- **Webhook верификация**: Проверка подписи от Telegram
- **User ID валидация**: Сопоставление с данными пациента
- **Bot token защита**: Хранение в переменных окружения

```python
def verify_telegram_webhook(request_data: bytes, signature: str) -> bool:
    """Проверяет подпись Telegram webhook"""
    secret_key = hashlib.sha256(TELEGRAM_BOT_TOKEN.encode()).digest()
    expected_signature = hmac.new(
        secret_key, 
        request_data, 
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)
```

#### PWA Security

- **HTTPS обязательно**: Все запросы только через защищенное соединение
- **CORS настройки**: Ограничение доменов для API запросов
- **CSP заголовки**: Content Security Policy для предотвращения XSS

```python
# CORS настройки
ALLOWED_ORIGINS = [
    "https://clinic.example.com",
    "https://pwa.clinic.example.com"
]

# CSP заголовки
CSP_HEADER = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https:; "
    "connect-src 'self' https://api.clinic.example.com"
)
```

### 4. Audit Logging (Аудит и логирование)

#### Структура логов

```python
@dataclass
class SecurityLogEntry:
    timestamp: datetime
    event_type: str  # "confirmation_attempt", "rate_limit_hit", etc.
    ip_address: str
    user_agent: str
    visit_id: Optional[int]
    token_hash: Optional[str]  # Хеш токена, не сам токен
    channel: str  # "telegram", "pwa", "phone"
    success: bool
    error_reason: Optional[str]
    additional_data: Dict[str, Any]
```

#### Типы событий

1. **confirmation_attempt** - Попытка подтверждения визита
2. **token_validation** - Валидация токена
3. **rate_limit_hit** - Превышение лимита запросов
4. **suspicious_activity** - Подозрительная активность
5. **token_expired** - Использование истекшего токена
6. **channel_mismatch** - Попытка использования неправильного канала

#### Мониторинг и алерты

```python
class SecurityMonitor:
    def __init__(self):
        self.alert_thresholds = {
            'failed_attempts_per_hour': 50,
            'rate_limit_hits_per_hour': 100,
            'suspicious_ips_per_day': 10
        }
    
    def check_security_metrics(self):
        """Проверяет метрики безопасности и отправляет алерты"""
        current_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        
        # Проверка неудачных попыток
        failed_count = self.count_failed_attempts(current_hour)
        if failed_count > self.alert_thresholds['failed_attempts_per_hour']:
            self.send_security_alert(
                f"High number of failed confirmation attempts: {failed_count}"
            )
        
        # Проверка превышений лимитов
        rate_limit_count = self.count_rate_limit_hits(current_hour)
        if rate_limit_count > self.alert_thresholds['rate_limit_hits_per_hour']:
            self.send_security_alert(
                f"High number of rate limit hits: {rate_limit_count}"
            )
```

## Обнаружение угроз

### 1. Автоматизированные атаки

#### Признаки ботов

- **Высокая частота запросов**: Более 10 запросов в минуту
- **Однообразный User-Agent**: Стандартные библиотеки HTTP
- **Отсутствие JavaScript**: Для PWA запросов
- **Подозрительные IP**: Известные прокси и VPN

#### Защитные меры

```python
def detect_bot_behavior(request_info: RequestInfo) -> bool:
    """Определяет признаки автоматизированного поведения"""
    
    # Проверка User-Agent
    suspicious_agents = [
        'python-requests', 'curl', 'wget', 'bot', 'crawler'
    ]
    if any(agent in request_info.user_agent.lower() for agent in suspicious_agents):
        return True
    
    # Проверка частоты запросов
    recent_requests = get_recent_requests(request_info.ip, minutes=5)
    if len(recent_requests) > 20:
        return True
    
    # Проверка отсутствия JavaScript (для PWA)
    if request_info.channel == 'pwa' and not request_info.has_javascript:
        return True
    
    return False
```

### 2. Социальная инженерия

#### Защита от фишинга

- **Доменная валидация**: Проверка источника запросов
- **Брендинг**: Четкая идентификация клиники в сообщениях
- **Обучение пользователей**: Инструкции по безопасности

#### Пример защищенного сообщения

```
🏥 Клиника "Здоровье" (ОФИЦИАЛЬНО)

⚠️ ВНИМАНИЕ: Мы никогда не просим:
• Данные банковских карт
• Пароли от других сервисов
• Личную информацию в ответных сообщениях

✅ Это официальное уведомление о визите
🔒 Ссылка ведет на clinic.example.com
```

### 3. Атаки на доступность (DoS)

#### Защитные механизмы

- **Rate Limiting**: Ограничение запросов с одного IP
- **Circuit Breaker**: Временное отключение при перегрузке
- **Graceful Degradation**: Упрощенный режим при высокой нагрузке

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func, *args, **kwargs):
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.timeout:
                self.state = 'HALF_OPEN'
            else:
                raise ServiceUnavailableError("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise e
```

## Конфигурация безопасности

### Переменные окружения

```bash
# Токены и ключи
TELEGRAM_BOT_TOKEN=
JWT_SECRET_KEY=
ENCRYPTION_KEY=

# Настройки безопасности
RATE_LIMIT_ENABLED=true
SECURITY_LOGGING_ENABLED=true
AUDIT_LOG_RETENTION_DAYS=90

# Лимиты
CONFIRMATION_RATE_LIMIT=5
INFO_REQUEST_RATE_LIMIT=10
FAILED_ATTEMPT_LIMIT=3

# Время блокировки (секунды)
CONFIRMATION_BLOCK_DURATION=900
INFO_REQUEST_BLOCK_DURATION=300
FAILED_ATTEMPT_BLOCK_DURATION=1800

# Время жизни токенов (часы)
CONFIRMATION_TOKEN_TTL=48
```

### Настройки базы данных

```sql
-- Индексы для производительности безопасности
CREATE INDEX idx_security_logs_timestamp ON security_logs(timestamp);
CREATE INDEX idx_security_logs_ip ON security_logs(ip_address);
CREATE INDEX idx_security_logs_event_type ON security_logs(event_type);

-- Индексы для rate limiting
CREATE INDEX idx_rate_limits_ip_window ON rate_limits(ip_address, window_start);
CREATE INDEX idx_rate_limits_expires ON rate_limits(expires_at);
```

## Мониторинг и алертинг

### Метрики безопасности

#### Дашборд безопасности

```
┌─────────────────────────────────────────────────────────┐
│ 🛡️ Панель безопасности подтверждения визитов            │
│                                                         │
│ 📊 За последний час:                                    │
│ ├─ Всего попыток подтверждения: 127                    │
│ ├─ Успешных: 119 (94%)                                 │
│ ├─ Заблокированных: 8 (6%)                             │
│ └─ Подозрительных: 3                                   │
│                                                         │
│ 🚫 Rate Limiting:                                       │
│ ├─ Заблокированных IP: 12                              │
│ ├─ Активных блокировок: 4                              │
│ └─ Средняя длительность: 8м 23с                        │
│                                                         │
│ ⚠️ Угрозы:                                              │
│ ├─ Подозрительные User-Agent: 5                        │
│ ├─ Высокочастотные IP: 2                               │
│ └─ Попытки брутфорса: 1                                │
│                                                         │
│ 🔍 Топ заблокированных IP:                              │
│ ├─ 192.168.1.100 (15 попыток)                         │
│ ├─ 10.0.0.50 (12 попыток)                             │
│ └─ 172.16.0.25 (8 попыток)                            │
└─────────────────────────────────────────────────────────┘
```

### Автоматические алерты

#### Критические события

1. **Массовые атаки**
   - Более 100 заблокированных запросов в час
   - Уведомление: Telegram админам + Email

2. **Подозрительная активность**
   - Попытки использования чужих токенов
   - Уведомление: Slack канал безопасности

3. **Системные проблемы**
   - Ошибки в системе безопасности
   - Уведомление: PagerDuty для дежурного

#### Конфигурация алертов

```python
SECURITY_ALERTS = {
    'mass_attack': {
        'threshold': 100,
        'window': 3600,  # 1 час
        'channels': ['telegram', 'email'],
        'severity': 'critical'
    },
    'suspicious_activity': {
        'threshold': 10,
        'window': 1800,  # 30 минут
        'channels': ['slack'],
        'severity': 'warning'
    },
    'system_errors': {
        'threshold': 5,
        'window': 300,  # 5 минут
        'channels': ['pagerduty'],
        'severity': 'critical'
    }
}
```

## Процедуры реагирования на инциденты

### 1. Обнаружение атаки

#### Автоматические действия
1. **Немедленная блокировка** подозрительных IP
2. **Увеличение лимитов** rate limiting
3. **Активация режима** повышенной безопасности
4. **Уведомление** команды безопасности

#### Ручные действия
1. **Анализ логов** для определения масштаба
2. **Блокировка диапазонов** IP при необходимости
3. **Временное отключение** каналов подтверждения
4. **Координация** с провайдерами услуг

### 2. Расследование инцидента

#### Сбор данных
```sql
-- Анализ подозрительной активности
SELECT 
    ip_address,
    COUNT(*) as attempt_count,
    MIN(timestamp) as first_attempt,
    MAX(timestamp) as last_attempt,
    COUNT(DISTINCT visit_id) as unique_visits
FROM security_logs 
WHERE event_type = 'confirmation_attempt'
    AND success = false
    AND timestamp > NOW() - INTERVAL '1 hour'
GROUP BY ip_address
HAVING COUNT(*) > 10
ORDER BY attempt_count DESC;
```

#### Документирование
- **Временная линия** событий
- **Затронутые системы** и пользователи
- **Примененные меры** защиты
- **Уроки** для будущего

### 3. Восстановление

#### Пошаговый план
1. **Устранение угрозы** (блокировка источника)
2. **Проверка целостности** данных
3. **Восстановление сервисов** в нормальный режим
4. **Уведомление пользователей** о решении проблемы
5. **Анализ эффективности** защитных мер

## Соответствие стандартам

### GDPR (Общий регламент по защите данных)

#### Принципы обработки данных
- **Законность**: Согласие пациента на обработку
- **Минимизация**: Только необходимые данные
- **Точность**: Актуальная информация
- **Ограничение хранения**: Удаление после срока

#### Права субъектов данных
- **Право на доступ**: Предоставление копии данных
- **Право на исправление**: Корректировка неточностей
- **Право на удаление**: "Право быть забытым"
- **Право на портируемость**: Передача данных

### HIPAA (Закон о переносимости и подотчетности медицинского страхования)

#### Технические гарантии
- **Контроль доступа**: Уникальные идентификаторы пользователей
- **Аудит**: Логирование всех действий с данными
- **Целостность**: Защита от несанкционированных изменений
- **Передача**: Шифрование при передаче данных

### Локальные требования (Узбекистан)

#### Закон "О персональных данных"
- **Согласие**: Явное согласие на обработку
- **Уведомление**: Информирование о целях обработки
- **Локализация**: Хранение данных граждан РУз в стране
- **Защита**: Технические и организационные меры

## Рекомендации по безопасности

### Для разработчиков

1. **Принцип минимальных привилегий**
   - Доступ только к необходимым данным
   - Временные токены вместо постоянных ключей

2. **Защита в глубину**
   - Множественные уровни защиты
   - Независимые системы контроля

3. **Безопасное кодирование**
   - Валидация всех входных данных
   - Использование параметризованных запросов
   - Обработка ошибок без раскрытия деталей

### Для администраторов

1. **Регулярное обновление**
   - Своевременные патчи безопасности
   - Обновление зависимостей

2. **Мониторинг**
   - Постоянный контроль метрик
   - Настройка алертов

3. **Резервное копирование**
   - Регулярные бэкапы данных
   - Тестирование восстановления

### Для пользователей

1. **Образование**
   - Обучение распознаванию фишинга
   - Инструкции по безопасному использованию

2. **Каналы связи**
   - Официальные способы связи с клиникой
   - Процедуры сообщения о подозрительной активности

## Заключение

Система безопасности подтверждения визитов обеспечивает:

- ✅ **Защиту от автоматизированных атак** через rate limiting
- ✅ **Безопасность токенов** с криптографической стойкостью
- ✅ **Полный аудит** всех операций
- ✅ **Соответствие** международным стандартам
- ✅ **Мониторинг** и быстрое реагирование на угрозы

Регулярный пересмотр и обновление мер безопасности обеспечивает актуальную защиту от развивающихся угроз.
