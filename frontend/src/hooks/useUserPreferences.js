/**
 * useUserPreferences - хук для работы с настройками пользователя
 * 
 * Загружает и сохраняет EMR preferences через API
 * Включает локальный кеш для быстрого доступа
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '../api/client';
import logger from '../utils/logger';
import tokenManager from '../utils/tokenManager';

// Дефолтные EMR настройки
const DEFAULT_EMR_PREFERENCES = {
    emr_smart_field_mode: 'ghost',
    emr_show_mode_switcher: true,
    emr_debounce_ms: 500,
    emr_recent_icd10: [],
    emr_recent_templates: [],
    emr_favorite_templates: {},
    emr_custom_templates: []
};

// Ключ для localStorage
const LOCAL_STORAGE_KEY = 'user_preferences_cache';

/**
 * Хук для работы с preferences пользователя
 * @param {number} userId - ID пользователя (опционально, берётся из auth)
 * @param {boolean} autoLoad - автоматически загружать при mount
 */
export const useUserPreferences = (userId = null, autoLoad = true) => {
    const [preferences, setPreferences] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [isDirty, setIsDirty] = useState(false);

    const saveTimeoutRef = useRef(null);
    const loadedRef = useRef(false);

    // Загрузка preferences из API
    const loadPreferences = useCallback(async (forceReload = false) => {
        if (loadedRef.current && !forceReload) return preferences;

        // Проверяем наличие токена авторизации - если нет, используем дефолты
        const token = tokenManager.getAccessToken();
        if (!token && !userId) {
            // Нет авторизации - используем дефолты без API запроса
            const defaultPrefs = { ...DEFAULT_EMR_PREFERENCES };
            setPreferences(defaultPrefs);
            loadedRef.current = true;
            return defaultPrefs;
        }

        setLoading(true);
        setError(null);

        try {
            // Попытка загрузить из localStorage (кеш)
            const cached = localStorage.getItem(LOCAL_STORAGE_KEY);
            if (cached && !forceReload) {
                const parsed = JSON.parse(cached);
                if (parsed && Date.now() - parsed._cachedAt < 5 * 60 * 1000) { // 5 минут
                    setPreferences(parsed);
                    loadedRef.current = true;
                    setLoading(false);
                    return parsed;
                }
            }

            // Загрузка с сервера
            const endpoint = userId
                ? `/user-management/users/${userId}/preferences`
                : '/users/me/preferences';

            const response = await api.get(endpoint);

            if (response.data) {
                const prefs = {
                    ...DEFAULT_EMR_PREFERENCES,
                    ...response.data,
                    _cachedAt: Date.now()
                };

                setPreferences(prefs);
                localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(prefs));
                loadedRef.current = true;

                return prefs;
            }
        } catch (err) {
            logger.warn('Failed to load preferences:', err);

            // Если 401, значит токен протух - чистим его
            if (err.response && err.response.status === 401) {
                localStorage.removeItem('auth_token');
            }

            // ВАЖНО: Устанавливаем loadedRef = true чтобы прекратить повторные попытки
            loadedRef.current = true;

            // Используем defaults если ошибка
            const defaultPrefs = { ...DEFAULT_EMR_PREFERENCES };
            setPreferences(defaultPrefs);
            setError(err.message);

            return defaultPrefs;
        } finally {
            setLoading(false);
        }
    }, [userId, preferences]);

    // Сохранение preferences в API
    const savePreferences = useCallback(async (updates = {}) => {
        if (!preferences) return false;

        const newPrefs = { ...preferences, ...updates };
        delete newPrefs._cachedAt;

        try {
            const endpoint = userId
                ? `/user-management/users/${userId}/preferences`
                : '/users/me/preferences';

            await api.put(endpoint, newPrefs);

            // Обновляем локальный кеш
            const cachedPrefs = { ...newPrefs, _cachedAt: Date.now() };
            setPreferences(cachedPrefs);
            localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(cachedPrefs));
            setIsDirty(false);

            return true;
        } catch (err) {
            logger.error('Failed to save preferences:', err);
            setError(err.message);
            return false;
        }
    }, [preferences, userId]);

    // Обновить одно поле (с дебаунсом сохранения)
    const updatePreference = useCallback((key, value, saveImmediately = false) => {
        setPreferences(prev => {
            const updated = { ...prev, [key]: value };
            localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify({ ...updated, _cachedAt: Date.now() }));
            return updated;
        });
        setIsDirty(true);

        // Дебаунс сохранения (3 сек)
        if (saveTimeoutRef.current) {
            clearTimeout(saveTimeoutRef.current);
        }

        if (saveImmediately) {
            savePreferences({ [key]: value });
        } else {
            saveTimeoutRef.current = setTimeout(() => {
                savePreferences({ [key]: value });
            }, 3000);
        }
    }, [savePreferences]);

    // ============================================
    // EMR-специфичные методы
    // ============================================

    // Получить EMR настройки
    const getEMRPreferences = useCallback(() => {
        return {
            mode: preferences?.emr_smart_field_mode || DEFAULT_EMR_PREFERENCES.emr_smart_field_mode,
            showModeSwitcher: preferences?.emr_show_mode_switcher ?? DEFAULT_EMR_PREFERENCES.emr_show_mode_switcher,
            debounceMs: preferences?.emr_debounce_ms || DEFAULT_EMR_PREFERENCES.emr_debounce_ms,
            recentIcd10: preferences?.emr_recent_icd10 || [],
            recentTemplates: preferences?.emr_recent_templates || [],
            favoriteTemplates: preferences?.emr_favorite_templates || {},
            customTemplates: preferences?.emr_custom_templates || []
        };
    }, [preferences]);

    // Обновить режим smart field
    const setSmartFieldMode = useCallback((mode) => {
        updatePreference('emr_smart_field_mode', mode);
    }, [updatePreference]);

    // Добавить недавний ICD-10 код
    const addRecentICD10 = useCallback((code) => {
        const current = preferences?.emr_recent_icd10 || [];
        if (current.includes(code)) {
            // Перемещаем в начало
            const updated = [code, ...current.filter(c => c !== code)].slice(0, 15);
            updatePreference('emr_recent_icd10', updated);
        } else {
            const updated = [code, ...current].slice(0, 15);
            updatePreference('emr_recent_icd10', updated);
        }
    }, [preferences?.emr_recent_icd10, updatePreference]);

    // Добавить недавний шаблон
    const addRecentTemplate = useCallback((templateId) => {
        const current = preferences?.emr_recent_templates || [];
        if (!current.includes(templateId)) {
            const updated = [templateId, ...current].slice(0, 10);
            updatePreference('emr_recent_templates', updated);
        }
    }, [preferences?.emr_recent_templates, updatePreference]);

    // Добавить в избранное
    const addFavoriteTemplate = useCallback((specialty, templateId) => {
        const current = preferences?.emr_favorite_templates || {};
        const specialtyFavorites = current[specialty] || [];

        if (!specialtyFavorites.includes(templateId)) {
            const updated = {
                ...current,
                [specialty]: [...specialtyFavorites, templateId].slice(0, 10)
            };
            updatePreference('emr_favorite_templates', updated);
        }
    }, [preferences?.emr_favorite_templates, updatePreference]);

    // Удалить из избранного
    const removeFavoriteTemplate = useCallback((specialty, templateId) => {
        const current = preferences?.emr_favorite_templates || {};
        const specialtyFavorites = current[specialty] || [];

        const updated = {
            ...current,
            [specialty]: specialtyFavorites.filter(id => id !== templateId)
        };
        updatePreference('emr_favorite_templates', updated);
    }, [preferences?.emr_favorite_templates, updatePreference]);

    // Автозагрузка при mount
    useEffect(() => {
        if (autoLoad && !loadedRef.current) {
            loadPreferences();
        }
    }, [autoLoad, loadPreferences]);

    // Cleanup
    useEffect(() => {
        return () => {
            if (saveTimeoutRef.current) {
                clearTimeout(saveTimeoutRef.current);
            }
        };
    }, []);

    return {
        // State
        preferences,
        loading,
        error,
        isDirty,

        // Actions
        loadPreferences,
        savePreferences,
        updatePreference,

        // EMR-specific
        getEMRPreferences,
        setSmartFieldMode,
        addRecentICD10,
        addRecentTemplate,
        addFavoriteTemplate,
        removeFavoriteTemplate,

        // Helpers
        clearCache: () => localStorage.removeItem(LOCAL_STORAGE_KEY)
    };
};

export default useUserPreferences;
