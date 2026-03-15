# 🔐 СИСТЕМА АУТЕНТИФИКАЦИИ И РОЛЕЙ - ПОЛНОЕ РУКОВОДСТВО

## 🎯 СТАТУС: ДОКУМЕНТАЦИОННЫЙ BASELINE, ТРЕБУЕТ РЕГУЛЯРНОЙ ВЕРИФИКАЦИИ

Система аутентификации описывает целевую реализацию блокирующего 2FA флоу и унифицированных моделей ролей; фактический operational-статус подтверждается текущими тестами и CI.

---

## 🚨 КРИТИЧЕСКИЕ ПРАВИЛА ДЛЯ РАЗРАБОТЧИКОВ

### ❌ НИКОГДА НЕ ДЕЛАТЬ:
1. **НЕ ИЗМЕНЯТЬ** систему ролей без обновления всех связанных файлов
2. **НЕ УДАЛЯТЬ** критических пользователей (admin, registrar, doctor, cardio, derma, dentist)
3. **НЕ НАРУШАТЬ** блокирующий 2FA флоу - токены выдаются ТОЛЬКО после верификации
4. **НЕ СМЕШИВАТЬ** схемы хеширования паролей (только argon2 для новых, bcrypt+argon2 для верификации)
5. **НЕ ДУБЛИРОВАТЬ** модели ролей - используйте ТОЛЬКО `app.models.role_permission.py`
6. **НЕ КОММИТИТЬ** без прохождения тестов системы ролей

### ✅ ОБЯЗАТЕЛЬНО ДЕЛАТЬ:
1. **ЗАПУСКАТЬ ТЕСТЫ** перед каждым коммитом: `python test_role_routing.py` и `pytest tests/integration/test_rbac_matrix.py -q`
2. **ОБНОВЛЯТЬ ДОКУМЕНТАЦИЮ** при любых изменениях в системе ролей
3. **ИСПОЛЬЗОВАТЬ** только `LoginFormStyled.jsx` как основную форму входа
4. **ПРОВЕРЯТЬ** работу 2FA флоу после изменений в аутентификации
5. **СИНХРОНИЗИРОВАТЬ** frontend и backend роли

---

## 🏗️ АРХИТЕКТУРА СИСТЕМЫ

### 1. **МОДЕЛИ ДАННЫХ (Источник истины)**

#### **Роли и разрешения** (`app/models/role_permission.py`):
```python
# ЕДИНСТВЕННЫЙ источник истины для ролей
class Role(Base):
    __tablename__ = "roles"
    # Связи с пользователями через user_roles_table

class Permission(Base):
    __tablename__ = "permissions"
    # Связи с ролями через role_permissions_table

class UserGroup(Base):
    __tablename__ = "user_groups"
    # Связи с пользователями через user_groups_table
```

#### **Пользователи** (`app/models/user.py`):
```python
class User(Base):
    # Связи с ролями и группами через M2M таблицы
    roles: Mapped[List["Role"]] = relationship("Role", secondary=user_roles_table)
    groups: Mapped[List["UserGroup"]] = relationship("UserGroup", secondary=user_groups_table)
```

#### **Аутентификация** (`app/models/authentication.py`):
```python
class RefreshToken(Base):      # JWT refresh токены
class UserSession(Base):       # Пользовательские сессии
class LoginAttempt(Base):      # Попытки входа
class UserActivity(Base):      # Активность пользователей
```

#### **2FA** (`app/models/two_factor_auth.py`):
```python
class TwoFactorAuth(Base):     # Настройки 2FA
class TwoFactorBackupCode(Base) # Backup коды
class TwoFactorDevice(Base):   # Доверенные устройства
```

### 2. **СИСТЕМА РОЛЕЙ** (`app/core/roles.py`)

```python
class Roles(str, Enum):
    # Основные роли
    ADMIN = "Admin"
    REGISTRAR = "Registrar" 
    DOCTOR = "Doctor"
    LAB = "Lab"
    CASHIER = "Cashier"
    MANAGER = "Manager"
    
    # Специализированные роли врачей
    CARDIO = "cardio"
    DERMA = "derma"
    DENTIST = "dentist"
    
    # Дополнительные роли
    NURSE = "Nurse"
    RECEPTIONIST = "Receptionist"
    PATIENT = "Patient"
    SUPER_ADMIN = "SuperAdmin"
```

---

## 🔐 АУТЕНТИФИКАЦИЯ И АВТОРИЗАЦИЯ

### **НОВЫЙ БЛОКИРУЮЩИЙ 2FA ФЛОУ**

#### 1. **Обычный вход (без 2FA)**:
```
POST /api/v1/authentication/login
{
  "username": "admin",
  "password": "admin123",
  "remember_me": false
}

Response:
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

#### 2. **Вход с 2FA (БЛОКИРУЮЩИЙ)**:
```
POST /api/v1/authentication/login
{
  "username": "admin",
  "password": "admin123"
}

Response (2FA требуется):
{
  "requires_2fa": true,
  "pending_2fa_token": "temp_token_123",
  "message": "Требуется двухфакторная аутентификация"
}

POST /api/v1/2fa/verify
{
  "pending_2fa_token": "temp_token_123",
  "totp_code": "123456",
  "remember_device": false
}

Response (после успешной верификации):
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

### **БЕЗОПАСНОСТЬ ПАРОЛЕЙ**

#### **Хеширование** (`app/core/security.py`):
```python
# Поддержка двух схем для совместимости
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")

# Новые пароли - только argon2
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)  # argon2

# Верификация - argon2 + bcrypt для старых
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
```

#### **JWT токены** (унифицировано на `python-jose`):
```python
# Все JWT операции через python-jose
from jose import jwt

def create_access_token(data: dict) -> str:
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
```

---

## 🎨 FRONTEND ИНТЕГРАЦИЯ

### **ОСНОВНАЯ ФОРМА ВХОДА** (`LoginFormStyled.jsx`)

```jsx
// ОСНОВНАЯ форма входа (заменила Login.jsx)
const LoginFormStyled = () => {
  // Поддержка username/email/phone
  // Автозаполнение браузера
  // Обработка 2FA флоу
  // Интеграция с TwoFactorVerify
}

// Роуты в App.jsx:
<Route path="/login" element={<LoginFormStyled />} />      // ОСНОВНАЯ
<Route path="/old-login" element={<Login />} />            // Для сравнения
```

### **2FA КОМПОНЕНТЫ**

#### **TwoFactorVerify.jsx**:
```jsx
const TwoFactorVerify = ({ pendingToken, method, onSuccess, onCancel }) => {
  // Поддержка pending_2fa_token
  // Методы: totp, backup, recovery
  // Интеграция с новым API
}
```

#### **Интеграция в LoginFormStyled**:
```jsx
// Если требуется 2FA - показываем компонент верификации
if (requires2FA) {
  return (
    <TwoFactorVerify
      method={twoFactorMethod}
      pendingToken={pending2FAToken}
      onSuccess={handle2FASuccess}
      onCancel={handle2FACancel}
    />
  );
}
```

---

## 🛡️ СИСТЕМА РАЗРЕШЕНИЙ

### **Критические пользователи и роли**:

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

### **Защищенные маршруты** (`App.jsx`):
```jsx
// КРИТИЧЕСКИ ВАЖНО: Не изменять роли без обновления тестов!
<Route path="registrar-panel" element={<RequireAuth roles={['Admin','Registrar']}><RegistrarPanel /></RequireAuth>} />
<Route path="doctor-panel" element={<RequireAuth roles={['Admin','Doctor']}><DoctorPanel /></RequireAuth>} />
<Route path="cardiologist" element={<RequireAuth roles={['Admin','Doctor','cardio']}><CardiologistPanel /></RequireAuth>} />
<Route path="dermatologist" element={<RequireAuth roles={['Admin','Doctor','derma']}><DermatologistPanel /></RequireAuth>} />
<Route path="dentist" element={<RequireAuth roles={['Admin','Doctor','dentist']}><DentistPanel /></RequireAuth>} />
```

---

## 🔧 API ENDPOINTS

### **Аутентификация**:
```
POST /api/v1/authentication/login          # Вход (с поддержкой 2FA)
POST /api/v1/authentication/refresh        # Обновление токена
POST /api/v1/authentication/logout         # Выход
POST /api/v1/authentication/password-reset # Сброс пароля
GET  /api/v1/auth/me                       # Профиль пользователя
```

### **2FA**:
```
GET  /api/v1/2fa/status                    # Статус 2FA
POST /api/v1/2fa/setup                     # Настройка 2FA
POST /api/v1/2fa/verify                    # Верификация (с pending_token)
POST /api/v1/2fa/disable                   # Отключение 2FA
GET  /api/v1/2fa/backup-codes              # Backup коды
```

### **Управление пользователями**:
```
GET  /api/v1/users                         # Список пользователей
POST /api/v1/users                         # Создание пользователя
GET  /api/v1/users/{id}                    # Получение пользователя
PUT  /api/v1/users/{id}                    # Обновление пользователя
DELETE /api/v1/users/{id}                  # Удаление пользователя
```

---

## 🧪 ТЕСТИРОВАНИЕ

### **Обязательные тесты перед коммитом**:
```bash
cd backend

# Быстрая проверка
python quick_check.py

# Полная проверка системы ролей
python test_role_routing.py

# Тестирование системы управления пользователями
python test_user_management_system.py

# Проверка целостности системы
python check_system_integrity.py
```

### **Что тестируется**:
- ✅ Логин всех критических пользователей
- ✅ Корректность ролей в профилях
- ✅ Доступность специализированных API
- ✅ Работа 2FA флоу
- ✅ Блокирующая логика токенов
- ✅ Унифицированные модели ролей

---

## 📋 ЧЕК-ЛИСТ РАЗРАБОТЧИКА

### **Перед изменением системы ролей**:
- [ ] Изучить текущую документацию
- [ ] Понять архитектуру моделей
- [ ] Проверить связанные файлы

### **При изменении**:
- [ ] Обновить `app/core/roles.py` (если нужно)
- [ ] Синхронизировать frontend маршруты
- [ ] Обновить backend API endpoints
- [ ] Проверить M2M таблицы

### **После изменения**:
- [ ] Запустить все тесты
- [ ] Обновить документацию
- [ ] Проверить работу входа для всех ролей
- [ ] Протестировать 2FA флоу

### **Перед коммитом**:
- [ ] Все тесты прошли успешно
- [ ] Документация обновлена
- [ ] Нет дублирования моделей
- [ ] 2FA флоу работает корректно

---

## 🚨 КРИТИЧЕСКИЕ ФАЙЛЫ

### **НЕ ИЗМЕНЯТЬ БЕЗ ПОНИМАНИЯ**:
1. `app/models/role_permission.py` - ЕДИНСТВЕННЫЙ источник истины для ролей
2. `app/core/roles.py` - Enum ролей системы
3. `app/core/security.py` - Хеширование паролей и JWT
4. `frontend/src/components/auth/LoginFormStyled.jsx` - Основная форма входа
5. `frontend/src/App.jsx` - Маршруты и роли

### **ОБЯЗАТЕЛЬНО СИНХРОНИЗИРОВАТЬ**:
1. Frontend роли в `App.jsx`
2. Backend роли в API endpoints
3. Функции перенаправления
4. Тесты системы ролей
5. Документацию

---

## 🎯 РЕЗУЛЬТАТ

При соблюдении этих правил:
- ✅ Система ролей остается стабильной
- ✅ Аутентификация работает корректно с 2FA
- ✅ Маршрутизация не нарушается
- ✅ Новые функции не ломают существующие
- ✅ Безопасность паролей обеспечена
- ✅ Модели ролей унифицированы

**СИСТЕМА ГОТОВА К ИСПОЛЬЗОВАНИЮ И ЗАЩИЩЕНА ОТ НАРУШЕНИЙ!** 🛡️

---

## 📞 ПОДДЕРЖКА

При возникновении проблем:
1. Проверить эту документацию
2. Запустить диагностические тесты
3. Проверить логи сервера
4. Обратиться к команде разработки

**Помните: Лучше спросить, чем сломать систему!** 💡

