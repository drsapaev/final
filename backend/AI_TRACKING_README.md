# 🤖 Трекинг AI Моделей в Авто Режиме

## 📋 Обзор

Система трекинга AI моделей позволяет определить, какая именно AI модель выполнила каждый запрос в авто режиме. Это обеспечивает полную прозрачность и контроль над использованием AI ресурсов.

## 🎯 Возможности

### ✅ Что можно отслеживать:

1. **🤖 Информация о модели:**
   - Название провайдера (OpenAI, Gemini, DeepSeek)
   - Название модели (gpt-4, gemini-pro, deepseek-chat)
   - Версия модели
   - Настройки (температура, max_tokens)
   - Возможности модели

2. **📊 Метрики производительности:**
   - Время ответа (миллисекунды)
   - Количество использованных токенов
   - Успешность выполнения
   - Сообщения об ошибках

3. **🔄 Кэширование:**
   - Был ли ответ из кэша
   - Хеш запроса для кэширования
   - TTL кэша

4. **👤 Контекст:**
   - ID пользователя
   - Тип задачи (анализ жалоб, генерация рецепта)
   - Специализация (cardio, derma, dental)

## 🚀 Использование

### 1. Базовое использование

```python
from app.services.ai_service_enhanced import get_enhanced_ai_service

# Получаем AI сервис с трекингом
async with get_enhanced_ai_service(db) as ai_service:
    
    # Анализ жалоб с трекингом
    result = await ai_service.analyze_complaints_with_tracking(
        complaints_text="Пациент жалуется на боль в груди",
        specialty="cardio",
        user_id=1
    )
    
    # Получаем информацию о модели
    tracking = result.tracking
    model_info = tracking.model_info
    
    print(f"Модель: {model_info.provider_name} - {model_info.model_name}")
    print(f"Время ответа: {tracking.response_time_ms}мс")
    print(f"Токены: {tracking.tokens_used}")
    print(f"Успешность: {tracking.success}")
```

### 2. Получение статистики

```python
# Статистика по моделям
model_stats = ai_service.get_model_stats(days_back=30)

for stat in model_stats:
    print(f"{stat.provider_name} - {stat.model_name}")
    print(f"  Запросов: {stat.total_requests}")
    print(f"  Успешных: {stat.successful_requests}")
    print(f"  Среднее время: {stat.average_response_time_ms}мс")
    print(f"  Токенов: {stat.total_tokens_used}")

# Статистика по провайдерам
provider_stats = ai_service.get_provider_stats(days_back=30)

for stat in provider_stats:
    print(f"{stat.display_name}")
    print(f"  Всего запросов: {stat.total_requests}")
    print(f"  Успешность: {stat.success_rate}%")
    print(f"  Моделей: {len(stat.models)}")
```

## 🔗 API Endpoints

### Получение статистики моделей
```http
GET /api/v1/ai-tracking/models/stats?days_back=30&provider_id=1&specialty=cardio
```

### Получение статистики провайдеров
```http
GET /api/v1/ai-tracking/providers/stats?days_back=30
```

### Текущие AI модели
```http
GET /api/v1/ai-tracking/models/current
```

### Последние запросы
```http
GET /api/v1/ai-tracking/requests/recent?limit=50
```

### Производительность моделей
```http
GET /api/v1/ai-tracking/models/performance?days_back=7
```

### Тренды использования
```http
GET /api/v1/ai-tracking/models/usage-trends?days_back=30
```

## 📊 Структура данных

### AIRequestTracking
```json
{
  "request_id": "uuid",
  "task_type": "complaints_analysis",
  "specialty": "cardio",
  "user_id": 1,
  "model_info": {
    "provider_id": 1,
    "provider_name": "openai",
    "model_name": "gpt-4",
    "model_version": "4.0",
    "temperature": 0.2,
    "max_tokens": 1000,
    "capabilities": ["text", "vision"]
  },
  "response_time_ms": 1250,
  "tokens_used": 450,
  "success": true,
  "cached_response": false,
  "request_hash": "sha256_hash",
  "created_at": "2024-01-15T10:30:00Z",
  "completed_at": "2024-01-15T10:30:01Z"
}
```

### AIResponseWithTracking
```json
{
  "data": {
    "summary": "Анализ жалоб выполнен",
    "diagnoses": ["ИБС", "Стенокардия"],
    "recommendations": ["ЭКГ", "ЭхоКГ"]
  },
  "tracking": {
    "request_id": "uuid",
    "model_info": { ... },
    "response_time_ms": 1250,
    "tokens_used": 450,
    "success": true
  },
  "model_confidence": 0.85,
  "processing_notes": "Обработано с высокой уверенностью"
}
```

## 🔧 Настройка

### 1. Создание AI провайдеров

```python
from app.crud import ai_config as crud_ai

# Создаем провайдер OpenAI
provider = crud_ai.create_ai_provider(db, {
    "name": "openai",
    "display_name": "OpenAI GPT-4",
    "model": "gpt-4",
    "temperature": 0.2,
    "max_tokens": 1000,
    "active": True,
    "is_default": True,
    "capabilities": ["text", "vision"]
})
```

### 2. Настройка шаблонов промптов

```python
# Создаем шаблон для анализа жалоб
template = crud_ai.create_prompt_template(db, {
    "provider_id": provider.id,
    "task_type": "complaints_analysis",
    "specialty": "cardio",
    "language": "ru",
    "template": "Проанализируйте жалобы: {complaints}",
    "active": True
})
```

## 📈 Мониторинг и Аналитика

### 1. Дашборд производительности

Система предоставляет детальную аналитику:
- Время ответа по моделям
- Успешность выполнения
- Использование токенов
- Популярные модели
- Тренды использования

### 2. Алерты и уведомления

Можно настроить уведомления при:
- Высоком времени ответа
- Низкой успешности
- Превышении лимитов токенов
- Ошибках AI моделей

### 3. Оптимизация

На основе данных трекинга можно:
- Выбрать лучшую модель для задачи
- Оптимизировать настройки
- Настроить fallback цепочки
- Улучшить кэширование

## 🛠️ Примеры использования

### 1. Анализ жалоб с трекингом

```python
async def analyze_patient_complaints(complaints: str, specialty: str):
    async with get_enhanced_ai_service(db) as ai_service:
        result = await ai_service.analyze_complaints_with_tracking(
            complaints_text=complaints,
            specialty=specialty,
            user_id=current_user.id
        )
        
        # Логируем информацию о модели
        logger.info(f"AI анализ выполнен моделью {result.tracking.model_info.model_name}")
        
        return result.data
```

### 2. Генерация рецепта с трекингом

```python
async def generate_prescription(patient_data: dict, diagnosis: str):
    async with get_enhanced_ai_service(db) as ai_service:
        result = await ai_service.generate_prescription_with_tracking(
            patient_data=patient_data,
            diagnosis=diagnosis,
            specialty="cardio",
            user_id=current_user.id
        )
        
        # Проверяем качество ответа
        if result.tracking.response_time_ms > 5000:
            logger.warning(f"Медленный ответ от {result.tracking.model_info.model_name}")
        
        return result.data
```

### 3. Мониторинг производительности

```python
async def monitor_ai_performance():
    async with get_enhanced_ai_service(db) as ai_service:
        # Получаем статистику
        model_stats = ai_service.get_model_stats(days_back=7)
        
        # Находим проблемные модели
        slow_models = [s for s in model_stats if s.average_response_time_ms > 3000]
        unreliable_models = [s for s in model_stats if s.successful_requests / s.total_requests < 0.9]
        
        # Отправляем уведомления
        if slow_models:
            send_alert(f"Медленные модели: {[s.model_name for s in slow_models]}")
        
        if unreliable_models:
            send_alert(f"Ненадежные модели: {[s.model_name for s in unreliable_models]}")
```

## 🎯 Заключение

Система трекинга AI моделей обеспечивает:

✅ **Полную прозрачность** - знаете, какая модель выполнила каждый запрос
✅ **Детальную аналитику** - метрики производительности и использования
✅ **Оптимизацию ресурсов** - выбор лучших моделей для задач
✅ **Мониторинг качества** - отслеживание ошибок и производительности
✅ **Аудит использования** - полная история AI запросов

**Теперь вы можете точно знать, какая AI модель выполнила каждый запрос в авто режиме!** 🚀
