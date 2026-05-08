# 📱 Telegram Bot & PWA Integration Guide

## Обзор

Система клиники интегрирована с Telegram ботом для уведомлений и PWA функциональностью для офлайн работы.

## 🤖 Telegram Bot

### Настройка

1. **Создание бота:**
   ```bash
   # 1. Найдите @BotFather в Telegram
   # 2. Отправьте /newbot
   # 3. Следуйте инструкциям
   # 4. Сохраните токен
   ```

2. **Установка токена:**
   ```bash
   # В .env файле
   TELEGRAM_BOT_TOKEN=
   
   # Или в переменных окружения
   export TELEGRAM_BOT_TOKEN=""
   ```

### Функции бота

#### Команды пользователей:
- `/start` - Главное меню с кнопками
- `/queue` - Утренняя очередь (07:00-08:00)
- `/appointment` - Запись на прием (Web App)
- `/help` - Справка по командам

#### Возможности:
- 🏥 **Утренняя очередь** - запись к специалистам
- 📅 **Web App интеграция** - полноценный интерфейс
- 📋 **Уведомления** - напоминания и статусы
- 📄 **Документы** - получение результатов и рецептов

### API Endpoints

#### Webhook:
```bash
POST /api/v1/telegram/bot/webhook
# Получение обновлений от Telegram
```

#### Управление:
```bash
# Установка webhook (админ)
POST /api/v1/telegram/bot/set-webhook
{
  "webhook_url": "https://your-domain.com/api/v1/telegram/bot/webhook"
}

# Удаление webhook (админ)  
DELETE /api/v1/telegram/bot/webhook

# Информация о боте
GET /api/v1/telegram/bot/info
```

#### Уведомления:
```bash
# Отправка уведомления
POST /api/v1/telegram/bot/send-notification
{
  "user_id": 123456789,
  "message": "Ваша очередь подошла!"
}

# Напоминание о визите
POST /api/v1/telegram/bot/send-appointment-reminder
{
  "user_id": 123456789,
  "appointment": {
    "doctor": "Иванов И.И.",
    "date": "2024-01-20",
    "time": "14:30"
  }
}

# Уведомление о результатах
POST /api/v1/telegram/bot/send-lab-notification
{
  "user_id": 123456789,
  "results": {
    "test_name": "Общий анализ крови",
    "date": "2024-01-19"
  }
}
```

### Использование в коде

```python
from app.services.telegram import telegram_bot, notification_service

# Отправка уведомления
await telegram_bot.send_notification(
    user_id=123456789,
    message="Ваши результаты готовы!"
)

# Напоминание о визите
await notification_service.send_appointment_reminder(
    user_id=user_id,
    visit_id=visit_id,
    hours_before=24
)
```

## 📱 PWA (Progressive Web App)

### Функции PWA

#### Service Worker:
- ✅ **Кэширование** - статические файлы и API данные
- ✅ **Офлайн режим** - работа без интернета
- ✅ **Background Sync** - синхронизация при подключении
- ✅ **Push уведомления** - системные уведомления
- ✅ **HEIC конвертация** - фоновая обработка изображений

#### Установка приложения:
- 📱 **На домашний экран** - как нативное приложение
- 🖥️ **На компьютер** - через браузер
- ⚡ **Быстрый запуск** - без загрузки браузера

### Использование PWA компонентов

#### PWA Hook:
```jsx
import { usePWA } from './hooks/usePWA';

function MyComponent() {
  const {
    isInstallable,
    isInstalled,
    isOnline,
    installPWA,
    sendNotification
  } = usePWA();

  return (
    <div>
      {isInstallable && (
        <button onClick={installPWA}>
          Установить приложение
        </button>
      )}
      
      <div>
        Статус: {isOnline ? 'Онлайн' : 'Офлайн'}
      </div>
    </div>
  );
}
```

#### Компоненты:
```jsx
import { PWAInstallPrompt, ConnectionStatus } from './components/pwa';

// Промпт установки PWA
<PWAInstallPrompt onClose={() => setShowPrompt(false)} />

// Индикатор подключения
<ConnectionStatus showOfflineAlert={true} />
```

#### HEIC конвертация:
```jsx
import { convertHEICToJPEG, isHEICFile } from './utils/heicConverter';

async function handleFileUpload(files) {
  for (const file of files) {
    if (isHEICFile(file)) {
      const jpegFile = await convertHEICToJPEG(file, 0.8);
      // Используем конвертированный файл
    }
  }
}
```

### Service Worker возможности

#### Кэширование:
```javascript
// Автоматически кэшируются:
- Статические файлы (HTML, CSS, JS)
- API endpoints (/api/v1/auth/me, /api/v1/patients, etc.)
- Изображения и ресурсы

// НЕ кэшируются:
- Платежи (/api/v1/payments)
- AI запросы (/api/v1/ai)
- Telegram webhook (/api/v1/telegram)
```

#### Background Sync:
```javascript
// Автоматическая синхронизация при подключении
// Обработка офлайн очереди запросов
// Уведомления об успешной синхронизации
```

#### Push уведомления:
```javascript
// Через Service Worker
await registration.showNotification('Заголовок', {
  body: 'Текст уведомления',
  icon: '/favicon.ico',
  actions: [
    { action: 'explore', title: 'Открыть' },
    { action: 'close', title: 'Закрыть' }
  ]
});
```

## 🔧 Настройка и деплой

### Backend настройка:

1. **Переменные окружения:**
   ```bash
   TELEGRAM_BOT_TOKEN=
   FRONTEND_URL=https://your-domain.com
   ```

2. **Webhook настройка:**
   ```bash
   # Через API (нужны права админа)
   curl -X POST https://your-api.com/api/v1/telegram/bot/set-webhook \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"webhook_url": "https://your-api.com/api/v1/telegram/bot/webhook"}'
   ```

### Frontend настройка:

1. **Manifest.json:**
   ```json
   {
     "name": "Клиника",
     "short_name": "Clinic",
     "start_url": "/",
     "display": "standalone",
     "theme_color": "#1976d2",
     "background_color": "#ffffff"
   }
   ```

2. **Service Worker регистрация:**
   ```javascript
   // Автоматически в main.jsx
   if ('serviceWorker' in navigator) {
     navigator.serviceWorker.register('/sw.js');
   }
   ```

## 🧪 Тестирование

### Запуск тестов:
```bash
python test_telegram_pwa.py
```

### Проверка функций:
1. **Telegram бот** - отправьте /start боту
2. **PWA установка** - откройте сайт в Chrome/Edge
3. **Офлайн режим** - отключите интернет
4. **Push уведомления** - разрешите уведомления
5. **HEIC конвертация** - загрузите .heic файл

## 📊 Мониторинг

### Статистика бота:
```bash
GET /api/v1/telegram/bot/stats
# Возвращает количество пользователей, сообщений, активность
```

### PWA метрики:
- Service Worker статус в DevTools
- Cache Storage размер
- Background Sync задачи
- Push уведомления доставка

## 🔒 Безопасность

### Telegram:
- Webhook URL должен быть HTTPS
- Валидация токена бота
- Ограничение прав по ролям

### PWA:
- HTTPS обязателен для Service Worker
- Валидация кэшируемых данных
- Безопасная обработка офлайн запросов

## 📱 Пользовательский опыт

### Telegram:
1. Найти бота по username
2. Отправить /start
3. Выбрать функцию из меню
4. Получать уведомления автоматически

### PWA:
1. Открыть сайт в браузере
2. Увидеть промпт "Установить приложение"
3. Установить на домашний экран
4. Пользоваться как нативным приложением

## 🐛 Troubleshooting

### Telegram бот не отвечает:
- Проверьте TELEGRAM_BOT_TOKEN
- Убедитесь что webhook настроен
- Проверьте логи backend

### PWA не устанавливается:
- Нужен HTTPS (кроме localhost)
- Проверьте manifest.json
- Service Worker должен быть зарегистрирован

### Офлайн режим не работает:
- Service Worker должен быть активен
- Проверьте Cache Storage в DevTools
- Убедитесь что нужные ресурсы кэшируются

### HEIC не конвертируется:
- Проверьте поддержку браузера
- Service Worker должен быть готов
- Fallback на heic2any библиотеку
