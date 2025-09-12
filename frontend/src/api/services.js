// Централизованные API сервисы
// Использует client.js и endpoints.js для единообразной работы с API

import { apiRequest, api } from './client.js';
import { API_ENDPOINTS, QUERY_PARAMS, buildQueryString } from './endpoints.js';

/**
 * Сервис аутентификации
 */
export const authService = {
  /**
   * Вход в систему
   */
  async login(username, password) {
    return apiRequest('POST', API_ENDPOINTS.AUTH.LOGIN, {
      data: { username, password }
    });
  },

  /**
   * Получение профиля текущего пользователя
   */
  async getProfile() {
    return apiRequest('GET', API_ENDPOINTS.AUTH.ME);
  },

  /**
   * Выход из системы
   */
  async logout() {
    return apiRequest('POST', API_ENDPOINTS.AUTH.LOGOUT);
  },

  /**
   * Обновление токена
   */
  async refreshToken() {
    return apiRequest('POST', API_ENDPOINTS.AUTH.REFRESH);
  }
};

/**
 * Сервис пользователей
 */
export const usersService = {
  /**
   * Получение списка пользователей
   */
  async getUsers(params = {}) {
    const queryString = buildQueryString(params);
    return apiRequest('GET', `${API_ENDPOINTS.USERS.LIST}?${queryString}`);
  },

  /**
   * Получение пользователя по ID
   */
  async getUser(id) {
    return apiRequest('GET', API_ENDPOINTS.USERS.GET(id));
  },

  /**
   * Создание пользователя
   */
  async createUser(userData) {
    return apiRequest('POST', API_ENDPOINTS.USERS.CREATE, {
      data: userData
    });
  },

  /**
   * Обновление пользователя
   */
  async updateUser(id, userData) {
    return apiRequest('PUT', API_ENDPOINTS.USERS.UPDATE(id), {
      data: userData
    });
  },

  /**
   * Удаление пользователя
   */
  async deleteUser(id) {
    return apiRequest('DELETE', API_ENDPOINTS.USERS.DELETE(id));
  },

  /**
   * Получение ролей
   */
  async getRoles() {
    return apiRequest('GET', API_ENDPOINTS.USERS.ROLES);
  },

  /**
   * Получение разрешений
   */
  async getPermissions() {
    return apiRequest('GET', API_ENDPOINTS.USERS.PERMISSIONS);
  }
};

/**
 * Сервис пациентов
 */
export const patientsService = {
  /**
   * Получение списка пациентов
   */
  async getPatients(params = {}) {
    const queryString = buildQueryString(params);
    return apiRequest('GET', `${API_ENDPOINTS.PATIENTS.LIST}?${queryString}`);
  },

  /**
   * Получение пациента по ID
   */
  async getPatient(id) {
    return apiRequest('GET', API_ENDPOINTS.PATIENTS.GET(id));
  },

  /**
   * Создание пациента
   */
  async createPatient(patientData) {
    return apiRequest('POST', API_ENDPOINTS.PATIENTS.CREATE, {
      data: patientData
    });
  },

  /**
   * Обновление пациента
   */
  async updatePatient(id, patientData) {
    return apiRequest('PUT', API_ENDPOINTS.PATIENTS.UPDATE(id), {
      data: patientData
    });
  },

  /**
   * Удаление пациента
   */
  async deletePatient(id) {
    return apiRequest('DELETE', API_ENDPOINTS.PATIENTS.DELETE(id));
  },

  /**
   * Поиск пациентов
   */
  async searchPatients(query, params = {}) {
    const searchParams = { ...params, [QUERY_PARAMS.SEARCH]: query };
    const queryString = buildQueryString(searchParams);
    return apiRequest('GET', `${API_ENDPOINTS.PATIENTS.SEARCH}?${queryString}`);
  },

  /**
   * Статистика пациентов
   */
  async getPatientsStats(params = {}) {
    const queryString = buildQueryString(params);
    return apiRequest('GET', `${API_ENDPOINTS.PATIENTS.STATS}?${queryString}`);
  }
};

/**
 * Сервис врачей
 */
export const doctorsService = {
  /**
   * Получение списка врачей
   */
  async getDoctors(params = {}) {
    const queryString = buildQueryString(params);
    return apiRequest('GET', `${API_ENDPOINTS.DOCTORS.LIST}?${queryString}`);
  },

  /**
   * Получение врача по ID
   */
  async getDoctor(id) {
    return apiRequest('GET', API_ENDPOINTS.DOCTORS.GET(id));
  },

  /**
   * Создание врача
   */
  async createDoctor(doctorData) {
    return apiRequest('POST', API_ENDPOINTS.DOCTORS.CREATE, {
      data: doctorData
    });
  },

  /**
   * Обновление врача
   */
  async updateDoctor(id, doctorData) {
    return apiRequest('PUT', API_ENDPOINTS.DOCTORS.UPDATE(id), {
      data: doctorData
    });
  },

  /**
   * Удаление врача
   */
  async deleteDoctor(id) {
    return apiRequest('DELETE', API_ENDPOINTS.DOCTORS.DELETE(id));
  },

  /**
   * Получение специализаций
   */
  async getSpecializations() {
    return apiRequest('GET', API_ENDPOINTS.DOCTORS.SPECIALIZATIONS);
  },

  /**
   * Получение отделений
   */
  async getDepartments() {
    return apiRequest('GET', API_ENDPOINTS.DOCTORS.DEPARTMENTS);
  },

  /**
   * Получение расписания врача
   */
  async getDoctorSchedule(id, params = {}) {
    const queryString = buildQueryString(params);
    return apiRequest('GET', `${API_ENDPOINTS.DOCTORS.SCHEDULE(id)}?${queryString}`);
  },

  /**
   * Получение доступности врача
   */
  async getDoctorAvailability(id, params = {}) {
    const queryString = buildQueryString(params);
    return apiRequest('GET', `${API_ENDPOINTS.DOCTORS.AVAILABILITY(id)}?${queryString}`);
  }
};

/**
 * Сервис записей на прием
 */
export const appointmentsService = {
  /**
   * Получение списка записей
   */
  async getAppointments(params = {}) {
    const queryString = buildQueryString(params);
    return apiRequest('GET', `${API_ENDPOINTS.APPOINTMENTS.LIST}?${queryString}`);
  },

  /**
   * Получение записи по ID
   */
  async getAppointment(id) {
    return apiRequest('GET', API_ENDPOINTS.APPOINTMENTS.GET(id));
  },

  /**
   * Создание записи
   */
  async createAppointment(appointmentData) {
    return apiRequest('POST', API_ENDPOINTS.APPOINTMENTS.CREATE, {
      data: appointmentData
    });
  },

  /**
   * Обновление записи
   */
  async updateAppointment(id, appointmentData) {
    return apiRequest('PUT', API_ENDPOINTS.APPOINTMENTS.UPDATE(id), {
      data: appointmentData
    });
  },

  /**
   * Удаление записи
   */
  async deleteAppointment(id) {
    return apiRequest('DELETE', API_ENDPOINTS.APPOINTMENTS.DELETE(id));
  },

  /**
   * Статистика записей
   */
  async getAppointmentsStats(params = {}) {
    const queryString = buildQueryString(params);
    return apiRequest('GET', `${API_ENDPOINTS.APPOINTMENTS.STATS}?${queryString}`);
  },

  /**
   * Записи пациента
   */
  async getPatientAppointments(patientId, params = {}) {
    const queryString = buildQueryString(params);
    return apiRequest('GET', `${API_ENDPOINTS.APPOINTMENTS.BY_PATIENT(patientId)}?${queryString}`);
  },

  /**
   * Записи врача
   */
  async getDoctorAppointments(doctorId, params = {}) {
    const queryString = buildQueryString(params);
    return apiRequest('GET', `${API_ENDPOINTS.APPOINTMENTS.BY_DOCTOR(doctorId)}?${queryString}`);
  },

  /**
   * Записи по дате
   */
  async getAppointmentsByDate(date, params = {}) {
    const searchParams = { ...params, date };
    const queryString = buildQueryString(searchParams);
    return apiRequest('GET', `${API_ENDPOINTS.APPOINTMENTS.BY_DATE}?${queryString}`);
  },

  /**
   * Отмена записи
   */
  async cancelAppointment(id) {
    return apiRequest('POST', API_ENDPOINTS.APPOINTMENTS.CANCEL(id));
  },

  /**
   * Подтверждение записи
   */
  async confirmAppointment(id) {
    return apiRequest('POST', API_ENDPOINTS.APPOINTMENTS.CONFIRM(id));
  }
};

/**
 * Сервис очереди
 */
export const queueService = {
  /**
   * Получение списка очереди
   */
  async getQueue(params = {}) {
    const queryString = buildQueryString(params);
    return apiRequest('GET', `${API_ENDPOINTS.QUEUE.LIST}?${queryString}`);
  },

  /**
   * Получение записи очереди по ID
   */
  async getQueueItem(id) {
    return apiRequest('GET', API_ENDPOINTS.QUEUE.GET(id));
  },

  /**
   * Добавление в очередь
   */
  async addToQueue(queueData) {
    return apiRequest('POST', API_ENDPOINTS.QUEUE.CREATE, {
      data: queueData
    });
  },

  /**
   * Обновление записи очереди
   */
  async updateQueueItem(id, queueData) {
    return apiRequest('PUT', API_ENDPOINTS.QUEUE.UPDATE(id), {
      data: queueData
    });
  },

  /**
   * Удаление из очереди
   */
  async removeFromQueue(id) {
    return apiRequest('DELETE', API_ENDPOINTS.QUEUE.DELETE(id));
  },

  /**
   * Статистика очереди
   */
  async getQueueStats(params = {}) {
    const queryString = buildQueryString(params);
    return apiRequest('GET', `${API_ENDPOINTS.QUEUE.STATS}?${queryString}`);
  },

  /**
   * Очередь по отделению
   */
  async getQueueByDepartment(department, params = {}) {
    const searchParams = { ...params, [QUERY_PARAMS.DEPARTMENT]: department };
    const queryString = buildQueryString(searchParams);
    return apiRequest('GET', `${API_ENDPOINTS.QUEUE.BY_DEPARTMENT}?${queryString}`);
  },

  /**
   * Вызов следующего
   */
  async callNext(department) {
    return apiRequest('POST', API_ENDPOINTS.QUEUE.CALL_NEXT, {
      data: { department }
    });
  },

  /**
   * Пропуск записи
   */
  async skipQueueItem(id) {
    return apiRequest('POST', API_ENDPOINTS.QUEUE.SKIP(id));
  },

  /**
   * Завершение записи
   */
  async completeQueueItem(id) {
    return apiRequest('POST', API_ENDPOINTS.QUEUE.COMPLETE(id));
  }
};

/**
 * Сервис услуг
 */
export const servicesService = {
  /**
   * Получение списка услуг
   */
  async getServices(params = {}) {
    const queryString = buildQueryString(params);
    return apiRequest('GET', `${API_ENDPOINTS.SERVICES.LIST}?${queryString}`);
  },

  /**
   * Получение услуги по ID
   */
  async getService(id) {
    return apiRequest('GET', API_ENDPOINTS.SERVICES.GET(id));
  },

  /**
   * Создание услуги
   */
  async createService(serviceData) {
    return apiRequest('POST', API_ENDPOINTS.SERVICES.CREATE, {
      data: serviceData
    });
  },

  /**
   * Обновление услуги
   */
  async updateService(id, serviceData) {
    return apiRequest('PUT', API_ENDPOINTS.SERVICES.UPDATE(id), {
      data: serviceData
    });
  },

  /**
   * Удаление услуги
   */
  async deleteService(id) {
    return apiRequest('DELETE', API_ENDPOINTS.SERVICES.DELETE(id));
  },

  /**
   * Услуги по отделению
   */
  async getServicesByDepartment(department, params = {}) {
    const searchParams = { ...params, [QUERY_PARAMS.DEPARTMENT]: department };
    const queryString = buildQueryString(searchParams);
    return apiRequest('GET', `${API_ENDPOINTS.SERVICES.BY_DEPARTMENT}?${queryString}`);
  },

  /**
   * Ценообразование
   */
  async getPricing(params = {}) {
    const queryString = buildQueryString(params);
    return apiRequest('GET', `${API_ENDPOINTS.SERVICES.PRICING}?${queryString}`);
  }
};

/**
 * Сервис аналитики
 */
export const analyticsService = {
  /**
   * Дашборд
   */
  async getDashboard(params = {}) {
    const queryString = buildQueryString(params);
    return apiRequest('GET', `${API_ENDPOINTS.ANALYTICS.DASHBOARD}?${queryString}`);
  },

  /**
   * Доходы
   */
  async getRevenue(params = {}) {
    const queryString = buildQueryString(params);
    return apiRequest('GET', `${API_ENDPOINTS.ANALYTICS.REVENUE}?${queryString}`);
  },

  /**
   * Аналитика пациентов
   */
  async getPatientsAnalytics(params = {}) {
    const queryString = buildQueryString(params);
    return apiRequest('GET', `${API_ENDPOINTS.ANALYTICS.PATIENTS}?${queryString}`);
  },

  /**
   * Аналитика записей
   */
  async getAppointmentsAnalytics(params = {}) {
    const queryString = buildQueryString(params);
    return apiRequest('GET', `${API_ENDPOINTS.ANALYTICS.APPOINTMENTS}?${queryString}`);
  },

  /**
   * Аналитика врачей
   */
  async getDoctorsAnalytics(params = {}) {
    const queryString = buildQueryString(params);
    return apiRequest('GET', `${API_ENDPOINTS.ANALYTICS.DOCTORS}?${queryString}`);
  },

  /**
   * Аналитика отделений
   */
  async getDepartmentsAnalytics(params = {}) {
    const queryString = buildQueryString(params);
    return apiRequest('GET', `${API_ENDPOINTS.ANALYTICS.DEPARTMENTS}?${queryString}`);
  },

  /**
   * Экспорт аналитики
   */
  async exportAnalytics(params = {}) {
    const queryString = buildQueryString(params);
    return apiRequest('GET', `${API_ENDPOINTS.ANALYTICS.EXPORT}?${queryString}`);
  }
};

/**
 * Сервис настроек
 */
export const settingsService = {
  /**
   * Получение всех настроек
   */
  async getSettings(params = {}) {
    const queryString = buildQueryString(params);
    return apiRequest('GET', `${API_ENDPOINTS.SETTINGS.LIST}?${queryString}`);
  },

  /**
   * Получение настройки по ключу
   */
  async getSetting(key) {
    return apiRequest('GET', API_ENDPOINTS.SETTINGS.GET(key));
  },

  /**
   * Обновление настройки
   */
  async updateSetting(key, value) {
    return apiRequest('PUT', API_ENDPOINTS.SETTINGS.UPDATE(key), {
      data: { value }
    });
  },

  /**
   * Массовое обновление настроек
   */
  async updateSettings(settings) {
    return apiRequest('POST', API_ENDPOINTS.SETTINGS.BULK_UPDATE, {
      data: { settings }
    });
  },

  /**
   * Получение категорий настроек
   */
  async getCategories() {
    return apiRequest('GET', API_ENDPOINTS.SETTINGS.CATEGORIES);
  }
};

/**
 * Сервис уведомлений
 */
export const notificationsService = {
  /**
   * Получение списка уведомлений
   */
  async getNotifications(params = {}) {
    const queryString = buildQueryString(params);
    return apiRequest('GET', `${API_ENDPOINTS.NOTIFICATIONS.LIST}?${queryString}`);
  },

  /**
   * Получение уведомления по ID
   */
  async getNotification(id) {
    return apiRequest('GET', API_ENDPOINTS.NOTIFICATIONS.GET(id));
  },

  /**
   * Отметка как прочитанное
   */
  async markAsRead(id) {
    return apiRequest('POST', API_ENDPOINTS.NOTIFICATIONS.MARK_READ(id));
  },

  /**
   * Отметка всех как прочитанных
   */
  async markAllAsRead() {
    return apiRequest('POST', API_ENDPOINTS.NOTIFICATIONS.MARK_ALL_READ);
  },

  /**
   * Отправка уведомления
   */
  async sendNotification(notificationData) {
    return apiRequest('POST', API_ENDPOINTS.NOTIFICATIONS.SEND, {
      data: notificationData
    });
  },

  /**
   * Получение типов уведомлений
   */
  async getNotificationTypes() {
    return apiRequest('GET', API_ENDPOINTS.NOTIFICATIONS.TYPES);
  }
};

/**
 * Сервис файлов
 */
export const filesService = {
  /**
   * Загрузка файла
   */
  async uploadFile(file, metadata = {}) {
    const formData = new FormData();
    formData.append('file', file);
    
    Object.entries(metadata).forEach(([key, value]) => {
      formData.append(key, value);
    });

    return api.post(API_ENDPOINTS.FILES.UPLOAD, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
  },

  /**
   * Получение файла по ID
   */
  async getFile(id) {
    return apiRequest('GET', API_ENDPOINTS.FILES.GET(id));
  },

  /**
   * Удаление файла
   */
  async deleteFile(id) {
    return apiRequest('DELETE', API_ENDPOINTS.FILES.DELETE(id));
  },

  /**
   * Скачивание файла
   */
  async downloadFile(id) {
    return api.get(API_ENDPOINTS.FILES.DOWNLOAD(id), {
      responseType: 'blob'
    });
  },

  /**
   * Получение списка файлов
   */
  async getFiles(params = {}) {
    const queryString = buildQueryString(params);
    return apiRequest('GET', `${API_ENDPOINTS.FILES.LIST}?${queryString}`);
  }
};

/**
 * Сервис здоровья системы
 */
export const healthService = {
  /**
   * Проверка здоровья
   */
  async checkHealth() {
    return apiRequest('GET', API_ENDPOINTS.HEALTH.CHECK);
  },

  /**
   * Статус системы
   */
  async getStatus() {
    return apiRequest('GET', API_ENDPOINTS.HEALTH.STATUS);
  },

  /**
   * Метрики системы
   */
  async getMetrics() {
    return apiRequest('GET', API_ENDPOINTS.HEALTH.METRICS);
  }
};
