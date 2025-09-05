import { useState, useEffect, useCallback } from 'react';

const useUsers = () => {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterRole, setFilterRole] = useState('');
  const [filterStatus, setFilterStatus] = useState('');

  // Моковые данные для демонстрации
  const mockUsers = [
    {
      id: 1,
      name: 'Ахмедов Алишер',
      email: 'ahmedov@clinic.uz',
      role: 'admin',
      status: 'active',
      lastLogin: '2 минуты назад',
      createdAt: '2024-01-15'
    },
    {
      id: 2,
      name: 'Иванов Иван',
      email: 'ivanov@clinic.uz',
      role: 'doctor',
      status: 'active',
      lastLogin: '1 час назад',
      createdAt: '2024-01-20'
    },
    {
      id: 3,
      name: 'Петрова Мария',
      email: 'petrova@clinic.uz',
      role: 'registrar',
      status: 'active',
      lastLogin: '30 минут назад',
      createdAt: '2024-01-25'
    },
    {
      id: 4,
      name: 'Сидоров Сергей',
      email: 'sidorov@clinic.uz',
      role: 'cashier',
      status: 'inactive',
      lastLogin: '2 дня назад',
      createdAt: '2024-01-10'
    },
    {
      id: 5,
      name: 'Козлова Анна',
      email: 'kozlova@clinic.uz',
      role: 'lab',
      status: 'active',
      lastLogin: '15 минут назад',
      createdAt: '2024-02-01'
    }
  ];

  // Загрузка пользователей
  const loadUsers = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      // Имитация API запроса
      await new Promise(resolve => setTimeout(resolve, 500));
      setUsers(mockUsers);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Создание пользователя
  const createUser = useCallback(async (userData) => {
    setLoading(true);
    setError(null);
    
    try {
      // Имитация API запроса
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      const newUser = {
        id: Date.now(),
        ...userData,
        lastLogin: 'Никогда',
        createdAt: new Date().toISOString().split('T')[0]
      };
      
      setUsers(prev => [newUser, ...prev]);
      return newUser;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Обновление пользователя
  const updateUser = useCallback(async (id, userData) => {
    setLoading(true);
    setError(null);
    
    try {
      // Имитация API запроса
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      setUsers(prev => prev.map(user => 
        user.id === id 
          ? { ...user, ...userData }
          : user
      ));
      
      return { id, ...userData };
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Удаление пользователя
  const deleteUser = useCallback(async (id) => {
    setLoading(true);
    setError(null);
    
    try {
      // Имитация API запроса
      await new Promise(resolve => setTimeout(resolve, 500));
      
      setUsers(prev => prev.filter(user => user.id !== id));
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Фильтрация пользователей
  const filteredUsers = users.filter(user => {
    const matchesSearch = !searchTerm || 
      user.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      user.email.toLowerCase().includes(searchTerm.toLowerCase());
    
    const matchesRole = !filterRole || user.role === filterRole;
    const matchesStatus = !filterStatus || user.status === filterStatus;
    
    return matchesSearch && matchesRole && matchesStatus;
  });

  // Загрузка при монтировании
  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  return {
    users: filteredUsers,
    allUsers: users,
    loading,
    error,
    searchTerm,
    setSearchTerm,
    filterRole,
    setFilterRole,
    filterStatus,
    setFilterStatus,
    createUser,
    updateUser,
    deleteUser,
    refresh: loadUsers
  };
};

export default useUsers;
