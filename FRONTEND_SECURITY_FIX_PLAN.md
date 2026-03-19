# План исправления проблем безопасности фронтенда

**Дата создания:** 2025-12-06
**Версия:** 1.0
**Проект:** Medical Clinic Management System
**Статус:** В ожидании утверждения

---

## Содержание

1. [Обзор](#обзор)
2. [Этап 1: Критические исправления (0-3 дня)](#этап-1-критические-исправления-0-3-дня)
3. [Этап 2: Высокий приоритет (1-2 недели)](#этап-2-высокий-приоритет-1-2-недели)
4. [Этап 3: Средний приоритет (2-4 недели)](#этап-3-средний-приоритет-2-4-недели)
5. [Этап 4: Долгосрочные улучшения (1-3 месяца)](#этап-4-долгосрочные-улучшения-1-3-месяца)
6. [План тестирования](#план-тестирования)
7. [Критерии завершения](#критерии-завершения)

---

## Обзор

### Статистика найденных проблем

| Приоритет | Количество | Статус |
|-----------|------------|--------|
| CRITICAL  | 8          | ⏳ Ожидает исправления |
| HIGH      | 12         | ⏳ Ожидает исправления |
| MEDIUM    | 6          | ⏳ Ожидает исправления |
| LOW       | 15+        | 📋 Запланировано |

### Оценка трудозатрат

- **Критические исправления:** 2-3 дня
- **Высокий приоритет:** 2 недели
- **Средний приоритет:** 2-4 недели
- **Долгосрочные:** 1-3 месяца
- **ИТОГО:** ~2-3 месяца до полного соответствия HIPAA

---

## Этап 1: Критические исправления (0-3 дня)

> **СРОК:** Немедленно (в течение 48 часов)
> **ОТВЕТСТВЕННЫЙ:** Frontend Team Lead
> **БЛОКИРУЕТ:** Производственный деплоймент

---

### 1.1. Удалить захардкоженные учетные данные

**Приоритет:** 🔴 CRITICAL
**Время:** 1 час
**Файлы:** `frontend/src/components/auth/LoginFormStyled.jsx`

#### Проблема

```javascript
// Строки 35-36, 66-67
const [formData, setFormData] = useState({
  username: 'admin@example.com',  // ❌ КРИТИЧНО
  password: 'admin123',             // ❌ КРИТИЧНО
  loginType: 'username'
});

// Строки 66-67 - используются как fallback
const username = formData.username || 'admin@example.com';  // ❌
const password = formData.password || 'admin123';            // ❌
```

#### Решение

**Шаг 1:** Удалить дефолтные значения

```javascript
// ✅ ИСПРАВЛЕНИЕ
const [formData, setFormData] = useState({
  username: '',  // Пустая строка
  password: '',  // Пустая строка
  loginType: 'username'
});
```

**Шаг 2:** Удалить fallback логику

```javascript
// ❌ УДАЛИТЬ строки 66-67
// const username = formData.username || 'admin@example.com';
// const password = formData.password || 'admin123';

// ✅ ЗАМЕНИТЬ на
const username = formData.username;
const password = formData.password;

// Добавить валидацию
if (!username || !password) {
  setError('Пожалуйста, введите логин и пароль');
  setLoading(false);
  return;
}
```

**Шаг 3 (опционально):** Для разработки использовать переменные окружения

```javascript
// .env.development (НЕ коммитить!)
VITE_DEV_USERNAME=admin@example.com
VITE_DEV_PASSWORD=admin123

// В коде (только для разработки)
const [formData, setFormData] = useState({
  username: import.meta.env.MODE === 'development'
    ? (import.meta.env.VITE_DEV_USERNAME || '')
    : '',
  password: import.meta.env.MODE === 'development'
    ? (import.meta.env.VITE_DEV_PASSWORD || '')
    : '',
  loginType: 'username'
});
```

#### Критерии приёмки
- [ ] В production build нет захардкоженных credentials
- [ ] Форма логина работает с пустыми значениями
- [ ] Добавлена валидация для пустых полей
- [ ] `.env.development` добавлен в `.gitignore`

---

### 1.2. Исправить несоответствие ключей токенов

**Приоритет:** 🔴 CRITICAL
**Время:** 2 часа
**Файлы:** `services/auth.js`, `api/ws.js`, `api/client.js`, `utils/api.js`, `utils/queueApi.js`

#### Проблема

Используются 3 разных ключа для одного токена:
- `auth_token` (в api/client.js)
- `token` (в services/auth.js) ❌
- `access_token` (в api/ws.js) ❌

#### Решение

**Шаг 1:** Создать единый модуль управления токенами

```javascript
// frontend/src/utils/tokenManager.js (НОВЫЙ ФАЙЛ)

const TOKEN_KEY = 'auth_token';
const REFRESH_TOKEN_KEY = 'refresh_token';
const USER_KEY = 'user';

/**
 * Централизованное управление токенами
 */
export const tokenManager = {
  // Получить access token
  getAccessToken() {
    return localStorage.getItem(TOKEN_KEY);
  },

  // Установить access token
  setAccessToken(token) {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  },

  // Получить refresh token
  getRefreshToken() {
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  },

  // Установить refresh token
  setRefreshToken(token) {
    if (token) {
      localStorage.setItem(REFRESH_TOKEN_KEY, token);
    } else {
      localStorage.removeItem(REFRESH_TOKEN_KEY);
    }
  },

  // Очистить все токены
  clearAll() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },

  // Проверить наличие токена
  hasToken() {
    return !!this.getAccessToken();
  }
};
```

**Шаг 2:** Обновить `services/auth.js`

```javascript
// БЫЛО (строка 67)
localStorage.setItem('token', response.data.access_token); // ❌

// СТАЛО
import { tokenManager } from '../utils/tokenManager';

// Строка 67
tokenManager.setAccessToken(response.data.access_token); // ✅

// Строка 102 - isAuthenticated()
isAuthenticated() {
  return tokenManager.hasToken(); // ✅
}
```

**Шаг 3:** Обновить `api/ws.js`

```javascript
// БЫЛО (строка 67)
const token = localStorage.getItem('access_token'); // ❌

// СТАЛО
import { tokenManager } from '../utils/tokenManager';

const token = tokenManager.getAccessToken(); // ✅
```

**Шаг 4:** Обновить все остальные файлы

Файлы для обновления:
- `utils/api.js` - заменить `localStorage.getItem('auth_token')`
- `utils/queueApi.js` - заменить `localStorage.getItem('access_token')`
- `utils/websocketAuth.js` - заменить `localStorage.getItem('access_token')`
- `components/dashboard/Dashboard.jsx` - заменить `localStorage.getItem('access_token')`
- `components/common/ScheduleNextModal.jsx` (3 места) - заменить `localStorage.getItem('access_token')`
- `hooks/useApi.js` - заменить `localStorage.getItem('access_token')`

**Шаг 5:** Обновить `api/interceptors.js`

```javascript
// Строка 15, 74, 96, 126, 207
import { tokenManager } from '../utils/tokenManager';

// Заменить все
localStorage.getItem('auth_token') → tokenManager.getAccessToken()
localStorage.getItem('refresh_token') → tokenManager.getRefreshToken()
localStorage.setItem('auth_token', ...) → tokenManager.setAccessToken(...)
localStorage.removeItem('auth_token') → tokenManager.clearAll()
```

#### Критерии приёмки
- [ ] Создан `utils/tokenManager.js`
- [ ] Все 82 файла с localStorage обновлены
- [ ] Используется только один ключ `auth_token`
- [ ] Тесты логина/логаута проходят
- [ ] WebSocket подключение работает

---

### 1.3. Удалить логирование медицинских данных

**Приоритет:** 🔴 CRITICAL (HIPAA VIOLATION)
**Время:** 4 часа
**Файлы:** 100+ файлов с console.log

#### Проблема

510 console.log statements, многие логируют PHI (Protected Health Information)

#### Решение

**Шаг 1:** Создать безопасную функцию логирования

```javascript
// frontend/src/utils/logger.js (НОВЫЙ ФАЙЛ)

const isDevelopment = import.meta.env.MODE === 'development';

/**
 * Список чувствительных полей для маскировки
 */
const SENSITIVE_FIELDS = [
  'password', 'token', 'access_token', 'refresh_token',
  'patient_name', 'full_name', 'phone', 'email',
  'passport', 'diagnosis', 'complaints', 'anamnesis',
  'examination', 'medical_history', 'treatment_plan',
  'medications', 'allergies', 'lab_results'
];

/**
 * Маскировка чувствительных данных
 */
function sanitizeData(data) {
  if (!data || typeof data !== 'object') return data;

  const sanitized = Array.isArray(data) ? [...data] : { ...data };

  Object.keys(sanitized).forEach(key => {
    const lowerKey = key.toLowerCase();

    // Проверка на чувствительные поля
    const isSensitive = SENSITIVE_FIELDS.some(field =>
      lowerKey.includes(field.toLowerCase())
    );

    if (isSensitive) {
      sanitized[key] = '[REDACTED]';
    } else if (typeof sanitized[key] === 'object') {
      sanitized[key] = sanitizeData(sanitized[key]);
    }
  });

  return sanitized;
}

/**
 * Безопасное логирование
 */
export const logger = {
  log(...args) {
    if (isDevelopment) {
      const sanitized = args.map(arg => sanitizeData(arg));
      console.log(...sanitized);
    }
  },

  warn(...args) {
    if (isDevelopment) {
      const sanitized = args.map(arg => sanitizeData(arg));
      console.warn(...sanitized);
    }
  },

  error(...args) {
    // Ошибки всегда логируем, но с маскировкой
    const sanitized = args.map(arg => sanitizeData(arg));
    console.error(...sanitized);
  },

  debug(...args) {
    if (isDevelopment) {
      const sanitized = args.map(arg => sanitizeData(arg));
      console.debug(...sanitized);
    }
  }
};
```

**Шаг 2:** Заменить console.log в критичных файлах

```javascript
// api/interceptors.js
import { logger } from '../utils/logger';

// Строка 22, 31, 41, 63 и т.д.
// БЫЛО
console.log(`🔄 API Request:`, { params: config.params, data: config.data });

// СТАЛО
logger.log(`🔄 API Request:`, {
  url: config.url,
  method: config.method,
  // params и data автоматически очистятся от PHI
  params: config.params,
  data: config.data
});
```

**Шаг 3:** Удалить логи из медицинских компонентов

```javascript
// components/medical/EMRSystem.jsx

// УДАЛИТЬ строки 196, 215, 723
// console.log('[Dental EMR] Tooth ${toothNumber} clicked:', toothData); ❌

// Если логирование необходимо для отладки:
logger.debug('[Dental EMR] Tooth interaction', {
  toothNumber,
  // toothData будет автоматически sanitized
});
```

**Шаг 4:** Обновить vite.config.js

Убедиться, что в production console.log удаляются:

```javascript
// vite.config.js - строки 154-159 (УЖЕ ЕСТЬ, проверить)
terserOptions: {
  compress: {
    drop_console: true,      // ✅ Удалять console.log
    drop_debugger: true      // ✅ Удалять debugger
  }
}
```

**Шаг 5:** Автоматизация с ESLint

```javascript
// .eslintrc.cjs или eslint.config.js
{
  rules: {
    'no-console': ['error', {
      allow: ['error', 'warn'] // Разрешить только error и warn
    }]
  }
}
```

#### Файлы для обновления (приоритет)

**Критичные (медицинские данные):**
1. `components/medical/EMRSystem.jsx` - удалить логи PHI
2. `components/medical/EMRInterface.jsx` - удалить логи PHI
3. `components/laboratory/LabResultsManager.jsx` - удалить логи
4. `components/cardiology/ECGViewer.jsx` - удалить логи
5. `components/dermatology/PhotoUploader.jsx` - удалить логи
6. `api/interceptors.js` - заменить на logger
7. `api/client.js` - заменить на logger

**Остальные (100+ файлов):**
- Постепенная замена или удаление через ESLint + автофикс

#### Критерии приёмки
- [ ] Создан `utils/logger.js` с sanitizeData
- [ ] Все медицинские компоненты используют logger
- [ ] В production build нет console.log (проверить через build)
- [ ] ESLint правило `no-console` активно
- [ ] Тесты показывают отсутствие PHI в логах

---

### 1.4. Обновить уязвимые зависимости

**Приоритет:** 🔴 CRITICAL
**Время:** 1 час
**Файлы:** `package.json`

#### Проблема

10 npm уязвимостей:
- axios@1.11.0 → DoS vulnerability (CVSS 7.5)
- vite@4.3.9 → 6 file disclosure vulnerabilities
- @playwright/test@1.48.0 → security issue
- esbuild@0.17.19 → CORS bypass

#### Решение

```bash
cd frontend

# Обновить критичные пакеты
npm install axios@latest
npm install vite@latest
npm install @playwright/test@latest
npm install esbuild@latest
npm install eslint@latest

# Проверить оставшиеся уязвимости
npm audit

# Попробовать автофикс
npm audit fix

# Для major версий (осторожно, могут быть breaking changes)
npm audit fix --force

# После обновления - тестировать!
npm run test
npm run build
npm run preview
```

#### Обновление package.json

```json
{
  "dependencies": {
    "axios": "^1.13.2",  // было 1.11.0
    // остальное без изменений
  },
  "devDependencies": {
    "@playwright/test": "^1.57.0",  // было 1.48.0
    "esbuild": "^0.24.3",           // было 0.17.19
    "eslint": "^9.39.1",            // было 9.16.0
    "vite": "^4.5.14"               // было 4.3.9
  }
}
```

#### Проверка совместимости

После обновления проверить:

1. **Axios:** API запросы работают
2. **Vite:** Dev server запускается, build успешен
3. **Playwright:** E2E тесты проходят
4. **ESLint:** Линтер работает без ошибок

#### Критерии приёмки
- [ ] `npm audit` показывает 0 critical/high уязвимостей
- [ ] Dev server запускается без ошибок
- [ ] Production build успешен
- [ ] E2E тесты проходят
- [ ] Нет breaking changes в API

---

### 1.5. Исправить утечки памяти с blob URLs

**Приоритет:** 🔴 CRITICAL
**Время:** 2 часа
**Файлы:** `components/medical/EMRSystem.jsx`, `components/dermatology/PhotoUploader.jsx`

#### Проблема

```javascript
// Создаётся blob URL, но НИКОГДА не освобождается
<img src={URL.createObjectURL(attachment.file)} />
```

При просмотре 50+ медицинских изображений браузер может упасть.

#### Решение

**Вариант 1: Custom Hook для управления Blob URLs**

```javascript
// frontend/src/hooks/useBlobURL.js (НОВЫЙ ФАЙЛ)
import { useEffect, useState } from 'react';

/**
 * Hook для безопасного управления Blob URLs
 * Автоматически очищает URL при размонтировании компонента
 */
export function useBlobURL(file) {
  const [blobURL, setBlobURL] = useState(null);

  useEffect(() => {
    if (!file) {
      setBlobURL(null);
      return;
    }

    // Создаём blob URL
    const url = URL.createObjectURL(file);
    setBlobURL(url);

    // Cleanup функция - освобождаем память
    return () => {
      URL.revokeObjectURL(url);
    };
  }, [file]);

  return blobURL;
}
```

**Использование в EMRSystem.jsx:**

```javascript
// БЫЛО (строка 1102)
{attachments.map((attachment, idx) => (
  <div key={idx}>
    <img src={URL.createObjectURL(attachment.file)} /> {/* ❌ УТЕЧКА */}
  </div>
))}

// СТАЛО
import { useBlobURL } from '../../hooks/useBlobURL';

// Внутри компонента
function AttachmentPreview({ file, name }) {
  const blobURL = useBlobURL(file); // ✅ Автоочистка

  if (!blobURL) return <div>Загрузка...</div>;

  return (
    <div>
      <img src={blobURL} alt={name} />
    </div>
  );
}

// Использование
{attachments.map((attachment, idx) => (
  <AttachmentPreview
    key={idx}
    file={attachment.file}
    name={attachment.name}
  />
))}
```

**Вариант 2: Компонент с ручным управлением**

```javascript
// Для PhotoUploader.jsx (строка 342)
import { useEffect, useState } from 'react';

function PhotoPreview({ photo }) {
  const [previewURL, setPreviewURL] = useState(null);

  useEffect(() => {
    if (photo.file) {
      const url = URL.createObjectURL(photo.file);
      setPreviewURL(url);

      return () => {
        URL.revokeObjectURL(url);
      };
    } else if (photo.preview) {
      setPreviewURL(photo.preview);
    }
  }, [photo]);

  return (
    <img
      src={previewURL}
      alt={photo.zone || 'Preview'}
    />
  );
}
```

#### Критерии приёмки
- [ ] Создан hook `useBlobURL.js`
- [ ] EMRSystem.jsx использует безопасный preview
- [ ] PhotoUploader.jsx использует безопасный preview
- [ ] Memory profiler показывает освобождение памяти
- [ ] Можно открыть 100+ изображений без краша

---

### 1.6. Убрать захардкоженные данные пациентов

**Приоритет:** 🔴 CRITICAL (HIPAA)
**Время:** 30 минут
**Файлы:** `components/medical/EMRInterface.jsx`

#### Проблема

```javascript
// Строки 108-149
const mockPatients = [
  {
    id: 1,
    full_name: 'Иванов Иван Иванович',  // ❌ PII
    phone: '+7 (999) 123-45-67',        // ❌ PII
    email: 'ivanov@example.com'         // ❌ PII
  }
];
```

#### Решение

```javascript
// УДАЛИТЬ весь блок mockPatients

// ЗАМЕНИТЬ на пустой массив или генератор тестовых данных
const mockPatients = import.meta.env.MODE === 'development'
  ? generateMockPatients(10) // Функция генерации
  : [];

// Функция генерации (только для разработки)
function generateMockPatients(count) {
  return Array.from({ length: count }, (_, i) => ({
    id: i + 1,
    full_name: `Пациент ${i + 1}`,
    phone: `+7 (900) ${String(i).padStart(7, '0')}`,
    email: `patient${i}@test.local`
  }));
}
```

#### Критерии приёмки
- [ ] Нет реальных ФИО в коде
- [ ] Нет реальных телефонов/email
- [ ] В production mockPatients = []
- [ ] Git history проверен на наличие реальных данных

---

### 1.7. Исправить client-side file validation

**Приоритет:** 🔴 CRITICAL
**Время:** 3 часа
**Файлы:** `components/medical/EMRSystem.jsx`, `components/dermatology/PhotoUploader.jsx`, `components/files/FileManager.jsx`

#### Проблема

```javascript
// Только клиентская валидация - легко обойти
<input accept="image/*,.pdf,.doc,.docx" />
if (file.type === 'image/heic') { ... }
```

Атакующий может загрузить `malware.exe` с MIME type `image/jpeg`.

#### Решение

**Шаг 1: Усиленная клиентская валидация**

```javascript
// frontend/src/utils/fileValidator.js (НОВЫЙ ФАЙЛ)

/**
 * Разрешённые MIME types для медицинских файлов
 */
const ALLOWED_MIME_TYPES = {
  images: [
    'image/jpeg',
    'image/jpg',
    'image/png',
    'image/gif',
    'image/heic',
    'image/heif',
    'image/webp'
  ],
  documents: [
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  ],
  medical: [
    'text/xml',           // ECG
    'application/dicom',  // Medical imaging
    'text/csv',           // Lab results
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
  ]
};

/**
 * Magic numbers (сигнатуры файлов) для проверки
 */
const FILE_SIGNATURES = {
  'image/jpeg': ['FFD8FF'],
  'image/png': ['89504E47'],
  'application/pdf': ['25504446'],
  'application/zip': ['504B0304'],
  // Добавить остальные
};

/**
 * Чтение первых байтов файла для проверки сигнатуры
 */
async function readFileSignature(file, bytesToRead = 4) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const arr = new Uint8Array(e.target.result);
      const hex = Array.from(arr)
        .map(b => b.toString(16).padStart(2, '0').toUpperCase())
        .join('');
      resolve(hex);
    };
    reader.onerror = reject;
    reader.readAsArrayBuffer(file.slice(0, bytesToRead));
  });
}

/**
 * Валидация файла по расширению, MIME type и magic numbers
 */
export async function validateFile(file, allowedCategories = ['images']) {
  const errors = [];

  // 1. Проверка размера (максимум 50MB для медицинских файлов)
  const MAX_SIZE = 50 * 1024 * 1024;
  if (file.size > MAX_SIZE) {
    errors.push(`Файл слишком большой. Максимум ${MAX_SIZE / 1024 / 1024}MB`);
  }

  // 2. Получить разрешённые MIME types
  const allowedTypes = allowedCategories.flatMap(cat =>
    ALLOWED_MIME_TYPES[cat] || []
  );

  // 3. Проверка MIME type
  if (!allowedTypes.includes(file.type)) {
    errors.push(`Недопустимый тип файла: ${file.type}`);
  }

  // 4. Проверка расширения
  const ext = file.name.split('.').pop().toLowerCase();
  const validExtensions = {
    'image/jpeg': ['jpg', 'jpeg'],
    'image/png': ['png'],
    'image/heic': ['heic'],
    'application/pdf': ['pdf'],
    // ... остальные
  };

  const expectedExts = validExtensions[file.type] || [];
  if (expectedExts.length > 0 && !expectedExts.includes(ext)) {
    errors.push(`Расширение ${ext} не соответствует типу ${file.type}`);
  }

  // 5. Проверка magic numbers (сигнатура файла)
  try {
    const signature = await readFileSignature(file);
    const expectedSig = FILE_SIGNATURES[file.type];

    if (expectedSig) {
      const matches = expectedSig.some(sig => signature.startsWith(sig));
      if (!matches) {
        errors.push('Содержимое файла не соответствует заявленному типу (magic number mismatch)');
      }
    }
  } catch (err) {
    errors.push('Не удалось прочитать файл для проверки');
  }

  return {
    valid: errors.length === 0,
    errors
  };
}
```

**Шаг 2: Использовать в PhotoUploader.jsx**

```javascript
import { validateFile } from '../../utils/fileValidator';

async function handleFileSelect(files) {
  for (const file of files) {
    // Усиленная валидация
    const validation = await validateFile(file, ['images']);

    if (!validation.valid) {
      setError(`Ошибка валидации ${file.name}:\n${validation.errors.join('\n')}`);
      continue;
    }

    // Файл прошёл все проверки
    // Но СЕРВЕРНАЯ валидация всё равно обязательна!
    uploadFile(file);
  }
}
```

**Шаг 3: Добавить серверную валидацию (Backend)**

> **ВАЖНО:** Клиентская валидация недостаточна! Нужна серверная проверка.

Создать задачу для backend team:

```markdown
## Backend Task: Implement Server-Side File Validation

**Endpoint:** `/api/v1/files/upload`

**Требования:**
1. Проверка MIME type через libmagic/python-magic
2. Проверка file signature (magic numbers)
3. Антивирус сканирование (ClamAV)
4. Валидация размера файла
5. Sanitization имени файла
6. Изоляция uploaded files в отдельной директории

**Пример кода (Python):**
```python
import magic
from werkzeug.utils import secure_filename

def validate_uploaded_file(file):
    # 1. Secure filename
    filename = secure_filename(file.filename)

    # 2. Check file signature
    mime = magic.from_buffer(file.read(1024), mime=True)
    file.seek(0)

    ALLOWED_TYPES = ['image/jpeg', 'image/png', 'application/pdf']
    if mime not in ALLOWED_TYPES:
        raise ValidationError(f"Invalid file type: {mime}")

    # 3. Антивирус (опционально)
    # scan_with_clamav(file)

    return True
```
```

#### Критерии приёмки
- [ ] Создан `utils/fileValidator.js`
- [ ] Все upload компоненты используют validateFile()
- [ ] Backend валидация реализована
- [ ] Тест: попытка загрузки .exe с MIME image/jpeg отклоняется
- [ ] Тест: валидный JPEG загружается успешно

---

## Этап 2: Высокий приоритет (1-2 недели)

> **СРОК:** 2 недели
> **ОТВЕТСТВЕННЫЙ:** Frontend + Backend Teams
> **БЛОКИРУЕТ:** HIPAA сертификацию

---

### 2.1. Мигрировать с localStorage на httpOnly cookies

**Приоритет:** 🟠 HIGH
**Время:** 3 дня
**Файлы:** Весь authentication flow

#### Проблема

Токены в localStorage доступны JavaScript → XSS атаки могут украсть токены.

#### Решение

**Архитектурное решение:**

1. **Access token:** httpOnly cookie (устанавливается сервером)
2. **Refresh token:** httpOnly cookie (устанавливается сервером)
3. **User profile:** localStorage (не критично, можно восстановить с сервера)

**Шаг 1: Backend изменения**

```python
# backend/app/api/v1/endpoints/authentication.py

from fastapi import Response

@router.post("/login")
async def login(
    response: Response,  # Добавить Response
    credentials: LoginRequest
):
    # ... проверка credentials ...

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    # Устанавливаем httpOnly cookies вместо возврата в JSON
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,      # ✅ Недоступно JS
        secure=True,        # ✅ Только HTTPS
        samesite="lax",     # ✅ CSRF защита
        max_age=1800        # 30 минут
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=604800      # 7 дней
    )

    # Возвращаем только user data
    return {
        "user": user_schema,
        "message": "Login successful"
    }
```

**Шаг 2: Frontend изменения**

```javascript
// api/client.js - УБРАТЬ установку токенов
async function login(username, password) {
  const resp = await api.post('/auth/login', {
    username,
    password
  }, {
    withCredentials: true  // ✅ Отправлять cookies
  });

  // Токены уже в cookies, не нужно сохранять в localStorage
  // localStorage.setItem('auth_token', ...) ❌ УДАЛИТЬ

  return resp.data;
}

// Все запросы должны включать credentials
api.defaults.withCredentials = true;
```

**Шаг 3: Interceptors обновление**

```javascript
// api/interceptors.js

// УДАЛИТЬ добавление Authorization header
// Cookies отправляются автоматически

api.interceptors.request.use((config) => {
  // Authorization header больше не нужен - cookie автоматически
  // ❌ УДАЛИТЬ: config.headers['Authorization'] = `Bearer ${token}`;

  config.withCredentials = true;  // Включить cookies
  return config;
});

// Response interceptor - refresh токена
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      try {
        // Refresh token уже в cookie, просто вызываем endpoint
        await api.post('/auth/refresh', {}, {
          withCredentials: true
        });

        // Повторяем оригинальный запрос
        return api(error.config);
      } catch (refreshError) {
        // Refresh failed - redirect to login
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);
```

**Шаг 4: CORS настройки**

```python
# backend/app/main.py

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Frontend URL
    allow_credentials=True,  # ✅ Разрешить cookies
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Шаг 5: CSRF защита (опционально)**

Для дополнительной безопасности:

```python
# Backend: добавить CSRF token в отдельную cookie
response.set_cookie(
    key="csrf_token",
    value=generate_csrf_token(),
    httponly=False,  # Доступно JS для чтения
    secure=True,
    samesite="lax"
)

# Frontend: отправлять CSRF token в заголовке
api.interceptors.request.use((config) => {
  const csrfToken = getCookie('csrf_token');
  if (csrfToken) {
    config.headers['X-CSRF-Token'] = csrfToken;
  }
  return config;
});
```

#### Критерии приёмки
- [ ] Backend устанавливает httpOnly cookies
- [ ] Frontend не хранит токены в localStorage
- [ ] `withCredentials: true` на всех запросах
- [ ] CORS настроен с `allow_credentials: true`
- [ ] Логин/логаут работает
- [ ] Token refresh работает
- [ ] WebSocket подключения обновлены (cookies в handshake)

---

### 2.2. Добавить input sanitization для медицинских форм

**Приоритет:** 🟠 HIGH
**Время:** 2 дня
**Файлы:** `components/medical/EMRSystem.jsx`, все формы

#### Проблема

```javascript
// Прямой ввод без sanitization
<textarea
  value={emrData.complaints}
  onChange={(e) => handleFieldChange('complaints', e.target.value)}
/>
```

Пользователь может вставить JavaScript, HTML entities, Unicode control characters.

#### Решение

**Шаг 1: Библиотека для sanitization**

```bash
npm install dompurify
npm install --save-dev @types/dompurify
```

**Шаг 2: Утилита sanitization**

```javascript
// frontend/src/utils/sanitizer.js (НОВЫЙ ФАЙЛ)
import DOMPurify from 'dompurify';

/**
 * Sanitization для текстовых медицинских полей
 */
export function sanitizeMedicalText(text) {
  if (!text || typeof text !== 'string') return text;

  // 1. Удалить HTML tags (но сохранить текст)
  let sanitized = DOMPurify.sanitize(text, {
    ALLOWED_TAGS: [],  // Никаких HTML тегов
    KEEP_CONTENT: true
  });

  // 2. Удалить опасные Unicode символы (control characters)
  sanitized = sanitized.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]/g, '');

  // 3. Нормализовать пробелы
  sanitized = sanitized.replace(/\s+/g, ' ').trim();

  // 4. Ограничить длину (защита от DoS)
  const MAX_LENGTH = 50000;
  if (sanitized.length > MAX_LENGTH) {
    sanitized = sanitized.substring(0, MAX_LENGTH);
  }

  return sanitized;
}

/**
 * Sanitization для имён пациентов
 */
export function sanitizePatientName(name) {
  if (!name) return name;

  // Разрешить только буквы, пробелы, дефисы
  return name
    .replace(/[^а-яА-ЯёЁa-zA-Z\s\-]/g, '')
    .trim();
}

/**
 * Sanitization для телефонов
 */
export function sanitizePhone(phone) {
  if (!phone) return phone;

  // Только цифры, +, -, (, ), пробелы
  return phone.replace(/[^0-9\+\-\(\)\s]/g, '');
}

/**
 * Sanitization для email
 */
export function sanitizeEmail(email) {
  if (!email) return email;

  // Базовая очистка (окончательная валидация на сервере)
  return email
    .toLowerCase()
    .trim()
    .replace(/[<>]/g, '');
}
```

**Шаг 3: Использование в EMRSystem.jsx**

```javascript
import {
  sanitizeMedicalText,
  sanitizePatientName,
  sanitizePhone
} from '../../utils/sanitizer';

// Обновить handleFieldChange
const handleFieldChange = (field, value) => {
  let sanitizedValue = value;

  // Применить соответствующую sanitization
  if (['complaints', 'anamnesis', 'examination', 'diagnosis', 'treatment_plan'].includes(field)) {
    sanitizedValue = sanitizeMedicalText(value);
  }

  setEmrData(prev => ({
    ...prev,
    [field]: sanitizedValue
  }));
};

// При отправке на сервер - дополнительная проверка
const handleSave = async () => {
  const sanitizedData = {
    ...emrData,
    complaints: sanitizeMedicalText(emrData.complaints),
    anamnesis: sanitizeMedicalText(emrData.anamnesis),
    examination: sanitizeMedicalText(emrData.examination),
    // ... остальные поля
  };

  await api.post('/emr/save', sanitizedData);
};
```

**Шаг 4: Валидация на backend (обязательно!)**

Backend тоже должен очищать input:

```python
# backend/app/schemas/emr.py
from pydantic import BaseModel, validator
import bleach

class EMRCreate(BaseModel):
    complaints: str
    anamnesis: str
    examination: str

    @validator('complaints', 'anamnesis', 'examination')
    def sanitize_text(cls, v):
        if not v:
            return v
        # Удалить HTML
        cleaned = bleach.clean(v, tags=[], strip=True)
        # Ограничить длину
        return cleaned[:50000]
```

#### Критерии приёмки
- [ ] Установлен DOMPurify
- [ ] Создан `utils/sanitizer.js`
- [ ] Все медицинские формы используют sanitization
- [ ] Backend валидация обновлена
- [ ] Тест: ввод `<script>alert('xss')</script>` очищается
- [ ] Тест: Unicode control characters удаляются

---

### 2.3. Валидация AI-генерируемого контента

**Приоритет:** 🟠 HIGH
**Время:** 2 дня
**Файлы:** `components/medical/EMRSystem.jsx`, AI компоненты

#### Проблема

```javascript
// Строки 156-160
if (result.findings) {
  const aiAnalysis = `\n\nAI Анализ изображения "${attachment.name}":\n${result.findings}`;
  handleFieldChange('examination', emrData.examination + aiAnalysis);
}
```

AI output вставляется напрямую без валидации.

#### Решение

**Шаг 1: Валидатор AI контента**

```javascript
// frontend/src/utils/aiValidator.js (НОВЫЙ ФАЙЛ)

/**
 * Проверка AI output на безопасность и корректность
 */
export function validateAIOutput(aiText, context = {}) {
  const warnings = [];
  const errors = [];

  // 1. Базовая sanitization
  const sanitized = sanitizeMedicalText(aiText);

  // 2. Проверка на минимальную/максимальную длину
  if (sanitized.length < 10) {
    errors.push('AI ответ слишком короткий (возможна ошибка генерации)');
  }
  if (sanitized.length > 10000) {
    warnings.push('AI ответ очень длинный');
  }

  // 3. Проверка на повторения (признак hallucination)
  const words = sanitized.split(/\s+/);
  const uniqueWords = new Set(words);
  if (words.length > 50 && uniqueWords.size < words.length * 0.3) {
    warnings.push('Обнаружены повторяющиеся фразы - возможна галлюцинация AI');
  }

  // 4. Проверка на вредоносные паттерны
  const dangerousPatterns = [
    /javascript:/i,
    /<script/i,
    /onclick=/i,
    /onerror=/i,
    /eval\(/i
  ];

  for (const pattern of dangerousPatterns) {
    if (pattern.test(sanitized)) {
      errors.push('AI output содержит потенциально опасный контент');
      break;
    }
  }

  // 5. Проверка на медицинские disclaimer
  const hasDisclaimer = /AI|искусственный интеллект|автоматически/i.test(sanitized);
  if (!hasDisclaimer) {
    warnings.push('Рекомендуется добавить пометку об AI-генерации');
  }

  return {
    sanitized,
    valid: errors.length === 0,
    errors,
    warnings
  };
}

/**
 * Форматирование AI output для вставки в медицинскую запись
 */
export function formatAIOutput(aiText, metadata = {}) {
  const validation = validateAIOutput(aiText);

  if (!validation.valid) {
    throw new Error(`AI output validation failed: ${validation.errors.join(', ')}`);
  }

  // Добавить metadata и disclaimer
  const timestamp = new Date().toLocaleString('ru-RU');
  const formatted = `
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 AI АНАЛИЗ (Требуется верификация врачом)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Время: ${timestamp}
Модель: ${metadata.model || 'Unknown'}
Изображение: ${metadata.imageName || 'N/A'}

${validation.sanitized}

⚠️ ВНИМАНИЕ: Данный анализ создан искусственным интеллектом и требует обязательной проверки и подтверждения врачом.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
`;

  return {
    formatted,
    warnings: validation.warnings
  };
}
```

**Шаг 2: Использование в EMRSystem.jsx**

```javascript
import { formatAIOutput } from '../../utils/aiValidator';

// Строки 156-160 - ЗАМЕНИТЬ
const handleAIAnalysis = async (attachment, result) => {
  try {
    // Валидация и форматирование
    const { formatted, warnings } = formatAIOutput(result.findings, {
      model: 'GPT-4 Vision',
      imageName: attachment.name
    });

    // Показать warnings если есть
    if (warnings.length > 0) {
      showWarningDialog({
        title: 'Предупреждения AI анализа',
        message: warnings.join('\n'),
        onContinue: () => {
          handleFieldChange('examination', emrData.examination + '\n\n' + formatted);
        }
      });
    } else {
      handleFieldChange('examination', emrData.examination + '\n\n' + formatted);
    }

    // Логирование для аудита
    logAIUsage({
      action: 'ai_image_analysis',
      patient_id: appointment?.patient_id,
      doctor_id: currentUser?.id,
      timestamp: new Date().toISOString(),
      image: attachment.name,
      model: 'GPT-4 Vision'
    });

  } catch (error) {
    setError(`Ошибка валидации AI анализа: ${error.message}`);
  }
};
```

**Шаг 3: Backend audit logging**

```python
# backend/app/models/ai_usage_log.py

class AIUsageLog(Base):
    __tablename__ = "ai_usage_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    patient_id = Column(Integer, ForeignKey("patients.id"))
    action = Column(String)  # 'ai_image_analysis', 'ai_diagnosis', etc.
    model = Column(String)
    input_data = Column(Text)  # Sanitized
    output_data = Column(Text)  # Sanitized
    timestamp = Column(DateTime, default=datetime.utcnow)
    verified_by_doctor = Column(Boolean, default=False)
    verification_timestamp = Column(DateTime, nullable=True)
```

#### Критерии приёмки
- [ ] Создан `utils/aiValidator.js`
- [ ] AI output проходит валидацию перед вставкой
- [ ] Добавлен disclaimer об AI-генерации
- [ ] Backend logging для AI usage
- [ ] UI показывает warnings при подозрительном output
- [ ] Тест: AI output с `<script>` отклоняется

---

### 2.4. Добавить защиту на unprotected routes

**Приоритет:** 🟠 HIGH
**Время:** 1 день
**Файлы:** `App.jsx`

#### Проблема

```javascript
// Строка 1156 - нет защиты
<Route path="/queue/join" element={<QueueJoin />} />
```

#### Решение

```javascript
// App.jsx

// Определить какие роли могут присоединяться к очереди
<Route
  path="/queue/join"
  element={
    <RequireAuth roles={['Patient', 'Registrar']}>
      <QueueJoin />
    </RequireAuth>
  }
/>

// Альтернатива: если это публичный endpoint для пациентов
// с QR кодами, добавить token validation внутри QueueJoin
```

**Аудит всех routes:**

```javascript
// Создать скрипт для аудита routes
// frontend/scripts/audit-routes.js

import fs from 'fs';
import path from 'path';

const appJsxPath = path.join(process.cwd(), 'src', 'App.jsx');
const content = fs.readFileSync(appJsxPath, 'utf-8');

// Найти все <Route> без RequireAuth
const routeRegex = /<Route\s+path="([^"]+)"\s+element={<(\w+)/g;
const matches = [...content.matchAll(routeRegex)];

const unprotectedRoutes = matches.filter(match => {
  const [fullMatch, path, component] = match;
  // Проверить нет ли RequireAuth перед Route
  const index = content.indexOf(fullMatch);
  const before = content.substring(Math.max(0, index - 200), index);
  return !before.includes('RequireAuth');
});

console.log('Unprotected routes:');
unprotectedRoutes.forEach(([, path, component]) => {
  console.log(`  ${path} → ${component}`);
});
```

Запустить:
```bash
node scripts/audit-routes.js
```

#### Критерии приёмки
- [ ] Все protected routes имеют RequireAuth
- [ ] Public routes документированы и обоснованы
- [ ] Скрипт audit-routes.js создан
- [ ] CI/CD проверка на unprotected routes

---

### 2.5. Исправить soft role checking

**Приоритет:** 🟠 HIGH
**Время:** 1 день
**Файлы:** `App.jsx`

#### Проблема

```javascript
// Строки 158-160
if (!profile?.roles || profile.roles.length === 0) {
  return true; // ❌ Разрешает доступ без ролей!
}
```

#### Решение

```javascript
// App.jsx - строки 150-205

function RequireAuth({ roles, children }) {
  const [loading, setLoading] = useState(true);
  const [authorized, setAuthorized] = useState(false);

  useEffect(() => {
    async function checkAuth() {
      const token = tokenManager.getAccessToken();

      // Нет токена = нет доступа
      if (!token) {
        setAuthorized(false);
        setLoading(false);
        return;
      }

      try {
        // Загрузить профиль
        const profileResponse = await api.get('/auth/me');
        const profile = profileResponse.data;
        setProfile(profile);

        // СТРОГАЯ ПРОВЕРКА РОЛЕЙ
        if (!profile || !profile.roles || profile.roles.length === 0) {
          // ❌ НЕТ РОЛЕЙ = НЕТ ДОСТУПА
          console.warn('User has no roles assigned');
          setAuthorized(false);
          setLoading(false);
          return;
        }

        // Если роли не указаны - требуется хотя бы одна роль
        if (!roles || roles.length === 0) {
          setAuthorized(profile.roles.length > 0);
        } else {
          // Проверка конкретных ролей
          const hasRequiredRole = profile.roles.some(userRole =>
            roles.includes(userRole)
          );
          setAuthorized(hasRequiredRole);
        }

      } catch (error) {
        console.error('Auth check failed:', error);
        setAuthorized(false);
      } finally {
        setLoading(false);
      }
    }

    checkAuth();
  }, [roles]);

  if (loading) {
    return <div>Проверка доступа...</div>;
  }

  if (!authorized) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
}
```

#### Критерии приёмки
- [ ] Пользователи без ролей не получают доступ
- [ ] Пользователи с неправильными ролями перенаправляются
- [ ] Логируются попытки несанкционированного доступа
- [ ] Тест: user без ролей → редирект на /login
- [ ] Тест: user с ролью 'Patient' не может на /admin

---

### 2.6. Удалить hardcoded localhost URLs

**Приоритет:** 🟠 HIGH
**Время:** 2 дня
**Файлы:** 27 файлов

#### Проблема

65 вхождений `http://localhost:18000` в коде.

#### Решение

**Шаг 1: Централизованная конфигурация**

```javascript
// frontend/src/config/api.js (НОВЫЙ ФАЙЛ)

/**
 * API конфигурация с fallback логикой
 */
export const API_CONFIG = {
  // Базовый URL API
  BASE_URL: import.meta.env.VITE_API_BASE_URL || getDefaultApiUrl(),

  // WebSocket URL
  WS_URL: import.meta.env.VITE_WS_URL || getDefaultWsUrl(),

  // Timeout для запросов
  TIMEOUT: parseInt(import.meta.env.VITE_API_TIMEOUT) || 30000,
};

/**
 * Определить дефолтный API URL на основе окружения
 */
function getDefaultApiUrl() {
  // Production
  if (import.meta.env.PROD) {
    // Предполагаем что API на том же домене
    return `${window.location.origin}/api/v1`;
  }

  // Development
  return 'http://localhost:18000/api/v1';
}

/**
 * Определить дефолтный WebSocket URL
 */
function getDefaultWsUrl() {
  if (import.meta.env.PROD) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}/ws`;
  }

  return 'ws://localhost:18000/ws';
}

export default API_CONFIG;
```

**Шаг 2: .env файлы**

```bash
# frontend/.env.development
VITE_API_BASE_URL=http://localhost:18000/api/v1
VITE_WS_URL=ws://localhost:18000/ws

# frontend/.env.production
VITE_API_BASE_URL=/api/v1
VITE_WS_URL=/ws

# frontend/.env.staging (опционально)
VITE_API_BASE_URL=https://staging.clinic.com/api/v1
VITE_WS_URL=wss://staging.clinic.com/ws
```

**Шаг 3: Обновить api/client.js**

```javascript
// БЫЛО
const API_BASE = 'http://localhost:18000/api/v1'; // ❌

// СТАЛО
import API_CONFIG from '../config/api';

const api = axios.create({
  baseURL: API_CONFIG.BASE_URL,  // ✅
  timeout: API_CONFIG.TIMEOUT,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true
});
```

**Шаг 4: Обновить LoginFormStyled.jsx**

```javascript
// БЫЛО (строка 79)
const response = await fetch('http://localhost:18000/api/v1/auth/minimal-login', ...); // ❌

// СТАЛО
import API_CONFIG from '../../config/api';

const response = await fetch(`${API_CONFIG.BASE_URL}/auth/minimal-login`, {  // ✅
  method: 'POST',
  ...
});
```

**Шаг 5: Массовая замена**

```bash
# Поиск всех hardcoded URLs
grep -r "http://localhost" frontend/src/ --include="*.jsx" --include="*.js"

# Для каждого файла:
# 1. Импортировать API_CONFIG
# 2. Заменить hardcoded URL на API_CONFIG.BASE_URL
```

Список файлов для обновления (27 файлов):
- `api/client.js`
- `components/auth/LoginFormStyled.jsx`
- `api/mcpClient.js`
- `hooks/usePayments.js`
- `services/queue.js`
- `utils/queueApi.js`
- ... и т.д.

#### Критерии приёмки
- [ ] Создан `config/api.js`
- [ ] `.env.development` и `.env.production` настроены
- [ ] 0 вхождений `http://localhost` в src/ (кроме комментариев)
- [ ] Dev режим работает с localhost
- [ ] Production build использует относительные URLs
- [ ] WebSocket подключение работает в обоих режимах

---

## Этап 3: Средний приоритет (2-4 недели)

> **СРОК:** 1 месяц
> **ОТВЕТСТВЕННЫЙ:** Full Team

---

### 3.1. Реализовать HIPAA audit logging

**Приоритет:** 🟡 MEDIUM (но критично для HIPAA)
**Время:** 5 дней
**Файлы:** Все медицинские компоненты

#### Решение

```javascript
// frontend/src/utils/auditLogger.js (НОВЫЙ ФАЙЛ)

/**
 * HIPAA Audit Logger
 * Логирует все доступы к PHI (Protected Health Information)
 */
export class AuditLogger {
  static async log(event) {
    const auditEntry = {
      timestamp: new Date().toISOString(),
      user_id: getCurrentUserId(),
      user_role: getCurrentUserRole(),
      event_type: event.type,
      resource_type: event.resourceType,
      resource_id: event.resourceId,
      action: event.action,
      ip_address: await getClientIP(),
      user_agent: navigator.userAgent,
      success: event.success ?? true,
      details: event.details
    };

    try {
      await api.post('/audit/log', auditEntry, {
        // Отправлять даже если основной запрос failed
        skipAuthRedirect: true
      });
    } catch (error) {
      // Fallback - localStorage queue
      const queue = JSON.parse(localStorage.getItem('audit_queue') || '[]');
      queue.push(auditEntry);
      localStorage.setItem('audit_queue', JSON.stringify(queue));
    }
  }

  // Специфичные методы для разных действий
  static async logPatientView(patientId) {
    await this.log({
      type: 'ACCESS',
      resourceType: 'PATIENT',
      resourceId: patientId,
      action: 'VIEW'
    });
  }

  static async logEMRModification(patientId, emrId, changes) {
    await this.log({
      type: 'MODIFICATION',
      resourceType: 'EMR',
      resourceId: emrId,
      action: 'UPDATE',
      details: {
        patient_id: patientId,
        fields_changed: Object.keys(changes)
      }
    });
  }

  static async logFileDownload(fileId, fileName) {
    await this.log({
      type: 'ACCESS',
      resourceType: 'MEDICAL_FILE',
      resourceId: fileId,
      action: 'DOWNLOAD',
      details: { file_name: fileName }
    });
  }
}
```

**Использование в компонентах:**

```javascript
// EMRSystem.jsx
import { AuditLogger } from '../../utils/auditLogger';

// При открытии EMR
useEffect(() => {
  if (appointment?.patient_id) {
    AuditLogger.logPatientView(appointment.patient_id);
  }
}, [appointment]);

// При сохранении EMR
const handleSave = async () => {
  const changes = getChangedFields(originalData, emrData);

  await api.post('/emr/save', emrData);

  await AuditLogger.logEMRModification(
    appointment.patient_id,
    emr.id,
    changes
  );
};
```

#### Критерии приёмки
- [ ] AuditLogger реализован
- [ ] Логируются: просмотр пациентов, изменение EMR, скачивание файлов
- [ ] Backend сохраняет audit logs в БД
- [ ] Audit logs недоступны для удаления/изменения
- [ ] Админ панель для просмотра audit trail

---

### 3.2. Добавить Content Security Policy

**Приоритет:** 🟡 MEDIUM
**Время:** 2 дня

#### Решение

```html
<!-- frontend/index.html -->
<meta http-equiv="Content-Security-Policy" content="
  default-src 'self';
  script-src 'self' 'unsafe-inline' 'unsafe-eval';
  style-src 'self' 'unsafe-inline';
  img-src 'self' data: blob: https:;
  font-src 'self' data:;
  connect-src 'self' ws://localhost:18000 wss://localhost:18000;
  frame-ancestors 'none';
  base-uri 'self';
  form-action 'self';
">
```

Постепенно ужесточать (убрать 'unsafe-inline', 'unsafe-eval').

---

### 3.3. Консолидировать RequireAuth implementations

**Приоритет:** 🟡 MEDIUM
**Время:** 1 день

Удалить дублирование между `App.jsx` и `RequireAuth.jsx`.

---

### 3.4. Оптимизация bundle size

**Приоритет:** 🟡 MEDIUM
**Время:** 3 дня

- Анализ bundle с `npm run analyze`
- Tree-shaking неиспользуемого кода
- Dynamic imports для крупных библиотек

---

## Этап 4: Долгосрочные улучшения (1-3 месяца)

### 4.1. HIPAA Compliance Certification
### 4.2. Zero-knowledge Architecture
### 4.3. Security Penetration Testing
### 4.4. Rate Limiting & DDoS Protection
### 4.5. Multi-Factor для критичных операций

---

## План тестирования

### Unit Tests

```bash
# Запустить тесты
npm run test

# Тесты для новых утилит
npm run test -- --grep "tokenManager"
npm run test -- --grep "fileValidator"
npm run test -- --grep "sanitizer"
```

### E2E Tests

```bash
# Playwright тесты
npm run test:e2e

# Специфичные сценарии
# 1. Login flow с httpOnly cookies
# 2. File upload validation
# 3. AI content validation
# 4. Role-based access control
```

### Security Tests

```bash
# XSS тесты
# CSRF тесты
# File upload bypass тесты
# Token theft simulation
```

---

## Критерии завершения

### Этап 1 (Critical)
- [ ] 0 hardcoded credentials
- [ ] Единый token key во всём коде
- [ ] 0 console.log с PHI в production
- [ ] 0 critical npm vulnerabilities
- [ ] Blob URLs освобождаются корректно
- [ ] File validation реализована
- [ ] Hardcoded patient data удалён

### Этап 2 (High)
- [ ] httpOnly cookies внедрены
- [ ] Input sanitization работает
- [ ] AI output валидируется
- [ ] Все routes защищены
- [ ] Soft role checking исправлен
- [ ] 0 hardcoded localhost URLs

### Этап 3 (Medium)
- [ ] Audit logging работает
- [ ] CSP настроен
- [ ] RequireAuth консолидирован
- [ ] Bundle size оптимизирован

### Этап 4 (Long-term)
- [ ] HIPAA сертификация получена
- [ ] Penetration testing пройден
- [ ] Production ready

---

## Отслеживание прогресса

### GitHub Issues

Создать issues для каждой задачи:

```
[CRITICAL] Remove hardcoded credentials (#1)
[CRITICAL] Fix token key inconsistency (#2)
[CRITICAL] Remove PHI logging (#3)
...
```

### Milestones

- Milestone 1: Critical Fixes (Week 1)
- Milestone 2: High Priority (Week 2-3)
- Milestone 3: Medium Priority (Week 4-6)
- Milestone 4: HIPAA Ready (Month 3)

---

## Контакты и ответственные

**Frontend Team Lead:** [Имя]
**Backend Team Lead:** [Имя]
**Security Officer:** [Имя]
**HIPAA Compliance Officer:** [Имя]

---

**Версия документа:** 1.0
**Последнее обновление:** 2025-12-06
**Следующий review:** 2025-12-13