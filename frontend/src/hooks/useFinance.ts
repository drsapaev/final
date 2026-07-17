import { useState, useEffect, useCallback, useMemo, useRef } from 'react';

import { api } from '../api/client';
import logger from '../utils/logger';

const FINANCE_CACHE_KEY = 'admin_finance_transactions_cache';

const normalizeTransaction = (transaction: Record<string, unknown> = {}) => ({
  id: (transaction as Record<string, unknown>).id,
  type: (transaction as Record<string, unknown>).type || 'income',
  category: (transaction as Record<string, unknown>).category || '',
  amount: Number((transaction as Record<string, unknown>).amount ?? 0),
  description: (transaction as Record<string, unknown>).description || '',
  patientId: (transaction as Record<string, unknown>).patient_id ?? (transaction as Record<string, unknown>).patientId ?? null,
  doctorId: (transaction as Record<string, unknown>).doctor_id ?? (transaction as Record<string, unknown>).doctorId ?? null,
  patientName: (transaction as Record<string, unknown>).patient_name ?? (transaction as Record<string, unknown>).patientName ?? null,
  doctorName: (transaction as Record<string, unknown>).doctor_name ?? (transaction as Record<string, unknown>).doctorName ?? null,
  paymentMethod: (transaction as Record<string, unknown>).payment_method || (transaction as Record<string, unknown>).paymentMethod || 'cash',
  status: (transaction as Record<string, unknown>).status ?? null,
  transactionDate: (transaction as Record<string, unknown>).transaction_date || (transaction as Record<string, unknown>).transactionDate || '',
  notes: (transaction as Record<string, unknown>).notes || '',
  reference: (transaction as Record<string, unknown>).reference || '',
  createdAt: (transaction as Record<string, unknown>).created_at || (transaction as Record<string, unknown>).createdAt || null,
  updatedAt: (transaction as Record<string, unknown>).updated_at || (transaction as Record<string, unknown>).updatedAt || null
});

const sortTransactions = (transactions: unknown[] = []) => {
  return [...transactions].sort((left, right) => {
    const leftTime = new Date(((left as Record<string, unknown>).transactionDate as string | number) || 0).getTime() || 0;
    const rightTime = new Date(((right as Record<string, unknown>).transactionDate as string | number) || 0).getTime() || 0;

    if (rightTime !== leftTime) {
      return rightTime - leftTime;
    }

    return Number((right as Record<string, unknown>).id || 0) - Number((left as Record<string, unknown>).id || 0);
  });
};

const normalizeDeletedIds = (deletedIds: unknown[] = []): number[] => {
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
    const deletedIds = new Set<number>(Array.isArray(parsed?.deletedIds) ? (parsed.deletedIds as number[]) : []);

    return {
      transactions: sortTransactions(cachedTransactions.map(normalizeTransaction)),
      deletedIds: normalizeDeletedIds(Array.from(deletedIds as Set<number> | unknown[]))
    };
  } catch (error) {
    logger.warn('[FIX:FINANCE] Не удалось прочитать локальный кэш финансов:', error);
    return { transactions: [], deletedIds: [] };
  }
};

const writeFinanceCache = (transactions, deletedIds: unknown[] = []) => {
  try {
    localStorage.setItem(
      FINANCE_CACHE_KEY,
      JSON.stringify({
        updatedAt: new Date().toISOString(),
        transactions: sortTransactions(transactions.map(normalizeTransaction)),
        deletedIds: normalizeDeletedIds(Array.from(deletedIds as Set<number> | unknown[]))
      })
    );
  } catch (error) {
    logger.warn('[FIX:FINANCE] Не удалось сохранить локальный кэш финансов:', error);
  }
};

const mergeTransactions = (serverTransactions: unknown[] = [], cacheState = { transactions: [], deletedIds: [] }) => {
  const deletedIds = new Set<number>(normalizeDeletedIds(cacheState.deletedIds as unknown[]));
  const merged = new Map();

  serverTransactions.forEach((transaction) => {
    const normalized = normalizeTransaction(transaction as Record<string, unknown>);
    if ((normalized as Record<string, unknown>).id == null || (deletedIds as Set<number>).has(Number((normalized as Record<string, unknown>).id))) {
      return;
    }
    merged.set(Number((normalized as Record<string, unknown>).id), normalized);
  });

  (cacheState.transactions || []).forEach((transaction) => {
    const normalized = normalizeTransaction(transaction as Record<string, unknown>);
    if ((normalized as Record<string, unknown>).id == null || (deletedIds as Set<number>).has(Number((normalized as Record<string, unknown>).id))) {
      return;
    }
    merged.set(Number((normalized as Record<string, unknown>).id), normalized);
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

  const transactionsRef = useRef<unknown[]>(initialCache.transactions);
  const deletedIdsRef = useRef<Set<number>>(new Set(initialCache.deletedIds));

  useEffect(() => {
    transactionsRef.current = transactions;
  }, [transactions]);

  const persistTransactions = useCallback((nextTransactions: unknown[], nextDeletedIds: unknown[] | Set<number> = deletedIdsRef.current) => {
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
        deletedIds: Array.from(deletedIdsRef.current as Set<number>)
      });

      persistTransactions(mergedTransactions, Array.from(deletedIdsRef.current as Set<number>) as unknown[]);
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
        persistTransactions(cachedState.transactions, (cachedState.deletedIds as unknown[]));
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
      const nextDeletedIds = Array.from(deletedIdsRef.current as Set<number>).filter(
        (deletedId) => Number(deletedId) !== Number(createdTransaction.id)
      );
      const nextTransactions = mergeTransactions(
        [...transactionsRef.current, createdTransaction],
        {
          transactions: [],
          deletedIds: nextDeletedIds
        }
      );

      persistTransactions(nextTransactions, nextDeletedIds as unknown[]);
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
      const nextDeletedIds = Array.from(deletedIdsRef.current as Set<number>).filter(
        (deletedId) => Number(deletedId) !== Number(updatedTransaction.id)
      );
      const nextTransactions = mergeTransactions(
        [
          ...transactionsRef.current.filter((transaction) => Number((transaction as Record<string, unknown>).id) !== Number(id)),
          updatedTransaction
        ],
        {
          transactions: [],
          deletedIds: nextDeletedIds
        }
      );

      persistTransactions(nextTransactions, nextDeletedIds as unknown[]);
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
        ...Array.from(deletedIdsRef.current as Set<number>),
        Number(id)
      ]);
      const nextTransactions = transactionsRef.current.filter((transaction) => Number((transaction as Record<string, unknown>).id) !== Number(id));

      persistTransactions(nextTransactions, nextDeletedIds as unknown[]);
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
        String((transaction as Record<string, unknown>).description).toLowerCase().includes(search) ||
        String((transaction as Record<string, unknown>).category).toLowerCase().includes(search) ||
        String((transaction as Record<string, unknown>).patientName).toLowerCase().includes(search) ||
        String((transaction as Record<string, unknown>).doctorName).toLowerCase().includes(search) ||
        String((transaction as Record<string, unknown>).reference).toLowerCase().includes(search);

      const matchesType = !filterType || (transaction as Record<string, unknown>).type === filterType;
      const matchesCategory = !filterCategory || (transaction as Record<string, unknown>).category === filterCategory;
      const matchesStatus = !filterStatus || (transaction as Record<string, unknown>).status === filterStatus;

      const matchesDateRange = !filterDateRange || (() => {
        const transactionDate = new Date((transaction as Record<string, unknown>).transactionDate as string | number);
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
      if ((transaction as Record<string, unknown>).type === 'income') {
        stats.totalIncome += Number((transaction as Record<string, unknown>).amount);
        stats.incomeCount += 1;
      } else {
        stats.totalExpense += Number((transaction as Record<string, unknown>).amount);
        stats.expenseCount += 1;
      }
    });

    stats.netProfit = stats.totalIncome - stats.totalExpense;

    return stats;
  };

  const getCategoryStats = () => {
    const categoryStats = {};

    transactions.forEach((transaction) => {
      if (!categoryStats[String((transaction as Record<string, unknown>).category)]) {
        categoryStats[String((transaction as Record<string, unknown>).category)] = {
          income: 0,
          expense: 0,
          count: 0
        };
      }

      if ((transaction as Record<string, unknown>).type === 'income') {
        categoryStats[String((transaction as Record<string, unknown>).category)].income += Number((transaction as Record<string, unknown>).amount);
      } else {
        categoryStats[String((transaction as Record<string, unknown>).category)].expense += Number((transaction as Record<string, unknown>).amount);
      }

      categoryStats[String((transaction as Record<string, unknown>).category)].count += 1;
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
      const transactionDate = (transaction as Record<string, unknown>).transactionDate;
      if (dailyStats[transactionDate as string]) {
        if ((transaction as Record<string, unknown>).type === 'income') {
          dailyStats[transactionDate as string].income += Number((transaction as Record<string, unknown>).amount);
        } else {
          dailyStats[transactionDate as string].expense += Number((transaction as Record<string, unknown>).amount);
        }
        dailyStats[transactionDate as string].count += 1;
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
