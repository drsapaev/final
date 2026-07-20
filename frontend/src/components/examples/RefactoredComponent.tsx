
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
import { buildWsUrl } from '../../api/runtime';
import { toast } from 'react-toastify';
import { usePatients, useFormSubmit, useWebSocket } from '../../hooks/useApi';
import { validators, validateForm } from '../../utils/errorHandler';

import logger from '../../utils/logger';
import tokenManager from '../../utils/tokenManager';
import { Input } from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';
import i18n from '../../i18n';
const t18 = i18n.t as unknown as (key: string, options?: Record<string, unknown>) => string;
// ❌ СТАРЫЙ ПОДХОД - НЕ ИСПОЛЬЗУЙТЕ
function OldPatientComponent() {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
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
        throw new Error(t18('misc.rc_oshibka_zagruzki_patsientov'));
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
          if (!(data as Record<string, string>).full_name.trim()) {
            return t18('misc.rc_imya_patsienta_obyazatelno');
          }
          return null;
        },
        transform: (data) => {
          // Трансформация данных перед отправкой
          return {
            ...data,
            full_name: (data as Record<string, string>).full_name.trim(),
            phone: (data as Record<string, string>).phone.replace(/\D/g, '') // Только цифры
          };
        }
      });

      // Успешное создание - очищаем форму и обновляем список
      setFormData({ full_name: '', phone: '', email: '', birth_date: '' });
      refreshPatients();
    } catch {





      // Ошибка уже обработана в submitForm
    }};return <div className="patient-component">
      <h2>{t18('misc.rc_patsienty_kardiologii')}</h2>

      {/* Форма создания пациента */}
      <form onSubmit={handleSubmit} className="patient-form">
        <Input type="text"
      aria-label="Patient full name"
      placeholder={t18('misc.rc_fio_patsienta')}
      value={formData.full_name}
      onChange={(e) => setFormData((prev) => ({ ...prev, full_name: e.target.value }))}
      disabled={submitting} />
        

        <Input
        type="tel"
        aria-label="Patient phone"
        placeholder={t18('misc.rc_telefon')}
        value={formData.phone}
        onChange={(e) => setFormData((prev) => ({ ...prev, phone: e.target.value }))}
        disabled={submitting} />
        

        <Input
        type="email"
        aria-label="Patient email"
        placeholder="Email"
        value={formData.email}
        onChange={(e) => setFormData((prev) => ({ ...prev, email: e.target.value }))}
        disabled={submitting} />
        

        <Input
        type="date"
        aria-label="Patient birth date"
        value={formData.birth_date}
        onChange={(e) => setFormData((prev) => ({ ...prev, birth_date: e.target.value }))}
        disabled={submitting} />
        

        <button type="submit" disabled={submitting}>
          {submitting ? t18('misc.rc_sozdanie') : t18('misc.rc_sozdat_patsienta')}
        </button>
      </form>

      {/* Список пациентов */}
      <div className="patients-list">
        {patientsLoading && <div>{t18('misc.rc_zagruzka_patsientov')}</div>}

        {patientsError &&
      <div className="error">
            Ошибка загрузки: {patientsError}
            <button onClick={refreshPatients}>{t18('misc.rc_povtorit')}</button>
          </div>
      }

        {patients && (patients as unknown[]).length > 0 ?
      <ul>
            {(patients as Array<Record<string, unknown>>).map((patient) =>
        <li key={String(patient.id)}>
                <strong>{String(patient.full_name)}</strong>
                <span>{String(patient.phone)}</span>
                <span>{String(patient.email)}</span>
              </li>
        )}
          </ul> :

      !patientsLoading && <div>{t18('misc.rc_patsienty_ne_naydeny')}</div>
      }
      </div>
    </div>;

}

// ✅ ПРИМЕР КОМПОНЕНТА С WEBSOCKET
function RealtimeQueueComponent() {
  const { connected, lastMessage, sendMessage } = useWebSocket(
    buildWsUrl('/api/v1/display/ws/queue/cardiology'),
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
        Статус: {connected ? t18('misc.rc_podklyuchen') : t18('misc.rc_otklyuchen')}
      </div>

      {lastMessage &&
      <div className="last-message">
          <h3>{t18('misc.rc_poslednee_obnovlenie')}</h3>
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
