import { useCallback, useState } from 'react';
import { api } from '../api/client';
import { getErrorMessage } from '../utils/errorHandler';
import logger from '../utils/logger';

const formatPaymentError = (err: unknown, fallbackMessage: string): string =>
  getErrorMessage(err, fallbackMessage);

interface PaginationInfo {
  total: number;
  page: number;
  size: number;
  pages: number;
}

interface PaymentListParams {
  date_from?: string;
  date_to?: string;
  search?: string;
  page?: number;
  size?: number;
  status?: string;
}

interface PaymentListResult {
  success: boolean;
  data: unknown[];
  pagination: PaginationInfo;
  error?: string;
}

interface PaymentResult {
  success: boolean;
  data?: unknown;
  error?: string;
}

interface DateRangeParams {
  date_from?: string;
  date_to?: string;
}

interface RefundParams {
  amount?: number;
  reason?: string;
}

interface HourlyStatsParams {
  target_date?: string;
}

export interface UsePaymentsReturn {
  loading: boolean;
  error: string | null;
  getPendingPayments: (params?: PaymentListParams) => Promise<PaymentListResult>;
  getPayments: (params?: PaymentListParams) => Promise<PaymentListResult>;
  createPayment: (paymentData: Record<string, unknown>) => Promise<PaymentResult>;
  markVisitAsPaid: (visitId: string | number) => Promise<PaymentResult>;
  getPaymentById: (paymentId: string | number) => Promise<PaymentResult>;
  cancelPayment: (paymentId: string | number, reason: string) => Promise<PaymentResult>;
  confirmPayment: (paymentId: string | number) => Promise<PaymentResult>;
  getStats: (params?: DateRangeParams) => Promise<PaymentResult>;
  exportPayments: (params?: DateRangeParams) => Promise<{ success: boolean; error?: string }>;
  refundPayment: (paymentId: string | number, params: RefundParams) => Promise<PaymentResult>;
  getReceipt: (paymentId: string | number) => Promise<{ success: boolean; error?: string }>;
  getHourlyStats: (params?: HourlyStatsParams) => Promise<PaymentResult>;
}

export const usePayments = (): UsePaymentsReturn => {
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const getPendingPayments = useCallback(
    async ({
      date_from,
      date_to,
      search,
      page = 1,
      size = 20,
    }: PaymentListParams = {}): Promise<PaymentListResult> => {
      setLoading(true);
      setError(null);

      try {
        const params: Record<string, unknown> = {
          page,
          size,
          ...(date_from && { date_from }),
          ...(date_to && { date_to }),
          ...(search && { search }),
        };

        const response = await api.get('/cashier/pending-payments', { params });
        const data = response.data as Record<string, unknown>;

        setLoading(false);

        return {
          success: true,
          data: (data.items as unknown[]) || [],
          pagination: {
            total: data.total as number,
            page: data.page as number,
            size: data.size as number,
            pages: data.pages as number,
          },
        };
      } catch (err) {
        logger.error('Error fetching pending payments:', err);
        const errorMessage = formatPaymentError(
          err,
          'Не удалось загрузить список ожидающих оплат. Проверьте соединение и попробуйте снова.',
        );
        setError(String(errorMessage));
        setLoading(false);

        return {
          success: false,
          error: errorMessage,
          data: [],
          pagination: { total: 0, page: 1, size: 20, pages: 0 },
        };
      }
    },
    [],
  );

  const getPayments = useCallback(
    async ({
      date_from,
      date_to,
      page = 1,
      size = 20,
      search,
      status,
    }: PaymentListParams = {}): Promise<PaymentListResult> => {
      setLoading(true);
      setError(null);

      try {
        const params: Record<string, unknown> = {
          page,
          size,
          ...(date_from && { date_from }),
          ...(date_to && { date_to }),
          ...(search && { search }),
          ...(status && { status }),
        };

        const response = await api.get('/cashier/payments', { params });
        const data = response.data as Record<string, unknown>;

        setLoading(false);

        return {
          success: true,
          data: (data.items as unknown[]) || [],
          pagination: {
            total: data.total as number,
            page: data.page as number,
            size: data.size as number,
            pages: data.pages as number,
          },
        };
      } catch (err) {
        logger.error('Error fetching payment history:', err);
        const errorMessage = formatPaymentError(
          err,
          'Не удалось загрузить историю платежей. Проверьте соединение и попробуйте снова.',
        );
        setError(String(errorMessage));
        setLoading(false);

        return {
          success: false,
          error: errorMessage,
          data: [],
          pagination: { total: 0, page: 1, size: 20, pages: 0 },
        };
      }
    },
    [],
  );

  const createPayment = useCallback(
    async (paymentData: Record<string, unknown>): Promise<PaymentResult> => {
      setLoading(true);
      setError(null);

      try {
        const response = await api.post('/cashier/payments', paymentData);
        setLoading(false);

        return { success: true, data: response.data };
      } catch (err) {
        logger.error('Error creating payment:', err);
        const errorMessage = formatPaymentError(
          err,
          'Не удалось создать платёж. Проверьте соединение и попробуйте снова.',
        );
        setError(String(errorMessage));
        setLoading(false);

        return { success: false, error: errorMessage };
      }
    },
    [],
  );

  const markVisitAsPaid = useCallback(
    async (visitId: string | number): Promise<PaymentResult> => {
      setLoading(true);
      setError(null);

      try {
        const response = await api.post(`/cashier/visits/${visitId}/mark-paid`, {});
        setLoading(false);

        return { success: true, data: response.data };
      } catch (err) {
        logger.error('Error marking visit as paid:', err);
        const errorMessage = formatPaymentError(
          err,
          'Не удалось отметить визит как оплаченный. Проверьте соединение и попробуйте снова.',
        );
        setError(String(errorMessage));
        setLoading(false);

        return { success: false, error: errorMessage };
      }
    },
    [],
  );

  const getPaymentById = useCallback(
    async (paymentId: string | number): Promise<PaymentResult> => {
      setLoading(true);
      setError(null);

      try {
        const response = await api.get(`/cashier/payments/${paymentId}`);
        setLoading(false);

        return { success: true, data: response.data };
      } catch (err) {
        logger.error('Error fetching payment:', err);
        const errorMessage = formatPaymentError(
          err,
          'Не удалось загрузить платёж. Проверьте соединение и попробуйте снова.',
        );
        setError(String(errorMessage));
        setLoading(false);

        return { success: false, error: errorMessage, data: null };
      }
    },
    [],
  );

  const cancelPayment = useCallback(
    async (paymentId: string | number, reason: string): Promise<PaymentResult> => {
      setLoading(true);
      setError(null);

      try {
        const response = await api.post(`/cashier/payments/${paymentId}/cancel`, { reason });
        setLoading(false);

        return { success: true, data: response.data };
      } catch (err) {
        logger.error('Error canceling payment:', err);
        const errorMessage = formatPaymentError(
          err,
          'Не удалось отменить платёж. Проверьте соединение и попробуйте снова.',
        );
        setError(String(errorMessage));
        setLoading(false);

        return { success: false, error: errorMessage };
      }
    },
    [],
  );

  const confirmPayment = useCallback(
    async (paymentId: string | number): Promise<PaymentResult> => {
      setLoading(true);
      setError(null);

      try {
        const response = await api.post(`/cashier/payments/${paymentId}/confirm`, {});
        setLoading(false);

        return { success: true, data: response.data };
      } catch (err) {
        logger.error('Error confirming payment:', err);
        const errorMessage = formatPaymentError(
          err,
          'Не удалось подтвердить платёж. Проверьте соединение и попробуйте снова.',
        );
        setError(String(errorMessage));
        setLoading(false);
        throw errorMessage;
      }
    },
    [],
  );

  const getStats = useCallback(
    async ({ date_from, date_to }: DateRangeParams = {}): Promise<PaymentResult> => {
      try {
        const params: Record<string, unknown> = {
          ...(date_from && { date_from }),
          ...(date_to && { date_to }),
        };

        const response = await api.get('/cashier/stats', { params });

        return { success: true, data: response.data };
      } catch (err) {
        logger.error('Error fetching stats:', err);
        return {
          success: false,
          error: formatPaymentError(
            err,
            'Не удалось загрузить статистику платежей. Проверьте соединение и попробуйте снова.',
          ),
          data: null,
        };
      }
    },
    [],
  );

  const exportPayments = useCallback(
    async ({ date_from, date_to }: DateRangeParams = {}): Promise<{ success: boolean; error?: string }> => {
      try {
        const params: Record<string, unknown> = {
          ...(date_from && { date_from }),
          ...(date_to && { date_to }),
        };

        const response = await api.get('/cashier/payments/export', {
          params,
          responseType: 'blob',
        });

        const blob = new Blob([response.data as BlobPart]);
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `payments_${date_from || 'all'}_${date_to || 'all'}.csv`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);

        return { success: true };
      } catch (err) {
        logger.error('Error exporting payments:', err);
        return {
          success: false,
          error: formatPaymentError(
            err,
            'Не удалось экспортировать платежи. Проверьте соединение и попробуйте снова.',
          ),
        };
      }
    },
    [],
  );

  const refundPayment = useCallback(
    async (paymentId: string | number, { amount, reason }: RefundParams): Promise<PaymentResult> => {
      setLoading(true);
      setError(null);

      try {
        const response = await api.post(`/cashier/payments/${paymentId}/refund`, {
          amount,
          reason,
        });
        setLoading(false);

        return { success: true, data: response.data };
      } catch (err) {
        logger.error('Error refunding payment:', err);
        const errorMessage = formatPaymentError(
          err,
          'Не удалось оформить возврат. Проверьте соединение и попробуйте снова.',
        );
        setError(String(errorMessage));
        setLoading(false);

        return { success: false, error: errorMessage };
      }
    },
    [],
  );

  const getReceipt = useCallback(
    async (paymentId: string | number): Promise<{ success: boolean; error?: string }> => {
      try {
        const response = await api.get(`/cashier/payments/${paymentId}/receipt`, {
          responseType: 'blob',
        });

        const blob =
          response.data instanceof Blob
            ? response.data
            : new Blob([response.data as BlobPart], { type: 'application/pdf' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `receipt_${paymentId}.pdf`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);

        return { success: true };
      } catch (err) {
        logger.error('Error getting receipt:', err);
        return {
          success: false,
          error: formatPaymentError(
            err,
            'Не удалось получить чек. Проверьте соединение и попробуйте снова.',
          ),
        };
      }
    },
    [],
  );

  const getHourlyStats = useCallback(
    async ({ target_date }: HourlyStatsParams = {}): Promise<PaymentResult> => {
      try {
        const params: Record<string, unknown> = {
          ...(target_date && { target_date }),
        };

        const response = await api.get('/cashier/stats/hourly', { params });

        return { success: true, data: response.data };
      } catch (err) {
        logger.error('Error fetching hourly stats:', err);
        return {
          success: false,
          error: formatPaymentError(
            err,
            'Не удалось загрузить почасовую статистику. Проверьте соединение и попробуйте снова.',
          ),
          data: [],
        };
      }
    },
    [],
  );

  return {
    loading,
    error,
    getPendingPayments,
    getPayments,
    createPayment,
    markVisitAsPaid,
    getPaymentById,
    cancelPayment,
    confirmPayment,
    getStats,
    exportPayments,
    refundPayment,
    getReceipt,
    getHourlyStats,
  };
};

export default usePayments;
