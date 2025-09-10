# Система ролей и маршрутизации

## 🎯 Критические пользователи и их роли

| Пользователь | Пароль | Роль | Маршрут | Описание |
|-------------|--------|------|---------|----------|
| admin | admin123 | Admin | /admin | Администратор системы |
| registrar | registrar123 | Registrar | /registrar-panel | Регистратура |
| lab | lab123 | Lab | /lab-panel | Лаборатория |
| doctor | doctor123 | Doctor | /doctor-panel | Врач общей практики |
| cashier | cashier123 | Cashier | /cashier-panel | Касса |
| cardio | cardio123 | cardio | /cardiologist | Кардиолог |
| derma | derma123 | derma | /dermatologist | Дерматолог-косметолог |
| dentist | dentist123 | dentist | /dentist | Стоматолог |

## 🔐 Система ролей и разрешений (НОВОЕ)

### Базовые роли в системе управления пользователями:
- **Admin** - Полный доступ ко всем функциям
- **Doctor** - Доступ к пациентам, записям, EMR, аналитике
- **Nurse** - Доступ к записям и расписанию
- **Receptionist** - Доступ к записям, платежам, расписанию
- **Patient** - Доступ к своему профилю и записям

### Разрешения по категориям:
- **users:** - Управление пользователями
- **profile:** - Управление профилями
- **patients:** - Управление пациентами
- **appointments:** - Управление записями
- **emr:** - Медицинские карты
- **payments:** - Платежи
- **analytics:** - Аналитика и отчеты
- **settings:** - Настройки системы
- **audit:** - Аудит действий
- **export:** - Экспорт данных

## 🛡️ Защищенные маршруты

### Frontend маршруты (App.jsx)
```javascript
// КРИТИЧЕСКИ ВАЖНО: Не изменять роли без обновления тестов!
<Route path="registrar-panel" element={<RequireAuth roles={['Admin','Registrar']}><RegistrarPanel /></RequireAuth>} />
<Route path="doctor-panel"    element={<RequireAuth roles={['Admin','Doctor']}><DoctorPanel /></RequireAuth>} />
<Route path="cashier-panel"   element={<RequireAuth roles={['Admin','Cashier']}><CashierPanel /></RequireAuth>} />
<Route path="lab-panel"       element={<RequireAuth roles={['Admin','Lab']}><LabPanel /></RequireAuth>} />

<Route path="cardiologist"    element={<RequireAuth roles={['Admin','Doctor','cardio']}><CardiologistPanel /></RequireAuth>} />
<Route path="dermatologist"   element={<RequireAuth roles={['Admin','Doctor','derma']}><DermatologistPanel /></RequireAuth>} />
<Route path="dentist"         element={<RequireAuth roles={['Admin','Doctor','dentist']}><DentistPanel /></RequireAuth>} />
```

### Backend API endpoints
```python
# КРИТИЧЕСКИ ВАЖНО: Синхронизировать с frontend ролями!
user: User = Depends(deps.require_roles("Admin", "Doctor", "cardio"))  # Cardio API
user: User = Depends(deps.require_roles("Admin", "Doctor", "derma"))   # Derma API  
user: User = Depends(deps.require_roles("Admin", "Doctor", "dentist")) # Dental API
```

### Новые API endpoints управления пользователями:
```python
# Система управления пользователями (НОВОЕ)
from app.api.deps import require_admin, require_staff

# Управление пользователями - только для администраторов
user: User = Depends(require_admin)  # /users/* (создание, удаление, массовые действия)

# Просмотр и редактирование - для персонала
user: User = Depends(require_staff)  # /users (список), /users/{id} (просмотр)

# Профили и настройки - для владельца или администратора
user: User = Depends(require_staff)  # /users/{id}/profile, /users/{id}/preferences
```

## 🔄 Функции перенаправления

### Login.jsx - pickRouteForRoleCached()
```javascript
// КРИТИЧЕСКИ ВАЖНО: Синхронизировать с маршрутами!
if (role === 'admin')     return '/admin';
if (role === 'registrar') return '/registrar-panel';
if (role === 'lab')       return '/lab-panel';
if (role === 'doctor')    return '/doctor-panel';
if (role === 'cashier')   return '/cashier-panel';
if (role === 'cardio')    return '/cardiologist';
if (role === 'derma')     return '/dermatologist';
if (role === 'dentist')   return '/dentist';
```

### UserSelect.jsx - routeForRole()
```javascript
// КРИТИЧЕСКИ ВАЖНО: Синхронизировать с Login.jsx!
if (r === 'admin')     return '/admin';
if (r === 'registrar') return '/registrar-panel';
if (r === 'lab')       return '/lab-panel';
if (r === 'doctor')    return '/doctor-panel';
if (r === 'cashier')   return '/cashier-panel';
if (r === 'cardio')    return '/cardiologist';
if (r === 'derma')     return '/dermatologist';
if (r === 'dentist')   return '/dentist';
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
   - `backend/app/api/v1/endpoints/user_management.py` - НОВОЕ: управление пользователями
   - `backend/app/middleware/user_permissions.py` - НОВОЕ: проверка прав
   - `backend/app/services/user_management_service.py` - НОВОЕ: сервис управления

3. **База данных:**
   - Таблица `users` - роли пользователей
   - Таблица `user_roles` - НОВОЕ: роли системы
   - Таблица `user_permissions` - НОВОЕ: разрешения
   - Таблица `role_permissions` - НОВОЕ: связи ролей и разрешений
   - Таблица `user_groups` - НОВОЕ: группы пользователей
   - Таблица `user_profiles` - НОВОЕ: профили пользователей
   - Таблица `user_preferences` - НОВОЕ: настройки пользователей
   - Таблица `user_notification_settings` - НОВОЕ: настройки уведомлений
   - Таблица `user_audit_logs` - НОВОЕ: аудит действий
   - Пароли пользователей

4. **Тесты:**
   - `backend/test_role_routing.py` - список пользователей и ролей
   - `backend/test_user_management_system.py` - НОВОЕ: тесты системы управления
   - `backend/create_user_management_tables.py` - НОВОЕ: создание таблиц

## 📋 Чек-лист перед коммитом

- [ ] Запущены тесты: `python test_role_routing.py`
- [ ] Запущены тесты системы управления: `python test_user_management_system.py`
- [ ] Все тесты прошли успешно
- [ ] Обновлена документация
- [ ] Синхронизированы frontend и backend роли
- [ ] Проверен логин для всех ролей
- [ ] Обновлены пароли в документации (если изменены)
- [ ] Проверена работа новых API endpoints управления пользователями
- [ ] Проверена система разрешений и middleware
