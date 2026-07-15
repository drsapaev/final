/**
 * usePatientSessions — P5 frontend integration for session management.
 *
 * Lists active patient sessions and provides revoke-all functionality.
 * Uses JWT auth (not initData) after M4-P0-2 exchange.
 *
 * Usage:
 *   const { sessions, loading, revokeAll } = usePatientSessions();
 */
import { useState, useCallback, useEffect } from 'react';
import { api } from '../../api/client';

export function usePatientSessions() {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const loadSessions = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await api.post('/telegram/mini-app/sessions/list', {});
      setSessions(response.data?.sessions || []);
    } catch (err) {
      setError(err?.response?.data?.detail?.reason || 'failed_to_load_sessions');
    } finally {
      setLoading(false);
    }
  }, []);

  const revokeAll = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      await api.post('/telegram/mini-app/sessions/revoke-all', {});
      setSessions([]);
      return true;
    } catch (err) {
      setError(err?.response?.data?.detail?.reason || 'failed_to_revoke');
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  return {
    sessions,
    loading,
    error,
    loadSessions,
    revokeAll,
  };
}

export default usePatientSessions;
