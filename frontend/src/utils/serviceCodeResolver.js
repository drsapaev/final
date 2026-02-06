/**
 * SSOT: Service Code Resolution Utilities
 * ========================================
 * 
 * Единственный источник истины для маппинга кодов услуг на frontend.
 * 
 * Формат кодов:
 * - K01, K10 - Кардиология (консультация, ЭхоКГ)
 * - D01 - Дерматология
 * - S01 - Стоматология
 * - L01 - Лаборатория
 * - P01 - Процедуры
 * - C01 - Косметология
 * 
 * @module serviceCodeResolver
 */

// ============================================================================
// SPECIALTY → SERVICE CODE MAPPING
// ============================================================================

/**
 * Маппинг: specialty/alias → default service code
 * Включает русские и английские варианты
 */
export const SPECIALTY_TO_CODE = {
    // Cardiology
    cardiology: 'K01',
    cardio: 'K01',
    cardiolog: 'K01',
    'кардиология': 'K01',
    'кардиолог': 'K01',

    // Dermatology
    dermatology: 'D01',
    derma: 'D01',
    dermatolog: 'D01',
    'дерматология': 'D01',
    'дерматолог': 'D01',

    // Stomatology
    stomatology: 'S01',
    dental: 'S01',
    dentist: 'S01',
    stom: 'S01',
    'стоматология': 'S01',
    'стоматолог': 'S01',

    // Laboratory
    laboratory: 'L01',
    lab: 'L01',
    'лаборатория': 'L01',

    // EchoKG (specialty within cardiology) - shared queue with K01
    echokg: 'K11',
    echo: 'K11',
    'эхокг': 'K11',

    // ECG - separate queue (K10 is the actual service code)
    ecg: 'K10',
    'экг': 'K10',

    // Procedures
    procedures: 'P01',
    procedure: 'P01',
    physio: 'P01',
    'процедуры': 'P01',

    // Cosmetology
    cosmetology: 'C01',
    'косметология': 'C01',
};

// ============================================================================
// SERVICE CODE → DISPLAY NAME MAPPING
// ============================================================================

/**
 * Маппинг: service code → display name (fallback when API unavailable)
 */
export const CODE_TO_NAME = {
    // Cardiology (shared queue: K01 + K11)
    K01: 'Консультация кардиолога',
    K11: 'ЭхоКГ',

    // ECG (separate queue) - K10 is actual code
    K10: 'ЭКГ',

    // Dermatology
    D01: 'Консультация дерматолога',
    D02: 'Дерматоскопия',

    // Stomatology (shared queue: S01 + S10)
    S01: 'Консультация стоматолога',
    S10: 'Рентгенография зубов',

    // Laboratory (shared queue: all L-codes)
    L01: 'Общий анализ крови',
    L00: 'Очередь в лабораторию',

    // Procedures
    P01: 'Дарсонваль',

    // Cosmetology
    C01: 'Плазмолифтинг лица',
};

/**
 * Расширенный маппинг для legacy кодов (из старой системы)
 */
export const LEGACY_CODE_TO_NAME = {
    'consultation.cardiology': 'Консультация кардиолога',
    'echo.cardiography': 'ЭхоКГ',
    'ecg': 'ЭКГ',
    'consultation.dermatology': 'Консультация дерматолога',
    'derm.skin_diagnostics': 'Дерматоскопия',
    'cosmetology.botox': 'Ботулотоксин',
    'cosmetology.mesotherapy': 'Мезотерапия',
    'cosmetology.peel': 'Пилинг',
    'cosmetology.laser': 'Лазерные процедуры',
    'consultation.dentistry': 'Консультация стоматолога',
    'lab.cbc': 'ОАК',
    'lab.biochem': 'Биохимия',
    'lab.urine': 'ОАМ',
    'lab.coag': 'Коагулограмма',
    'lab.hormones': 'Гормоны',
    'lab.infection': 'Инфекции',
    'other.general': 'Прочее',
};

/**
 * Маппинг: service ID (numeric string) → display name
 * Используется для legacy данных где услуги представлены как числовые ID
 */
export const ID_TO_NAME = {
    '1': 'Консультация кардиолога',
    '2': 'ЭхоКГ',
    '3': 'ЭКГ',
    '4': 'Консультация дерматолога',
    '5': 'Дерматоскопия',
    '6': 'Ботулотоксин',
    '7': 'Мезотерапия',
    '8': 'Пилинг',
    '9': 'Лазерные процедуры',
    '10': 'Консультация стоматолога',
    '11': 'ОАК',
    '12': 'Биохимия',
    '13': 'ОАМ',
    '14': 'Коагулограмма',
    '15': 'Гормоны',
    '16': 'Инфекции',
    '17': 'Прочее',
    '29': 'Процедура 29',
    '30': 'Процедура 30',
};

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/**
 * Проверяет, является ли строка валидным кодом формата K01, D01 и т.д.
 * @param {string} value - Значение для проверки
 * @returns {boolean}
 */
export function isServiceCode(value) {
    if (!value || typeof value !== 'string') return false;
    return /^[A-Z]\d{2}$/i.test(value.trim());
}

/**
 * Нормализует specialty/service name → service code
 * 
 * @param {string} value - Specialty, service name, или уже код
 * @returns {string|null} - Service code (K01, D01, etc.) или null
 * 
 * @example
 * toServiceCode('cardiology') // 'K01'
 * toServiceCode('кардиолог')  // 'K01'
 * toServiceCode('K01')        // 'K01'
 * toServiceCode(null)         // null
 */
export function toServiceCode(value) {
    if (!value) return null;

    const normalized = String(value).toLowerCase().trim();

    // Уже код формата K01, D01, etc. - возвращаем в uppercase
    if (isServiceCode(normalized)) {
        return normalized.toUpperCase();
    }

    // Ищем в маппинге
    return SPECIALTY_TO_CODE[normalized] || null;
}

/**
 * Получает display name для service code
 * 
 * @param {string} code - Service code (K01, D01, etc.)
 * @param {Array} servicesData - Массив услуг из API (опционально)
 * @returns {string} - Название услуги для отображения
 * 
 * @example
 * getServiceDisplayName('K01') // 'Консультация кардиолога'
 * getServiceDisplayName('K01', [...services]) // 'Консультация кардиолога' из API
 */
export function getServiceDisplayName(code, servicesData = []) {
    if (!code) return '';

    const normalizedCode = String(code).toUpperCase().trim();

    // Приоритет 1: Ищем в загруженных данных из API
    if (Array.isArray(servicesData) && servicesData.length > 0) {
        const service = servicesData.find(s => {
            const sCode = (s.code || s.service_code || '').toUpperCase();
            return sCode === normalizedCode;
        });
        if (service?.name) return service.name;
    }

    // Приоритет 2: SSOT маппинг
    if (CODE_TO_NAME[normalizedCode]) {
        return CODE_TO_NAME[normalizedCode];
    }

    // Приоритет 3: Legacy маппинг
    if (LEGACY_CODE_TO_NAME[code]) {
        return LEGACY_CODE_TO_NAME[code];
    }

    // Fallback: возвращаем сам код
    return code;
}

/**
 * Извлекает категорию (первая буква) из service code
 * 
 * @param {string} code - Service code (K01, D01, etc.)
 * @returns {string|null} - K, D, S, L, P, C или null
 * 
 * @example
 * getServiceCategory('K01') // 'K'
 * getServiceCategory('K10') // 'K'
 */
export function getServiceCategory(code) {
    if (!isServiceCode(code)) return null;
    return code.charAt(0).toUpperCase();
}

/**
 * Проверяет, относится ли услуга к указанному отделению
 * 
 * @param {string} code - Service code
 * @param {string} department - Department key (cardio, derma, etc.)
 * @returns {boolean}
 */
export function isServiceInDepartment(code, department) {
    if (!code || !department) return false;

    const category = getServiceCategory(code);
    if (!category) return false;

    const departmentToCategory = {
        cardio: 'K',
        cardiology: 'K',
        echokg: 'K',
        derma: 'D',
        dermatology: 'D',
        dental: 'S',
        stomatology: 'S',
        lab: 'L',
        laboratory: 'L',
        procedures: 'P',
        cosmetology: 'C',
    };

    const expectedCategory = departmentToCategory[department.toLowerCase()];
    return category === expectedCategory;
}

/**
 * Резолвит услугу из различных форматов данных
 * 
 * @param {Object} serviceItem - Объект услуги из cart/queue_numbers
 * @param {Array} servicesData - Данные услуг из API
 * @returns {Object} - { service_id, service_code, service_name }
 */
export function resolveService(serviceItem, servicesData = []) {
    const result = {
        service_id: null,
        service_code: null,
        service_name: null,
    };

    if (!serviceItem) return result;

    // Извлекаем service_id
    result.service_id = serviceItem.service_id || serviceItem.id || null;

    // Извлекаем service_code
    result.service_code = serviceItem.service_code
        || serviceItem.code
        || toServiceCode(serviceItem.specialty)
        || toServiceCode(serviceItem.service_name)
        || null;

    // Извлекаем service_name
    if (serviceItem.service_name || serviceItem.name) {
        result.service_name = serviceItem.service_name || serviceItem.name;
    } else if (result.service_code) {
        result.service_name = getServiceDisplayName(result.service_code, servicesData);
    }

    // Если есть service_id, пробуем найти полные данные
    if (result.service_id && Array.isArray(servicesData)) {
        const fullService = servicesData.find(s => s.id === result.service_id);
        if (fullService) {
            result.service_code = result.service_code || fullService.code || fullService.service_code;
            result.service_name = result.service_name || fullService.name;
        }
    }

    return result;
}

// ============================================================================
// UNIFIED SERVICE EXTRACTION FROM INITIAL DATA
// ============================================================================

/**
 * ⭐ SSOT: Унифицированное извлечение услуг из initialData для AppointmentWizardV2
 * 
 * Решает проблему 5 разных источников услуг:
 * 1. service_details (полные данные)
 * 2. services (массив строк/кодов)
 * 3. service_codes (массив кодов)
 * 4. queue_numbers[].service_details
 * 5. queue_numbers[] (fallback на specialty)
 * 
 * @param {Object} initialData - Данные из RegistrarPanel для редактирования
 * @param {Array} servicesData - Загруженные услуги из API (опционально)
 * @returns {Array} - Массив cart items в унифицированном формате
 * 
 * @example
 * const cartItems = normalizeServicesFromInitialData(initialData, servicesData);
 */
export function normalizeServicesFromInitialData(initialData, servicesData = []) {
    if (!initialData) return [];

    const items = [];
    const today = new Date().toISOString().split('T')[0];

    // Получаем doctor_id из initialData
    const defaultDoctorId = initialData.doctor_id
        || initialData.specialist_id
        || (initialData.queue_numbers?.[0]?.specialist_id)
        || null;

    const defaultDate = initialData.date || today;

    /**
     * Helper: Создаёт cart item из данных услуги
     */
    const createCartItem = (serviceData, queueId = null) => {
        const resolved = resolveService(serviceData, servicesData);

        return {
            id: Date.now() + Math.random(),
            service_id: resolved.service_id || serviceData.service_id || serviceData.id || null,
            service_name: resolved.service_name || serviceData.name || serviceData.code || 'Услуга',
            service_code: resolved.service_code || serviceData.code || serviceData.service_code || null,
            service_price: serviceData.price || serviceData.service_price || 0,
            quantity: serviceData.quantity || 1,
            doctor_id: serviceData.doctor_id || defaultDoctorId,
            visit_date: serviceData.date || defaultDate,
            visit_time: serviceData.visit_time || null,
            original_queue_id: queueId,
            _source: serviceData._source || 'unknown',
        };
    };

    /**
     * Helper: Дедупликация и сортировка услуг
     */
    const finalizeItems = (rawItems) => {
        const uniqueItems = [];
        const seenKeys = new Set();

        rawItems.forEach(item => {
            // Формируем уникальный ключ: ID > Code > Name
            // Используем toLowerCase для кодов и имен для надежности
            let key = null;
            if (item.service_id) {
                key = `id:${item.service_id}`;
            } else if (item.service_code) {
                key = `code:${String(item.service_code).toUpperCase()}`;
            } else if (item.service_name) {
                key = `name:${String(item.service_name).toLowerCase()}`;
            } else {
                return; // Пропускаем пустые
            }

            if (!seenKeys.has(key)) {
                seenKeys.add(key);
                uniqueItems.push(item);
            }
        });

        return uniqueItems;
    };

    // ⭐ Приоритет 1: service_details (полные данные из backend)
    if (Array.isArray(initialData.service_details) && initialData.service_details.length > 0) {
        initialData.service_details.forEach(svc => {
            if (svc) {
                items.push(createCartItem({ ...svc, _source: 'service_details' }));
            }
        });
        return finalizeItems(items);
    }

    // ⭐ Приоритет 2: services (массив строк/кодов ИЛИ объектов)
    if (Array.isArray(initialData.services) && initialData.services.length > 0) {
        initialData.services.forEach(serviceItem => {
            if (!serviceItem) return;

            // ⭐ FIX: Обрабатываем как объекты (новый формат), так и строки (legacy)
            if (typeof serviceItem === 'object' && serviceItem !== null) {
                // Объект с service_id, name, code, price, queue_time, etc.
                const foundService = servicesData.find(s =>
                    s.id === serviceItem.service_id ||
                    s.service_code === serviceItem.code ||
                    s.code === serviceItem.code
                );

                items.push(createCartItem({
                    id: serviceItem.service_id || foundService?.id || null,
                    service_id: serviceItem.service_id || foundService?.id || null,
                    name: serviceItem.name || foundService?.name || 'Услуга',
                    code: serviceItem.code || foundService?.service_code || null,
                    price: serviceItem.price || foundService?.price || 0,
                    quantity: serviceItem.quantity || 1,
                    _source: 'services_array',
                }));
            } else {
                // Строка - legacy формат (код или название услуги)
                const serviceName = serviceItem;
                const serviceCode = toServiceCode(serviceName);
                const foundService = servicesData.find(s =>
                    s.service_code === serviceCode ||
                    s.code === serviceCode ||
                    s.name === serviceName
                );

                items.push(createCartItem({
                    id: foundService?.id || null,
                    name: foundService?.name || serviceName,
                    code: serviceCode || serviceName,
                    price: foundService?.price || 0,
                    _source: 'services_array',
                }));
            }
        });
        return finalizeItems(items);
    }

    // ⭐ Приоритет 3: service_codes (массив кодов)
    if (Array.isArray(initialData.service_codes) && initialData.service_codes.length > 0) {
        initialData.service_codes.forEach(serviceCode => {
            if (serviceCode) {
                const normalizedCode = toServiceCode(serviceCode);
                const foundService = servicesData.find(s =>
                    s.service_code === normalizedCode || s.code === normalizedCode
                );

                items.push(createCartItem({
                    id: foundService?.id || null,
                    name: foundService?.name || getServiceDisplayName(normalizedCode),
                    code: normalizedCode || serviceCode,
                    price: foundService?.price || 0,
                    _source: 'service_codes',
                }));
            }
        });
        return finalizeItems(items);
    }

    // ⭐ Приоритет 4: queue_numbers с service_details
    if (Array.isArray(initialData.queue_numbers)) {
        // Сначала проверяем service_details в queue_numbers
        const firstQueueWithDetails = initialData.queue_numbers.find(q =>
            Array.isArray(q.service_details) && q.service_details.length > 0
        );

        if (firstQueueWithDetails) {
            firstQueueWithDetails.service_details.forEach(svc => {
                if (svc) {
                    items.push(createCartItem(
                        { ...svc, _source: 'queue_numbers.service_details' },
                        firstQueueWithDetails.id
                    ));
                }
            });
            return finalizeItems(items);
        }

        // ⭐ Приоритет 5: queue_numbers (fallback на specialty/service_name)
        initialData.queue_numbers.forEach(q => {
            const serviceName = q.service_name || q.specialty || 'Консультация';
            const serviceCode = toServiceCode(serviceName) || toServiceCode(q.specialty);
            const foundService = servicesData.find(s =>
                s.service_code === serviceCode ||
                s.code === serviceCode ||
                s.id === q.service_id
            );

            items.push(createCartItem({
                id: q.service_id || foundService?.id || null,
                name: foundService?.name || q.service_name || serviceName,
                code: serviceCode,
                price: foundService?.price || q.service_price || 0,
                quantity: q.quantity || 1,
                doctor_id: q.doctor_id,
                date: q.date,
                visit_time: q.visit_time,
                _source: 'queue_numbers',
            }, q.id));
        });
        return finalizeItems(items);
    }

    return finalizeItems(items);
}




// ============================================================================
// BACKEND SYNCHRONIZATION
// ============================================================================

/**
 * Кэш для динамически загруженных маппингов
 */
let cachedMappings = null;
let lastLoadTime = 0;
const CACHE_TTL = 5 * 60 * 1000; // 5 минут

/**
 * Загружает маппинги с backend API
 * Кэширует результат на 5 минут
 * 
 * @returns {Promise<Object>} - { specialty_to_code, code_to_name, category_mapping, specialty_aliases }
 */
export async function loadMappingsFromBackend() {
    const now = Date.now();

    // Используем кэш если он валиден
    if (cachedMappings && (now - lastLoadTime) < CACHE_TTL) {
        return cachedMappings;
    }

    try {
        // Динамический импорт чтобы избежать циклических зависимостей
        const { servicesService } = await import('../api/services.js');
        const response = await servicesService.getCodeMappings();

        if (response && response.specialty_to_code) {
            cachedMappings = response;
            lastLoadTime = now;

            // Обновляем локальные маппинги
            Object.assign(SPECIALTY_TO_CODE, response.specialty_to_code);
            Object.assign(CODE_TO_NAME, response.code_to_name);

            return response;
        }
    } catch (error) {
        // eslint-disable-next-line no-console
        console.warn('[serviceCodeResolver] Failed to load mappings from backend:', error.message);
    }

    // Fallback на статические маппинги
    return {
        specialty_to_code: SPECIALTY_TO_CODE,
        code_to_name: CODE_TO_NAME,
        category_mapping: {},
        specialty_aliases: {},
    };
}

/**
 * Сбрасывает кэш маппингов
 * Используйте при изменении услуг в админке
 */
export function invalidateMappingsCache() {
    cachedMappings = null;
    lastLoadTime = 0;
}

export default {
    SPECIALTY_TO_CODE,
    CODE_TO_NAME,
    LEGACY_CODE_TO_NAME,
    ID_TO_NAME,
    isServiceCode,
    toServiceCode,
    getServiceDisplayName,
    getServiceCategory,
    isServiceInDepartment,
    resolveService,
    normalizeServicesFromInitialData,
    loadMappingsFromBackend,
    invalidateMappingsCache,
};

