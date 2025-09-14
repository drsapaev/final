# 📋 МАСТЕР TODO СПИСОК - СИСТЕМА КЛИНИКИ

[[memory:7752001]] [[memory:7752047]] [[memory:8016693]]

## 🎯 **СТАТУС ПРОЕКТА**
- **Backend**: 90% готов ✅
- **Frontend**: 70% готов ⚠️
- **Критичные функции**: 0% готов ❌
- **Общая готовность**: 80%

---

## 🔴 **БЛОК 1: КРИТИЧНАЯ ФУНКЦИОНАЛЬНОСТЬ (Приоритет: ВЫСОКИЙ)**

### **1.1 ОНЛАЙН-ОЧЕРЕДЬ С QR (07:00)**
**AI АГЕНТ: Claude 4 Sonnet** | **Время: 3 дня** | **Статус: ❌ НЕ НАЧАТО**

#### **Backend задачи:**
- [ ] **Создать модели БД** - `backend/app/models/queue.py`
  - [ ] Модель `DailyQueue` (день, специалист, активность, opened_at)
  - [ ] Модель `QueueEntry` (номер, пациент, телефон, telegram_id)
  - [ ] Миграции Alembic
- [ ] **API endpoints** - `backend/app/api/v1/endpoints/queue.py`
  - [ ] `POST /api/queue/qrcode?day&specialist_id` - генерация токена
  - [ ] `POST /api/queue/join` - вступление в очередь с проверкой 07:00
  - [ ] `POST /api/queue/open` - открытие приема (закрывает QR)
  - [ ] `GET /api/queue/today?specialist_id` - текущая очередь
- [ ] **Бизнес-логика** - `backend/app/services/queue_service.py`
  - [ ] Проверка окна времени 07:00 - opened_at
  - [ ] Уникальность по телефону/Telegram
  - [ ] Стартовые номера по специальности
  - [ ] Лимиты на количество мест

#### **Frontend задачи:**
- [ ] **Страница QR** - `frontend/src/pages/QueueJoin.jsx`
  - [ ] Сканирование QR кода
  - [ ] Ввод телефона/Telegram ID
  - [ ] Отображение номера очереди
- [ ] **Компонент управления** - `frontend/src/components/queue/OnlineQueueManager.jsx`
  - [ ] Кнопка "Открыть прием"
  - [ ] Отображение онлайн-очереди
  - [ ] Генерация QR кода
- [ ] **Интеграция** - обновить `RegistrarPanel.jsx`
  - [ ] Добавить вкладку "Онлайн-очередь"
  - [ ] Кнопка "Открыть прием сейчас"

#### **Тестирование:**
- [ ] Проверить окно 07:00 - opened_at
- [ ] Проверить уникальность номера
- [ ] Проверить лимиты
- [ ] Проверить стартовые номера

---

### **1.2 ПЛАТЕЖНАЯ СИСТЕМА**
**AI АГЕНТ: Claude 4 Sonnet** | **Время: 2 дня** | **Статус: ❌ НЕ НАЧАТО**

#### **Backend задачи:**
- [ ] **Провайдеры платежей** - `backend/app/services/payment_providers/`
  - [ ] `click.py` - интеграция Click
  - [ ] `payme.py` - интеграция Payme
  - [ ] `kaspi.py` - интеграция Kaspi
- [ ] **API endpoints** - `backend/app/api/v1/endpoints/payments.py`
  - [ ] `POST /api/payments/init` - инициализация платежа
  - [ ] `POST /api/payments/{provider}/webhook` - обработка webhook
  - [ ] `GET /api/payments/{payment_id}` - статус платежа
  - [ ] `POST /api/payments/{payment_id}/attach-visit` - привязка к визиту
- [ ] **Модели БД** - обновить существующие
  - [ ] Добавить поля в таблицу `payments`
  - [ ] Связь с визитами

#### **Frontend задачи:**
- [ ] **Компонент платежей** - `frontend/src/components/payment/PaymentWidget.jsx`
  - [ ] Выбор провайдера
  - [ ] Форма инициализации
  - [ ] Отображение статуса
- [ ] **Страница успеха** - `frontend/src/pages/PaymentSuccess.jsx`
  - [ ] Подтверждение оплаты
  - [ ] Скачивание квитанции
- [ ] **Интеграция** - обновить `CashierPanel.jsx`
  - [ ] Кнопка "Оплатить онлайн"
  - [ ] Отображение статуса оплаты

---

### **1.3 WEBSOCKET ДЛЯ ТАБЛО**
**AI АГЕНТ: Claude 4 Sonnet** | **Время: 2 дня** | **Статус: ❌ НЕ НАЧАТО**

#### **Backend задачи:**
- [ ] **WebSocket сервер** - `backend/app/websocket/queue_ws.py`
  - [ ] Endpoint `/ws/queue/{department}`
  - [ ] События: `queue.created`, `queue.called`, `queue.updated`
  - [ ] Redis pub/sub для масштабирования
- [ ] **Интеграция** - обновить существующие endpoints
  - [ ] При создании записи - отправка события
  - [ ] При вызове пациента - отправка события

#### **Frontend задачи:**
- [ ] **WebSocket клиент** - обновить `DisplayBoardUnified.jsx`
  - [ ] Подключение к WebSocket
  - [ ] Обработка событий
  - [ ] Real-time обновления
- [ ] **Звуковые уведомления**
  - [ ] Звук при вызове пациента
  - [ ] Настройка громкости
- [ ] **Анимации**
  - [ ] Появление/исчезновение карточек
  - [ ] Плавные переходы

---

### **1.4 ПЕЧАТЬ ДОКУМЕНТОВ**
**AI АГЕНТ: Claude 4 Sonnet** | **Время: 2 дня** | **Статус: ❌ НЕ НАЧАТО**

#### **Backend задачи:**
- [ ] **Установить зависимости**
  - [ ] `python-escpos` для термопринтеров
  - [ ] `reportlab` для PDF генерации
  - [ ] `jinja2` для шаблонов
- [ ] **API endpoints** - `backend/app/api/v1/endpoints/print.py`
  - [ ] `POST /api/print/ticket` - печать талона ESC/POS
  - [ ] `POST /api/pdf/prescription` - рецепт A5 PDF
  - [ ] `POST /api/pdf/memo` - памятка PDF
- [ ] **Шаблоны** - `backend/app/templates/`
  - [ ] `ticket.html` - шаблон талона
  - [ ] `prescription.html` - шаблон рецепта
  - [ ] `memo.html` - шаблон памятки

#### **Frontend задачи:**
- [ ] **Компонент печати** - `frontend/src/components/print/PrintDialog.jsx`
  - [ ] Выбор принтера
  - [ ] Предпросмотр документа
  - [ ] Кнопка печати
- [ ] **Интеграция** - обновить панели врачей
  - [ ] Кнопка "Печать талона"
  - [ ] Кнопка "Печать рецепта"
  - [ ] Кнопка "Печать памятки"

---

## 🟡 **БЛОК 2: FRONTEND РЕФАКТОРИНГ (Приоритет: СРЕДНИЙ)**

### **2.1 РЕОРГАНИЗАЦИЯ СТРУКТУРЫ**
**AI АГЕНТ: Claude 4 Sonnet** | **Время: 1 день** | **Статус: ❌ НЕ НАЧАТО**

#### **Создание папок:**
- [ ] `mkdir frontend/src/components/layout`
- [ ] `mkdir frontend/src/components/dashboard`
- [ ] `mkdir frontend/src/components/queue`
- [ ] `mkdir frontend/src/components/payment`
- [ ] `mkdir frontend/src/components/print`
- [ ] `mkdir frontend/src/components/medical`
- [ ] `mkdir frontend/src/services`

#### **Перемещение файлов:**
- [ ] `mv components/Header.jsx → components/layout/`
- [ ] `mv components/Sidebar.jsx → components/layout/`
- [ ] `mv components/Dashboard.jsx → components/dashboard/`
- [ ] `mv components/QueueManager.jsx → components/queue/`
- [ ] `mv components/EMRInterface.jsx → components/medical/`
- [ ] `mv components/UserManagement.jsx → components/admin/`
- [ ] `mv components/FileManager.jsx → components/files/`
- [ ] `mv components/LoginForm.jsx → components/auth/`
- [ ] **И еще 35+ файлов...**

#### **Удаление дубликатов:**
- [ ] Удалить `components/FileManager.jsx` (оставить в `files/`)
- [ ] Удалить `components/LoginForm.jsx` (оставить `LoginFormStyled.jsx`)
- [ ] Удалить `components/TwoFactorManager.jsx` (оставить в `security/`)
- [ ] Удалить `components/EmailSMSManager.jsx` (оставить в `notifications/`)

#### **Обновление импортов:**
- [ ] Найти все `import Header from '../components/Header'`
- [ ] Заменить на `import { Header } from '@/components/layout'`
- [ ] Создать `index.js` в каждой папке для экспортов
- [ ] Проверить работоспособность

---

### **2.2 API ИНТЕГРАЦИЯ**
**AI АГЕНТ: Claude 4 Sonnet** | **Время: 2 дня** | **Статус: ❌ НЕ НАЧАТО**

#### **Централизация API:**
- [ ] **Дополнить** `frontend/src/api/endpoints.js`
  - [ ] Добавить все queue endpoints
  - [ ] Добавить все payment endpoints
  - [ ] Добавить все print endpoints
- [ ] **Создать** `frontend/src/api/interceptors.js`
  - [ ] Request interceptor для токенов
  - [ ] Response interceptor для ошибок
  - [ ] Refresh token логика
- [ ] **Создать** `frontend/src/api/services/`
  - [ ] `auth.js` - аутентификация
  - [ ] `queue.js` - очередь
  - [ ] `payment.js` - платежи
  - [ ] `medical.js` - медкарты
  - [ ] `print.js` - печать

#### **Обработка ошибок:**
- [ ] **Создать** `frontend/src/utils/errorHandler.js`
  - [ ] Единая функция обработки ошибок
  - [ ] Логирование ошибок
  - [ ] Показ пользователю
- [ ] **Применить** во всех компонентах
  - [ ] Заменить try/catch на errorHandler
  - [ ] Унифицировать сообщения об ошибках

---

### **2.3 UI/UX УНИФИКАЦИЯ**
**AI АГЕНТ: Claude 4 Sonnet** | **Время: 2 дня** | **Статус: ❌ НЕ НАЧАТО**

#### **Design System:**
- [ ] **Создать** `frontend/src/design-system/`
  - [ ] `components/Button.jsx` - единая кнопка
  - [ ] `components/Input.jsx` - единое поле ввода
  - [ ] `components/Card.jsx` - единая карточка
  - [ ] `components/Table.jsx` - единая таблица
  - [ ] `components/Modal.jsx` - единое модальное окно
- [ ] **Создать** `frontend/src/design-system/theme/`
  - [ ] `colors.js` - палитра цветов
  - [ ] `typography.js` - типографика
  - [ ] `spacing.js` - отступы
  - [ ] `breakpoints.js` - брейкпоинты

#### **Применение:**
- [ ] **Заменить все кнопки** на единый компонент
- [ ] **Унифицировать формы** - использовать единые поля
- [ ] **Применить цветовую схему** - заменить все цвета
- [ ] **Настроить отступы** - единые margin/padding

---

## 🟢 **БЛОК 3: СПЕЦИАЛИЗИРОВАННЫЕ ПАНЕЛИ (Приоритет: СРЕДНИЙ)**

### **3.1 ПАНЕЛЬ КАРДИОЛОГА**
**AI АГЕНТ: Claude 4 Opus** | **Время: 3 дня** | **Статус: ❌ НЕ НАЧАТО**

#### **Функциональность:**
- [ ] **Загрузка ЭКГ файлов** (PDF/SCP/XML)
- [ ] **Парсинг SCP формата** - извлечение параметров
- [ ] **Загрузка ЭхоКГ результатов** - PDF отчеты
- [ ] **AI интерпретация** - анализ ЭКГ/ЭхоКГ
- [ ] **Общая очередь** - консультация+ЭхоКГ

#### **Компоненты:**
- [ ] `components/cardiology/ECGViewer.jsx` - просмотр ЭКГ
- [ ] `components/cardiology/EchoForm.jsx` - форма ЭхоКГ
- [ ] `components/cardiology/ECGParser.jsx` - парсинг файлов
- [ ] **Доработать** `CardiologistPanelUnified.jsx`

---

### **3.2 ПАНЕЛЬ ДЕРМАТОЛОГА**
**AI АГЕНТ: Claude 4 Opus** | **Время: 3 дня** | **Статус: ❌ НЕ НАЧАТО**

#### **Функциональность:**
- [ ] **Загрузка фото до/после** - JPG/PNG/HEIC
- [ ] **HEIC конвертация** - в JPEG на клиенте
- [ ] **AI анализ кожи** - выявление проблем
- [ ] **Шаблоны процедур** - ботокс, мезотерапия
- [ ] **Стартовый номер №15** - настройка очереди

#### **Компоненты:**
- [ ] `components/dermatology/PhotoUploader.jsx` - загрузка фото
- [ ] `components/dermatology/PhotoComparison.jsx` - сравнение до/после
- [ ] `components/dermatology/ProcedureTemplates.jsx` - шаблоны
- [ ] `components/dermatology/SkinAnalysis.jsx` - AI анализ
- [ ] **Доработать** `DermatologistPanelUnified.jsx`

---

### **3.3 ПАНЕЛЬ СТОМАТОЛОГА**
**AI АГЕНТ: Claude 4 Opus** | **Время: 3 дня** | **Статус: ❌ НЕ НАЧАТО**

#### **Функциональность:**
- [ ] **Интерактивная зубная карта** - клик по зубу
- [ ] **Выбор процедур** - пломба, коронка, удаление
- [ ] **План лечения** - этапы с датами
- [ ] **Стартовый номер №3** - настройка очереди
- [ ] **Интеграция с лабораторией** - заявки на протезы

#### **Компоненты:**
- [ ] `components/dental/TeethChart.jsx` - зубная карта
- [ ] `components/dental/ToothModal.jsx` - модалка зуба
- [ ] `components/dental/TreatmentPlanner.jsx` - план лечения
- [ ] `components/dental/LabOrders.jsx` - заявки в лабораторию
- [ ] **Доработать** `DentistPanelUnified.jsx`

---

### **3.4 ПАНЕЛЬ ЛАБОРАТОРИИ**
**AI АГЕНТ: Claude 4 Sonnet** | **Время: 2 дня** | **Статус: ❌ НЕ НАЧАТО**

#### **Функциональность:**
- [ ] **Заявки от врачей** - список назначений
- [ ] **Ввод результатов** - формы для анализов
- [ ] **PDF генерация** - результаты в PDF
- [ ] **AI интерпретация** - анализ показателей

#### **Компоненты:**
- [ ] `components/lab/ResultsForm.jsx` - форма результатов
- [ ] `components/lab/LabQueue.jsx` - очередь заявок
- [ ] `components/lab/PDFGenerator.jsx` - генерация PDF
- [ ] **Доработать** `LabPanel.jsx`

---

## 🔵 **БЛОК 4: AI ИНТЕГРАЦИЯ (Приоритет: НИЗКИЙ)**

### **4.1 BACKEND AI СЕРВИС**
**AI АГЕНТ: Claude 4 Opus** | **Время: 3 дня** | **Статус: ❌ НЕ НАЧАТО**

#### **Провайдеры:**
- [ ] `services/ai/base_provider.py` - базовый класс
- [ ] `services/ai/openai_provider.py` - OpenAI интеграция
- [ ] `services/ai/gemini_provider.py` - Google Gemini
- [ ] `services/ai/deepseek_provider.py` - DeepSeek
- [ ] `services/ai/ai_manager.py` - управление провайдерами

#### **API endpoints:**
- [ ] `POST /api/ai/complaint-to-plan` - жалобы → план
- [ ] `POST /api/ai/icd-suggest` - подсказки МКБ-10
- [ ] `POST /api/ai/lab-interpret` - интерпретация анализов
- [ ] `POST /api/ai/skin-analyze` - анализ кожи
- [ ] `POST /api/ai/ecg-interpret` - интерпретация ЭКГ

---

### **4.2 FRONTEND AI КОМПОНЕНТЫ**
**AI АГЕНТ: Claude 4 Sonnet** | **Время: 2 дня** | **Статус: ❌ НЕ НАЧАТО**

#### **Компоненты:**
- [ ] `components/ai/AIAssistant.jsx` - универсальный помощник
- [ ] `components/ai/AIButton.jsx` - кнопка вызова AI
- [ ] `components/ai/AISuggestions.jsx` - отображение подсказок
- [ ] `components/ai/AILoader.jsx` - индикатор загрузки

#### **Интеграция:**
- [ ] Добавить AI кнопки в панели врачей
- [ ] Интегрировать подсказки МКБ-10
- [ ] Добавить AI анализ в лабораторию

---

## 🟣 **БЛОК 5: TELEGRAM И PWA (Приоритет: НИЗКИЙ)**

### **5.1 TELEGRAM БОТ**
**AI АГЕНТ: Claude 4 Sonnet** | **Время: 3 дня** | **Статус: ❌ НЕ НАЧАТО**

#### **Backend:**
- [ ] Установить `aiogram`
- [ ] `services/telegram_bot.py` - основной бот
- [ ] `POST /api/telegram/webhook` - webhook endpoint
- [ ] Команды: `/start`, `/queue`, `/appointment`
- [ ] Inline клавиатуры для навигации

#### **Функции:**
- [ ] Утренняя очередь через бот
- [ ] Напоминания о визитах
- [ ] Отправка PDF документов
- [ ] Подтверждение/отмена записей

---

### **5.2 PWA УЛУЧШЕНИЯ**
**AI АГЕНТ: Claude 4 Sonnet** | **Время: 2 дня** | **Статус: ❌ НЕ НАЧАТО**

#### **Service Worker:**
- [ ] Настроить background sync
- [ ] Реализовать офлайн кэширование
- [ ] Добавить push уведомления
- [ ] Настроить periodic sync

#### **Функции:**
- [ ] Офлайн режим для критичных страниц
- [ ] Автоматическая синхронизация данных
- [ ] HEIC → JPEG конвертация на клиенте
- [ ] Установка на домашний экран

---

## 🧪 **БЛОК 6: ТЕСТИРОВАНИЕ (Приоритет: НИЗКИЙ)**

### **6.1 E2E ТЕСТЫ**
**AI АГЕНТ: Claude 4 Sonnet** | **Время: 2 дня** | **Статус: ❌ НЕ НАЧАТО**

- [ ] Playwright тесты основных флоу
- [ ] Тест очереди 07:00
- [ ] Тест оплаты
- [ ] Тест печати
- [ ] Тест авторизации

### **6.2 ОПТИМИЗАЦИЯ**
**AI АГЕНТ: Claude 4 Sonnet** | **Время: 3 дня** | **Статус: ❌ НЕ НАЧАТО**

- [ ] Code splitting
- [ ] Lazy loading
- [ ] API кэширование
- [ ] Индексы БД
- [ ] Минификация бандла

---

## 📊 **СТАТИСТИКА TODO**

| Блок | Задач | Выполнено | Осталось | Приоритет |
|------|-------|-----------|----------|-----------|
| Критичная функциональность | 24 | 0 | 24 | 🔴 ВЫСОКИЙ |
| Frontend рефакторинг | 18 | 0 | 18 | 🟡 СРЕДНИЙ |
| Специализированные панели | 20 | 0 | 20 | 🟡 СРЕДНИЙ |
| AI интеграция | 10 | 0 | 10 | 🟢 НИЗКИЙ |
| Telegram и PWA | 8 | 0 | 8 | 🟢 НИЗКИЙ |
| Тестирование | 8 | 0 | 8 | 🟢 НИЗКИЙ |
| **ИТОГО** | **88** | **0** | **88** | |

---

## 🎯 **СЛЕДУЮЩИЙ ШАГ**

**НАЧИНАЕМ С:**
1. **Онлайн-очередь с QR** - самая критичная функция
2. **AI АГЕНТ: Claude 4 Sonnet** - для быстрой реализации
3. **Время: 3 дня** - полная реализация

**ГОТОВЫ НАЧАТЬ?** Скажите "НАЧИНАЕМ" и я дам точные инструкции для первого шага!

---

*TODO список создан на основе анализа всех документов проекта*
