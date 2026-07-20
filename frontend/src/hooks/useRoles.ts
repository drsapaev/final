/**
 * Hook for fetching roles from the API.
 * Replaces hardcoded role lists with dynamic data from database.
 */
import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';
import { getErrorMessage } from '../utils/errorHandler';
import logger from '../utils/logger';

export interface RoleOption {
  value: string;
  label: string;
}

export interface Role {
  id: number;
  name: string;
  display_name: string;
  description: string;
  level: number;
  is_active: boolean;
  is_system: boolean;
}

export interface UseRolesOptions {
  includeAll?: boolean;
}

export interface UseRolesReturn {
  roleOptions: RoleOption[];
  roles: Role[];
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
  fetchAllRoles: () => Promise<void>;
}

export function useRoles({ includeAll = false }: UseRolesOptions = {}): UseRolesReturn {
  const [roleOptions, setRoleOptions] = useState<RoleOption[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchRoleOptions = useCallback(async (): Promise<void> => {
    try {
      setLoading(true);
      setError(null);

      const response = await api.get('/roles/options', {
        params: { include_all: includeAll },
      });

      setRoleOptions((response.data as { options?: RoleOption[] }).options || []);
    } catch (err) {
      const errorMessage = getErrorMessage(
        err,
        'Не удалось загрузить роли. Проверьте соединение и попробуйте снова.',
      );
      setError(String(errorMessage));
      logger.error('Error fetching role options:', err);

      const fallbackRoles: RoleOption[] = [
        { value: 'Admin', label: 'Администратор' },
        { value: 'Doctor', label: 'Врач' },
        { value: 'Registrar', label: 'Регистратор' },
        { value: 'Cashier', label: 'Кассир' },
        { value: 'Lab', label: 'Лаборант' },
        { value: 'cardio', label: 'Кардиолог' },
        { value: 'derma', label: 'Дерматолог' },
        { value: 'dentist', label: 'Стоматолог' },
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

  const fetchAllRoles = useCallback(async (): Promise<void> => {
    try {
      setLoading(true);
      setError(null);

      const response = await api.get('/roles');
      setRoles((response.data as { roles?: Role[] }).roles || []);
    } catch (err) {
      const errorMessage = getErrorMessage(
        err,
        'Не удалось загрузить роли. Проверьте соединение и попробуйте снова.',
      );
      setError(String(errorMessage));
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
    fetchAllRoles,
  };
}

export default useRoles;
