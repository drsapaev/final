import { useState, useEffect, useCallback, useMemo, useRef } from 'react';

import { api } from '../api/client';
import logger from '../utils/logger';
import type { Transaction } from '../types/domain/clinic';
import type { AsyncState } from '../types/async-state';
import { successState, loadingState, errorState, getData, getError } from '../types/async-state';
import { safeJsonParse } from '../utils/safeJsonParse';
// Wire-up: payment invariant validator (Track 2 + Wire-up).
import { checkPaymentAmount } from '../types/domain/invariants/billing';

const FINANCE_CACHE_KEY = 'admin_finance_transactions_cache';
// audit/phase-8, BS-36: TTL for deletedIds. Previously deletedIds grew
// monotonically and never expired — after a DB restore or ID recycling,
// deleted IDs would filter out valid new transactions forever. 7-day TTL
// is long enough to cover the "delete then refresh" use case but short
// enough to self-heal after ID recycling.
const DELETED_IDS_TTL_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

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

// audit/phase-8, BS-36: deletedIds with TTL. Each entry stores { id, deletedAt }.
// Entries older than DELETED_IDS_TTL_MS are pruned on read + write.
// This prevents the unbounded growth + ID-recycling false-filter bug.
interface DeletedIdEntry {
  id: number;
  deletedAt: number;
}

const normalizeDeletedIdEntries = (raw: unknown[]): DeletedIdEntry[] => {
  const now = Date.now();
  const seen = new Set<number>();
  const entries: DeletedIdEntry[] = [];
  for (const item of raw) {
    let id: number;
    let deletedAt: number;
    if (item && typeof item === 'object' && 'id' in item) {
      id = Number((item as DeletedIdEntry).id);
      deletedAt = Number((item as DeletedIdEntry).deletedAt) || now;
    } else {
      // Legacy format: bare numeric id (treat as deleted "now")
      id = Number(item);
      deletedAt = now;
    }
    if (!Number.isFinite(id) || seen.has(id)) continue;
    // Prune expired entries during normalization
    if (now - deletedAt > DELETED_IDS_TTL_MS) continue;
    seen.add(id);
    entries.push({ id, deletedAt });
  }
  return entries;
};

const entriesToIds = (entries: DeletedIdEntry[]): number[] => entries.map(e => e.id);

const readFinanceCache = () => {
  try {
    const raw = localStorage.getItem(FINANCE_CACHE_KEY);
    if (!raw) {
      return { transactions: [], deletedIds: [] };
    }

    const parsed = safeJsonParse(raw);
    const cachedTransactions = Array.isArray(parsed)
      ? parsed
      : Array.isArray(parsed?.transactions)
        ? parsed.transactions
        : [];
    // audit/phase-8, BS-36: read deletedIds with TTL pruning.
    // Supports legacy format (bare number[]) and new format ({id, deletedAt}[]).
    const rawDeletedIds = Array.isArray(parsed?.deletedIds) ? parsed.deletedIds : [];
    const entries = normalizeDeletedIdEntries(rawDeletedIds as unknown[]);

    return {
      transactions: sortTransactions(cachedTransactions.map(normalizeTransaction)),
      deletedIds: entriesToIds(entries)
    };
  } catch (error) {
    logger.warn('[FIX:FINANCE] Не удалось прочитать локальный кэш финансов:', error);
    return { transactions: [], deletedIds: [] };
  }
};

const writeFinanceCache = (transactions: unknown[], deletedIds: unknown[] = []) => {
  try {
    // audit/phase-8, BS-36: write deletedIds with timestamps for TTL.
    // Accept both legacy number[] and new DeletedIdEntry[] formats.
    const now = Date.now();
    const entries: DeletedIdEntry[] = normalizeDeletedIdEntries(deletedIds as unknown[]);
    // For legacy bare-number entries, normalizeDeletedIdEntries already
    // assigned deletedAt = now. For new entries, preserve their deletedAt.
    // Re-stamp any entry that lost its timestamp.
    const stampedEntries = entries.map(e => ({
      id: e.id,
      deletedAt: e.deletedAt || now,
    }));

    localStorage.setItem(
      FINANCE_CACHE_KEY,
      JSON.stringify({
        updatedAt: new Date().toISOString(),
        transactions: sortTransactions(transactions.map((tx) => normalizeTransaction(tx as Record<string, unknown>))),
        deletedIds: stampedEntries
      })
    );
  } catch (error) {
    logger.warn('[FIX:FINANCE] Не удалось сохранить локальный кэш финансов:', error);
  }
};

const mergeTransactions = (
  serverTransactions: unknown[] = [],
  cacheState: { transactions: unknown[]; deletedIds: unknown[] } = { transactions: [], deletedIds: [] }
) => {
  // audit/phase-8, BS-36: deletedIds are pruned by TTL on read, so this
  // Set only contains IDs still within their TTL window.
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

const toApiPayload = (transactionData: Record<string, unknown>) => ({
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
  // AsyncState unifies the (transactions, loading, error) triple. Initialize
  // from cache so consumers see cached data immediately on mount — the cache
  // is the source of truth for offline-first behavior.
  const [transactionsState, setTransactionsState] = useState<AsyncState<unknown[]>>(successState<unknown[]>(initialCache.transactions));
  const [searchTerm, setSearchTerm] = useState('');
  const [filterType, setFilterType] = useState('');
  const [filterCategory, setFilterCategory] = useState('');
  const [filterDateRange, setFilterDateRange] = useState('');
  const [filterStatus, setFilterStatus] = useState('');

  // Backward-compatible accessors — preserve the (transactions, loading, error)
  // shape consumers depend on.
  const transactions = getData(transactionsState, initialCache.transactions);
  const loading = transactionsState.status === 'loading';
  const error = getError(transactionsState);

  // Ref mirror of `transactions` so callbacks that transition through 'loading'
  // (where AsyncState drops the data) can still read the previous data.
  const transactionsRef = useRef<unknown[]>(transactions);
  transactionsRef.current = transactions;
  const deletedIdsRef = useRef<Set<number>>(new Set(initialCache.deletedIds));

  const persistTransactions = useCallback((nextTransactions: unknown[], nextDeletedIds: unknown[] | Set<number> = deletedIdsRef.current) => {
    const normalizedTransactions = sortTransactions(nextTransactions.map((tx) => normalizeTransaction(tx as Record<string, unknown>)));
    const normalizedDeletedIds = normalizeDeletedIds(Array.isArray(nextDeletedIds) ? nextDeletedIds : Array.from(nextDeletedIds || []));

    transactionsRef.current = normalizedTransactions;
    deletedIdsRef.current = new Set(normalizedDeletedIds);
    setTransactionsState(successState<unknown[]>(normalizedTransactions));
    writeFinanceCache(normalizedTransactions, normalizedDeletedIds);

    return normalizedTransactions;
  }, []);

  const loadTransactions = useCallback(async () => {
    setTransactionsState(loadingState<unknown[]>());

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

      // Cache-fallback behavior (preserve initialCache contract): when we have
      // data — either live (transactionsRef) or persisted (localStorage) — keep
      // the data visible via successState. AsyncState is a discriminated union
      // and cannot represent (data + error) simultaneously, so the error is
      // logged but not surfaced via the `error` field when cached data is
      // available. Only when there is no data anywhere do we transition to
      // errorState so consumers can render an error UI.
      if (transactionsRef.current.length > 0) {
        logger.warn('[FIX:FINANCE] Используем локальный кэш финансовых транзакций после ошибки загрузки');
        setTransactionsState(successState<unknown[]>(transactionsRef.current));
        return transactionsRef.current;
      }

      const cachedState = readFinanceCache();
      if (cachedState.transactions.length > 0) {
        logger.info('[FIX:FINANCE] Восстановили финансовые транзакции из локального кэша');
        persistTransactions(cachedState.transactions, (cachedState.deletedIds as unknown[]));
        return cachedState.transactions;
      }

      setTransactionsState(errorState<unknown[]>(String(err)));
      return [];
    }
  }, [persistTransactions]);

  const createTransaction = useCallback(async (transactionData: Partial<Transaction>) => {
    // Wire-up: validate payment invariant before API call.
    const amountCheck = checkPaymentAmount({
      amount: transactionData.amount as number | undefined,
    });
    if (!amountCheck.ok) {
      setTransactionsState(errorState<unknown[]>(amountCheck.message));
      throw new Error(amountCheck.message);
    }

    setTransactionsState(loadingState<unknown[]>());

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
      setTransactionsState(errorState<unknown[]>(String(err)));
      throw err;
    }
  }, [loadTransactions, persistTransactions]);

  const updateTransaction = useCallback(async (id: string | number, transactionData: Record<string, unknown>) => {
    setTransactionsState(loadingState<unknown[]>());

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
      setTransactionsState(errorState<unknown[]>(String(err)));
      throw err;
    }
  }, [loadTransactions, persistTransactions]);

  const deleteTransaction = useCallback(async (id: string | number) => {
    setTransactionsState(loadingState<unknown[]>());

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
      setTransactionsState(errorState<unknown[]>(String(err)));
      throw err;
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
    const categoryStats: Record<string, { income: number; expense: number; count: number }> = {};

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
    const dailyStats: Record<string, { income: number; expense: number; count: number }> = {};
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
