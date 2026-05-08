# 🔧 План стабилизации PWA и восстановления функциональности

**Дата создания:** 05.10.2025  
**Статус:** В процессе  
**Приоритет:** Средний

---

## 🚨 Проблема

При использовании хуков `usePWA` и `useMediaQuery` возникает ошибка:
```
TypeError: Cannot read properties of null (reading 'useState')
Warning: Invalid hook call
```

### Причины

1. **Несоответствие версий React:**
   - В `package.json` (корень): `react@18.3.1`
   - Фактически установлено: `react@18.2.0`
   - Все зависимости используют `18.2.0 deduped` (дубликатов нет)

2. **Проблемные компоненты:**
   - `CompactConnectionStatus` в `HeaderNew.jsx` → вызывает `usePWA()`
   - `RegistrarPanel.jsx` → вызывает `useBreakpoint()` → `useMediaQuery()`

3. **Временные решения применены:**
   - ✅ Отключен `CompactConnectionStatus` в `HeaderNew.jsx`
   - ✅ Убран прямой вызов `usePWA()` в `App.jsx`
   - ✅ Заменён `QRCodeSVG` на иконку в `ModernQueueManager.jsx`

---

## 📋 Шаги стабилизации

### Этап 1: Синхронизация версий React ✅

```bash
cd frontend

# 1. Обновить package.json до актуальной версии
npm install react@18.2.0 react-dom@18.2.0 --save-exact

# 2. Чистая установка без ручного удаления дерева зависимостей
# npm ci сам синхронизирует node_modules с package-lock.json
npm ci

# 3. Проверка
npm run build

# 4. Проверить отсутствие дубликатов
npm ls react react-dom
```

**Ожидаемый результат:** Все зависимости используют `react@18.2.0` без дубликатов.

---

### Этап 2: Исправление хуков ⏳

#### 2.1 Исправить `usePWA.js`

**Файл:** `frontend/src/hooks/usePWA.js`

**Проблема:** Импорт `React` не используется, но указан в import.

**Исправление:**
```javascript
// БЫЛО
import React, { useState, useEffect, useCallback } from 'react';

// СТАЛО
import { useState, useEffect, useCallback } from 'react';
```

**Обоснование:** Избыточный импорт React может вызывать конфликты в некоторых сборках.

#### 2.2 Исправить `useMediaQuery.js`

**Файл:** `frontend/src/hooks/useMediaQuery.js`

**Проблема:** Аналогично - избыточный импорт React.

**Исправление:**
```javascript
// БЫЛО
import React, { useState, useEffect } from 'react';

// СТАЛО
import { useState, useEffect } from 'react';
```

#### 2.3 Добавить проверки SSR

**В `usePWA.js` и `useMediaQuery.js`** добавить защиту от SSR:

```javascript
// В начале каждого хука
if (typeof window === 'undefined') {
  // Возвращаем безопасные значения для SSR
  return {
    isOnline: true,
    isInstallable: false,
    // ... другие поля
  };
}
```

---

### Этап 3: Восстановление QR функциональности ⏳

#### 3.1 Установить зависимость

```bash
cd frontend
npm install qrcode.react@4.2.0 --save-exact
```

#### 3.2 Обновить `ModernQueueManager.jsx`

**Файл:** `frontend/src/components/queue/ModernQueueManager.jsx`

**Восстановить импорт:**
```javascript
import { QRCodeSVG } from 'qrcode.react';
```

**Восстановить рендеринг:**
```javascript
<QRCodeSVG
  value={`${window.location.origin}${qrData.qr_url}`}
  size={200}
  level="M"
  includeMargin={true}
/>
```

---

### Этап 4: Восстановление PWA индикатора ⏳

#### 4.1 Исправить `CompactConnectionStatus.jsx`

**Файл:** `frontend/src/components/pwa/CompactConnectionStatus.jsx`

**Исправления:**

1. Убрать избыточный импорт React:
```javascript
// БЫЛО
import React, { useState, useEffect } from 'react';

// СТАЛО  
import { useState, useEffect } from 'react';
```

2. Добавить fallback для SSR/ошибок:
```javascript
const CompactConnectionStatus = ({ className = '', showTooltip = true }) => {
  // Безопасный вызов хука с обработкой ошибок
  let pwaState = { isOnline: true, isServiceWorkerReady: false };
  
  try {
    pwaState = usePWA();
  } catch (error) {
    console.warn('PWA hook failed, using fallback:', error);
  }
  
  const { isOnline, isServiceWorkerReady } = pwaState;
  // ... остальной код
};
```

#### 4.2 Восстановить в `HeaderNew.jsx`

**Файл:** `frontend/src/components/layout/HeaderNew.jsx`

**Раскомментировать:**
```javascript
// Импорт
import CompactConnectionStatus from '../pwa/CompactConnectionStatus';

// Рендеринг
<CompactConnectionStatus className="mr-2" />
```

---

### Этап 5: Тестирование ⏳

#### 5.1 Проверка хуков

```bash
# Запустить dev сервер
cd frontend
npm run dev

# Открыть в браузере
http://localhost:5173

# Проверить консоль:
# ✅ Нет ошибок "Invalid hook call"
# ✅ Нет ошибок "Cannot read properties of null"
```

#### 5.2 Тестовые сценарии

1. **Тест PWA индикатора:**
   - Индикатор подключения виден в хедере
   - При отключении интернета → иконка меняется на WifiOff
   - При включении → возвращается к Cloud/Wifi

2. **Тест QR генерации:**
   - Открыть RegistrarPanel
   - Перейти на вкладку "Очередь"
   - Выбрать врача и дату
   - Нажать "Генерировать QR код"
   - ✅ Отображается реальный QR код (не иконка)
   - ✅ QR код сканируется телефоном
   - ✅ Ссылка ведёт на `/queue/join?token=...`

3. **Тест адаптивности:**
   - Открыть RegistrarPanel на разных разрешениях
   - ✅ `useBreakpoint()` работает без ошибок
   - ✅ Layout адаптируется под мобильные/планшет/десктоп

---

## 📁 Затронутые файлы

### Изменены (временные фиксы):
- ✅ `frontend/src/App.jsx` - отключен usePWA в AppContent
- ✅ `frontend/src/components/layout/HeaderNew.jsx` - закомментирован CompactConnectionStatus
- ✅ `frontend/src/components/queue/ModernQueueManager.jsx` - заменён QRCodeSVG на иконку

### Требуют исправления:
- ⏳ `frontend/src/hooks/usePWA.js` - убрать React import, добавить SSR checks
- ⏳ `frontend/src/hooks/useMediaQuery.js` - убрать React import, добавить SSR checks
- ⏳ `frontend/src/components/pwa/CompactConnectionStatus.jsx` - добавить try/catch, fallback
- ⏳ `frontend/package.json` - синхронизировать версии React

### Восстановить после исправлений:
- ⏳ `frontend/src/App.jsx` - вернуть usePWA
- ⏳ `frontend/src/components/layout/HeaderNew.jsx` - раскомментировать CompactConnectionStatus
- ⏳ `frontend/src/components/queue/ModernQueueManager.jsx` - вернуть QRCodeSVG

---

## 🔍 Диагностика

### Проверка дубликатов React

```bash
cd frontend
npm ls react react-dom

# Должно быть:
# └── react@18.2.0
# └── react-dom@18.2.0
# Все зависимости должны показывать "deduped"
```

### Проверка импортов

```bash
# Найти все файлы с избыточным импортом React
cd frontend/src
grep -r "import React, { " hooks/
grep -r "import React, { " components/pwa/

# Все хуки должны импортировать только нужные функции:
# import { useState, useEffect } from 'react';
# НЕ: import React, { useState } from 'react';
```

### Проверка версий в package.json

```bash
# Корень
cat package.json | grep "react"

# Должно быть:
"react": "18.2.0",
"react-dom": "18.2.0"
```

---

## ⚠️ Известные ограничения

1. **PWA функциональность отключена** до завершения стабилизации
2. **QR код отображается как иконка** вместо реального изображения
3. **Индикатор подключения скрыт** в хедере

---

## ✅ Критерии успеха

- [ ] Нет ошибок "Invalid hook call" в консоли
- [ ] Все хуки работают корректно
- [ ] PWA индикатор отображается и работает
- [ ] QR коды генерируются и отображаются корректно
- [ ] Адаптивный layout работает на всех устройствах
- [ ] Нет дубликатов React в дереве зависимостей

---

## 📝 Следующие шаги

1. **Немедленно:**
   - ✅ Синхронизировать версии React
   - ⏳ Исправить импорты в хуках

2. **В ближайшее время:**
   - ⏳ Добавить SSR checks
   - ⏳ Восстановить QR функциональность
   - ⏳ Восстановить PWA индикатор

3. **После стабилизации:**
   - ⏳ Полное тестирование PWA функций
   - ⏳ Тестирование на мобильных устройствах
   - ⏳ Обновить документацию

---

## 📚 Полезные ссылки

- [React Rules of Hooks](https://reactjs.org/docs/hooks-rules.html)
- [React Invalid Hook Call Warning](https://reactjs.org/link/invalid-hook-call)
- [Fixing Duplicate React](https://reactjs.org/warnings/invalid-hook-call-warning.html#duplicate-react)
- [qrcode.react Documentation](https://github.com/zpao/qrcode.react)

---

**Последнее обновление:** 05.10.2025  
**Автор:** AI Assistant  
**Статус:** В процессе выполнения

