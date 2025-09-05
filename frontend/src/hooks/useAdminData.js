import { useState, useEffect, useCallback, useMemo } from 'react';

const useAdminData = (endpoint, options = {}) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const {
    autoFetch = true,
    refreshInterval = null,
    onSuccess = null,
    onError = null
  } = options;

  const fetchData = useCallback(async (showRefreshing = false) => {
    try {
      if (showRefreshing) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError(null);

      const storedToken = localStorage.getItem('auth_token');
      const response = await fetch(endpoint, {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': storedToken ? `Bearer ${storedToken}` : undefined
        }
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      setData(result);
      
      if (onSuccess) {
        onSuccess(result);
      }
      return result;
    } catch (err) {
      console.error('Admin data fetch error:', err);
      setError(err);
      
      if (onError) {
        onError(err);
      }
      return null;
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [endpoint, onSuccess, onError]);

  const refresh = useCallback(() => {
    fetchData(true);
  }, []); // Убрали зависимость

  const retry = useCallback(() => {
    fetchData(false);
  }, []); // Убрали зависимость

  useEffect(() => {
    if (autoFetch && endpoint) {
      fetchData();
    }
  }, [autoFetch, endpoint]); // Убрали fetchData из зависимостей

  useEffect(() => {
    if (refreshInterval && endpoint) {
      const interval = setInterval(() => {
        fetchData(true);
      }, refreshInterval);

      return () => clearInterval(interval);
    }
  }, [refreshInterval, endpoint]); // Убрали fetchData из зависимостей


  return useMemo(() => ({
    data,
    loading,
    error,
    refreshing,
    refresh,
    retry,
    setData
  }), [data, loading, error, refreshing, refresh, retry, setData]);
};

export default useAdminData;
