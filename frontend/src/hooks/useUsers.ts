import { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';
import { toast } from 'react-toastify';

import logger from '../utils/logger';
import { getErrorMessage } from '../utils/errorHandler';
import type { AsyncState } from '../types/async-state';
import { idleState, loadingState, successState, errorState, getData, getError } from '../types/async-state';

const useUsers = () => {
  const [usersState, setUsersState] = useState<AsyncState<unknown[]>>(idleState<unknown[]>());
  const [searchTerm, setSearchTerm] = useState('');
  const [filterRole, setFilterRole] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [pagination, setPagination] = useState({
    page: 1,
    per_page: 20,
    total: 0,
    total_pages: 0
  });

  const users = getData(usersState, []);
  const loading = usersState.status === 'loading';
  const error = getError(usersState);

  // Загрузка пользователей
  const loadUsers = useCallback(async (page = 1) => {
    setUsersState(loadingState<unknown[]>());
    
    try {
      const params: Record<string, unknown> = {
        page,
        per_page: pagination.per_page,
      };
      if (searchTerm) params.search = searchTerm;
      if (filterRole) params.role = filterRole;
      if (filterStatus) params.is_active = filterStatus;

      // Используем относительный путь, так как api уже настроен на API_BASE
      const response = await api.get('/users/users', { params });
      
      if (response.data) {
        setUsersState(successState(response.data.users || []));
        setPagination({
          page: response.data.page || 1,
          per_page: response.data.per_page || 20,
          total: response.data.total || 0,
          total_pages: response.data.total_pages || 0
        });
      }
    } catch (err) {
      logger.error('Ошибка загрузки пользователей:', err);
      const errorMessage = getErrorMessage(
        err,
        'Не удалось загрузить пользователей. Проверьте соединение и попробуйте снова.'
      );
      setUsersState(errorState<unknown[]>(String(errorMessage)));
      toast.error(errorMessage);
    }
  }, [searchTerm, filterRole, filterStatus, pagination.per_page]);

  // Создание пользователя
  const createUser = useCallback(async (userData: Record<string, unknown>) => {
    setUsersState(loadingState<unknown[]>());
    
    try {
      const response = await api.post('/users/users', userData);
      
      if (response.data) {
        toast.success('Пользователь успешно создан');
        // Перезагружаем список пользователей
        await loadUsers(pagination.page);
        return response.data;
      }
    } catch (err) {
      logger.error('Ошибка создания пользователя:', err);
      const errorMessage = getErrorMessage(
        err,
        'Не удалось создать пользователя. Проверьте соединение и попробуйте снова.'
      );
      setUsersState(errorState<unknown[]>(String(errorMessage)));
      toast.error(errorMessage);
      throw err;
    }
  }, [loadUsers, pagination.page]);

  // Обновление пользователя
  const updateUser = useCallback(async (id: string | number, userData: Record<string, unknown>) => {
    setUsersState(loadingState<unknown[]>());
    
    try {
      const response = await api.put(`/users/users/${id}`, userData);
      
      if (response.data) {
        toast.success('Пользователь успешно обновлен');
        // Перезагружаем список пользователей
        await loadUsers(pagination.page);
        return response.data;
      }
    } catch (err) {
      logger.error('Ошибка обновления пользователя:', err);
      const errorMessage = getErrorMessage(
        err,
        'Не удалось обновить пользователя. Проверьте соединение и попробуйте снова.'
      );
      setUsersState(errorState<unknown[]>(String(errorMessage)));
      toast.error(errorMessage);
      throw err;
    }
  }, [loadUsers, pagination.page]);

  // Удаление пользователя
  const deleteUser = useCallback(async (id: string | number) => {
    setUsersState(loadingState<unknown[]>());
    
    try {
      await api.delete(`/users/users/${id}`);
      
      toast.success('Пользователь успешно удален');
      // Перезагружаем список пользователей
      await loadUsers(pagination.page);
    } catch (err) {
      logger.error('Ошибка удаления пользователя:', err);
      const errorMessage = getErrorMessage(
        err,
        'Не удалось удалить пользователя. Проверьте соединение и попробуйте снова.'
      );
      setUsersState(errorState<unknown[]>(String(errorMessage)));
      toast.error(errorMessage);
      throw err;
    }
  }, [loadUsers, pagination.page]);

  // Поиск с дебаунсом
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      loadUsers(1); // Сбрасываем на первую страницу при поиске
    }, 500);

    return () => clearTimeout(timeoutId);
  }, [searchTerm, filterRole, filterStatus, loadUsers]);

  // Загрузка при монтировании
  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  // Функция для смены страницы
  const changePage = useCallback((newPage: number) => {
    loadUsers(newPage);
  }, [loadUsers]);

  return {
    users,
    loading,
    error,
    searchTerm,
    setSearchTerm,
    filterRole,
    setFilterRole,
    filterStatus,
    setFilterStatus,
    pagination,
    changePage,
    createUser,
    updateUser,
    deleteUser,
    refresh: loadUsers
  };
};

export default useUsers;
