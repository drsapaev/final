import { useState, useEffect, useCallback } from 'react';
import { api } from '../utils/api';
const API_BASE = import.meta.env?.VITE_API_BASE || 'http://localhost:8000/api/v1';
import { toast } from 'react-toastify';

const useUsers = () => {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterRole, setFilterRole] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [pagination, setPagination] = useState({
    page: 1,
    per_page: 20,
    total: 0,
    total_pages: 0
  });

  // Загрузка пользователей
  const loadUsers = useCallback(async (page = 1) => {
    setLoading(true);
    setError(null);
    
    try {
      const params = {
        page,
        per_page: pagination.per_page,
      };
      if (searchTerm) params.search = searchTerm;
      if (filterRole) params.role = filterRole;
      if (filterStatus) params.is_active = filterStatus;

      // Используем относительный путь, так как api уже настроен на API_BASE
      const response = await api.get('/users/users', { params });
      
      if (response.data) {
        setUsers(response.data.users || []);
        setPagination({
          page: response.data.page || 1,
          per_page: response.data.per_page || 20,
          total: response.data.total || 0,
          total_pages: response.data.total_pages || 0
        });
      }
    } catch (err) {
      console.error('Ошибка загрузки пользователей:', err);
      setError(err);
      toast.error('Ошибка загрузки пользователей');
    } finally {
      setLoading(false);
    }
  }, [searchTerm, filterRole, filterStatus, pagination.per_page]);

  // Создание пользователя
  const createUser = useCallback(async (userData) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await api.post('/users/users', userData);
      
      if (response.data) {
        toast.success('Пользователь успешно создан');
        // Перезагружаем список пользователей
        await loadUsers(pagination.page);
        return response.data;
      }
    } catch (err) {
      console.error('Ошибка создания пользователя:', err);
      setError(err);
      const errorMessage = err.response?.data?.detail || 'Ошибка создания пользователя';
      toast.error(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [loadUsers, pagination.page]);

  // Обновление пользователя
  const updateUser = useCallback(async (id, userData) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await api.put(`/users/users/${id}`, userData);
      
      if (response.data) {
        toast.success('Пользователь успешно обновлен');
        // Перезагружаем список пользователей
        await loadUsers(pagination.page);
        return response.data;
      }
    } catch (err) {
      console.error('Ошибка обновления пользователя:', err);
      setError(err);
      const errorMessage = err.response?.data?.detail || 'Ошибка обновления пользователя';
      toast.error(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [loadUsers, pagination.page]);

  // Удаление пользователя
  const deleteUser = useCallback(async (id) => {
    setLoading(true);
    setError(null);
    
    try {
      await api.delete(`/users/users/${id}`);
      
      toast.success('Пользователь успешно удален');
      // Перезагружаем список пользователей
      await loadUsers(pagination.page);
    } catch (err) {
      console.error('Ошибка удаления пользователя:', err);
      setError(err);
      const errorMessage = err.response?.data?.detail || 'Ошибка удаления пользователя';
      toast.error(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [loadUsers, pagination.page]);

  // Поиск с дебаунсом
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      loadUsers(1); // Сбрасываем на первую страницу при поиске
    }, 500);

    return () => clearTimeout(timeoutId);
  }, [searchTerm, filterRole, filterStatus]);

  // Загрузка при монтировании
  useEffect(() => {
    loadUsers();
  }, []);

  // Функция для смены страницы
  const changePage = useCallback((newPage) => {
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
