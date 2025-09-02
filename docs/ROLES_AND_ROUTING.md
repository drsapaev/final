# Система ролей и маршрутизации

## 🎯 Критические пользователи и их роли

| Пользователь | Пароль | Роль | Маршрут | Описание |
|-------------|--------|------|---------|----------|
| admin | admin123 | Admin | /admin | Администратор системы |
| registrar | registrar123 | Registrar | /registrar-panel | Регистратура |
| lab | lab123 | Lab | /lab-panel | Лаборатория |
| doctor | doctor123 | Doctor | /doctor-panel | Врач общей практики |
| cashier | cashier123 | Cashier | /cashier | Касса |
| cardio | cardio123 | cardio | /cardiologist | Кардиолог |
| derma | derma123 | derma | /dermatologist | Дерматолог-косметолог |
| dentist | dentist123 | dentist | /dentist | Стоматолог |

## 🛡️ Защищенные маршруты

### Frontend маршруты (App.jsx)
```javascript
// КРИТИЧЕСКИ ВАЖНО: Не изменять роли без обновления тестов!
<Route path="cardiologist" element={<RequireAuth roles={['Admin','Doctor','cardio']}><CardiologistPanel /></RequireAuth>} />
<Route path="dermatologist" element={<RequireAuth roles={['Admin','Doctor','derma']}><DermatologistPanel /></RequireAuth>} />
<Route path="dentist" element={<RequireAuth roles={['Admin','Doctor','dentist']}><DentistPanel /></RequireAuth>} />
```

### Backend API endpoints
```python
# КРИТИЧЕСКИ ВАЖНО: Синхронизировать с frontend ролями!
user: User = Depends(deps.require_roles("Admin", "Doctor", "cardio"))  # Cardio API
user: User = Depends(deps.require_roles("Admin", "Doctor", "derma"))   # Derma API  
user: User = Depends(deps.require_roles("Admin", "Doctor", "dentist")) # Dental API
```

## 🔄 Функции перенаправления

### Login.jsx - pickRouteForRoleCached()
```javascript
// КРИТИЧЕСКИ ВАЖНО: Синхронизировать с маршрутами!
if (role === 'cardio') return '/cardiologist';
if (role === 'derma') return '/dermatologist';
if (role === 'dentist') return '/dentist';
```

### UserSelect.jsx - routeForRole()
```javascript
// КРИТИЧЕСКИ ВАЖНО: Синхронизировать с Login.jsx!
if (r === 'cardio') return '/cardiologist';
if (r === 'derma') return '/dermatologist';
if (r === 'dentist') return '/dentist';
```

## ⚠️ Правила изменений

### ❌ НЕ ДЕЛАТЬ:
1. **Не изменять роли** без обновления всех связанных файлов
2. **Не удалять пользователей** cardio, derma, dentist
3. **Не изменять маршруты** без обновления функций перенаправления
4. **Не изменять пароли** без обновления документации

### ✅ ОБЯЗАТЕЛЬНО ДЕЛАТЬ:
1. **Запускать тесты** после каждого изменения: `python test_role_routing.py`
2. **Обновлять документацию** при добавлении новых ролей
3. **Синхронизировать** frontend и backend роли
4. **Тестировать логин** для всех ролей после изменений

## 🧪 Автоматическое тестирование

### Запуск тестов:
```bash
cd backend
python test_role_routing.py
```

### Что тестируется:
- ✅ Логин всех критических пользователей
- ✅ Корректность ролей в профилях
- ✅ Доступность специализированных API
- ✅ Соответствие ролей ожидаемым значениям

## 🚨 Критические файлы для синхронизации

При изменении системы ролей ОБЯЗАТЕЛЬНО обновить:

1. **Frontend:**
   - `frontend/src/App.jsx` - маршруты RequireAuth
   - `frontend/src/pages/Login.jsx` - pickRouteForRoleCached()
   - `frontend/src/pages/UserSelect.jsx` - routeForRole()

2. **Backend:**
   - `backend/app/api/v1/endpoints/cardio.py` - require_roles
   - `backend/app/api/v1/endpoints/derma.py` - require_roles  
   - `backend/app/api/v1/endpoints/dental.py` - require_roles

3. **База данных:**
   - Таблица `users` - роли пользователей
   - Пароли пользователей

4. **Тесты:**
   - `backend/test_role_routing.py` - список пользователей и ролей

## 📋 Чек-лист перед коммитом

- [ ] Запущены тесты: `python test_role_routing.py`
- [ ] Все тесты прошли успешно
- [ ] Обновлена документация
- [ ] Синхронизированы frontend и backend роли
- [ ] Проверен логин для всех ролей
- [ ] Обновлены пароли в документации (если изменены)
