/**
 * Registrar worklist — department-based service filtering (pure).
 *
 * PR-UI-13-2: extracted verbatim from RegistrarPanel.tsx (the 265-LOC
 * filterServicesByDepartment useCallback). The only change: the `services`
 * reference-data map (previously a state closure) is now an explicit
 * parameter — same value, same semantics.
 *
 * Contract (pinned by RegistrarPanel.contract.test.tsx
 * 'filters displayed services by backend department metadata before legacy
 * code prefixes'):
 * - filterByBackendDepartment (backend service_details / services-map
 *   department_key metadata) runs BEFORE the legacy code-prefix fallback
 *   (departmentCodePrefixes) and BEFORE the serviceToCodeMap fallback.
 * - QR-records (queue_numbers) aggregate services across all queue numbers
 *   for the "all departments" tab (departmentKey === null).
 *
 * PRESENTATION-ONLY: filters which services are DISPLAYED per department
 * tab. NOT used for routing, department decisions, or business logic.
 */
import type { Appointment, QueueNumberInfo } from '../../types/domain/clinic';
import { toServiceCode as ssotToServiceCode } from '../../utils/serviceCodeResolver';

export const filterServicesByDepartment = (
  appointment: Appointment,
  departmentKey: string | null,
  services: Record<string, unknown>,
) => {
  // ⭐ SSOT: Используем централизованную функцию toServiceCode
  // Используем только канонический резолв из SSOT
  const toServiceCode = (value: unknown) => {
    if (!value) return null;

    // Сначала пробуем SSOT резолвер
    const ssotResult = ssotToServiceCode(value);
    if (ssotResult) return ssotResult;

    return null;
  };

  // ⭐ Для QR-записей с queue_numbers - собираем услуги из всех queue_numbers
  const normalizeDepartmentKey = (value: unknown) => value ? String(value).toLowerCase().trim() : null;
  const targetDepartmentKey = normalizeDepartmentKey(departmentKey);

  const getServiceIdentity = (serviceItem: unknown): { id: unknown; code: unknown; name: unknown; departmentKey: unknown } => {
    if (serviceItem && typeof serviceItem === 'object') {
      const item = serviceItem as Record<string, unknown>;
      return {
        id: item.id ?? item.service_id ?? null,
        code: item.service_code ?? item.code ?? null,
        name: item.name ?? item.service_name ?? null,
        departmentKey: item.department_key ?? item.departmentKey ?? null
      };
    }

    return {
      id: typeof serviceItem === 'number' || typeof serviceItem === 'string' && !isNaN(Number(serviceItem)) ? Number(serviceItem) : null,
      code: typeof serviceItem === 'string' ? serviceItem : null,
      name: typeof serviceItem === 'string' ? serviceItem : null,
      departmentKey: null
    };
  };

  const serviceMatchesIdentity = (candidate: unknown, identity: { id: unknown; code: unknown; name: unknown; departmentKey: unknown }) => {
    if (!candidate || typeof candidate !== 'object') return false;
    const c = candidate as Record<string, unknown>;
    const candidateId = c.id ?? c.service_id ?? null;
    if (identity.id != null && candidateId != null && Number(candidateId) === Number(identity.id)) return true;

    const candidateCode = c.service_code ?? c.code ?? null;
    if (identity.code && candidateCode && String(candidateCode).toUpperCase() === String(identity.code).toUpperCase()) return true;

    const candidateName = c.name ?? c.service_name ?? null;
    if (identity.name && candidateName && String(candidateName).trim() === String(identity.name).trim()) return true;

    return false;
  };

  const findBackendServiceMeta = (serviceItem: unknown, index: number): Record<string, unknown> | null => {
    const identity = getServiceIdentity(serviceItem);
    if (identity.departmentKey) return identity as Record<string, unknown>;

    const serviceDetails = Array.isArray(appointment.service_details) ? appointment.service_details : [];
    const indexedDetail = serviceDetails[index] as Record<string, unknown> | undefined;
    if (indexedDetail?.department_key) return indexedDetail;

    const detailMatch = serviceDetails.find((detail: unknown) => serviceMatchesIdentity(detail, identity)) as Record<string, unknown> | undefined;
    if (detailMatch?.department_key) return detailMatch;

    if (services && typeof services === 'object') {
      for (const groupServices of Object.values(services)) {
        if (!Array.isArray(groupServices)) continue;
        const serviceMatch = groupServices.find((service: unknown) => serviceMatchesIdentity(service, identity)) as Record<string, unknown> | undefined;
        if (serviceMatch?.department_key) return serviceMatch;
      }
    }

    return null;
  };

  const filterByBackendDepartment = (appointmentServices: unknown[]): unknown[] | null => {
    if (!targetDepartmentKey || !Array.isArray(appointmentServices) || appointmentServices.length === 0) {
      return null;
    }

    let sawBackendDepartment = false;
    const filtered = appointmentServices.filter((serviceItem, index) => {
      const serviceMeta = findBackendServiceMeta(serviceItem, index);
      const serviceDepartmentKey = normalizeDepartmentKey(serviceMeta?.department_key ?? serviceMeta?.departmentKey);
      if (!serviceDepartmentKey) return false;
      sawBackendDepartment = true;
      return serviceDepartmentKey === targetDepartmentKey;
    });

    return sawBackendDepartment ? filtered : null;
  };

  if (appointment.queue_numbers && Array.isArray(appointment.queue_numbers) && appointment.queue_numbers.length > 0) {

    // ⭐ Если НЕТ departmentKey (вкладка "Все отделения") - используем уже имеющиеся services
    if (!departmentKey) {
      // ✅ ИСПРАВЛЕНО: Используем appointment.services напрямую, т.к. они уже содержат правильные коды (K11, L02 и т.д.)
      // Раньше мы генерировали коды из specialty/service_name, что приводило к fallback на K01/L01
      if (appointment.services && Array.isArray(appointment.services) && appointment.services.length > 0) {
        return appointment.services;
      }

      // Fallback: только если services пустой, генерируем из queue_numbers
      const allCodes: string[] = [];
      const seenCodes = new Set<string>();

      appointment.queue_numbers.forEach((qn: QueueNumberInfo) => {
        // Приоритет 1: service_name
        const serviceNameCode = toServiceCode(qn.service_name);
        if (serviceNameCode && !seenCodes.has(serviceNameCode)) {
          allCodes.push(serviceNameCode);
          seenCodes.add(serviceNameCode);
        }
      });

      return allCodes.length > 0 ? allCodes : [];
    }

    // ⭐ Для конкретной вкладки - фильтруем из существующих services по категории
    // ✅ ИСПРАВЛЕНО: Используем appointment.services напрямую, фильтруя по категории отделения
    const backendFilteredServices = filterByBackendDepartment(appointment.services || []);
    if (backendFilteredServices) {
      return backendFilteredServices;
    }

    const departmentCodePrefixes: Record<string, string[]> = {
      'cardio': ['K'], // K01, K11 и т.д. - все кардиоуслуги кроме ECG
      'echokg': ['K10', 'ECG'], // Только ЭКГ (K10)
      'derma': ['D'], // D01 и т.д. (только консультации, не D_PROC)
      'dental': ['S'], // S01, S10 и т.д.
      'lab': ['L'], // L01, L02, L11 и т.д.
      'procedures': ['P', 'C', 'D_PROC'] // P01, P02, C01, C05, D_PROC02 и т.д.
    };

    const allowedPrefixes = departmentCodePrefixes[departmentKey as keyof typeof departmentCodePrefixes] || [];

    // ✅ Фильтруем существующие services по категории
    if (appointment.services && Array.isArray(appointment.services) && appointment.services.length > 0) {
      const filteredByDepartment = appointment.services.filter((serviceItem) => {
        // ✅ ИСПРАВЛЕНО: Извлекаем код из объекта если это объект, иначе используем как строку
        // Backend может возвращать services как [{code: "L10", name: "Общий белок", ...}] или как ["L10"]
        const code = typeof serviceItem === 'object' && serviceItem?.code ?
        String((serviceItem as Record<string, unknown>).code).toUpperCase() :
        String(serviceItem).toUpperCase();

        // Специальная логика для echokg: только K10 и ECG коды
        if (departmentKey === 'echokg') {
          return code === 'K10' || code.startsWith('ECG');
        }

        // Специальная логика для cardio: все K-коды КРОМЕ K10 (ЭКГ)
        if (departmentKey === 'cardio') {
          return code.startsWith('K') && code !== 'K10';
        }

        // Для остальных отделений - проверяем по префиксу
        return allowedPrefixes.some((prefix: string) => code.startsWith(prefix));
      });

      if (filteredByDepartment.length > 0) {
        return filteredByDepartment;
      }
    }

    // Если services не дали подходящих кодов, не подменяем их specialty-эвристикой.
    return [];
  }

  // ⭐ Для обычных записей без queue_numbers
  if (!departmentKey) {
    return appointment.services;
  }

  // ⭐ Стандартная фильтрация по service_codes
  if (!appointment.services || !Array.isArray(appointment.services) || appointment.services.length === 0) {
    return appointment.services;
  }

  const appointmentServiceCodes = appointment.service_codes || [];
  const appointmentServices = appointment.services || [];

  // Создаем маппинг service -> service_code
  const backendFilteredServices = filterByBackendDepartment(appointmentServices);
  if (backendFilteredServices) {
    return backendFilteredServices;
  }

  const serviceToCodeMap = new Map<unknown, string>();

  appointmentServices.forEach((service: unknown, index: number) => {
    if (appointmentServiceCodes[index]) {
      serviceToCodeMap.set(service, String(appointmentServiceCodes[index]).toUpperCase());
      return;
    }

    if (services && typeof services === 'object') {
      for (const groupName in services) {
        const groupServices = (services as Record<string, unknown>)[groupName];
        if (Array.isArray(groupServices)) {
          if (typeof service === 'number' || typeof service === 'string' && !isNaN(Number(service))) {
            const serviceId = parseInt(String(service));
            const serviceByID = groupServices.find((s: Record<string, unknown>) => s.id === serviceId) as Record<string, unknown> | undefined;
            if (serviceByID && serviceByID.service_code) {
              serviceToCodeMap.set(service, String(serviceByID.service_code).toUpperCase());
              return;
            }
          }
          const serviceByName = groupServices.find((s: Record<string, unknown>) => s.name === service) as Record<string, unknown> | undefined;
          if (serviceByName && serviceByName.service_code) {
            serviceToCodeMap.set(service, String(serviceByName.service_code).toUpperCase());
            return;
          }
        }
      }
    }
  });

  // Маппинг категорий по вкладкам
  const departmentCategoryMapping: Record<string, string[]> = {
    'cardio': ['K', 'ECHO'],
    'echokg': ['ECG'],
    'derma': ['D', 'DERM', 'DERM_PROC'],
    'dental': ['S', 'DENT', 'STOM'],
    'lab': ['L'],
    'procedures': ['P', 'C', 'D_PROC']
  };

  const getServiceCategoryByCode = (serviceCode: string) => {
    if (!serviceCode) return null;
    const normalizedCode = String(serviceCode).toUpperCase();

    if (normalizedCode === 'K10' || normalizedCode === 'CARD_ECG' || normalizedCode.includes('ECG') || normalizedCode.includes('ЭКГ')) return 'ECG';
    if (normalizedCode === 'CARD_ECHO' || normalizedCode.includes('ECHO') || normalizedCode.includes('ЭХОКГ')) return 'ECHO';
    if (normalizedCode.match(/^P\d+$/)) return 'P';
    if (normalizedCode.match(/^D_PROC\d+$/)) return 'D_PROC';
    if (normalizedCode.match(/^C\d+$/)) return 'C';
    if (normalizedCode.match(/^K\d+$/) && normalizedCode !== 'K10') return 'K';
    if (normalizedCode.match(/^S\d+$/)) return 'S';
    if (normalizedCode.match(/^L\d+$/)) return 'L';
    if (normalizedCode === 'D01') return 'D';
    if (normalizedCode.startsWith('CONS_CARD')) return 'K';
    if (normalizedCode.startsWith('CONS_DERM') || normalizedCode.startsWith('DERMA_')) return 'DERM';
    if (normalizedCode.startsWith('CONS_DENT') || normalizedCode.startsWith('DENT_') || normalizedCode.startsWith('STOM_')) return 'DENT';
    if (normalizedCode.startsWith('LAB_')) return 'L';
    if (normalizedCode.startsWith('COSM_')) return 'C';
    if (normalizedCode.startsWith('PHYSIO_') || normalizedCode.startsWith('PHYS_')) return 'P';
    if (normalizedCode.startsWith('DERM_PROC_') || normalizedCode.startsWith('DERM_')) return 'D_PROC';
    if (normalizedCode.startsWith('CARD_') && !normalizedCode.includes('ECG')) return 'K';
    return null;
  };

  const targetCategoryCodes = departmentCategoryMapping[departmentKey as keyof typeof departmentCategoryMapping] || [];

  const filteredServices = appointmentServices.
  filter((service: unknown) => {
    const serviceCode = serviceToCodeMap.get(service);
    if (!serviceCode) return false;
    const category = getServiceCategoryByCode(serviceCode);
    return category != null && targetCategoryCodes.includes(category);
  });

  return filteredServices;
};

export default filterServicesByDepartment;
