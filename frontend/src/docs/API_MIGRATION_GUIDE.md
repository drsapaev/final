# 🔗 Руководство по миграции на унифицированную API интеграцию

## 📋 Обзор

Это руководство поможет вам мигрировать существующие компоненты с прямых `fetch` запросов на унифицированную систему API интеграции.

## 🎯 Цели миграции

- ✅ Унификация API вызовов
- ✅ Централизованная обработка ошибок
- ✅ Автоматическое управление состоянием загрузки
- ✅ Валидация форм
- ✅ Кэширование данных
- ✅ WebSocket интеграция

## 🔄 Пошаговая миграция

### Шаг 1: Замена прямых fetch запросов

#### ❌ Было:
```javascript
const [data, setData] = useState([]);
const [loading, setLoading] = useState(false);
const [error, setError] = useState(null);

const loadData = async () => {
  try {
    setLoading(true);
    const response = await fetch('/api/v1/patients', {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (response.ok) {
      setData(await response.json());
    }
  } catch (err) {
    setError(err.message);
  } finally {
    setLoading(false);
  }
};
```

#### ✅ Стало:
```javascript
import { usePatients } from '../hooks/useApi';

const { data, loading, error, refresh } = usePatients();
```

### Шаг 2: Унификация отправки форм

#### ❌ Было:
```javascript
const handleSubmit = async (formData) => {
  try {
    setLoading(true);
    const response = await fetch('/api/v1/patients', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify(formData)
    });
    
    if (!response.ok) {
      throw new Error('Ошибка создания');
    }
    
    toast.success('Создано успешно');
  } catch (error) {
    toast.error(error.message);
  } finally {
    setLoading(false);
  }
};
```

#### ✅ Стало:
```javascript
import { useFormSubmit } from '../hooks/useApi';
import { validators, validateForm } from '../utils/errorHandler';

const { submitForm, loading } = useFormSubmit();

const handleSubmit = async (formData) => {
  await submitForm('/patients', formData, {
    validate: (data) => {
      const { isValid, errors } = validateForm(data, {
        full_name: [validators.required],
        phone: [validators.required, validators.phone]
      });
      return isValid ? null : Object.values(errors)[0];
    }
  });
};
```

### Шаг 3: Обработка ошибок

#### ❌ Было:
```javascript
.catch(error => {
  console.error('Error:', error);
  toast.error('Произошла ошибка');
});
```

#### ✅ Стало:
```javascript
import { useErrorHandler } from '../utils/errorHandler';

const handleError = useErrorHandler('PatientComponent');

// Автоматическая обработка в хуках или:
.catch(error => handleError(error));
```

## 📚 Доступные хуки

### useApiData
Универсальный хук для загрузки данных:
```javascript
const { data, loading, error, refresh } = useApiData('/endpoint', {
  params: { limit: 10 },
  fallbackData: [],
  autoLoad: true
});
```

### usePatients
Специализированный хук для пациентов:
```javascript
const { data: patients, loading, refresh } = usePatients('Cardio');
```

### useAppointments
Хук для записей/визитов:
```javascript
const { data: appointments, loading } = useAppointments({ 
  department: 'Cardio', 
  limit: 50 
});
```

### useFormSubmit
Хук для отправки форм:
```javascript
const { submitForm, loading, error } = useFormSubmit();

await submitForm('/endpoint', data, {
  method: 'POST',
  validate: (data) => /* валидация */,
  transform: (data) => /* трансформация */
});
```

### useWebSocket
Хук для WebSocket соединений:
```javascript
const { connected, lastMessage, sendMessage } = useWebSocket(url, {
  onMessage: (msg) => console.log(msg),
  autoConnect: true
});
```

## 🔧 Валидация форм

### Встроенные валидаторы:
```javascript
import { validators } from '../utils/errorHandler';

const rules = {
  email: [validators.required, validators.email],
  phone: [validators.required, validators.phone],
  name: [validators.required, validators.minLength(2)],
  age: [validators.required, validators.number, validators.positive]
};
```

### Кастомные валидаторы:
```javascript
const customValidator = (value, fieldName) => {
  if (value < 18) {
    return `${fieldName} должен быть больше 18`;
  }
  return null;
};
```

## 🚀 Примеры миграции компонентов

### Компоненты для миграции:

1. **LabPanel.jsx** - заменить fetch на useApiData
2. **DermatologistPanelUnified.jsx** - использовать usePatients
3. **DentistPanelUnified.jsx** - унифицировать загрузку данных
4. **RegistrarPanel.jsx** - заменить на useAppointments
5. **CardiologistPanelUnified.jsx** - использовать новые хуки

### Пример миграции LabPanel:

#### ❌ Было:
```javascript
const loadPatients = async () => {
  try {
    setLoading(true);
    const res = await fetch('/api/v1/patients?department=Lab&limit=100', { 
      headers: authHeader() 
    });
    if (res.ok) setPatients(await res.json());
  } catch {
    // Игнорируем ошибки
  } finally { 
    setLoading(false); 
  }
};
```

#### ✅ Стало:
```javascript
import { usePatients } from '../hooks/useApi';

const { data: patients, loading, error } = usePatients('Lab');
```

## 📊 Чек-лист миграции

### Для каждого компонента:

- [ ] Заменить прямые fetch на хуки useApi
- [ ] Удалить дублированную логику авторизации
- [ ] Заменить ручное управление состоянием
- [ ] Добавить валидацию форм
- [ ] Использовать централизованную обработку ошибок
- [ ] Протестировать функциональность
- [ ] Обновить документацию компонента

### Глобальные изменения:

- [ ] Настроить interceptors в main.jsx
- [ ] Добавить обработчик ошибок в App.jsx
- [ ] Создать типы для TypeScript (если используется)
- [ ] Обновить тесты компонентов
- [ ] Добавить E2E тесты для критичных флоу

## 🔍 Отладка

### Логирование API запросов:
```javascript
// В development режиме автоматически логируются все запросы
// Для дополнительной отладки:
const { data, loading, error } = useApiData('/endpoint', {
  onSuccess: (data) => console.log('Loaded:', data),
  onError: (error) => console.error('Failed:', error)
});
```

### Проверка сетевых запросов:
1. Откройте DevTools → Network
2. Проверьте заголовки Authorization
3. Убедитесь в корректности URL и параметров
4. Проверьте коды ответов и сообщения об ошибках

## 🎯 Результат миграции

После миграции вы получите:

- 📦 **Меньше кода** - убрано дублирование
- 🐛 **Меньше багов** - унифицированная обработка ошибок
- 🚀 **Лучшую производительность** - автоматическое кэширование
- 🔧 **Проще поддержка** - централизованная логика API
- 🧪 **Проще тестирование** - мокирование хуков
- 📱 **Лучший UX** - консистентные состояния загрузки

## 📞 Поддержка

При возникновении проблем:
1. Проверьте консоль браузера на ошибки
2. Убедитесь в правильности импортов
3. Проверьте сетевые запросы в DevTools
4. Обратитесь к примерам в `RefactoredComponent.jsx`
