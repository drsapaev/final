/**
 * Hook for fetching roles from the API
 * Replaces hardcoded role lists with dynamic data from database
 */
import { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';
import logger from '../utils/logger';

/**
 * @typedef {Object} RoleOption
 * @property {string} value - Role name (e.g., "Admin")
 * @property {string} label - Display name (e.g., "Администратор")
 */

/**
 * @typedef {Object} Role
 * @property {number} id
 * @property {string} name
 * @property {string} display_name
 * @property {string} description
 * @property {number} level
 * @property {boolean} is_active
 * @property {boolean} is_system
 */

/**
 * Hook to fetch role options for dropdowns
 * @param {Object} options
 * @param {boolean} options.includeAll - Include "All roles" option for filters
 * @returns {Object} { roleOptions, roles, loading, error, refetch }
 */
export function useRoles({ includeAll = false } = {}) {
    const [roleOptions, setRoleOptions] = useState([]);
    const [roles, setRoles] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const fetchRoleOptions = useCallback(async () => {
        try {
            setLoading(true);
            setError(null);

            const response = await api.get('/roles/options', {
                params: { include_all: includeAll }
            });

            setRoleOptions(response.data.options || []);
        } catch (err) {
            const errorMessage = err.response?.data?.detail || err.message || 'Failed to load roles';
            setError(errorMessage);
            logger.error('Error fetching role options:', err);

            // Fallback to hardcoded roles if API fails
            const fallbackRoles = [
                { value: 'Admin', label: 'Администратор' },
                { value: 'Doctor', label: 'Врач' },
                { value: 'Nurse', label: 'Медсестра' },
                { value: 'Receptionist', label: 'Регистратор' },
                { value: 'Cashier', label: 'Кассир' },
                { value: 'Lab', label: 'Лаборант' },
                { value: 'Patient', label: 'Пациент' }
            ];

            if (includeAll) {
                setRoleOptions([{ value: '', label: 'Все роли' }, ...fallbackRoles]);
            } else {
                setRoleOptions(fallbackRoles);
            }
        } finally {
            setLoading(false);
        }
    }, [includeAll]);

    const fetchAllRoles = useCallback(async () => {
        try {
            setLoading(true);
            setError(null);

            const response = await api.get('/roles');
            setRoles(response.data.roles || []);
        } catch (err) {
            const errorMessage = err.response?.data?.detail || err.message || 'Failed to load roles';
            setError(errorMessage);
            logger.error('Error fetching roles:', err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchRoleOptions();
    }, [fetchRoleOptions]);

    return {
        roleOptions,
        roles,
        loading,
        error,
        refetch: fetchRoleOptions,
        fetchAllRoles
    };
}

export default useRoles;
