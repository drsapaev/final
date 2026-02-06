// Централизованные типы данных для API интеграции
// Синхронизировано с backend API документацией

/**
 * Базовые типы пользователей
 */
export const USER_ROLES = {
  ADMIN: 'Admin',
  REGISTRAR: 'Registrar',
  RECEPTIONIST: 'Receptionist',  // Alias for REGISTRAR - same role
  DOCTOR: 'Doctor',
  LAB: 'Lab',
  CASHIER: 'Cashier',
  CARDIO: 'cardio',
  DERMA: 'derma',
  DENTIST: 'dentist',
  PATIENT: 'Patient'
};

/**
 * Статусы записей
 */
export const APPOINTMENT_STATUS = {
  SCHEDULED: 'scheduled',
  CONFIRMED: 'confirmed',
  IN_PROGRESS: 'in_progress',
  COMPLETED: 'completed',
  CANCELLED: 'cancelled',
  NO_SHOW: 'no_show'
};

/**
 * Статусы очереди
 */
export const QUEUE_STATUS = {
  WAITING: 'waiting',
  CALLED: 'called',
  IN_PROGRESS: 'in_progress',
  COMPLETED: 'completed',
  CANCELLED: 'cancelled'
};

/**
 * Типы уведомлений
 */
export const NOTIFICATION_TYPES = {
  EMAIL: 'email',
  SMS: 'sms',
  TELEGRAM: 'telegram',
  PUSH: 'push'
};

/**
 * DTO для пользователя
 */
export const UserDTO = {
  id: 'number',
  username: 'string',
  email: 'string',
  role: 'string',
  role_name: 'string',
  roles: 'array',
  is_active: 'boolean',
  is_superuser: 'boolean',
  is_admin: 'boolean',
  created_at: 'string',
  updated_at: 'string'
};

/**
 * DTO для профиля пользователя (GET /me)
 */
export const ProfileDTO = {
  id: 'number',
  username: 'string',
  email: 'string',
  role: 'string',
  role_name: 'string',
  roles: 'array',
  is_active: 'boolean',
  is_superuser: 'boolean',
  is_admin: 'boolean',
  permissions: 'array',
  created_at: 'string',
  updated_at: 'string'
};

/**
 * DTO для аутентификации (POST /login)
 */
export const LoginResponseDTO = {
  access_token: 'string',
  token_type: 'string',
  expires_in: 'number',
  scope: 'string'
};

/**
 * DTO для записи на прием
 */
export const AppointmentDTO = {
  id: 'number',
  patient_id: 'number',
  doctor_id: 'number',
  department: 'string',
  service_id: 'number',
  appointment_date: 'string',
  appointment_time: 'string',
  status: 'string',
  notes: 'string',
  created_at: 'string',
  updated_at: 'string'
};

/**
 * DTO для пациента
 */
export const PatientDTO = {
  id: 'number',
  first_name: 'string',
  last_name: 'string',
  middle_name: 'string',
  birth_date: 'string',
  phone: 'string',
  email: 'string',
  address: 'string',
  insurance_number: 'string',
  created_at: 'string',
  updated_at: 'string'
};

/**
 * DTO для врача
 */
export const DoctorDTO = {
  id: 'number',
  user_id: 'number',
  first_name: 'string',
  last_name: 'string',
  middle_name: 'string',
  specialization: 'string',
  department: 'string',
  license_number: 'string',
  is_active: 'boolean',
  created_at: 'string',
  updated_at: 'string'
};

/**
 * DTO для услуги
 */
export const ServiceDTO = {
  id: 'number',
  name: 'string',
  description: 'string',
  price: 'number',
  duration: 'number',
  department: 'string',
  is_active: 'boolean',
  created_at: 'string',
  updated_at: 'string'
};

/**
 * DTO для очереди
 */
export const QueueDTO = {
  id: 'number',
  patient_id: 'number',
  doctor_id: 'number',
  department: 'string',
  queue_number: 'number',
  status: 'string',
  estimated_time: 'string',
  actual_time: 'string',
  created_at: 'string',
  updated_at: 'string'
};

/**
 * DTO для статистики
 */
export const StatsDTO = {
  total_patients: 'number',
  total_appointments: 'number',
  total_doctors: 'number',
  total_services: 'number',
  appointments_today: 'number',
  patients_today: 'number',
  revenue_today: 'number',
  revenue_month: 'number'
};

/**
 * DTO для отчета
 */
export const ReportDTO = {
  id: 'number',
  title: 'string',
  type: 'string',
  data: 'object',
  generated_at: 'string',
  created_by: 'number'
};

/**
 * DTO для настроек
 */
export const SettingsDTO = {
  id: 'number',
  key: 'string',
  value: 'string',
  description: 'string',
  category: 'string',
  is_public: 'boolean',
  updated_at: 'string'
};

/**
 * DTO для уведомления
 */
export const NotificationDTO = {
  id: 'number',
  user_id: 'number',
  type: 'string',
  title: 'string',
  message: 'string',
  is_read: 'boolean',
  sent_at: 'string',
  created_at: 'string'
};

/**
 * DTO для файла
 */
export const FileDTO = {
  id: 'number',
  filename: 'string',
  original_name: 'string',
  file_path: 'string',
  file_size: 'number',
  mime_type: 'string',
  uploaded_by: 'number',
  created_at: 'string'
};

/**
 * DTO для аудита
 */
export const AuditLogDTO = {
  id: 'number',
  user_id: 'number',
  action: 'string',
  resource: 'string',
  resource_id: 'number',
  details: 'object',
  ip_address: 'string',
  user_agent: 'string',
  created_at: 'string'
};

/**
 * DTO для ошибки API
 */
export const ApiErrorDTO = {
  detail: 'string|array',
  message: 'string',
  status_code: 'number',
  timestamp: 'string'
};

/**
 * DTO для пагинации
 */
export const PaginationDTO = {
  page: 'number',
  per_page: 'number',
  total: 'number',
  pages: 'number',
  has_next: 'boolean',
  has_prev: 'boolean'
};

/**
 * DTO для ответа с пагинацией
 */
export const PaginatedResponseDTO = {
  items: 'array',
  pagination: 'object'
};

/**
 * Валидация DTO
 */
export function validateDTO(data, dto) {
  const errors = [];

  for (const [key, expectedType] of Object.entries(dto)) {
    if (!(key in data)) {
      errors.push(`Missing required field: ${key}`);
      continue;
    }

    const value = data[key];
    const actualType = Array.isArray(value) ? 'array' : typeof value;

    if (actualType !== expectedType) {
      errors.push(`Field ${key} expected ${expectedType}, got ${actualType}`);
    }
  }

  return errors;
}

/**
 * Создание типизированного объекта
 */
export function createDTO(data, dto) {
  const validated = {};

  for (const [key, expectedType] of Object.entries(dto)) {
    if (key in data) {
      validated[key] = data[key];
    }
  }

  return validated;
}
