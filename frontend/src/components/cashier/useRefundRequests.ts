/**
 * PR-UI-14-6: refund-request data lifecycle + process actions (verbatim
 * move from RefundRequestsTable.tsx — behavior-preserving decomposition).
 *
 * Owns: requests/loading/error/processingId/filter state, the
 * status_filter query load, and the approve/reject/complete process
 * command routed through the existing backend endpoint
 * POST /force-majeure/refund-requests/{id}/process.
 */

import { useState, useEffect, useCallback } from 'react';

import notify from '../../services/notify';
import logger from '../../utils/logger';
import tokenManager from '../../utils/tokenManager';
import type { RefundRequest, RefundTranslationFn } from './refundRequestsContracts';

const getAuthToken = () => {
  return tokenManager.getAccessToken() || '';
};

export const useRefundRequests = (t: RefundTranslationFn, onRefresh?: () => void) => {
  const [requests, setRequests] = useState<RefundRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [processingId, setProcessingId] = useState<string | number | null>(null);
  const [filter, setFilter] = useState('all'); // 'all' | 'pending' | 'approved' | 'rejected' | 'completed'

  // Load refund requests
  const loadRequests = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const token = getAuthToken();
      const params = new URLSearchParams();
      if (filter !== 'all') {
        params.append('status_filter', filter);
      }

      const response = await fetch(`/force-majeure/refund-requests?${params}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json() as RefundRequest[] | { requests?: RefundRequest[] };
        setRequests(Array.isArray(data) ? data : data.requests || []);
      } else {
        throw new Error('Failed to load refund requests');
      }
    } catch (err) {
      logger.error('[RefundRequestsTable] Error loading requests:', err);
      setError((err instanceof Error ? err.message : String(err)));
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    loadRequests();
  }, [loadRequests]);

  const processRefundRequest = async (
    requestId: string | number,
    action: string,
    extraPayload: Record<string, unknown> = {}
  ) => {
    setProcessingId(requestId);
    try {
      const token = getAuthToken();
      const response = await fetch(`/force-majeure/refund-requests/${requestId}/process`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ action, ...extraPayload })
      });

      if (response.ok) {
        logger.log('[RefundRequestsTable] Processed request:', { requestId, action });
        await loadRequests();
        if (onRefresh) onRefresh();
      } else {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to process refund request');
      }
    } catch (err) {
      logger.error('[RefundRequestsTable] Process error:', err);
      notify.error(t('payment.refund_error') + ((err instanceof Error ? err.message : String(err)) || t('payment.unknown_error')));
    } finally {
      setProcessingId(null);
    }
  };

  // Approve request
  const handleApprove = async (requestId: string | number | undefined) => {
    if (requestId === undefined) return;
    await processRefundRequest(requestId, 'approve');
  };

  // Reject request
  const handleReject = async (requestId: string | number | undefined, reason: string = t('misc.rrt_otkloneno_kassirom')) => {
    if (requestId === undefined) return;
    await processRefundRequest(requestId, 'reject', { rejection_reason: reason });
  };

  // Complete request (mark as refunded)
  const handleComplete = async (requestId: string | number | undefined) => {
    if (requestId === undefined) return;
    await processRefundRequest(requestId, 'complete');
  };

  return {
    requests,
    loading,
    error,
    processingId,
    filter,
    setFilter,
    loadRequests,
    handleApprove,
    handleReject,
    handleComplete,
  };
};
