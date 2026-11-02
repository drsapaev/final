/**
 * PR-UI-14-6: refund-request data lifecycle + process actions (verbatim
 * move from RefundRequestsTable.tsx — behavior-preserving decomposition).
 *
 * CSH-FE-011/012 (#3813): the list GET and the process POST now go through
 * the shared axios instance from api/client.ts instead of raw fetch calls —
 * canonical /api/v1 base URL and configured API origin (011), CSRF
 * X-CSRF-Token on the POST, single-flight 401 token refresh and 429
 * cooldown handling (012). Bearer attachment and error-detail surfacing
 * follow the shared client contract used by ForceMajeureModal and the
 * cashier payment contracts.
 *
 * Owns: requests/loading/error/processingId/filter state, the
 * status_filter query load, and the approve/reject/complete process
 * command routed through the existing backend endpoint
 * POST /force-majeure/refund-requests/{id}/process.
 */

import { useState, useEffect, useCallback } from 'react';

import notify from '../../services/notify';
import logger from '../../utils/logger';
import { api } from '../../api/client';
import { getErrorMessage } from '../../utils/type-guards';
import type { RefundRequest, RefundTranslationFn } from './refundRequestsContracts';

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
      const params: Record<string, unknown> = {};
      if (filter !== 'all') {
        params.status_filter = filter;
      }

      const response = await api.get('/force-majeure/refund-requests', { params });
      const data = response.data as RefundRequest[] | { requests?: RefundRequest[] };
      setRequests(Array.isArray(data) ? data : data.requests || []);
    } catch (err) {
      logger.error('[RefundRequestsTable] Error loading requests:', err);
      setError(getErrorMessage(err));
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
      await api.post(`/force-majeure/refund-requests/${requestId}/process`, {
        action,
        ...extraPayload,
      });

      logger.log('[RefundRequestsTable] Processed request:', { requestId, action });
      await loadRequests();
      if (onRefresh) onRefresh();
    } catch (err) {
      logger.error('[RefundRequestsTable] Process error:', err);
      notify.error(t('payment.refund_error') + (getErrorMessage(err) || t('payment.unknown_error')));
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
