/**
 * Hook for fetching roles from the API.
 * Replaces hardcoded role lists with dynamic data from database.
 */
import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';
import { getErrorMessage } from '../utils/errorHandler';
import logger from '../utils/logger';
import type { RoleRecord } from '../types/domain/auth';
import type { AsyncState } from '../types/async-state';
import { idleState, loadingState, successState, errorState, getData, getError } from '../types/async-state';

// Re-export for backwards compatibility with any caller that still imports
// `Role` from this module. New code should import RoleRecord from
// '@/types/domain/auth' directly.
export type { RoleRecord } from '../types/domain/auth';
/**
 * @deprecated Use `RoleRecord` from '@/types/domain/auth' instead.
 * Kept as an alias so existing imports keep compiling.
 */
export type Role = RoleRecord;

export interface RoleOption {
  value: string;
  label: string;
}

export interface UseRolesOptions {
  includeAll?: boolean;
}

export interface UseRolesReturn {
  roleOptions: RoleOption[];
  roles: RoleRecord[];
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
  fetchAllRoles: () => Promise<void>;
}

export function useRoles({ includeAll = false }: UseRolesOptions = {}): UseRolesReturn {
  const [roleOptions, setRoleOptions] = useState<RoleOption[]>([]);
  const [roles, setRoles] = useState<RoleRecord[]>([]);
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
