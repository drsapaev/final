import { useState, useEffect, useCallback } from 'react';

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

      const response = await fetch(endpoint, {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
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
    } catch (err) {
      console.error('Admin data fetch error:', err);
      setError(err);
      
      if (onError) {
        onError(err);
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [endpoint, onSuccess, onError]);

  const refresh = useCallback(() => {
    fetchData(true);
  }, [fetchData]);

  const retry = useCallback(() => {
    fetchData(false);
  }, [fetchData]);

  useEffect(() => {
    if (autoFetch && endpoint) {
      fetchData();
    }
  }, [autoFetch, endpoint, fetchData]);

  useEffect(() => {
    if (refreshInterval && endpoint) {
      const interval = setInterval(() => {
        fetchData(true);
      }, refreshInterval);

      return () => clearInterval(interval);
    }
  }, [refreshInterval, endpoint, fetchData]);

  return {
    data,
    loading,
    error,
    refreshing,
    refresh,
    retry,
    setData
  };
};

export default useAdminData;
