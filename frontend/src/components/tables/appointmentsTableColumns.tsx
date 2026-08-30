/**
 * PR-UI-09e-2: EnhancedAppointmentsTable presentation module —
 * cell renderers hook + canonical DataTable column builder.
 *
 * Verbatim move from EnhancedAppointmentsTable.tsx:
 *   - useAppointmentsTableRenderers: renderStatus / renderServices /
 *     renderVisitType / renderPaymentType / renderQueueNumbers (+ the two
 *     SSOT void-blocks). useCallback wrappers preserved; deps arrays list
 *     ONLY closure values (withOpacity / createServiceMapping are now
 *     stable module-scope imports from appointmentsTableContracts —
 *     dropped from deps, documented per react-hooks/exhaustive-deps).
 *   - buildAppointmentsTableColumns: the 13-column configuration (select /
 *     № / patient / phone / birth-year / address / visit-type / services /
 *     payment+lab / date / status / cost / actions). All identifiers are
 *     destructured from the deps object so the moved column bodies stay
 *     byte-identical to the original.
 *
 * File shape follows the RRT precedent (refundRequestsColumns.tsx,
 * PR-UI-14-6): renderers + columns live in ONE presentation module.
 */

import { useCallback } from 'react';
import { Phone, Home, FileText, Eye, Edit, X, MoreHorizontal, CalendarClock, Calendar, Clock } from 'lucide-react';
import {
  CheckCircle,
  User,
  CreditCard,
  XCircle,
  AlertCircle } from 'lucide-react';
import { Checkbox } from '../ui/macos';
import type { DataTableColumn } from '../ui/DataTable';
import { QueueActionButtons } from '../queue/QueueManagementCard';
import logger from '../../utils/logger';
import { getRegistrarTimestampDisplay } from '../../utils/dateUtils';
import type { RegistrarTimestampRecord } from '../../utils/dateUtils';
import { getLocalDateString } from '../../utils/dateUtils';
import { getServiceDisplayName } from '../../utils/serviceCodeResolver';
import type { Appointment, QueueNumberInfo } from '../../types/domain/clinic';
import {
  type AppointmentRow,
  type AppointmentsTranslationFn,
  withOpacity,
  createServiceMapping,
  getBackendActionAvailability,
  getSessionColorIndex,
} from './appointmentsTableContracts';

export interface UseAppointmentsTableRenderersParams {
  t: AppointmentsTranslationFn;
  services: Record<string, unknown>;
  data: AppointmentRow[];
}

export const useAppointmentsTableRenderers = ({ t, services, data }: UseAppointmentsTableRenderersParams) => {
  // ⭐ SSOT: Display helper for services with queue numbers
  // Format: "K01 (1), D01 (2), L10 (3)"
  void useCallback((rows: Appointment[]) => {
    if (!rows || rows.length === 0) return '—';

    return rows.map((row: Appointment) => {
      let serviceDisplay = '—';
      if (Array.isArray(row.services) && row.services.length > 0) {
        const svc = row.services[0];
        serviceDisplay = typeof svc === 'object' ? svc.code || svc.name || '—' : String(svc);
      } else if (row.service_codes && row.service_codes.length > 0) {
        serviceDisplay = row.service_codes[0];
      }

      const queueNum = row.queue_number ?? row.number ?? '?';
      return `${serviceDisplay} (${queueNum})`;
    }).join(', ');
  }, []);

  // ⭐ SSOT: Display helper for queue numbers
  // Format: "1, 2, 3"
  void useCallback((rows: Appointment[]) => {
    if (!rows || rows.length === 0) return '—';
    return rows.map((r) => r.queue_number ?? r.number ?? '?').join(', ');
  }, []);

  // ✅ Улучшенный рендер статуса (полный контекстный)
  const renderStatus = useCallback((status: string): React.ReactNode => {
    const statusConfig = {
      // Статусы записи
      scheduled: {
        color: 'var(--mac-accent-blue)',
        bg: withOpacity('var(--mac-accent-blue)', 0.12),
        icon: Calendar,
        text: t('misc.eat_status_scheduled'),
        emoji: '📅'
      },
      confirmed: {
        color: 'var(--mac-success)',
        bg: withOpacity('var(--mac-success)', 0.12),
        icon: CheckCircle,
        text: t('misc.eat_status_confirmed'),
        emoji: '✅'
      },

      // Статусы очереди
      waiting: {
        color: 'var(--mac-warning)',
        bg: withOpacity('var(--mac-warning)', 0.12),
        icon: Clock,
        text: t('misc.eat_status_waiting'),
        emoji: '⏳'
      },
      queued: {
        color: 'var(--mac-warning)',
        bg: withOpacity('var(--mac-warning)', 0.12),
        icon: Clock,
        text: t('misc.eat_status_queued'),
        emoji: '⏳'
      },
      called: {
        color: 'var(--mac-accent-blue)',
        bg: withOpacity('var(--mac-accent-blue)', 0.12),
        icon: User,
        text: t('misc.eat_status_called'),
        emoji: '📢'
      },
      in_progress: {
        color: 'var(--mac-accent-blue)',
        bg: withOpacity('var(--mac-accent-blue)', 0.12),
        icon: User,
        text: t('misc.eat_status_in_progress'),
        emoji: '👨‍⚕️'
      },
      in_cabinet: {
        color: 'var(--mac-accent-blue)',
        bg: withOpacity('var(--mac-accent-blue)', 0.12),
        icon: User,
        text: t('misc.eat_status_in_cabinet'),
        emoji: '👤'
      },
      in_visit: {
        color: 'var(--mac-accent-blue)',
        bg: withOpacity('var(--mac-accent-blue)', 0.12),
        icon: User,
        text: t('misc.eat_status_in_visit'),
        emoji: '👨‍⚕️'
      },

      // Завершённые статусы
      served: {
        color: 'var(--mac-success)',
        bg: withOpacity('var(--mac-success)', 0.12),
        icon: CheckCircle,
        text: t('misc.eat_status_served'),
        emoji: '✅'
      },
      done: {
        color: 'var(--mac-success)',
        bg: withOpacity('var(--mac-success)', 0.12),
        icon: CheckCircle,
        text: t('misc.eat_status_done'),
        emoji: '✅'
      },

      // Статусы оплаты
      paid_pending: {
        color: 'var(--mac-warning)',
        bg: withOpacity('var(--mac-warning)', 0.12),
        icon: CreditCard,
        text: t('misc.eat_status_paid_pending'),
        emoji: '⏳'
      },
      payment_paid: {
        color: 'var(--mac-success)',
        bg: withOpacity('var(--mac-success)', 0.12),
        icon: CheckCircle,
        text: t('misc.eat_status_payment_paid'),
        emoji: '✅'
      },
      paid: {
        color: 'var(--mac-success)',
        bg: withOpacity('var(--mac-success)', 0.12),
        icon: CheckCircle,
        text: t('misc.eat_status_paid'),
        emoji: '✅'
      },

      // Отрицательные статусы
      cancelled: {
        color: 'var(--mac-error)',
        bg: withOpacity('var(--mac-error)', 0.12),
        icon: XCircle,
        text: t('misc.eat_status_cancelled'),
        emoji: '❌'
      },
      // ✅ Исправлено: поддержка написания с одной l (как на бэкенде)
      canceled: {
        color: 'var(--mac-error)',
        bg: withOpacity('var(--mac-error)', 0.12),
        icon: XCircle,
        text: t('misc.eat_status_canceled'),
        emoji: '❌'
      },
      no_show: {
        color: 'var(--mac-text-secondary)',
        bg: withOpacity('var(--mac-text-secondary)', 0.12),
        icon: AlertCircle,
        text: t('misc.eat_status_no_show'),
        emoji: '👻'
      },

      // Старые статусы (для совместимости)
      plan: {
        color: 'var(--mac-accent-blue)',
        bg: withOpacity('var(--mac-accent-blue)', 0.12),
        icon: Calendar,
        text: t('misc.eat_status_plan'),
        emoji: '📅'
      }
    };

    const config = statusConfig[status as keyof typeof statusConfig] || statusConfig.scheduled;

    return (
      <div
        className="status-badge"
        title={config.text}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-1)',
          padding: 'var(--mac-spacing-1) var(--mac-spacing-2)',
          borderRadius: 'var(--mac-radius-sm)',
          backgroundColor: config.bg,
          color: config.color,
          fontSize: 'var(--mac-font-size-xs)',
          fontWeight: 'var(--mac-font-weight-medium)',
          cursor: 'help',
          border: `1px solid ${withOpacity(config.color, 0.2)}`
        }}>
        <span className="eat-status-emoji">{config.emoji}</span>
        <span>{config.text}</span>
      </div>);

  }, [t]);

  // Рендер услуг с динамическим маппингом
  const renderServices = useCallback((appointmentServices: unknown, allPatientServices: Array<unknown> | null = null) => {
    if (!appointmentServices) {
      return '—';
    }

    const { mapping: serviceMapping, nameToService, codeToService } = createServiceMapping(services);

    // Поддерживаем как массив строк, так и массив объектов
    let servicesList: unknown[] = [];
    if (Array.isArray(appointmentServices)) {
      servicesList = appointmentServices.map((service: unknown) => {
        // Обрабатываем строки-числа (ID услуг)
        if (typeof service === 'string' && /^\d+$/.test(service)) {
          return serviceMapping[service] || t('misc.eat_service_label', { service });
        }
        // Если это просто число
        if (typeof service === 'number') {
          return serviceMapping[service] || serviceMapping[String(service)] || t('misc.eat_service_label', { service });
        }
        // Потом обычные строки
        if (typeof service === 'string') return service;
        // ⭐ ИСПРАВЛЕНО: Если объект имеет code - возвращаем код напрямую (не name!)
        // Это важно, чтобы K11 не превратился в K01 при поиске по name
        if (typeof service === 'object' && service !== null && (service as Record<string, unknown>).code) {
          return String((service as Record<string, unknown>).code).toUpperCase();
        }
        if (typeof service === 'object' && service !== null && (service as Record<string, unknown>).name) return String((service as Record<string, unknown>).name);
        return String(service);
      });
    } else if (typeof appointmentServices === 'string') {
      servicesList = [appointmentServices];
    } else {
      return String(appointmentServices);
    }

    if (servicesList.length === 0) {
      return '—';
    }

    // ✅ Функция проверки, является ли строка кодом (а не названием)
    const isServiceCode = (str: string) => {
      if (!str || typeof str !== 'string') return false;
      // Коды обычно короткие (до 20 символов), без пробелов, могут содержать подчеркивания, дефисы, буквы и цифры
      // Названия обычно длинные (более 20 символов), содержат пробелы и русские буквы
      if (str.length > 30) return false; // Длинные строки - скорее названия
      if (/\s/.test(str)) return false; // Содержит пробелы - скорее название
      // Паттерны кодов: K01, D02, D_PROC03, ECG-001, C01 и т.д.
      return /^[A-Z][A-Z0-9_-]*\d+$/i.test(str) || /^[A-Z]\d{2}$/.test(str);
    };

    // ✅ ИСПОЛЬЗУЕМ НОВЫЕ КОДЫ ИЗ БАЗЫ ДАННЫХ
    // audit/phase-6, BS-61: use nameToService map (O(1)) instead of nested
    // Object.values(services).find() (O(groups × group_size) per service).
    const compactCodes: string[] = servicesList.map((serviceName: unknown) => {
      // Если это уже код (K01, D02, D_PROC03, etc), возвращаем в верхнем регистре
      if (isServiceCode(String(serviceName))) {
        return String(serviceName).toUpperCase();
      }

      // Если это название, ищем услугу через O(1) map lookup
      const foundService = nameToService[String(serviceName).toLowerCase()];
      if (foundService) {
        // Используем service_code если есть, иначе генерируем из category_code
        if (foundService.service_code) {
          return String(foundService.service_code).toUpperCase();
        }
        // Если есть category_code но нет service_code, генерируем временный код
        if (foundService.category_code) {
          return `${String(foundService.category_code).toUpperCase()}${String(foundService.id).padStart(2, '0')}`;
        }
      }

      // Если ничего не найдено и это не код, возвращаем как есть (название)
      return String(serviceName);
    });

    // ✅ Преобразуем коды обратно в названия для tooltip
    // ⭐ SSOT: Используем централизованную функцию getServiceDisplayName
    // audit/phase-6, BS-61: use codeToService map (O(1)) instead of nested find().
    const serviceNamesForTooltip: string[] = compactCodes.map((code: string) => {
      // Если это код, ищем полное название через SSOT
      if (isServiceCode(code)) {
        // ⭐ SSOT: Сначала используем централизованный маппинг
        const ssotName = getServiceDisplayName(code);
        if (ssotName && ssotName !== code) {
          return ssotName;
        }

        // Fallback: O(1) lookup in codeToService map (keyed by uppercase code)
        const foundService = codeToService[code.toUpperCase()];
        if (foundService) {
          return String(foundService.name);
        }

        // Если не нашли название для кода, возвращаем код как есть
        return code;
      }

      // Если это не код (уже название), возвращаем как есть
      return code;
    });

    // Создаем tooltip с полным списком услуг пациента
    let tooltipText = '';

    if (allPatientServices && allPatientServices.length > 0) {
      // ✅ Преобразуем коды всех услуг в названия
      // audit/phase-6, BS-61: use codeToService map (O(1)) instead of two
      // nested find() loops per service.
      const allPatientServiceNames = allPatientServices.map((service: unknown) => {
        // Если это уже название (длинное, с пробелами), возвращаем как есть
        if (typeof service === 'string' && service.length > 20 && /\s/.test(service)) {
          return service;
        }

        // Если это код, ищем название через O(1) map lookup
        if (isServiceCode(service as string)) {
          const foundService = codeToService[String(service).toUpperCase()];
          if (foundService) {
            return String(foundService.name);
          }

          // Если не нашли, возвращаем код
          return String(service);
        }

        // Иначе возвращаем как есть
        return String(service);
      });

      // Показываем все услуги пациента из всех отделений
      tooltipText = `${t('misc.eat_all_services_tooltip', { count: allPatientServiceNames.length })}\n\n`;
      allPatientServiceNames.forEach((service: unknown, idx: number) => {
        tooltipText += `${idx + 1}. ${String(service)}\n`;
      });

      // Добавляем информацию о текущих услугах с полными названиями
      if (serviceNamesForTooltip.length > 0) {
        tooltipText += `\n${t('misc.eat_current_services_tooltip', { count: serviceNamesForTooltip.length })}\n`;
        serviceNamesForTooltip.forEach((serviceName) => {
          tooltipText += `• ${serviceName}\n`;
        });
      }
    } else {
      // Fallback: показываем только текущие услуги с полными названиями
      tooltipText = serviceNamesForTooltip.length > 1 ?
      `${t('misc.eat_services_tooltip')}\n${serviceNamesForTooltip.map((serviceName: string, idx: number) => `${idx + 1}. ${serviceName}`).join('\n')}` :
      serviceNamesForTooltip[0] || '';
    }

    return (
      <div
        className="eat-service-code-wrap"
        title={tooltipText}>

        {compactCodes.map((code: string, idx: number) =>
        <span
          key={idx}
          style={{
            padding: '2px 6px',
            borderRadius: 'var(--mac-radius-sm)',
            fontSize: 'var(--mac-font-size-xs)',
            fontWeight: 'var(--mac-font-weight-bold)',
            backgroundColor: withOpacity('var(--mac-accent-blue)', 0.12),
            color: 'var(--mac-accent-blue)',
            border: `1px solid ${withOpacity('var(--mac-accent-blue)', 0.25)}`
          }}>

            {code}
          </span>
        )}
      </div>);

  }, [services, t]);

  // Рендер типа обращения
  const renderVisitType = useCallback((visitType: string) => {
    const typeColors = {
      paid: 'var(--mac-accent-blue)',
      repeat: 'var(--mac-success)',
      free: 'var(--mac-warning)',
      allfree: '#ff6b35',
      mixed: 'var(--mac-text-secondary)'
    };

    const typeText = t(`misc.eat_${visitType}`, { defaultValue: visitType });
    const color = typeColors[visitType as keyof typeof typeColors] || 'var(--mac-text-secondary)';

    // ✅ ИСПРАВЛЕНО: Для allfree используем rgba напрямую, так как withOpacity работает только с CSS переменными
    const isAllFree = visitType === 'allfree';
    const isMixed = visitType === 'mixed';
    const backgroundColor = isAllFree ?
    'rgba(255, 107, 53, 0.08)' :
    isMixed ?
    'rgba(142, 142, 147, 0.10)' :
    withOpacity(color, 0.08);
    const borderColor = isAllFree ?
    'rgba(255, 107, 53, 0.2)' :
    isMixed ?
    'rgba(142, 142, 147, 0.25)' :
    withOpacity(color, 0.2);

    return (
      <span style={{
        padding: '3px 6px',
        borderRadius: 'var(--mac-radius-md)',
        fontSize: 'var(--mac-font-size-xs)',
        fontWeight: 'var(--mac-font-weight-semibold)',
        backgroundColor: backgroundColor,
        color: color,
        border: `1px solid ${borderColor}`
      }}>
        {typeText}
      </span>);

  }, [t]);

  // Рендер вида оплаты (i18next migration)
  const renderPaymentType = useCallback((paymentType: string, paymentStatus: string) => {
    const paymentIcons = {
      cash: '💵',
      card: '💳',
      online: '🌐',
      free: '🆓',
      approval_pending: '📝',
      pending_payment: '⌛',
      unknown_payment: '💰',
      mixed_payment: '🔀'
    };

    const paymentColors = {
      cash: 'var(--mac-success)',
      card: 'var(--mac-accent-blue)',
      online: 'var(--mac-accent-blue)',
      free: 'var(--mac-warning)',
      approval_pending: 'var(--mac-warning)',
      pending_payment: 'var(--mac-warning)',
      unknown_payment: 'var(--mac-text-secondary)',
      mixed_payment: 'var(--mac-text-secondary)'
    };

    const statusColors = {
      paid: 'var(--mac-success)',
      pending: 'var(--mac-warning)',
      failed: 'var(--mac-error)'
    };

    const paymentLabels = {
      free: t('misc.eat_payment_free'),
      approval_pending: t('misc.eat_approval_pending'),
      pending_payment: t('misc.eat_pending_payment'),
      unknown_payment: t('misc.eat_unknown_payment'),
      mixed_payment: t('misc.eat_mixed_payment')
    };
    const typeText = paymentLabels[paymentType as keyof typeof paymentLabels] || t(`misc.eat_${paymentType}`, { defaultValue: paymentType });
    const icon = paymentIcons[paymentType as keyof typeof paymentIcons] || '💰';
    const color = paymentColors[paymentType as keyof typeof paymentColors] || 'var(--mac-text-secondary)';void (
    statusColors[paymentStatus as keyof typeof statusColors] || 'var(--mac-text-secondary)');

    // ✅ Упрощённый вид: вид оплаты + иконка статуса
    return (
      <div className="eat-payment-type-wrap">
        <span style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-1)',
          padding: '3px 8px',
          borderRadius: 'var(--mac-radius-sm)',
          fontSize: 'var(--mac-font-size-xs)',
          fontWeight: 'var(--mac-font-weight-medium)',
          backgroundColor: withOpacity(color, 0.08),
          color: color,
          border: `1px solid ${withOpacity(color, 0.2)}`
        }}>
          <span>{icon}</span>
          <span>{typeText}</span>
        </span>
        {paymentStatus &&
        <span className="eat-payment-status-icon">
            {paymentStatus === 'paid' ? '✅' :
          paymentStatus === 'pending' ? '⏳' :
          paymentStatus === 'failed' ? '❌' : ''}
          </span>
        }
      </div>);

  }, [t]);

  // Функция для отображения номеров очередей
  const renderQueueNumbers = useCallback((row: Appointment) => {
    // Получаем текущую дату
    const today = getLocalDateString();

    // Helper для форматирования времени





    // Если запись на текущий день - показываем номер в очереди
    if (row.date === today || row.appointment_date === today) {
      // ✅ ИСПРАВЛЕНО: Используем queue_number (уже выбран для текущей вкладки в RegistrarPanel)
      // вместо отображения всех номеров из queue_numbers, что вызывало дублирование
      if (row.queue_number !== undefined && row.queue_number !== null) {
        // ✅ ИСПРАВЛЕНО: Используем статус из queue_number_status (соответствует текущей вкладке)
        // или ищем соответствующий queue_number в queue_numbers для получения его статуса
        let queueStatus: string | undefined = row.queue_number_status;
        if (!queueStatus && row.queue_numbers && Array.isArray(row.queue_numbers)) {
          // Ищем queue_number в queue_numbers и берём его статус
          const matchingQueue = row.queue_numbers.find((q: QueueNumberInfo) => q.number === row.queue_number);
          if (matchingQueue) {
            queueStatus = matchingQueue.status as string | undefined;
          } else if (row.queue_numbers.length > 0) {
            // ✅ ИСПРАВЛЕНО: Если не нашли точное совпадение, используем статус из первого queue_number
            // вместо общего row.status, так как статусы отдельных очередей могут отличаться
            queueStatus = row.queue_numbers[0].status as string | undefined;
          }
        }
        const queueStatusKey = queueStatus || 'unknown';
        const statusConfig = {
          waiting: {
            bg: 'var(--mac-warning, #ff9500)',
            icon: '⏳',
            text: t('misc.eat_q_status_waiting'),
            pulse: true
          },
          called: {
            bg: 'var(--mac-accent-blue, #007aff)',
            icon: '📢',
            text: t('misc.eat_status_called'),
            pulse: true
          },
          served: {
            bg: 'var(--mac-success, #34c759)',
            icon: '✅',
            text: t('misc.eat_status_served'),
            pulse: false
          },
          no_show: {
            bg: 'var(--mac-error, #ff3b30)',
            icon: '❌',
            text: t('misc.eat_status_no_show'),
            pulse: false
          },
          unknown: {
            bg: 'var(--mac-text-secondary, #8e8e93)',
            icon: '?',
            text: t('misc.eat_q_status_unknown'),
            pulse: false
          }
        };

        const config = statusConfig[queueStatusKey as keyof typeof statusConfig] || statusConfig.unknown;

        return (
          <>
          <span
            style={{
              padding: 'var(--mac-spacing-1) var(--mac-spacing-2)',
              backgroundColor: config.bg,
              color: 'var(--mac-text-primary)',
              borderRadius: 'var(--mac-radius-sm)',
              fontSize: 'var(--mac-font-size-base)',
              fontWeight: 'var(--mac-font-weight-bold)',
              minWidth: '32px',
              textAlign: 'center',
              display: 'inline-block',
              boxShadow: 'var(--mac-shadow-sm, 0 2px 4px rgba(0,0,0,0.1))'
            }}
            title={`№${String(row.queue_number ?? '')}`}>

            {String(row.queue_number ?? '')}
          </span>

          {/* UX Audit Registrar #8: показываем дополнительные queue numbers
              если у пациента несколько талонов (multi-service запись).
              Раньше показывался только первый номер — остальные игнорировались. */}
          {Array.isArray(row.queue_numbers) && row.queue_numbers.length > 1 && (
            <span
              style={{
                marginLeft: 'var(--mac-spacing-1)',
                padding: '2px 6px',
                backgroundColor: 'color-mix(in srgb, var(--mac-accent-blue, #007aff), transparent 85%)',
                color: 'var(--mac-accent-blue, #007aff)',
                borderRadius: 'var(--mac-radius-sm)',
                fontSize: 'var(--mac-font-size-xs)',
                fontWeight: 'var(--mac-font-weight-semibold)',
              }}
              title={row.queue_numbers.map((q: QueueNumberInfo) => t('misc.eat_queue_label', { queueName: q.queue_name || t('misc.eat_queue_default'), number: q.number })).join('\n')}
            >
              +{row.queue_numbers.length - 1}
            </span>
          )}
          </>
      );
      }

      // Fallback: Если есть номера очередей, но нет queue_number - показываем первый
      if (row.queue_numbers && Array.isArray(row.queue_numbers) && row.queue_numbers.length > 0) {
        const firstQueue = row.queue_numbers[0];
        const queueStatusKey = firstQueue.status || 'unknown';
        const statusConfig = {
          waiting: {
            bg: 'var(--mac-warning, #ff9500)',
            icon: '⏳',
            text: t('misc.eat_q_status_waiting'),
            pulse: true
          },
          called: {
            bg: 'var(--mac-accent-blue, #007aff)',
            icon: '📢',
            text: t('misc.eat_status_called'),
            pulse: true
          },
          served: {
            bg: 'var(--mac-success, #34c759)',
            icon: '✅',
            text: t('misc.eat_status_served'),
            pulse: false
          },
          no_show: {
            bg: 'var(--mac-error, #ff3b30)',
            icon: '❌',
            text: t('misc.eat_status_no_show'),
            pulse: false
          },
          unknown: {
            bg: 'var(--mac-text-secondary, #8e8e93)',
            icon: '?',
            text: t('misc.eat_q_status_unknown'),
            pulse: false
          }
        };

        const config = statusConfig[queueStatusKey as keyof typeof statusConfig] || statusConfig.unknown;

        return (
          <>
          <span
            style={{
              padding: 'var(--mac-spacing-1) var(--mac-spacing-2)',
              backgroundColor: config.bg,
              color: 'var(--mac-text-primary)',
              borderRadius: 'var(--mac-radius-sm)',
              fontSize: 'var(--mac-font-size-base)',
              fontWeight: 'var(--mac-font-weight-bold)',
              minWidth: '32px',
              textAlign: 'center',
              display: 'inline-block',
              boxShadow: 'var(--mac-shadow-sm, 0 2px 4px rgba(0,0,0,0.1))'
            }}
            title={t('misc.eat_queue_label', { queueName: firstQueue.queue_name || t('misc.eat_queue_default'), number: firstQueue.number })}>

            {firstQueue.number}
          </span>

          {/* UX Audit Registrar #8: multi-badge  fallback . */}
          {row.queue_numbers.length > 1 && (
            <span
              style={{
                marginLeft: 'var(--mac-spacing-1)',
                padding: '2px 6px',
                backgroundColor: 'color-mix(in srgb, var(--mac-accent-blue, #007aff), transparent 85%)',
                color: 'var(--mac-accent-blue, #007aff)',
                borderRadius: 'var(--mac-radius-sm)',
                fontSize: 'var(--mac-font-size-xs)',
                fontWeight: 'var(--mac-font-weight-semibold)',
              }}
              title={row.queue_numbers.map((q: QueueNumberInfo) => t('misc.eat_queue_label', { queueName: q.queue_name || t('misc.eat_queue_default'), number: q.number })).join('\n')}
            >
              +{row.queue_numbers.length - 1}
            </span>
          )}
          </>
      );
      }

      // Если нет номеров очередей, но запись на сегодня - показываем порядковый номер
      // Для этого нужно найти позицию записи среди всех записей на сегодня
      const todayAppointments = data.filter((item) =>
      item.date === today || item.appointment_date === today
      );
      const todayIndex = todayAppointments.findIndex((item: AppointmentRow) => item.id === row.id) + 1;

      return (
        <span style={{
          padding: 'var(--mac-spacing-1) var(--mac-spacing-2)',
          backgroundColor: 'var(--mac-accent-blue)',
          color: 'var(--mac-text-primary)',
          borderRadius: 'var(--mac-radius-sm)',
          fontSize: 'var(--mac-font-size-base)',
          fontWeight: 'var(--mac-font-weight-bold)',
          minWidth: '32px',
          textAlign: 'center',
          display: 'inline-block',
          boxShadow: 'var(--mac-shadow-sm, 0 2px 4px rgba(0,0,0,0.1))'
        }}>
          {todayIndex}
        </span>);

    }

    // Для записей не на сегодня показываем дефолтный номер
    const fallbackIndex = data.findIndex((item) => item.id === row.id) + 1;
    return (
      <span style={{
        color: 'var(--mac-text-secondary)',
        fontSize: 'var(--mac-font-size-xs)',
        padding: '2px 6px',
        backgroundColor: withOpacity('var(--mac-text-secondary)', 0.06),
        borderRadius: 'var(--mac-radius-sm)'
      }}>
        #{fallbackIndex}
      </span>);

  }, [data, t]);

  return {
    renderStatus,
    renderServices,
    renderVisitType,
    renderPaymentType,
    renderQueueNumbers,
  };
};

export interface AppointmentsTableColumnsDeps {
  t: AppointmentsTranslationFn;
  isDoctorView: boolean;
  showCheckboxes: boolean;
  selectedRows: Set<unknown>;
  paginatedData: AppointmentRow[];
  handleRowSelect: (id: string | number, checked: boolean) => void;
  handleSelectAll: (checked: boolean) => void;
  onActionClick?: (action: string, row: AppointmentRow, event?: unknown) => void;
  renderStatus: (status: string) => React.ReactNode;
  renderServices: (appointmentServices: unknown, allPatientServices?: Array<unknown> | null) => React.ReactNode;
  renderVisitType: (visitType: string) => React.ReactNode;
  renderPaymentType: (paymentType: string, paymentStatus: string) => React.ReactNode;
  renderQueueNumbers: (row: Appointment) => React.ReactNode;
  formatPhoneNumber: (phone: string) => string;
  getDisplayAmount: (row: Appointment) => number;
}

export const buildAppointmentsTableColumns = ({
  t,
  isDoctorView,
  showCheckboxes,
  selectedRows,
  paginatedData,
  handleRowSelect,
  handleSelectAll,
  onActionClick,
  renderStatus,
  renderServices,
  renderVisitType,
  renderPaymentType,
  renderQueueNumbers,
  formatPhoneNumber,
  getDisplayAmount,
}: AppointmentsTableColumnsDeps): DataTableColumn<AppointmentRow>[] => {
  // PR-UI-09c-4: canonical DataTable column config — internal refactor of the
  // bespoke native <table> onto ui/DataTable (Rule 1: ONE design system).
  // Public props / behavior contract unchanged for all 6 consumers.
  // Layout note: canonical DataTable (09a foundation) does not yet apply
  // per-column width/align to its generated th/td — the legacy 13-column
  // registrar layout is approximated via minWidth wrappers in column titles
  // and content wrappers in renderers. The visual delta is intentional and
  // re-baselined per Rule 13 step A-D (visual-regression.spec.ts 09d/09c-4 note).
  const columns: DataTableColumn<AppointmentRow>[] = [];

  if (showCheckboxes) {
    columns.push({
      key: 'select',
      sortable: false,
      title: (
        <Checkbox
          aria-label={t('misc.eat_select_all')}
          checked={selectedRows.size === paginatedData.length && paginatedData.length > 0}
          onChange={(checked: boolean) => handleSelectAll(checked)} />
      ),
      render: (_value: unknown, row: AppointmentRow) => (
        // Codex P2 fix (09c-4): stop keydown bubbling so Space/Enter on the
        // checkbox toggles selection WITHOUT also activating the row's new
        // keyboard handler (legacy rows had no row keyboard handler; click
        // bubbling is intentionally preserved to match legacy behavior).
        <span
          role="presentation"
          onKeyDown={(e: React.KeyboardEvent<HTMLElement>) => {
            e.stopPropagation();
          }}>
          <Checkbox
            aria-label={`${t('misc.eat_select_all')}: ${row.patient_fio || row.patient_name || row.id}`}
            checked={selectedRows.has(row.id)}
            onChange={(checked: boolean) => {
              handleRowSelect(row.id ?? '', checked);
            }} />
        </span>
      )
    });
  }

  // № — sortable; first content cell carries the session-color and
  // selected-row markers driving the CSS :has() row styling (canonical
  // DataTable has no row-level className/style prop — same CSS-only
  // technique as QueueTable 09c-2, PR-2860).
  columns.push({
    key: 'queue_number',
    sortable: true,
    title: <div className="eat-th-content" style={{ minWidth: '60px' }}>{t('misc.eat_number')}</div>,
    render: (_value: unknown, row: AppointmentRow) => {
      const sessionIdx = getSessionColorIndex(row.session_id ?? '');
      return (
        <span
          className="eat-cell eat-cell--center eat-cell--secondary"
          title={row.session_id ? t('misc.eat_session_label', { sessionId: row.session_id }) : undefined}>
          {sessionIdx >= 0 && <span className={`eat-session-marker eat-session-${sessionIdx}`} aria-hidden="true" />}
          {selectedRows.has(row.id) && <span className="eat-row-selected-marker" aria-hidden="true" />}
          {renderQueueNumbers(row as unknown as Appointment)}
        </span>
      );
    }
  });

  // Пациент
  columns.push({
    key: 'patient_fio',
    sortable: true,
    title: <div className="eat-th-content" style={{ minWidth: isDoctorView ? '15%' : '200px' }}>{t('misc.eat_patient')}</div>,
    render: (_value: unknown, row: AppointmentRow) => (
      <div
        className="eat-cell eat-cell--patient eat-cell--nowrap"
        style={{ minWidth: isDoctorView ? '15%' : '200px' }}
        title={isDoctorView ? `${row.patient_fio || '—'}\n📞 ${formatPhoneNumber(row.patient_phone ?? '')}\n🏠 ${row.address || '—'}` : undefined}>
        <div>
          <div className="eat-td-flex">
            <span>{row.patient_fio || '—'}</span>
            {/* SSOT: source='online' → QR badge */}
            {row.source === 'online' &&
              <span
                style={{
                  fontSize: 'var(--mac-font-size-xs)',
                  padding: '2px 6px',
                  borderRadius: 'var(--mac-radius-sm)',
                  background: 'linear-gradient(135deg, var(--mac-accent-purple) 0%, var(--mac-accent-purple) 100%)',
                  color: 'white',
                  fontWeight: 'var(--mac-font-weight-semibold)',
                  whiteSpace: 'nowrap'
                }}
                title={t('misc.eat_qr_priority_title')}>
                QR
              </span>
            }
            {row.source === 'desk' &&
              <span
                style={{
                  fontSize: 'var(--mac-font-size-xs)',
                  padding: '2px 6px',
                  borderRadius: 'var(--mac-radius-sm)',
                  background: 'var(--mac-separator)',
                  color: 'var(--mac-text-secondary)',
                  fontWeight: 'var(--mac-font-weight-semibold)',
                  whiteSpace: 'nowrap'
                }}>
                Manual
              </span>
            }
          </div>
          {typeof row.patient_birth_year === 'number' && row.patient_birth_year > 0 &&
            <div className="eat-patient-age">
              {t('misc.eat_years_old', { count: new Date().getFullYear() - row.patient_birth_year })}
            </div>
          }
        </div>
      </div>
    )
  });

  // Телефон (только registrar view)
  if (!isDoctorView) {
    columns.push({
      key: 'patient_phone',
      sortable: false,
      title: <div className="eat-th-content" style={{ minWidth: '170px' }}>{t('misc.eat_phone')}</div>,
      render: (_value: unknown, row: AppointmentRow) => (
        <div className="eat-cell eat-cell--primary eat-cell--nowrap" style={{ minWidth: '170px' }}>
          <div className="eat-phone-cell">
            <Phone size={18} className="eat-phone-icon" />
            {formatPhoneNumber(row.patient_phone ?? '')}
          </div>
        </div>
      )
    });
  }

  // Год рождения
  columns.push({
    key: 'patient_birth_year',
    sortable: true,
    title: <div className="eat-th-content eat-cell--center" style={{ minWidth: '60px' }}>{t('misc.eat_birth_year')}</div>,
    render: (_value: unknown, row: AppointmentRow) => (
      <span className="eat-cell eat-cell--center eat-cell--primary">
        {String(row.patient_birth_year ?? '—')}
      </span>
    )
  });

  // Адрес (только registrar view, скрыт на mobile)
  if (!isDoctorView) {
    columns.push({
      key: 'patient_address',
      sortable: false,
      title: <div className="eat-th-content hide-on-mobile" style={{ minWidth: '140px' }}>{t('misc.eat_address')}</div>,
      render: (_value: unknown, row: AppointmentRow) => (
        <div
          className="eat-cell eat-cell--primary hide-on-mobile"
          style={{ minWidth: '140px', whiteSpace: 'normal', lineHeight: '1.4' }}
          title={String(row.address ?? '')}>
          {row.address ?
            <div className="eat-phone-cell">
              <Home size={18} style={{
                color: 'var(--mac-accent-blue)',
                fontWeight: 'var(--mac-font-weight-bold)',
                filter: 'drop-shadow(0 1px 2px rgba(0,0,0,0.1))',
                flexShrink: 0
              }} />
              <span className="eat-address-text">
                {String(row.address ?? '')}
              </span>
            </div> :
            '—'}
        </div>
      )
    });
  }

  // Тип визита
  columns.push({
    key: 'visit_type',
    sortable: false,
    title: <div className="eat-th-content eat-cell--center" style={{ minWidth: isDoctorView ? '70px' : '80px' }}>{t('misc.eat_visit_type')}</div>,
    render: (_value: unknown, row: AppointmentRow) => (
      <span className="eat-cell eat-cell--center" style={{ minWidth: isDoctorView ? '70px' : '80px' }}>
        {renderVisitType((() => {
          // Проверяем и discount_mode, и approval_status для all_free
          const discountMode = row.discount_mode;
          if (discountMode === 'mixed') return 'mixed';
          const isAllFreeApproved = discountMode === 'all_free' && row.approval_status === 'approved';
          if (discountMode === 'benefit') return 'free';
          if (discountMode === 'repeat') return 'repeat';
          if (isAllFreeApproved || discountMode === 'all_free') return 'allfree';
          return 'paid';
        })())}
      </span>
    )
  });

  // Услуги
  columns.push({
    key: 'services',
    sortable: false,
    title: <div className="eat-th-content" style={{ minWidth: isDoctorView ? '12%' : '180px' }}>{t('misc.eat_services')}</div>,
    render: (_value: unknown, row: AppointmentRow) => (
      <div className="eat-cell" style={{ minWidth: isDoctorView ? '12%' : '180px' }}>
        {/* Fallback-цепочка: services → service_name → queue_numbers[0].service_name → specialty */}
        {renderServices(
          (() => {
            if (row.services && (Array.isArray(row.services) ? row.services.length > 0 : true)) {
              return row.services;
            }
            if (row.service_name) {
              return [row.service_name];
            }
            if (row.queue_numbers && row.queue_numbers.length > 0 && row.queue_numbers[0].service_name) {
              return [row.queue_numbers[0].service_name];
            }
            if (row.queue_numbers && row.queue_numbers.length > 0 && row.queue_numbers[0].specialty) {
              return [row.queue_numbers[0].specialty];
            }
            return row.services;
          })(),
          (Array.isArray(row.all_patient_services) ? row.all_patient_services : null)
        )}
      </div>
    )
  });

  // Тип оплаты (+ lab report badge — в 09c-4 свёрнута в эту ячейку:
  // условный построчный <td> в legacy-разметке смещал колонки)
  columns.push({
    key: 'payment_type',
    sortable: false,
    title: <div className="eat-th-content eat-cell--center" style={{ minWidth: isDoctorView ? '8%' : '100px' }}>{t('misc.eat_payment_type')}</div>,
    render: (_value: unknown, row: AppointmentRow) => (
      <div className="eat-cell eat-cell--center" style={{ minWidth: isDoctorView ? '8%' : '100px' }}>
        {renderPaymentType(
          String((() => {
            if (row.payment_type === 'mixed_payment') {
              return 'mixed_payment';
            }
            if (row.payment_type === 'approval_pending') {
              return 'approval_pending';
            }
            if (row.payment_type === 'free') {
              return 'free';
            }
            const discountMode = row.discount_mode;
            const paymentStatus = (String(row.payment_status || '')).toLowerCase();
            const amount = getDisplayAmount(row as unknown as Appointment);
            const isApprovedAllFree = discountMode === 'all_free' && row.approval_status === 'approved';
            const isPendingAllFree = discountMode === 'all_free' && row.approval_status !== 'approved';
            const isZeroCostDiscount = ['repeat', 'benefit'].includes(String(discountMode)) && amount <= 0 && paymentStatus !== 'paid';

            if (isPendingAllFree) {
              return 'approval_pending';
            }
            if (isApprovedAllFree || isZeroCostDiscount) {
              return 'free';
            }
            return row.payment_type || (paymentStatus === 'paid' ? 'unknown_payment' : 'pending_payment');
          })()),
          String(row.payment_status ?? '')
        )}
        {Boolean(row.latest_lab_report) && (() => {
          const labReport = row.latest_lab_report as { status?: string; flagged_findings_count?: number; template_name?: string; [k: string]: unknown } | undefined;
          const labStatus = labReport?.status || '';
          const isReady = labStatus === 'FINALIZED' || labStatus === 'PRINTED';
          const flagCount = labReport?.flagged_findings_count || 0;
          return (
            <span
              title={`${labReport?.template_name || t('misc.eat_lab_report_default')} — ${isReady ? t('misc.eat_lab_ready') : t('misc.eat_lab_in_progress')}${flagCount > 0 ? t('misc.eat_lab_flagged', { count: flagCount }) : ''}`}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                marginTop: '2px',
                padding: '2px 8px',
                borderRadius: '10px',
                fontSize: '11px',
                fontWeight: 600,
                background: isReady ? 'rgba(52, 199, 89, 0.12)' : 'rgba(255, 149, 0, 0.12)',
                color: isReady ? 'var(--mac-success)' : 'var(--mac-warning)',
              }}>
              {isReady ? t('misc.eat_lab_ready_badge') : t('misc.eat_lab_in_progress_badge')}
              {flagCount > 0 && ` ⚠${flagCount}`}
            </span>
          );
        })()}
      </div>
    )
  });

  // Дата / время
  columns.push({
    key: 'appointment_date',
    sortable: true,
    title: <div className="eat-th-content eat-cell--center" style={{ minWidth: isDoctorView ? '9%' : '100px' }}>{t('misc.eat_date')}</div>,
    render: (_value: unknown, row: AppointmentRow) => (
      <div className="eat-cell eat-cell--center" style={{ minWidth: isDoctorView ? '9%' : '100px' }}>
        {/* SSOT FIX: ONLY use queue_time. Compute earliest from all patient entries if needed. */}
        {(() => {
          // SSOT: use row.queue_time directly — no aggregation
          const timeDisplay = getRegistrarTimestampDisplay(row as unknown as RegistrarTimestampRecord);

          if (timeDisplay.primaryDate || timeDisplay.primaryTime) {
            return (
              <div title={t('misc.eat_timezone_label', { timeZone: timeDisplay.timeZone })}>
                <div className="eat-time-label">
                  {timeDisplay.primaryLabel}
                </div>
                <div className="eat-th-content">
                  <Calendar size={12} className="eat-calendar-icon" />
                  {timeDisplay.primaryDate}
                </div>
                <div className="eat-time-row">
                  <Clock size={10} />
                  {timeDisplay.primaryTime}
                </div>
                {timeDisplay.showChanged &&
                  <div className="eat-time-changed">
                    {timeDisplay.changedLabel}: {timeDisplay.changedDate} {timeDisplay.changedTime}
                  </div>
                }
              </div>);
          }

          // Fallback: use appointment_date/time for legacy records without queue_time
          if (row.appointment_date || row.appointment_time) {
            return (
              <div>
                <div className="eat-th-content">
                  <Calendar size={12} className="eat-calendar-icon" />
                  {row.appointment_date || '—'}
                </div>
                {row.appointment_time &&
                  <div className="eat-time-row">
                    <Clock size={10} />
                    {String(row.appointment_time ?? '')}
                  </div>
                }
              </div>);
          }

          return '-';
        })()}
      </div>
    )
  });

  // Статус (+ payment sub-badge)
  columns.push({
    key: 'status',
    sortable: true,
    title: <div className="eat-th-content eat-cell--center" style={{ minWidth: isDoctorView ? '7%' : '80px' }}>{t('misc.eat_status')}</div>,
    render: (_value: unknown, row: AppointmentRow) => (
      <div className="eat-cell eat-cell--center eat-cell--nowrap" style={{ minWidth: isDoctorView ? '7%' : '80px' }}>
        {/* UX Audit R-4.4: visit status (основной) + payment badge (если есть). */}
        {renderStatus(String(row.status ?? ''))}
        {row.payment_status && row.payment_status !== 'paid' && (
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '2px',
            marginTop: '2px',
            padding: '1px 4px',
            borderRadius: 'var(--mac-radius-sm)',
            backgroundColor: 'var(--mac-accent-orange-soft, rgba(255, 149, 0, 0.12))',
            color: 'var(--mac-accent-orange, #ff9500)',
            fontSize: '9px',
            fontWeight: 'var(--mac-font-weight-medium)',
          }}>
            💰 {row.payment_status === 'paid_pending' ? t('misc.eat_pending_payment') : String(row.payment_status ?? '')}
          </div>
        )}
      </div>
    )
  });

  // Стоимость
  columns.push({
    key: 'cost',
    sortable: true,
    title: <div className="eat-th-content eat-cell--end" style={{ minWidth: isDoctorView ? '8%' : '90px' }}>{t('misc.eat_cost')}</div>,
    render: (_value: unknown, row: AppointmentRow) => (
      <span
        className="eat-cell eat-cell--end"
        style={{
          minWidth: isDoctorView ? '8%' : '90px',
          color: (() => {
            if (row.cost_display === 'free') return 'var(--mac-warning)';
            const discountMode = row.discount_mode;
            const amount = getDisplayAmount(row as unknown as Appointment);
            const isZeroCostRegistration = ['all_free', 'repeat', 'benefit', 'mixed'].includes(String(discountMode)) && amount <= 0;
            if (isZeroCostRegistration) return 'var(--mac-warning)';
            return amount > 0 ? 'var(--mac-success, #34c759)' : 'var(--mac-text-secondary)';
          })(),
          fontSize: 'var(--mac-font-size-base)',
          fontWeight: 'var(--mac-font-weight-semibold)'
        }}>
        {(() => {
          if (row.cost_display === 'free') {
            return t('misc.eat_payment_free');
          }
          const discountMode = row.discount_mode;
          const amount = getDisplayAmount(row as unknown as Appointment);
          const isZeroCostRegistration = ['all_free', 'repeat', 'benefit', 'mixed'].includes(String(discountMode)) && amount <= 0;
          if (isZeroCostRegistration) {
            return t('misc.eat_payment_free');
          }
          return amount > 0 ? t('misc.eat_amount_with_currency', { amount: amount.toLocaleString() }) : '—';
        })()}
      </span>
    )
  });

  // Действия
  columns.push({
    key: 'actions',
    sortable: false,
    title: <div className="eat-th-content eat-cell--center" style={{ minWidth: isDoctorView ? '15%' : '200px' }}>{t('misc.eat_actions')}</div>,
    render: (_value: unknown, row: AppointmentRow) => {
      const rowRecord = row as Record<string, unknown>;
      const backendCanPay = getBackendActionAvailability(rowRecord, 'payment', 'can_mark_paid');
      const backendCanCall = getBackendActionAvailability(rowRecord, 'call', 'can_start_visit');
      const backendCanPrint = getBackendActionAvailability(rowRecord, 'print', 'can_print_ticket');
      const backendCanComplete = getBackendActionAvailability(rowRecord, 'complete', 'can_complete');
      const backendCanViewEmr = getBackendActionAvailability(rowRecord, 'view_emr', 'can_view_emr');
      const backendCanScheduleNext = getBackendActionAvailability(rowRecord, 'schedule_next', 'can_schedule_next');
      const canPay = !isDoctorView && backendCanPay === true;
      const canCall = isDoctorView && backendCanCall === true;
      const canPrint = backendCanPrint === true;
      const canComplete = isDoctorView && backendCanComplete === true;
      const canViewEmr = isDoctorView && backendCanViewEmr === true;
      const canScheduleNext = isDoctorView && backendCanScheduleNext === true;
      // UX Audit Registrar #4: inline кнопки Cancel и Reschedule для registrar view.
      // Раньше были доступны только через context menu (правый клик),
      // что не работало на touch-устройствах (планшеты в регистратуре).
      const canCancel = !isDoctorView && (
        row?.status === 'waiting' ||
        row?.status === 'called' ||
        row?.status === 'pending' ||
        row?.status === 'confirmed'
      );
      const canReschedule = !isDoctorView && (
        row?.status === 'waiting' ||
        row?.status === 'pending' ||
        row?.status === 'confirmed'
      );
      return (
        <div
          className="eat-actions-cell"
          role="presentation"
          onClick={(e: React.MouseEvent<HTMLElement>) => {
            // Блокируем клик на строку при клике в ячейке действий
            e?.stopPropagation();
          }}
          onMouseDown={(e: React.MouseEvent<HTMLElement>) => {
            // Блокируем mousedown на строку при клике в ячейке действий
            e?.stopPropagation();
          }}
          onKeyDown={(e: React.KeyboardEvent<HTMLElement>) => {
            // Клавиатурная активность кнопок не должна активировать строку
            e.stopPropagation();
          }}>
          {canPay ? (
            <button
              className="action-button action-button--success"
              onMouseDown={(e: React.MouseEvent<HTMLElement>) => {
                e.preventDefault();
                e?.stopPropagation();
              }}
              onClick={(e: React.MouseEvent<HTMLElement>) => {
                e.preventDefault();
                e?.stopPropagation();
                onActionClick?.('payment', row as unknown as AppointmentRow, e);
              }}
              title={t('misc.eat_payment')}>
              {t('misc.eat_payment')}
            </button>
          ) : null}

          {canCall ? (
            <button
              className="action-button action-button--primary"
              onMouseDown={(e: React.MouseEvent<HTMLElement>) => {
                e.preventDefault();
                e?.stopPropagation();
              }}
              onClick={(e: React.MouseEvent<HTMLElement>) => {
                e.preventDefault();
                e?.stopPropagation();
                onActionClick?.('call', row as unknown as AppointmentRow, e);
              }}
              title={t('misc.eat_call_action')}>
              {t('misc.eat_call_action')}
            </button>
          ) : null}

          {canPrint ? (
            <button
              className="action-button"
              onMouseDown={(e: React.MouseEvent<HTMLElement>) => {
                e.preventDefault();
                e?.stopPropagation();
              }}
              onClick={(e: React.MouseEvent<HTMLElement>) => {
                e.preventDefault();
                e?.stopPropagation();
                onActionClick?.('print', row as unknown as AppointmentRow, e);
              }}
              title={t('misc.eat_print')}
              aria-label={t('misc.eat_print')}>
              <FileText size={14} />
            </button>
          ) : null}

          {canComplete ? (
            <button
              className="action-button"
              onMouseDown={(e: React.MouseEvent<HTMLElement>) => {
                e.preventDefault();
                e?.stopPropagation();
              }}
              onClick={(e: React.MouseEvent<HTMLElement>) => {
                e.preventDefault();
                e?.stopPropagation();
                onActionClick?.('complete', row as unknown as AppointmentRow, e);
              }}
              title={t('misc.eat_complete')}>
              {t('misc.eat_complete')}
            </button>
          ) : null}

          {/* Doctor view: очередь — queue action buttons */}
          {isDoctorView && row.queue_entry_id ? (
            <QueueActionButtons
              entry={{
                queue_entry_id: row.queue_entry_id,
                status: row.status,
                queue_status: row.queue_status,
                available_actions: row.available_actions,
                can_no_show: row.can_no_show,
                can_send_to_diagnostics: row.can_send_to_diagnostics,
                can_notify_diagnostics_return: row.can_notify_diagnostics_return,
                can_restore_next: row.can_restore_next,
                can_incomplete: row.can_incomplete,
                can_complete: getBackendActionAvailability(row as Record<string, unknown>, 'complete', 'can_complete')
              }}
              onStatusChange={(action, entry, result) => {
                logger.log(`[EnhancedAppointmentsTable] Queue action: ${action}`, entry, result);
                // Передаём событие наружу для обновления списка
                onActionClick?.(`queue_${action}`, row as unknown as AppointmentRow, null);
              }}
              compact={true} />
          ) : null}

          <button
            className="action-button"
            onMouseDown={(e: React.MouseEvent<HTMLElement>) => {
              e.preventDefault();
              e?.stopPropagation();
              logger.log('[EnhancedAppointmentsTable] Кнопка Просмотр нажата:', row);
            }}
            onClick={(e: React.MouseEvent<HTMLElement>) => {
              e.preventDefault();
              e?.stopPropagation();
              onActionClick?.('view', row as unknown as AppointmentRow, e);
            }}
            title={t('misc.eat_view')}
            aria-label={t('misc.eat_view')}>
            <Eye size={14} />
          </button>

          <button
            className="action-button"
            onMouseDown={(e: React.MouseEvent<HTMLElement>) => {
              e.preventDefault();
              e?.stopPropagation();
              logger.log('[EnhancedAppointmentsTable] Кнопка Редактировать нажата:', row);
            }}
            onClick={(e: React.MouseEvent<HTMLElement>) => {
              e.preventDefault();
              e?.stopPropagation();
              onActionClick?.('edit', row as unknown as AppointmentRow, e);
            }}
            title={t('misc.eat_edit')}
            aria-label={t('misc.eat_edit')}>
            <Edit size={14} />
          </button>

          {/* EMR (doctor view) */}
          {canViewEmr ? (
            <button
              className="action-button action-button--primary"
              onMouseDown={(e: React.MouseEvent<HTMLElement>) => {
                e.preventDefault();
                e?.stopPropagation();
              }}
              onClick={(e: React.MouseEvent<HTMLElement>) => {
                e.preventDefault();
                e?.stopPropagation();
                onActionClick?.('view_emr', row as unknown as AppointmentRow, e);
              }}
              title={t('misc.eat_view_emr')}
              aria-label={t('misc.eat_view_emr')}>
              <FileText size={14} />
            </button>
          ) : null}

          {/* UX Audit Registrar #4: inline кнопки Cancel и Reschedule.
              Раньше только через context menu — недоступно на touch-устройствах. */}
          {canReschedule ? (
            <button
              className="action-button"
              onMouseDown={(e: React.MouseEvent<HTMLElement>) => {
                e.preventDefault();
                e?.stopPropagation();
              }}
              onClick={(e: React.MouseEvent<HTMLElement>) => {
                e.preventDefault();
                e?.stopPropagation();
                onActionClick?.('reschedule', row as unknown as AppointmentRow, e);
              }}
              title={t('misc.eat_reschedule')}
              aria-label={t('misc.eat_reschedule_aria')}>
              <CalendarClock size={14} />
            </button>
          ) : null}

          {canCancel ? (
            <button
              className="action-button"
              onMouseDown={(e: React.MouseEvent<HTMLElement>) => {
                e.preventDefault();
                e?.stopPropagation();
              }}
              onClick={(e: React.MouseEvent<HTMLElement>) => {
                e.preventDefault();
                e?.stopPropagation();
                onActionClick?.('cancel', row as unknown as AppointmentRow, e);
              }}
              title={t('misc.eat_cancel')}
              aria-label={t('misc.eat_cancel_aria')}>
              <X size={14} />
            </button>
          ) : null}

          <button
            className="action-button"
            onMouseDown={(e: React.MouseEvent<HTMLElement>) => {
              e.preventDefault();
              e?.stopPropagation();
            }}
            onClick={(e: React.MouseEvent<HTMLElement>) => {
              e.preventDefault();
              e?.stopPropagation();
              onActionClick?.('more', row as unknown as AppointmentRow, e);
            }}
            title={t('misc.eat_more')}
            aria-label={t('misc.eat_more')}>
            <MoreHorizontal size={14} />
          </button>

          {canScheduleNext ? (
            <button
              className="action-button action-button--primary"
              onMouseDown={(e: React.MouseEvent<HTMLElement>) => {
                e.preventDefault();
                e?.stopPropagation();
              }}
              onClick={(e: React.MouseEvent<HTMLElement>) => {
                e.preventDefault();
                e?.stopPropagation();
                onActionClick?.('schedule_next', row as unknown as AppointmentRow, e);
              }}
              title={t('misc.eat_schedule_next_title')}>
              {t('misc.eat_schedule_next')}
            </button>
          ) : null}
        </div>
      );
    }
  });
  return columns;
};
