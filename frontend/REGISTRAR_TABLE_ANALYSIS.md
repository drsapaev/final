# 🔍 Анализ проблем с таблицами в панели регистратуры

## 🚨 ВЫЯВЛЕННЫЕ ПРОБЛЕМЫ

### 1. **Двойная инициализация данных**
**Проблема:** В `RegistrarPanel.jsx` данные инициализируются дважды:

```javascript
// Строки 57-137: Хардкод демо-данных в useState
const [appointments, setAppointments] = useState([
  // 6 тестовых записей с хардкодом
]);

// Строки 501-518: API загрузка
const loadAppointments = async () => {
  const response = await fetch('/api/v1/appointments/?limit=50');
  if (response.ok) {
    const data = await response.json();
    setAppointments(data); // ПЕРЕЗАПИСЫВАЕТ демо-данные
  }
};
```

**Результат:** Таблица то показывает демо-данные (при ошибке API), то реальные данные (при успешном API).

### 2. **Проблемы с аутентификацией**
**API ответ:** `{"detail":"Not authenticated"}`

**Причина:** 
- Токен аутентификации отсутствует или недействителен
- API требует авторизации, но фронтенд не передает корректный токен

### 3. **Конфликт между демо и реальными данными**
```javascript
// useEffect вызывает ОБЕ функции одновременно
useEffect(() => {
  loadAppointments();        // Может упасть с 401
  loadIntegratedData();      // Может упасть с 401
}, []);
```

### 4. **Отсутствие обработки ошибок**
```javascript
// В loadAppointments НЕТ обработки ошибок для setAppointments
if (response.ok) {
  const data = await response.json();
  setAppointments(data); // Если data пустой - таблица пустая
}
// Если НЕ ok - appointments остаются демо-данными
```

## 🎯 КОРНЕВЫЕ ПРИЧИНЫ

### A. **Race Condition между демо и API данными**
1. Компонент загружается с демо-данными
2. API вызов может быть успешным или неуспешным
3. Если успешный - демо-данные заменяются на API данные
4. Если неуспешный - остаются демо-данные
5. **Результат:** Непредсказуемое поведение

### B. **Проблемы с токеном аутентификации**
```javascript
headers: { 'Authorization': `Bearer ${localStorage.getItem('auth_token')}` }
```
- Токен может быть `null`, `undefined`, или устаревшим
- Нет проверки валидности токена перед запросом

### C. **Отсутствие fallback стратегии**
- Нет четкого разделения между демо-режимом и продакшн-режимом
- Нет индикации пользователю о том, какие данные показываются

## 🔧 ПЛАН ИСПРАВЛЕНИЯ

### 1. **Создать единую стратегию загрузки данных**
```javascript
const [dataSource, setDataSource] = useState('loading'); // 'demo' | 'api' | 'loading' | 'error'
const [appointments, setAppointments] = useState([]);
```

### 2. **Исправить логику загрузки**
```javascript
const loadAppointments = async () => {
  try {
    setAppointmentsLoading(true);
    setDataSource('loading');
    
    const token = localStorage.getItem('auth_token');
    if (!token) {
      setDataSource('demo');
      setAppointments(DEMO_APPOINTMENTS);
      return;
    }
    
    const response = await fetch('/api/v1/appointments/?limit=50', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    
    if (response.ok) {
      const data = await response.json();
      setAppointments(Array.isArray(data) ? data : data.items || []);
      setDataSource('api');
    } else if (response.status === 401) {
      // Токен недействителен
      localStorage.removeItem('auth_token');
      setDataSource('demo');
      setAppointments(DEMO_APPOINTMENTS);
    } else {
      throw new Error(`API Error: ${response.status}`);
    }
  } catch (error) {
    console.error('Ошибка загрузки записей:', error);
    setDataSource('demo');
    setAppointments(DEMO_APPOINTMENTS);
  } finally {
    setAppointmentsLoading(false);
  }
};
```

### 3. **Добавить индикацию источника данных**
```javascript
{dataSource === 'demo' && (
  <div className="demo-indicator">
    ⚠️ Показаны демо-данные. Проверьте подключение к серверу.
  </div>
)}
```

### 4. **Исправить проблемы с бэкендом**
- Проверить работу аутентификации
- Убедиться что API `/appointments` возвращает корректные данные
- Добавить логирование запросов

## 📊 ТЕКУЩЕЕ СОСТОЯНИЕ

### ✅ Что работает:
- Демо-данные отображаются корректно
- UI компонентов функционален
- Таблица рендерится без ошибок

### ❌ Что не работает:
- API аутентификация (401 ошибки)
- Стабильная загрузка данных
- Четкое разделение демо/продакшн режимов
- Обработка ошибок API

### 🔄 Непредсказуемое поведение:
- Таблица то показывает демо-данные, то пустая
- Зависит от состояния API и токена
- Нет индикации пользователю о проблемах

## 🚀 РЕКОМЕНДАЦИИ

1. **Немедленно:** Исправить логику загрузки данных
2. **Критично:** Решить проблемы с аутентификацией
3. **Важно:** Добавить индикацию источника данных
4. **Желательно:** Создать отдельный демо-режим
