// @ts-nocheck — Phase 2: file converted .js → .ts but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';

import { api } from '../api/client';
import logger from '../utils/logger';

const FINANCE_CACHE_KEY = 'admin_finance_transactions_cache';

const normalizeTransaction = (transaction: Record<string, unknown> = {}) => ({
  id: transaction.id,
  type: transaction.type || 'income',
  category: transaction.category || '',
  amount: Number(transaction.amount ?? 0),
  description: transaction.description || '',
  patientId: transaction.patient_id ?? transaction.patientId ?? null,
  doctorId: transaction.doctor_id ?? transaction.doctorId ?? null,
  patientName: transaction.patient_name ?? transaction.patientName ?? null,
  doctorName: transaction.doctor_name ?? transaction.doctorName ?? null,
  paymentMethod: transaction.payment_method || transaction.paymentMethod || 'cash',
  status: transaction.status ?? null,
  transactionDate: transaction.transaction_date || transaction.transactionDate || '',
  notes: transaction.notes || '',
  reference: transaction.reference || '',
  createdAt: transaction.created_at || transaction.createdAt || null,
  updatedAt: transaction.updated_at || transaction.updatedAt || null
});

const sortTransactions = (transactions = []) => {
  return [...transactions].sort((left, right) => {
    const leftTime = new Date(left.transactionDate || 0).getTime() || 0;
    const rightTime = new Date(right.transactionDate || 0).getTime() || 0;

    if (rightTime !== leftTime) {
      return rightTime - leftTime;
    }

    return Number(right.id || 0) - Number(left.id || 0);
  });
};

const normalizeDeletedIds = (deletedIds = []) => {
  return [...new Set(deletedIds.map((id) => Number(id)).filter((id) => Number.isFinite(id)))];
};

const readFinanceCache = () => {
  try {
    const raw = localStorage.getItem(FINANCE_CACHE_KEY);
    if (!raw) {
      return { transactions: [], deletedIds: [] };
    }

    const parsed = JSON.parse(raw);
    const cachedTransactions = Array.isArray(parsed)
      ? parsed
      : Array.isArray(parsed?.transactions)
        ? parsed.transactions
        : [];
    const deletedIds = Array.isArray(parsed?.deletedIds) ? parsed.deletedIds : [];

    return {
      transactions: sortTransactions(cachedTransactions.map(normalizeTransaction)),
      deletedIds: normalizeDeletedIds(deletedIds)
    };
  } catch (error) {
    logger.warn('[FIX:FINANCE] Не удалось прочитать локальный кэш финансов:', error);
    return { transactions: [], deletedIds: [] };
  }
};

const writeFinanceCache = (transactions, deletedIds = []) => {
  try {
    localStorage.setItem(
      FINANCE_CACHE_KEY,
      JSON.stringify({
        updatedAt: new Date().toISOString(),
        transactions: sortTransactions(transactions.map(normalizeTransaction)),
        deletedIds: normalizeDeletedIds(deletedIds)
      })
    );
  } catch (error) {
    logger.warn('[FIX:FINANCE] Не удалось сохранить локальный кэш финансов:', error);
  }
};

const mergeTransactions = (serverTransactions = [], cacheState = { transactions: [], deletedIds: [] }) => {
  const deletedIds = new Set(normalizeDeletedIds(cacheState.deletedIds));
  const merged = new Map();

  serverTransactions.forEach((transaction) => {
    const normalized = normalizeTransaction(transaction);
    if (normalized.id == null || deletedIds.has(Number(normalized.id))) {
      return;
    }
    merged.set(Number(normalized.id), normalized);
  });

  (cacheState.transactions || []).forEach((transaction) => {
    const normalized = normalizeTransaction(transaction);
    if (normalized.id == null || deletedIds.has(Number(normalized.id))) {
      return;
    }
    merged.set(Number(normalized.id), normalized);
  });

  return sortTransactions(Array.from(merged.values()));
};

const toApiPayload = (transactionData) => ({
  type: transactionData.type,
  category: transactionData.category,
  amount: Number(transactionData.amount),
  description: transactionData.description,
  patient_id: transactionData.patientId ? Number(transactionData.patientId) : null,
  doctor_id: transactionData.doctorId ? Number(transactionData.doctorId) : null,
  payment_method: transactionData.paymentMethod,
  status: transactionData.status,
  transaction_date: transactionData.transactionDate,
  notes: transactionData.notes ? transactionData.notes : null,
  reference: transactionData.reference ? transactionData.reference : null
});

const useFinance = () => {
  const initialCache = readFinanceCache();
  const [transactions, setTransactions] = useState(initialCache.transactions);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterType, setFilterType] = useState('');
  const [filterCategory, setFilterCategory] = useState('');
  const [filterDateRange, setFilterDateRange] = useState('');
  const [filterStatus, setFilterStatus] = useState('');

  const transactionsRef = useRef(initialCache.transactions);
  const deletedIdsRef = useRef(new Set(initialCache.deletedIds));

  useEffect(() => {
    transactionsRef.current = transactions;
  }, [transactions]);

  const persistTransactions = useCallback((nextTransactions, nextDeletedIds = deletedIdsRef.current) => {
    const normalizedTransactions = sortTransactions(nextTransactions.map(normalizeTransaction));
    const normalizedDeletedIds = normalizeDeletedIds(Array.isArray(nextDeletedIds) ? nextDeletedIds : Array.from(nextDeletedIds || []));

    transactionsRef.current = normalizedTransactions;
    deletedIdsRef.current = new Set(normalizedDeletedIds);
    setTransactions(normalizedTransactions);
    writeFinanceCache(normalizedTransactions, normalizedDeletedIds);

    return normalizedTransactions;
  }, []);

  const loadTransactions = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await api.get('/admin/finance/transactions', {
        params: {
          skip: 0,
          limit: 1000
        }
      });

      const rawTransactions = Array.isArray(response.data) ? response.data : [];
      const mergedTransactions = mergeTransactions(rawTransactions, {
        transactions: transactionsRef.current,
        deletedIds: Array.from(deletedIdsRef.current)
      });

      persistTransactions(mergedTransactions, Array.from(deletedIdsRef.current));
      return mergedTransactions;
    } catch (err) {
      logger.error('Ошибка загрузки финансовых транзакций:', err);
      setError(err);

      if (transactionsRef.current.length > 0) {
        logger.warn('[FIX:FINANCE] Используем локальный кэш финансовых транзакций после ошибки загрузки');
        return transactionsRef.current;
      }

      const cachedState = readFinanceCache();
      if (cachedState.transactions.length > 0) {
        logger.info('[FIX:FINANCE] Восстановили финансовые транзакции из локального кэша');
        persistTransactions(cachedState.transactions, cachedState.deletedIds);
        return cachedState.transactions;
      }

      return [];
    } finally {
      setLoading(false);
    }
  }, [persistTransactions]);

  const createTransaction = useCallback(async (transactionData) => {
    setLoading(true);
    setError(null);

    try {
      const response = await api.post('/admin/finance/transactions', toApiPayload(transactionData));
      const createdTransaction = normalizeTransaction(response.data);
      const nextDeletedIds = Array.from(deletedIdsRef.current).filter(
        (deletedId) => Number(deletedId) !== Number(createdTransaction.id)
      );
      const nextTransactions = mergeTransactions(
        [...transactionsRef.current, createdTransaction],
        {
          transactions: [],
          deletedIds: nextDeletedIds
        }
      );

      persistTransactions(nextTransactions, nextDeletedIds);
      await loadTransactions();
      return createdTransaction;
    } catch (err) {
      logger.error('Ошибка создания финансовой транзакции:', err);
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [loadTransactions, persistTransactions]);

  const updateTransaction = useCallback(async (id, transactionData) => {
    setLoading(true);
    setError(null);

    try {
      const response = await api.put(`/admin/finance/transactions/${id}`, toApiPayload(transactionData));
      const updatedTransaction = normalizeTransaction(response.data);
      const nextDeletedIds = Array.from(deletedIdsRef.current).filter(
        (deletedId) => Number(deletedId) !== Number(updatedTransaction.id)
      );
      const nextTransactions = mergeTransactions(
        [
          ...transactionsRef.current.filter((transaction) => Number(transaction.id) !== Number(id)),
          updatedTransaction
        ],
        {
          transactions: [],
          deletedIds: nextDeletedIds
        }
      );

      persistTransactions(nextTransactions, nextDeletedIds);
      await loadTransactions();
      return updatedTransaction;
    } catch (err) {
      logger.error('Ошибка обновления финансовой транзакции:', err);
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [loadTransactions, persistTransactions]);

  const deleteTransaction = useCallback(async (id) => {
    setLoading(true);
    setError(null);

    try {
      await api.delete(`/admin/finance/transactions/${id}`);
      const nextDeletedIds = normalizeDeletedIds([
        ...Array.from(deletedIdsRef.current),
        Number(id)
      ]);
      const nextTransactions = transactionsRef.current.filter((transaction) => Number(transaction.id) !== Number(id));

      persistTransactions(nextTransactions, nextDeletedIds);
      await loadTransactions();
    } catch (err) {
      logger.error('Ошибка удаления финансовой транзакции:', err);
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [loadTransactions, persistTransactions]);

  const filteredTransactions = useMemo(() => {
    return transactions.filter((transaction) => {
      const search = searchTerm.toLowerCase();
      const matchesSearch =
        !searchTerm ||
        transaction.description.toLowerCase().includes(search) ||
        transaction.category.toLowerCase().includes(search) ||
        transaction.patientName?.toLowerCase().includes(search) ||
        transaction.doctorName?.toLowerCase().includes(search) ||
        transaction.reference?.toLowerCase().includes(search);

      const matchesType = !filterType || transaction.type === filterType;
      const matchesCategory = !filterCategory || transaction.category === filterCategory;
      const matchesStatus = !filterStatus || transaction.status === filterStatus;

      const matchesDateRange = !filterDateRange || (() => {
        const transactionDate = new Date(transaction.transactionDate);
        const today = new Date();

        switch (filterDateRange) {
          case 'today':
            return transactionDate.toDateString() === today.toDateString();
          case 'week': {
            const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
            return transactionDate >= weekAgo;
          }
          case 'month': {
            const monthAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);
            return transactionDate >= monthAgo;
          }
          case 'year': {
            const yearAgo = new Date(today.getTime() - 365 * 24 * 60 * 60 * 1000);
            return transactionDate >= yearAgo;
          }
          default:
            return true;
        }
      })();

      return matchesSearch && matchesType && matchesCategory && matchesStatus && matchesDateRange;
    });
  }, [filterCategory, filterDateRange, filterStatus, filterType, searchTerm, transactions]);

  const getFinancialStats = () => {
    const stats = {
      totalIncome: 0,
      totalExpense: 0,
      netProfit: 0,
      transactionCount: transactions.length,
      incomeCount: 0,
      expenseCount: 0
    };

    transactions.forEach((transaction) => {
      if (transaction.type === 'income') {
        stats.totalIncome += transaction.amount;
        stats.incomeCount += 1;
      } else {
        stats.totalExpense += transaction.amount;
        stats.expenseCount += 1;
      }
    });

    stats.netProfit = stats.totalIncome - stats.totalExpense;

    return stats;
  };

  const getCategoryStats = () => {
    const categoryStats = {};

    transactions.forEach((transaction) => {
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

      categoryStats[transaction.category].count += 1;
    });

    return categoryStats;
  };

  const getDailyStats = (days = 7) => {
    const dailyStats = {};
    const today = new Date();

    for (let i = 0; i < days; i += 1) {
      const date = new Date(today.getTime() - i * 24 * 60 * 60 * 1000);
      const dateStr = date.toISOString().split('T')[0];
      dailyStats[dateStr] = { income: 0, expense: 0, count: 0 };
    }

    transactions.forEach((transaction) => {
      const transactionDate = transaction.transactionDate;
      if (dailyStats[transactionDate]) {
        if (transaction.type === 'income') {
          dailyStats[transactionDate].income += transaction.amount;
        } else {
          dailyStats[transactionDate].expense += transaction.amount;
        }
        dailyStats[transactionDate].count += 1;
      }
    });

    return dailyStats;
  };

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
