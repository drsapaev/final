/**
 * Date utility functions for the application
 * Provides consistent date formatting across the app
 */

/**
 * Converts a Date object to YYYY-MM-DD format string
 * @param {Date} date - The date to format (defaults to current date)
 * @returns {string} Date string in YYYY-MM-DD format
 */
export const getLocalDateString = (date = new Date()) => {
    const d = new Date(date);
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
};

/**
 * Gets yesterday's date in YYYY-MM-DD format
 * @returns {string} Yesterday's date string in YYYY-MM-DD format
 */
export const getYesterdayDateString = () => {
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    return getLocalDateString(yesterday);
};

/**
 * Gets tomorrow's date in YYYY-MM-DD format
 * @returns {string} Tomorrow's date string in YYYY-MM-DD format
 */
export const getTomorrowDateString = () => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    return getLocalDateString(tomorrow);
};

/**
 * Gets a date N days from now in YYYY-MM-DD format
 * @param {number} days - Number of days to add (negative for past dates)
 * @returns {string} Date string in YYYY-MM-DD format
 */
export const getDateOffset = (days) => {
    const date = new Date();
    date.setDate(date.getDate() + days);
    return getLocalDateString(date);
};

/**
 * Gets the start of the week (Monday) in YYYY-MM-DD format
 * @param {Date} date - The date to get the week start for (defaults to current date)
 * @returns {string} Week start date string in YYYY-MM-DD format
 */
export const getWeekStart = (date = new Date()) => {
    const d = new Date(date);
    const day = d.getDay();
    const diff = d.getDate() - day + (day === 0 ? -6 : 1); // Adjust when day is Sunday
    d.setDate(diff);
    return getLocalDateString(d);
};

/**
 * Gets the end of the week (Sunday) in YYYY-MM-DD format
 * @param {Date} date - The date to get the week end for (defaults to current date)
 * @returns {string} Week end date string in YYYY-MM-DD format
 */
export const getWeekEnd = (date = new Date()) => {
    const d = new Date(date);
    const day = d.getDay();
    const diff = d.getDate() + (day === 0 ? 0 : 7 - day);
    d.setDate(diff);
    return getLocalDateString(d);
};

/**
 * Formats a date string or Date object to a localized string
 * @param {string|Date} date - The date to format
 * @param {string} locale - The locale to use (defaults to 'ru-RU')
 * @returns {string} Formatted date string
 */
export const formatDate = (date, locale = 'ru-RU') => {
    const d = typeof date === 'string' ? new Date(date) : date;
    return d.toLocaleDateString(locale, {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric'
    });
};

/**
 * Formats a date string or Date object to a localized date-time string
 * @param {string|Date} date - The date to format
 * @param {string} locale - The locale to use (defaults to 'ru-RU')
 * @returns {string} Formatted date-time string
 */
export const formatDateTime = (date, locale = 'ru-RU') => {
    const d = typeof date === 'string' ? new Date(date) : date;
    return d.toLocaleString(locale, {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
};

/**
 * Checks if a date string is today
 * @param {string} dateString - Date string in YYYY-MM-DD format
 * @returns {boolean} True if the date is today
 */
export const isToday = (dateString) => {
    return dateString === getLocalDateString();
};

/**
 * Checks if a date string is in the past
 * @param {string} dateString - Date string in YYYY-MM-DD format
 * @returns {boolean} True if the date is in the past
 */
export const isPast = (dateString) => {
    return dateString < getLocalDateString();
};

/**
 * Checks if a date string is in the future
 * @param {string} dateString - Date string in YYYY-MM-DD format
 * @returns {boolean} True if the date is in the future
 */
export const isFuture = (dateString) => {
    return dateString > getLocalDateString();
};

/**
 * Formats a date for display in a user-friendly format
 * @param {string|Date} date - Date to format
 * @param {string} locale - Locale to use (defaults to 'ru-RU')
 * @returns {string} Formatted date string
 */
export const formatDateDisplay = (date, locale = 'ru-RU') => {
    if (!date) return '';

    try {
        const d = typeof date === 'string' ? new Date(date) : date;
        return d.toLocaleDateString(locale, {
            day: '2-digit',
            month: 'long',
            year: 'numeric'
        });
    } catch {
        return '';
    }
};
