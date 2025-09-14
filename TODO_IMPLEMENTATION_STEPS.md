# 📝 ПОШАГОВЫЙ ПЛАН РЕАЛИЗАЦИИ С РЕКОМЕНДАЦИЯМИ ПО AI МОДЕЛЯМ

[[memory:7752001]] [[memory:7752047]] [[memory:8016693]]

## 🎯 **КЛЮЧЕВЫЕ ЗАДАЧИ**

### **1. АУДИТ FRONTEND** ✅
### **2. ИНТЕГРАЦИЯ FRONTEND-BACKEND** 
### **3. УНИФИКАЦИЯ UI/UX**

---

## 📋 **ДЕТАЛЬНЫЕ ШАГИ РЕАЛИЗАЦИИ**

### **БЛОК 1: КРИТИЧНАЯ ФУНКЦИОНАЛЬНОСТЬ (Приоритет: 🔴)**

#### **1.1 ОНЛАЙН-ОЧЕРЕДЬ С QR (07:00)**
**AI Модель: Claude 4 Sonnet** (быстрая реализация)

```markdown
BACKEND:
□ Создать модель daily_queues и queue_entries
□ Реализовать POST /api/queue/qrcode?day&specialist_id
□ Реализовать POST /api/queue/join с проверкой времени 07:00
□ Добавить логику уникальности по телефону/Telegram
□ Настроить стартовые номера по специальности в settings

FRONTEND:
□ Создать страницу QueueJoin.jsx для QR сканирования
□ Добавить компонент OnlineQueueManager.jsx в registrar/
□ Интегрировать кнопку "Открыть прием" в RegistrarPanel
□ Добавить отображение онлайн-очереди в DisplayBoard

ТЕСТИРОВАНИЕ:
□ Проверить окно 07:00 - opened_at
□ Проверить уникальность номера
□ Проверить лимиты
```

#### **1.2 ПЛАТЕЖНАЯ СИСТЕМА**
**AI Модель: Claude 4 Sonnet** (интеграция API)

```markdown
BACKEND:
□ Создать services/payment_providers/click.py
□ Создать services/payment_providers/payme.py
□ Реализовать POST /api/payments/init
□ Реализовать POST /api/payments/{provider}/webhook
□ Добавить привязку платежей к визитам

FRONTEND:
□ Создать components/payment/PaymentWidget.jsx
□ Создать pages/PaymentSuccess.jsx
□ Интегрировать в CashierPanel.jsx
□ Добавить статус оплаты в VisitDetails.jsx
```

#### **1.3 WEBSOCKET ДЛЯ ТАБЛО**
**AI Модель: Claude 4 Sonnet** (WebSocket интеграция)

```markdown
BACKEND:
□ Настроить WebSocket endpoint /ws/queue/{department}
□ Реализовать события: queue.created, queue.called, queue.updated
□ Настроить Redis pub/sub для масштабирования

FRONTEND:
□ Добавить WebSocket клиент в DisplayBoardUnified.jsx
□ Реализовать real-time обновления очереди
□ Добавить звуковые уведомления при вызове
□ Добавить анимации появления/исчезновения
```

#### **1.4 ПЕЧАТЬ ДОКУМЕНТОВ**
**AI Модель: Claude 4 Sonnet** (генерация PDF)

```markdown
BACKEND:
□ Установить python-escpos для термопринтеров
□ Реализовать POST /api/print/ticket - печать талона
□ Реализовать POST /api/pdf/prescription - рецепт A5
□ Реализовать POST /api/pdf/memo - памятка
□ Создать Jinja2 шаблоны для PDF

FRONTEND:
□ Создать components/print/PrintDialog.jsx
□ Создать components/print/PrintPreview.jsx
□ Интегрировать в панели врачей
□ Добавить выбор принтера
```

---

### **БЛОК 2: FRONTEND РЕФАКТОРИНГ (Приоритет: 🟡)**

#### **2.1 РЕОРГАНИЗАЦИЯ СТРУКТУРЫ**
**AI Модель: Claude 4 Sonnet** (рефакторинг)

```markdown
СОЗДАТЬ СТРУКТУРУ:
□ mkdir components/layout
□ mkdir components/dashboard  
□ mkdir components/queue
□ mkdir components/payment
□ mkdir components/print

ПЕРЕМЕСТИТЬ ФАЙЛЫ:
□ mv components/Header.jsx components/layout/
□ mv components/Sidebar.jsx components/layout/
□ mv components/Dashboard.jsx components/dashboard/
□ mv components/QueueManager.jsx components/queue/
□ Переместить остальные 40+ компонентов

ОБНОВИТЬ ИМПОРТЫ:
□ Обновить все import statements
□ Создать index.js в каждой папке для экспортов
□ Проверить работоспособность
```

#### **2.2 API ИНТЕГРАЦИЯ**
**AI Модель: Claude 4 Sonnet** (интеграция)

```markdown
ЦЕНТРАЛИЗАЦИЯ API:
□ Дополнить api/endpoints.js всеми endpoints
□ Создать api/interceptors.js для токенов
□ Добавить единую обработку ошибок
□ Создать api/services/ для бизнес-логики

СЕРВИСЫ:
□ api/services/auth.js - аутентификация
□ api/services/queue.js - очередь
□ api/services/payment.js - платежи
□ api/services/medical.js - медкарты
```

#### **2.3 UI/UX УНИФИКАЦИЯ**
**AI Модель: Claude 4 Sonnet** (дизайн)

```markdown
DESIGN SYSTEM:
□ Создать design-system/components/Button.jsx
□ Создать design-system/components/Input.jsx
□ Создать design-system/components/Card.jsx
□ Создать design-system/components/Table.jsx
□ Создать design-system/theme/colors.js
□ Создать design-system/theme/typography.js

ПРИМЕНИТЬ:
□ Заменить все кнопки на единый компонент
□ Унифицировать формы
□ Применить единую цветовую схему
□ Настроить единые отступы
```

---

### **БЛОК 3: СПЕЦИАЛИЗИРОВАННЫЕ ПАНЕЛИ (Приоритет: 🟡)**

#### **3.1 ПАНЕЛЬ КАРДИОЛОГА**
**AI Модель: Claude 4 Opus** (сложная логика)

```markdown
ФУНКЦИОНАЛЬНОСТЬ:
□ Добавить загрузку ЭКГ файлов (PDF/SCP/XML)
□ Реализовать парсинг SCP формата
□ Добавить загрузку ЭхоКГ результатов
□ Интегрировать AI интерпретацию ЭКГ
□ Настроить общую очередь консультация+ЭхоКГ

КОМПОНЕНТЫ:
□ components/cardiology/ECGViewer.jsx
□ components/cardiology/EchoForm.jsx
□ components/cardiology/ECGParser.jsx
□ Доработать CardiologistPanelUnified.jsx
```

#### **3.2 ПАНЕЛЬ ДЕРМАТОЛОГА**
**AI Модель: Claude 4 Opus** (обработка изображений)

```markdown
ФУНКЦИОНАЛЬНОСТЬ:
□ Реализовать загрузку фото до/после
□ Добавить поддержку HEIC формата
□ Интегрировать AI анализ кожи
□ Создать шаблоны косметологических процедур
□ Настроить стартовый номер №15

КОМПОНЕНТЫ:
□ components/dermatology/PhotoUploader.jsx
□ components/dermatology/PhotoComparison.jsx
□ components/dermatology/ProcedureTemplates.jsx
□ components/dermatology/SkinAnalysis.jsx
```

#### **3.3 ПАНЕЛЬ СТОМАТОЛОГА**
**AI Модель: Claude 4 Opus** (интерактивные элементы)

```markdown
ФУНКЦИОНАЛЬНОСТЬ:
□ Создать интерактивную зубную карту
□ Реализовать выбор процедур для каждого зуба
□ Добавить план лечения с этапами
□ Настроить стартовый номер №3
□ Интегрировать с зуботехнической лабораторией

КОМПОНЕНТЫ:
□ components/dental/TeethChart.jsx
□ components/dental/ToothModal.jsx
□ components/dental/TreatmentPlanner.jsx
□ components/dental/LabOrders.jsx
```

---

### **БЛОК 4: AI ИНТЕГРАЦИЯ (Приоритет: 🟢)**

#### **4.1 BACKEND AI СЕРВИС**
**AI Модель: Claude 4 Opus** (архитектура AI)

```markdown
ПРОВАЙДЕРЫ:
□ services/ai/base_provider.py - базовый класс
□ services/ai/openai_provider.py
□ services/ai/gemini_provider.py
□ services/ai/deepseek_provider.py
□ services/ai/ai_manager.py - управление провайдерами

API ENDPOINTS:
□ POST /api/ai/complaint-to-plan
□ POST /api/ai/icd-suggest
□ POST /api/ai/lab-interpret
□ POST /api/ai/skin-analyze
□ POST /api/ai/ecg-interpret
```

#### **4.2 FRONTEND AI КОМПОНЕНТЫ**
**AI Модель: Claude 4 Sonnet** (UI компоненты)

```markdown
КОМПОНЕНТЫ:
□ components/ai/AIAssistant.jsx
□ components/ai/AIButton.jsx
□ components/ai/AISuggestions.jsx
□ components/ai/AILoader.jsx

ИНТЕГРАЦИЯ:
□ Добавить AI кнопки в панели врачей
□ Интегрировать подсказки МКБ-10
□ Добавить AI анализ в лабораторию
```

---

### **БЛОК 5: TELEGRAM И PWA (Приоритет: 🟢)**

#### **5.1 TELEGRAM БОТ**
**AI Модель: Claude 4 Sonnet** (бот интеграция)

```markdown
BACKEND:
□ Установить aiogram
□ Создать services/telegram_bot.py
□ Реализовать команды: /start, /queue, /appointment
□ Добавить inline клавиатуры
□ Настроить webhook

ФУНКЦИИ:
□ Утренняя очередь через бот
□ Напоминания о визитах
□ Отправка PDF документов
□ Подтверждение/отмена записей
```

#### **5.2 PWA УЛУЧШЕНИЯ**
**AI Модель: Claude 4 Sonnet** (PWA функции)

```markdown
SERVICE WORKER:
□ Настроить background sync
□ Реализовать офлайн кэширование
□ Добавить push уведомления
□ Настроить periodic sync

ФУНКЦИИ:
□ Офлайн режим для критичных страниц
□ Автоматическая синхронизация данных
□ HEIC → JPEG конвертация на клиенте
□ Установка на домашний экран
```

---

## 📊 **РАСПРЕДЕЛЕНИЕ ЗАДАЧ ПО AI МОДЕЛЯМ**

### **Claude 4 Sonnet (70% задач):**
- ✅ Онлайн-очередь
- ✅ Платежная система
- ✅ WebSocket интеграция
- ✅ Печать документов
- ✅ Frontend рефакторинг
- ✅ API интеграция
- ✅ UI/UX унификация
- ✅ Telegram бот
- ✅ PWA функции

### **Claude 4 Opus (25% задач):**
- ✅ Панель кардиолога (ЭКГ/ЭхоКГ)
- ✅ Панель дерматолога (фото анализ)
- ✅ Панель стоматолога (зубная карта)
- ✅ AI архитектура backend
- ✅ Сложная бизнес-логика

### **Claude 3.5 Sonnet (5% задач):**
- ✅ Простые исправления
- ✅ CSS стили
- ✅ Документация

---

## 🚦 **КОНТРОЛЬНЫЕ ТОЧКИ**

### **День 1-3: Критичная функциональность**
- [ ] Онлайн-очередь работает
- [ ] Платежи инициализируются
- [ ] WebSocket подключен
- [ ] Печать талонов работает

### **День 4-7: Frontend рефакторинг**
- [ ] Структура реорганизована
- [ ] API централизован
- [ ] UI унифицирован

### **День 8-14: Специализированные панели**
- [ ] Кардиолог готов
- [ ] Дерматолог готов
- [ ] Стоматолог готов

### **День 15-18: AI и интеграции**
- [ ] AI сервис работает
- [ ] Telegram бот запущен
- [ ] PWA улучшения готовы

### **День 19-21: Тестирование**
- [ ] E2E тесты пройдены
- [ ] Производительность оптимизирована
- [ ] Документация обновлена

---

## ✅ **КРИТЕРИИ ГОТОВНОСТИ**

1. **Авторизация и роли не нарушены** ✅
2. **Все endpoints интегрированы** ✅
3. **UI/UX унифицирован** ✅
4. **Структура файлов правильная** ✅
5. **Обработка ошибок единая** ✅
6. **Производительность оптимальная** ✅

---

*План создан с учетом текущего состояния проекта и оптимального распределения AI моделей*
