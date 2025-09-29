# GraphQL API для системы управления клиникой

## Обзор

GraphQL API предоставляет гибкий и эффективный способ взаимодействия с данными клиники. В отличие от REST API, GraphQL позволяет клиентам запрашивать только те данные, которые им нужны, в одном запросе.

## Доступ к API

- **Endpoint**: `http://localhost:8000/api/graphql`
- **GraphiQL интерфейс**: `http://localhost:8000/api/graphql` (в браузере)
- **Метод**: POST
- **Content-Type**: application/json

## Аутентификация

Для доступа к GraphQL API требуется JWT токен:

```javascript
{
  "Authorization": "Bearer YOUR_JWT_TOKEN"
}
```

## Основные типы данных

### PatientType
```graphql
type PatientType {
  id: Int!
  fullName: String!
  phone: String!
  email: String
  birthDate: Date
  address: String
  passportSeries: String
  passportNumber: String
  createdAt: DateTime!
  updatedAt: DateTime!
}
```

### DoctorType
```graphql
type DoctorType {
  id: Int!
  user: UserType
  specialty: String!
  cabinet: String
  priceDefault: Float
  startNumberOnline: Int!
  maxOnlinePerDay: Int!
  autoCloseTime: Time
  active: Boolean!
  createdAt: DateTime!
  updatedAt: DateTime!
}
```

### ServiceType
```graphql
type ServiceType {
  id: Int!
  name: String!
  code: String!
  price: Float!
  category: String
  description: String
  durationMinutes: Int
  doctor: DoctorType
  active: Boolean!
  createdAt: DateTime!
  updatedAt: DateTime!
}
```

### AppointmentType
```graphql
type AppointmentType {
  id: Int!
  patient: PatientType!
  doctor: DoctorType!
  service: ServiceType!
  appointmentDate: DateTime!
  status: String!
  notes: String
  paymentStatus: String!
  paymentAmount: Float
  createdAt: DateTime!
  updatedAt: DateTime!
}
```

### VisitType
```graphql
type VisitType {
  id: Int!
  patient: PatientType!
  doctor: DoctorType!
  visitDate: Date!
  visitTime: Time
  status: String!
  discountMode: String
  allFree: Boolean!
  totalAmount: Float
  paymentStatus: String!
  createdAt: DateTime!
  updatedAt: DateTime!
}
```

## Примеры запросов

### 1. Получить список пациентов с пагинацией

```graphql
query GetPatients($filter: PatientFilter, $pagination: PaginationInput) {
  patients(filter: $filter, pagination: $pagination) {
    items {
      id
      fullName
      phone
      email
      birthDate
      createdAt
    }
    pagination {
      page
      perPage
      total
      pages
      hasNext
      hasPrev
    }
  }
}
```

**Переменные:**
```json
{
  "filter": {
    "fullName": "Иванов"
  },
  "pagination": {
    "page": 1,
    "perPage": 10
  }
}
```

### 2. Получить врачей по специальности

```graphql
query GetDoctorsBySpecialty($filter: DoctorFilter) {
  doctors(filter: $filter) {
    items {
      id
      specialty
      cabinet
      active
      user {
        fullName
        email
        phone
      }
    }
  }
}
```

**Переменные:**
```json
{
  "filter": {
    "specialty": "cardiology",
    "active": true
  }
}
```

### 3. Получить записи за определенный период

```graphql
query GetAppointmentsByDate($filter: AppointmentFilter) {
  appointments(filter: $filter) {
    items {
      id
      appointmentDate
      status
      paymentStatus
      patient {
        fullName
        phone
      }
      doctor {
        specialty
        user {
          fullName
        }
      }
      service {
        name
        price
      }
    }
  }
}
```

**Переменные:**
```json
{
  "filter": {
    "dateFrom": "2024-01-01T00:00:00Z",
    "dateTo": "2024-01-31T23:59:59Z",
    "status": "scheduled"
  }
}
```

### 4. Получить услуги с фильтрацией по цене

```graphql
query GetServicesByPrice($filter: ServiceFilter) {
  services(filter: $filter) {
    items {
      id
      name
      code
      price
      category
      description
      active
      doctor {
        specialty
        user {
          fullName
        }
      }
    }
  }
}
```

**Переменные:**
```json
{
  "filter": {
    "priceMin": 50000,
    "priceMax": 200000,
    "active": true
  }
}
```

### 5. Получить статистику

```graphql
query GetStatistics {
  appointmentStats {
    total
    today
    thisWeek
    thisMonth
  }
  visitStats {
    total
    today
    totalRevenue
  }
  queueStats {
    totalEntries
    activeQueues
    averageWaitTime
  }
}
```

## Примеры мутаций

### 1. Создать нового пациента

```graphql
mutation CreatePatient($input: PatientInput!) {
  createPatient(input: $input) {
    success
    message
    errors
    patient {
      id
      fullName
      phone
      email
      createdAt
    }
  }
}
```

**Переменные:**
```json
{
  "input": {
    "fullName": "Петров Петр Петрович",
    "phone": "+998901234567",
    "email": "petrov@example.com",
    "birthDate": "1985-05-15",
    "address": "г. Ташкент, ул. Навои, 123"
  }
}
```

### 2. Создать запись на прием

```graphql
mutation CreateAppointment($input: AppointmentInput!) {
  createAppointment(input: $input) {
    success
    message
    errors
    appointment {
      id
      appointmentDate
      status
      patient {
        fullName
      }
      doctor {
        user {
          fullName
        }
      }
      service {
        name
        price
      }
    }
  }
}
```

**Переменные:**
```json
{
  "input": {
    "patientId": 1,
    "doctorId": 2,
    "serviceId": 3,
    "appointmentDate": "2024-02-15T10:00:00Z",
    "notes": "Первичная консультация"
  }
}
```

### 3. Создать визит с несколькими услугами

```graphql
mutation CreateVisit($input: VisitInput!) {
  createVisit(input: $input) {
    success
    message
    errors
    visit {
      id
      visitDate
      status
      discountMode
      allFree
      totalAmount
      patient {
        fullName
      }
      doctor {
        user {
          fullName
        }
      }
    }
  }
}
```

**Переменные:**
```json
{
  "input": {
    "patientId": 1,
    "doctorId": 2,
    "visitDate": "2024-02-15",
    "visitTime": "14:30:00",
    "discountMode": "repeat",
    "allFree": false,
    "serviceIds": [1, 2, 3]
  }
}
```

### 4. Обновить статус записи

```graphql
mutation UpdateAppointmentStatus($id: Int!, $status: String!) {
  updateAppointmentStatus(id: $id, status: $status) {
    success
    message
    errors
    appointment {
      id
      status
      patient {
        fullName
      }
    }
  }
}
```

**Переменные:**
```json
{
  "id": 123,
  "status": "completed"
}
```

### 5. Встать в очередь

```graphql
mutation JoinQueue($input: QueueEntryInput!) {
  joinQueue(input: $input) {
    success
    message
    errors
    queueEntry {
      id
      queueNumber
      status
      patient {
        fullName
      }
      doctor {
        user {
          fullName
        }
      }
    }
  }
}
```

**Переменные:**
```json
{
  "input": {
    "patientId": 1,
    "doctorId": 2,
    "queueTag": "cardiology"
  }
}
```

## Фильтрация и пагинация

### Фильтры

Большинство запросов поддерживают фильтрацию:

```graphql
input PatientFilter {
  fullName: String
  phone: String
  email: String
  createdAfter: DateTime
  createdBefore: DateTime
}

input AppointmentFilter {
  patientId: Int
  doctorId: Int
  serviceId: Int
  status: String
  paymentStatus: String
  dateFrom: DateTime
  dateTo: DateTime
}

input ServiceFilter {
  name: String
  code: String
  category: String
  doctorId: Int
  active: Boolean
  priceMin: Float
  priceMax: Float
}
```

### Пагинация

```graphql
input PaginationInput {
  page: Int = 1
  perPage: Int = 20
}

type PaginationInfo {
  page: Int!
  perPage: Int!
  total: Int!
  pages: Int!
  hasNext: Boolean!
  hasPrev: Boolean!
}
```

## Обработка ошибок

GraphQL API возвращает ошибки в стандартном формате:

```json
{
  "data": null,
  "errors": [
    {
      "message": "Пациент не найден",
      "locations": [{"line": 2, "column": 3}],
      "path": ["patient"]
    }
  ]
}
```

Мутации также возвращают информацию об ошибках:

```json
{
  "data": {
    "createPatient": {
      "success": false,
      "message": "Пациент с таким номером телефона уже существует",
      "errors": ["PHONE_EXISTS"],
      "patient": null
    }
  }
}
```

## Интроспекция схемы

Для получения полной схемы API:

```graphql
query IntrospectionQuery {
  __schema {
    types {
      name
      description
      fields {
        name
        description
        type {
          name
        }
      }
    }
  }
}
```

## Лучшие практики

1. **Запрашивайте только нужные поля** - это основное преимущество GraphQL
2. **Используйте фрагменты** для переиспользования частей запросов
3. **Применяйте пагинацию** для больших списков данных
4. **Обрабатывайте ошибки** как на уровне GraphQL, так и на уровне мутаций
5. **Используйте переменные** вместо встраивания значений в запросы

## Примеры с фрагментами

```graphql
fragment PatientInfo on PatientType {
  id
  fullName
  phone
  email
  birthDate
}

fragment DoctorInfo on DoctorType {
  id
  specialty
  cabinet
  user {
    fullName
    email
  }
}

query GetAppointmentsWithDetails {
  appointments {
    items {
      id
      appointmentDate
      status
      patient {
        ...PatientInfo
      }
      doctor {
        ...DoctorInfo
      }
      service {
        name
        price
      }
    }
  }
}
```

## Производительность

- GraphQL API оптимизирован для минимизации N+1 запросов
- Используется DataLoader для батчинга запросов к базе данных
- Поддерживается кэширование на уровне резолверов
- Реализована пагинация для предотвращения загрузки больших объемов данных

## Мониторинг и отладка

- Все запросы логируются с информацией о времени выполнения
- Доступны метрики производительности через `/metrics` endpoint
- GraphiQL интерфейс предоставляет интерактивную документацию и возможность тестирования запросов

