
import { useState, useCallback } from 'react';
import { api } from '../api/client';
import logger from '../utils/logger';

export const usePayments = () => {
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    /**
     * Get pending payments (appointments/visits awaiting payment)
     * Supports server-side pagination
     */
    const getPendingPayments = useCallback(async ({ date_from, date_to, search, page = 1, size = 20 } = {}) => {
        setLoading(true);
        setError(null);

        try {
            const params = {
                page,
                size,
                ...(date_from && { date_from }),
                ...(date_to && { date_to }),
                ...(search && { search })
            };

            const response = await api.get('/cashier/pending-payments', { params });
            const data = response.data;

            setLoading(false);

            return {
                success: true,
                data: data.items || [],
                pagination: {
                    total: data.total,
                    page: data.page,
                    size: data.size,
                    pages: data.pages
                }
            };
        } catch (err) {
            logger.error('Error fetching pending payments:', err);
            const errorMessage = err.response?.data?.detail || err.message || 'Error fetching pending payments';
            setError(errorMessage);
            setLoading(false);

            return {
                success: false,
                error: errorMessage,
                data: []
            };
        }
    }, []);

    /**
     * Get payment history
     */
    const getPayments = useCallback(async ({ date_from, date_to, page = 1, size = 20, search } = {}) => {
        setLoading(true);
        setError(null);

        try {
            const params = {
                page,
                size,
                ...(date_from && { date_from }),
                ...(date_to && { date_to }),
                ...(search && { search })
            };

            const response = await api.get('/cashier/payments', { params });
            const data = response.data;

            setLoading(false);

            return {
                success: true,
                data: data.items || [],
                pagination: {
                    total: data.total,
                    page: data.page,
                    size: data.size,
                    pages: data.pages
                }
            };
        } catch (err) {
            logger.error('Error fetching payment history:', err);
            const errorMessage = err.response?.data?.detail || err.message || 'Error fetching payment history';
            setError(errorMessage);
            setLoading(false);

            return {
                success: false,
                error: errorMessage,
                data: [],
                pagination: { total: 0, page: 1, size: 20, pages: 0 }
            };
        }
    }, []);

    /**
     * Create a new payment
     */
    const createPayment = useCallback(async (paymentData) => {
        setLoading(true);
        setError(null);

        try {
            const response = await api.post('/cashier/payments', paymentData);
            setLoading(false);

            return {
                success: true,
                data: response.data
            };
        } catch (err) {
            logger.error('Error creating payment:', err);
            const errorMessage = err.response?.data?.detail || err.message || 'Error creating payment';
            setError(errorMessage);
            setLoading(false);

            return {
                success: false,
                error: errorMessage
            };
        }
    }, []);

    /**
     * Mark a visit as paid
     */
    const markVisitAsPaid = useCallback(async (visitId) => {
        setLoading(true);
        setError(null);

        try {
            const response = await api.post(`/cashier/visits/${visitId}/mark-paid`);
            setLoading(false);

            return {
                success: true,
                data: response.data
            };
        } catch (err) {
            logger.error('Error marking visit as paid:', err);
            const errorMessage = err.response?.data?.detail || err.message || 'Error marking visit as paid';
            setError(errorMessage);
            setLoading(false);

            return {
                success: false,
                error: errorMessage
            };
        }
    }, []);

    /**
     * Get payment by ID
     */
    const getPaymentById = useCallback(async (paymentId) => {
        setLoading(true);
        setError(null);

        try {
            const response = await api.get(`/cashier/payments/${paymentId}`);
            setLoading(false);

            return {
                success: true,
                data: response.data
            };
        } catch (err) {
            logger.error('Error fetching payment:', err);
            const errorMessage = err.response?.data?.detail || err.message || 'Error fetching payment';
            setError(errorMessage);
            setLoading(false);

            return {
                success: false,
                error: errorMessage,
                data: null
            };
        }
    }, []);

    /**
     * Cancel/refund a payment
     */
    const cancelPayment = useCallback(async (paymentId, reason) => {
        setLoading(true);
        setError(null);

        try {
            const response = await api.post(`/cashier/payments/${paymentId}/cancel`, { reason });
            setLoading(false);

            return {
                success: true,
                data: response.data
            };
        } catch (err) {
            logger.error('Error canceling payment:', err);
            const errorMessage = err.response?.data?.detail || err.message || 'Error canceling payment';
            setError(errorMessage);
            setLoading(false);

            return {
                success: false,
                error: errorMessage
            };
        }
    }, []);

    /**
     * Manually confirm payment
     */
    const confirmPayment = useCallback(async (paymentId) => {
        setLoading(true);
        setError(null);

        try {
            const response = await api.post(`/cashier/payments/${paymentId}/confirm`);
            setLoading(false);

            return {
                success: true,
                data: response.data
            };
        } catch (err) {
            logger.error('Error confirming payment:', err);
            const errorMessage = err.response?.data?.detail || err.message || 'Error confirming payment';
            setError(errorMessage);
            setLoading(false);
            throw errorMessage;
        }
    }, []);

    /**
     * Get aggregated statistics
     */
    const getStats = useCallback(async ({ date_from, date_to } = {}) => {
        try {
            const params = {
                ...(date_from && { date_from }),
                ...(date_to && { date_to })
            };

            const response = await api.get('/cashier/stats', { params });

            return {
                success: true,
                data: response.data
            };
        } catch (err) {
            logger.error('Error fetching stats:', err);
            return {
                success: false,
                error: err.response?.data?.detail || err.message || 'Error fetching stats',
                data: null
            };
        }
    }, []);

    /**
     * Export payments to CSV (triggers download)
     */
    const exportPayments = useCallback(async ({ date_from, date_to } = {}) => {
        try {
            const params = {
                ...(date_from && { date_from }),
                ...(date_to && { date_to })
            };

            const response = await api.get('/cashier/payments/export', {
                params,
                responseType: 'blob'
            });

            const blob = new Blob([response.data]);
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
                error: err.response?.data?.detail || err.message || 'Error exporting payments'
            };
        }
    }, []);

    /**
     * Refund a payment (partial or full)
     */
    const refundPayment = useCallback(async (paymentId, { amount, reason }) => {
        setLoading(true);
        setError(null);

        try {
            const response = await api.post(`/cashier/payments/${paymentId}/refund`, {
                amount,
                reason
            });
            setLoading(false);

            return {
                success: true,
                data: response.data
            };
        } catch (err) {
            logger.error('Error refunding payment:', err);
            const errorMessage = err.response?.data?.detail || err.message || 'Error refunding payment';
            setError(errorMessage);
            setLoading(false);

            return {
                success: false,
                error: errorMessage
            };
        }
    }, []);

    /**
     * Get payment receipt (download)
     */
    const getReceipt = useCallback(async (paymentId) => {
        try {
            const response = await api.get(`/cashier/payments/${paymentId}/receipt`, {
                responseType: 'blob'
            });

            const blob = new Blob([response.data]);
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `receipt_${paymentId}.txt`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);

            return { success: true };
        } catch (err) {
            logger.error('Error getting receipt:', err);
            return {
                success: false,
                error: err.response?.data?.detail || err.message || 'Error getting receipt'
            };
        }
    }, []);

    /**
     * Get hourly statistics
     */
    const getHourlyStats = useCallback(async ({ target_date } = {}) => {
        try {
            const params = {
                ...(target_date && { target_date })
            };

            const response = await api.get('/cashier/stats/hourly', { params });

            return {
                success: true,
                data: response.data
            };
        } catch (err) {
            logger.error('Error fetching hourly stats:', err);
            return {
                success: false,
                error: err.response?.data?.detail || err.message || 'Error fetching hourly stats',
                data: []
            };
        }
    }, []);

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
        getHourlyStats
    };
};

export default usePayments;
