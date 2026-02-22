/**
 * Пример рефакторинга компонента с использованием новых API хуков
 * 
 * БЫЛО (старый подход):
 * - Прямые fetch запросы
 * - Дублирование логики обработки ошибок
 * - Ручное управление состоянием загрузки
 * 
 * СТАЛО (новый подход):
 * - Унифицированные хуки useApi
 * - Централизованная обработка ошибок
 * - Автоматическое управление состоянием
 */

import { useState } from 'react';
import { toast } from 'react-toastify';
import { usePatients, useFormSubmit, useWebSocket } from '../../hooks/useApi';
import { validators, validateForm } from '../../utils/errorHandler';

import logger from '../../utils/logger';
import tokenManager from '../../utils/tokenManager';
// ❌ СТАРЫЙ ПОДХОД - НЕ ИСПОЛЬЗУЙТЕ
function OldPatientComponent() {
  const [, setPatients] = useState([]);
  const [, setLoading] = useState(false);
  const [, setError] = useState(null);

  // Дублирование логики авторизации
  const authHeader = () => ({
    Authorization: `Bearer ${tokenManager.getAccessToken() || ''}`
  });

  // Ручная обработка загрузки
  void (async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/v1/patients?department=Cardio&limit=100', {
        headers: authHeader()
      });

      if (response.ok) {
        const data = await response.json();
        setPatients(Array.isArray(data) ? data : []);
      } else {
        throw new Error('Ошибка загрузки пациентов');
      }
    } catch (error) {
      setError(error.message);
      logger.error('Ошибка загрузки пациентов:', error);
    } finally {
      setLoading(false);
    }
  });

  // Ручная обработка создания пациента
























  return (
    <div>
      {/* Компонент с дублированной логикой */}
    </div>);

}
void OldPatientComponent;

// ✅ НОВЫЙ ПОДХОД - ИСПОЛЬЗУЙТЕ
function NewPatientComponent() {
  // Автоматическая загрузка пациентов с обработкой ошибок
  const {
    data: patients,
    loading: patientsLoading,
    error: patientsError,
    refresh: refreshPatients
  } = usePatients('Cardio');

  // Хук для отправки форм с валидацией
  const { submitForm, loading: submitting } = useFormSubmit();

  // Локальное состояние формы
  const [formData, setFormData] = useState({
    full_name: '',
    phone: '',
    email: '',
    birth_date: ''
  });

  // Правила валидации
  const validationRules = {
    full_name: [validators.required],
    phone: [validators.required, validators.phone],
    email: [validators.email],
    birth_date: [validators.required]
  };

  // Обработчик отправки формы
  const handleSubmit = async (e) => {
    e.preventDefault();

    // Валидация
    const { isValid, errors } = validateForm(formData, validationRules);
    if (!isValid) {
      Object.values(errors).forEach((error) => toast.error(error));
      return;
    }

    try {
      await submitForm('/patients', formData, {
        validate: (data) => {
          // Дополнительная валидация
          if (!data.full_name.trim()) {
            return 'Имя пациента обязательно';
          }
          return null;
        },
        transform: (data) => {
          // Трансформация данных перед отправкой
          return {
            ...data,
            full_name: data.full_name.trim(),
            phone: data.phone.replace(/\D/g, '') // Только цифры
          };
        }
      });

      // Успешное создание - очищаем форму и обновляем список
      setFormData({ full_name: '', phone: '', email: '', birth_date: '' });
      refreshPatients();
    } catch {





      // Ошибка уже обработана в submitForm
    }};return <div className="patient-component">
      <h2>Пациенты кардиологии</h2>

      {/* Форма создания пациента */}
      <form onSubmit={handleSubmit} className="patient-form">
        <input type="text"
      placeholder="ФИО пациента"
      value={formData.full_name}
      onChange={(e) => setFormData((prev) => ({ ...prev, full_name: e.target.value }))}
      disabled={submitting} />
        

        <input
        type="tel"
        placeholder="Телефон"
        value={formData.phone}
        onChange={(e) => setFormData((prev) => ({ ...prev, phone: e.target.value }))}
        disabled={submitting} />
        

        <input
        type="email"
        placeholder="Email"
        value={formData.email}
        onChange={(e) => setFormData((prev) => ({ ...prev, email: e.target.value }))}
        disabled={submitting} />
        

        <input
        type="date"
        value={formData.birth_date}
        onChange={(e) => setFormData((prev) => ({ ...prev, birth_date: e.target.value }))}
        disabled={submitting} />
        

        <button type="submit" disabled={submitting}>
          {submitting ? 'Создание...' : 'Создать пациента'}
        </button>
      </form>

      {/* Список пациентов */}
      <div className="patients-list">
        {patientsLoading && <div>Загрузка пациентов...</div>}

        {patientsError &&
      <div className="error">
            Ошибка загрузки: {patientsError}
            <button onClick={refreshPatients}>Повторить</button>
          </div>
      }

        {patients && patients.length > 0 ?
      <ul>
            {patients.map((patient) =>
        <li key={patient.id}>
                <strong>{patient.full_name}</strong>
                <span>{patient.phone}</span>
                <span>{patient.email}</span>
              </li>
        )}
          </ul> :

      !patientsLoading && <div>Пациенты не найдены</div>
      }
      </div>
    </div>;

}

// ✅ ПРИМЕР КОМПОНЕНТА С WEBSOCKET
function RealtimeQueueComponent() {
  const { connected, lastMessage, sendMessage } = useWebSocket(
    'ws://localhost:8000/api/v1/display/ws/queue/cardiology',
    {
      onMessage: (message) => {
        logger.log('Получено сообщение очереди:', message);
      },
      onConnect: () => {
        logger.log('Подключен к очереди кардиологии');
      }
    }
  );

  return (
    <div className="realtime-queue">
      <div className="connection-status">
        Статус: {connected ? '🟢 Подключен' : '🔴 Отключен'}
      </div>

      {lastMessage &&
      <div className="last-message">
          <h3>Последнее обновление:</h3>
          <pre>{JSON.stringify(lastMessage, null, 2)}</pre>
        </div>
      }

      <button
        onClick={() => sendMessage({ type: 'request_update' })}
        disabled={!connected}>
        
        Запросить обновление
      </button>
    </div>);

}

export { NewPatientComponent, RealtimeQueueComponent };
