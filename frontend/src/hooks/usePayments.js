/**
 * usePayments Hook
 * Centralized hook for managing payment operations
 */

import { useState, useCallback } from 'react';

const API_BASE = import.meta?.env?.VITE_API_BASE_URL || 'http://localhost:8000';

export const usePayments = () => {
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    /**
     * Get authentication headers
     */
    const getHeaders = () => {
        const token = localStorage.getItem('auth_token');
        return {
            'Content-Type': 'application/json',
            'Authorization': token ? `Bearer ${token}` : ''
        };
    };

    /**
     * Get pending payments (appointments/visits awaiting payment)
     */
    const getPendingPayments = useCallback(async ({ date_from, date_to, limit = 100 } = {}) => {
        setLoading(true);
        setError(null);

        try {
            const params = new URLSearchParams();
            if (date_from) params.append('date_from', date_from);
            if (date_to) params.append('date_to', date_to);
            if (limit) params.append('limit', limit.toString());
            params.append('payment_status', 'pending');

            const response = await fetch(`${API_BASE}/api/v1/cashier/pending-payments?${params}`, {
                headers: getHeaders()
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            setLoading(false);

            return {
                success: true,
                data: data || []
            };
        } catch (err) {
            console.error('Error fetching pending payments:', err);
            setError(err.message);
            setLoading(false);

            return {
                success: false,
                error: err.message,
                data: []
            };
        }
    }, []);

    /**
     * Get payment history
     */
    const getPayments = useCallback(async ({ date_from, date_to, limit = 50 } = {}) => {
        setLoading(true);
        setError(null);

        try {
            const params = new URLSearchParams();
            if (date_from) params.append('date_from', date_from);
            if (date_to) params.append('date_to', date_to);
            if (limit) params.append('limit', limit.toString());

            const response = await fetch(`${API_BASE}/api/v1/cashier/payments?${params}`, {
                headers: getHeaders()
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            setLoading(false);

            return {
                success: true,
                data: data || []
            };
        } catch (err) {
            console.error('Error fetching payments:', err);
            setError(err.message);
            setLoading(false);

            return {
                success: false,
                error: err.message,
                data: []
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
            const response = await fetch(`${API_BASE}/api/v1/cashier/payments`, {
                method: 'POST',
                headers: getHeaders(),
                body: JSON.stringify(paymentData)
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            setLoading(false);

            return {
                success: true,
                data
            };
        } catch (err) {
            console.error('Error creating payment:', err);
            setError(err.message);
            setLoading(false);

            return {
                success: false,
                error: err.message
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
            const response = await fetch(`${API_BASE}/api/v1/cashier/visits/${visitId}/mark-paid`, {
                method: 'POST',
                headers: getHeaders()
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            setLoading(false);

            return {
                success: true,
                data
            };
        } catch (err) {
            console.error('Error marking visit as paid:', err);
            setError(err.message);
            setLoading(false);

            return {
                success: false,
                error: err.message
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
            const response = await fetch(`${API_BASE}/api/v1/cashier/payments/${paymentId}`, {
                headers: getHeaders()
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            setLoading(false);

            return {
                success: true,
                data
            };
        } catch (err) {
            console.error('Error fetching payment:', err);
            setError(err.message);
            setLoading(false);

            return {
                success: false,
                error: err.message
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
            const response = await fetch(`${API_BASE}/api/v1/cashier/payments/${paymentId}/cancel`, {
                method: 'POST',
                headers: getHeaders(),
                body: JSON.stringify({ reason })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            setLoading(false);

            return {
                success: true,
                data
            };
        } catch (err) {
            console.error('Error canceling payment:', err);
            setError(err.message);
            setLoading(false);

            return {
                success: false,
                error: err.message
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
        cancelPayment
    };
};

export default usePayments;
