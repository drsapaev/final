import { useState, useEffect, useCallback } from 'react';

const useFinance = () => {
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterType, setFilterType] = useState('');
  const [filterCategory, setFilterCategory] = useState('');
  const [filterDateRange, setFilterDateRange] = useState('');
  const [filterStatus, setFilterStatus] = useState('');

  // Моковые данные для демонстрации
  const mockTransactions = [
    {
      id: 1,
      type: 'income',
      category: 'Консультация врача',
      amount: 150000,
      description: 'Консультация кардиолога - Иванов И.И.',
      patientId: 1,
      doctorId: 1,
      patientName: 'Иванова Анна Сергеевна',
      doctorName: 'Иванов Иван Иванович',
      paymentMethod: 'card',
      status: 'completed',
      transactionDate: '2024-02-01',
      notes: 'Плановый осмотр',
      reference: '****1234',
      createdAt: '2024-02-01T10:00:00Z'
    },
    {
      id: 2,
      type: 'income',
      category: 'Диагностика',
      amount: 250000,
      description: 'ЭКГ и УЗИ сердца',
      patientId: 2,
      doctorId: 1,
      patientName: 'Петров Дмитрий Александрович',
      doctorName: 'Иванов Иван Иванович',
      paymentMethod: 'cash',
      status: 'completed',
      transactionDate: '2024-02-01',
      notes: 'Полный комплекс диагностики',
      reference: null,
      createdAt: '2024-02-01T14:30:00Z'
    },
    {
      id: 3,
      type: 'expense',
      category: 'Зарплата персонала',
      amount: 5000000,
      description: 'Зарплата врачей за январь',
      patientId: null,
      doctorId: null,
      patientName: null,
      doctorName: null,
      paymentMethod: 'transfer',
      status: 'completed',
      transactionDate: '2024-02-01',
      notes: 'Ежемесячная выплата зарплаты',
      reference: 'TRF-2024-001',
      createdAt: '2024-02-01T09:00:00Z'
    },
    {
      id: 4,
      type: 'income',
      category: 'Лечение',
      amount: 300000,
      description: 'Лечение дерматологических проблем',
      patientId: 3,
      doctorId: 2,
      patientName: 'Сидорова Мария Ивановна',
      doctorName: 'Петрова Мария Сергеевна',
      paymentMethod: 'mobile',
      status: 'completed',
      transactionDate: '2024-02-02',
      notes: 'Курс лечения 2 недели',
      reference: 'MOB-789456',
      createdAt: '2024-02-02T11:15:00Z'
    },
    {
      id: 5,
      type: 'expense',
      category: 'Медикаменты',
      amount: 750000,
      description: 'Закупка лекарств для клиники',
      patientId: null,
      doctorId: null,
      patientName: null,
      doctorName: null,
      paymentMethod: 'card',
      status: 'completed',
      transactionDate: '2024-02-02',
      notes: 'Закупка у поставщика "ФармаМед"',
      reference: '****5678',
      createdAt: '2024-02-02T16:45:00Z'
    },
    {
      id: 6,
      type: 'income',
      category: 'Анализы',
      amount: 120000,
      description: 'Лабораторные анализы крови',
      patientId: 4,
      doctorId: 4,
      patientName: 'Козлов Алексей Владимирович',
      doctorName: 'Козлова Анна Владимировна',
      paymentMethod: 'cash',
      status: 'pending',
      transactionDate: '2024-02-03',
      notes: 'Общий анализ крови + биохимия',
      reference: null,
      createdAt: '2024-02-03T08:30:00Z'
    },
    {
      id: 7,
      type: 'expense',
      category: 'Коммунальные услуги',
      amount: 450000,
      description: 'Оплата электроэнергии и воды',
      patientId: null,
      doctorId: null,
      patientName: null,
      doctorName: null,
      paymentMethod: 'transfer',
      status: 'completed',
      transactionDate: '2024-02-03',
      notes: 'За январь 2024',
      reference: 'UTIL-2024-001',
      createdAt: '2024-02-03T10:00:00Z'
    },
    {
      id: 8,
      type: 'income',
      category: 'Процедуры',
      amount: 180000,
      description: 'Физиотерапевтические процедуры',
      patientId: 5,
      doctorId: 4,
      patientName: 'Новикова Елена Дмитриевна',
      doctorName: 'Козлова Анна Владимировна',
      paymentMethod: 'card',
      status: 'completed',
      transactionDate: '2024-02-03',
      notes: 'Курс из 10 процедур',
      reference: '****9012',
      createdAt: '2024-02-03T15:20:00Z'
    }
  ];

  // Загрузка транзакций
  const loadTransactions = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      // Имитация API запроса
      await new Promise(resolve => setTimeout(resolve, 500));
      setTransactions(mockTransactions);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Создание транзакции
  const createTransaction = useCallback(async (transactionData) => {
    setLoading(true);
    setError(null);
    
    try {
      // Имитация API запроса
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      const newTransaction = {
        id: Date.now(),
        ...transactionData,
        createdAt: new Date().toISOString()
      };
      
      setTransactions(prev => [newTransaction, ...prev]);
      return newTransaction;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Обновление транзакции
  const updateTransaction = useCallback(async (id, transactionData) => {
    setLoading(true);
    setError(null);
    
    try {
      // Имитация API запроса
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      setTransactions(prev => prev.map(transaction => 
        transaction.id === id 
          ? { ...transaction, ...transactionData }
          : transaction
      ));
      
      return { id, ...transactionData };
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Удаление транзакции
  const deleteTransaction = useCallback(async (id) => {
    setLoading(true);
    setError(null);
    
    try {
      // Имитация API запроса
      await new Promise(resolve => setTimeout(resolve, 500));
      
      setTransactions(prev => prev.filter(transaction => transaction.id !== id));
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Фильтрация транзакций
  const filteredTransactions = transactions.filter(transaction => {
    const matchesSearch = !searchTerm || 
      transaction.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
      transaction.category.toLowerCase().includes(searchTerm.toLowerCase()) ||
      transaction.patientName?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      transaction.doctorName?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      transaction.reference?.toLowerCase().includes(searchTerm.toLowerCase());
    
    const matchesType = !filterType || transaction.type === filterType;
    const matchesCategory = !filterCategory || transaction.category === filterCategory;
    const matchesStatus = !filterStatus || transaction.status === filterStatus;
    
    const matchesDateRange = !filterDateRange || (() => {
      const transactionDate = new Date(transaction.transactionDate);
      const today = new Date();
      
      switch (filterDateRange) {
        case 'today':
          return transactionDate.toDateString() === today.toDateString();
        case 'week':
          const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
          return transactionDate >= weekAgo;
        case 'month':
          const monthAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);
          return transactionDate >= monthAgo;
        case 'year':
          const yearAgo = new Date(today.getTime() - 365 * 24 * 60 * 60 * 1000);
          return transactionDate >= yearAgo;
        default:
          return true;
      }
    })();
    
    return matchesSearch && matchesType && matchesCategory && matchesStatus && matchesDateRange;
  });

  // Получение финансовой статистики
  const getFinancialStats = () => {
    const stats = {
      totalIncome: 0,
      totalExpense: 0,
      netProfit: 0,
      transactionCount: transactions.length,
      incomeCount: 0,
      expenseCount: 0
    };
    
    transactions.forEach(transaction => {
      if (transaction.type === 'income') {
        stats.totalIncome += transaction.amount;
        stats.incomeCount++;
      } else {
        stats.totalExpense += transaction.amount;
        stats.expenseCount++;
      }
    });
    
    stats.netProfit = stats.totalIncome - stats.totalExpense;
    
    return stats;
  };

  // Получение статистики по категориям
  const getCategoryStats = () => {
    const categoryStats = {};
    
    transactions.forEach(transaction => {
      if (!categoryStats[transaction.category]) {
        categoryStats[transaction.category] = {
          income: 0,
          expense: 0,
          count: 0
        };
      }
      
      if (transaction.type === 'income') {
        categoryStats[transaction.category].income += transaction.amount;
      } else {
        categoryStats[transaction.category].expense += transaction.amount;
      }
      
      categoryStats[transaction.category].count++;
    });
    
    return categoryStats;
  };

  // Получение статистики по дням
  const getDailyStats = (days = 7) => {
    const dailyStats = {};
    const today = new Date();
    
    for (let i = 0; i < days; i++) {
      const date = new Date(today.getTime() - i * 24 * 60 * 60 * 1000);
      const dateStr = date.toISOString().split('T')[0];
      dailyStats[dateStr] = { income: 0, expense: 0, count: 0 };
    }
    
    transactions.forEach(transaction => {
      const transactionDate = transaction.transactionDate;
      if (dailyStats[transactionDate]) {
        if (transaction.type === 'income') {
          dailyStats[transactionDate].income += transaction.amount;
        } else {
          dailyStats[transactionDate].expense += transaction.amount;
        }
        dailyStats[transactionDate].count++;
      }
    });
    
    return dailyStats;
  };

  // Загрузка при монтировании
  useEffect(() => {
    loadTransactions();
  }, [loadTransactions]);

  return {
    transactions: filteredTransactions,
    allTransactions: transactions,
    loading,
    error,
    searchTerm,
    setSearchTerm,
    filterType,
    setFilterType,
    filterCategory,
    setFilterCategory,
    filterDateRange,
    setFilterDateRange,
    filterStatus,
    setFilterStatus,
    createTransaction,
    updateTransaction,
    deleteTransaction,
    refresh: loadTransactions,
    getFinancialStats,
    getCategoryStats,
    getDailyStats
  };
};

export default useFinance;
