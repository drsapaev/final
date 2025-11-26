/**
 * Service Code Utilities
 * Helper functions for working with service codes and categories
 */

/**
 * Normalizes a category code to a standard format
 * @param {string} code - The category code to normalize
 * @returns {string} Normalized category code
 */
export const normalizeCategoryCode = (code) => {
    if (!code) return 'other';

    const normalized = code.toLowerCase().trim();

    // Map common variations to standard codes
    const codeMap = {
        // Specialists
        'k': 'specialists',
        'cardio': 'specialists',
        'cardiology': 'specialists',
        'd': 'specialists',
        'derma': 'specialists',
        'dermatology': 'specialists',
        'c': 'specialists',
        'cosmetology': 'specialists',
        'stomatology': 'specialists',
        'dentistry': 'specialists',
        'dental': 'specialists',

        // Laboratory
        'l': 'laboratory',
        'lab': 'laboratory',
        'laboratory': 'laboratory',

        // Procedures
        'p': 'procedures',
        'proc': 'procedures',
        'procedures': 'procedures',
        'cosmetology': 'procedures',

        // Other
        'o': 'other',
        'other': 'other',
        'general': 'other'
    };

    return codeMap[normalized] || 'other';
};

/**
 * Normalizes a service code (alias for normalizeCategoryCode for backwards compatibility)
 * @param {string} code - Service code to normalize
 * @returns {string} Normalized code
 */
export const normalizeServiceCode = (code) => {
    return normalizeCategoryCode(code);
};

/**
 * Gets the category name from a code
 * @param {string} code - The category code
 * @param {string} language - Language for the name (default: 'ru')
 * @returns {string} Category name
 */
export const getCategoryName = (code, language = 'ru') => {
    const normalized = normalizeCategoryCode(code);

    const names = {
        ru: {
            specialists: 'Специалисты',
            laboratory: 'Лаборатория',
            procedures: 'Процедуры',
            other: 'Прочее'
        },
        uz: {
            specialists: 'Mutaxassislar',
            laboratory: 'Laboratoriya',
            procedures: 'Muolajalar',
            other: 'Boshqa'
        },
        en: {
            specialists: 'Specialists',
            laboratory: 'Laboratory',
            procedures: 'Procedures',
            other: 'Other'
        }
    };

    return names[language]?.[normalized] || names.ru[normalized] || 'Other';
};

/**
 * Gets the category icon/emoji
 * @param {string} code - The category code
 * @returns {string} Category icon
 */
export const getCategoryIcon = (code) => {
    const normalized = normalizeCategoryCode(code);

    const icons = {
        specialists: '👨‍⚕️',
        laboratory: '🧪',
        procedures: '💉',
        other: '📋'
    };

    return icons[normalized] || '📋';
};

/**
 * Parses a service code to extract category and number
 * @param {string} serviceCode - Service code (e.g., 'K01', 'L05')
 * @returns {object} Object with category and number
 */
export const parseServiceCode = (serviceCode) => {
    if (!serviceCode || typeof serviceCode !== 'string') {
        return { category: 'other', number: null };
    }

    const match = serviceCode.match(/^([A-Za-z]+)(\d+)$/);

    if (match) {
        return {
            category: normalizeCategoryCode(match[1]),
            number: parseInt(match[2], 10)
        };
    }

    return { category: 'other', number: null };
};

/**
 * Formats a service code for display
 * @param {string} serviceCode - Service code to format
 * @returns {string} Formatted service code
 */
export const formatServiceCode = (serviceCode) => {
    if (!serviceCode) return '';
    return serviceCode.toUpperCase();
};

/**
 * Formats service code input (uppercase, removes invalid characters)
 * @param {string} input - Raw input
 * @returns {string} Formatted service code
 */
export const formatServiceCodeInput = (input) => {
    if (!input) return '';
    // Remove any non-alphanumeric characters and convert to uppercase
    return input.replace(/[^a-zA-Z0-9]/g, '').toUpperCase();
};

/**
 * Validates a service code format
 * @param {string} serviceCode - Service code to validate
 * @returns {boolean} True if valid
 */
export const isValidServiceCode = (serviceCode) => {
    if (!serviceCode || typeof serviceCode !== 'string') return false;
    return /^[A-Za-z]+\d+$/.test(serviceCode);
};

/**
 * Validates if a category code is valid
 * @param {string} code - Category code to validate
 * @returns {boolean} True if valid
 */
export const isValidCategoryCode = (code) => {
    if (!code || typeof code !== 'string') return false;

    const validCodes = [
        'k', 'cardio', 'cardiology',
        'd', 'derma', 'dermatology',
        'c', 'cosmetology',
        'stomatology', 'dentistry', 'dental',
        'l', 'lab', 'laboratory',
        'p', 'proc', 'procedures',
        'o', 'other', 'general',
        'specialists', 'laboratory', 'procedures', 'other'
    ];

    return validCodes.includes(code.toLowerCase().trim());
};

/**
 * Groups services by category
 * @param {Array} services - Array of service objects
 * @returns {object} Services grouped by category
 */
export const groupServicesByCategory = (services) => {
    if (!Array.isArray(services)) return {};

    return services.reduce((groups, service) => {
        const category = service.category || service.group ||
            normalizeCategoryCode(service.service_code) || 'other';

        if (!groups[category]) {
            groups[category] = [];
        }

        groups[category].push(service);
        return groups;
    }, {});
};

/**
 * Sorts services by code
 * @param {Array} services - Array of service objects
 * @returns {Array} Sorted services
 */
export const sortServicesByCode = (services) => {
    if (!Array.isArray(services)) return [];

    return [...services].sort((a, b) => {
        const codeA = a.service_code || '';
        const codeB = b.service_code || '';
        return codeA.localeCompare(codeB);
    });
};
