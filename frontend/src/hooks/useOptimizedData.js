import { useState, useEffect, useCallback, useRef } from 'react';
import tokenManager from '../utils/tokenManager';

/**
 * Хук для оптимизированной загрузки данных с кэшированием и дебаунсингом
 */
export const useOptimizedData = (url, options = {}) => {
  const {
    dependencies = [],
    cacheKey = url,
    cacheTime = 5 * 60 * 1000, // 5 минут
    debounceTime = 300,
    enabled = true,
    onError,
    onSuccess
  } = options;

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const abortControllerRef = useRef(null);
  const cacheRef = useRef(new Map());
  const debounceRef = useRef(null);

  // Функция загрузки данных
  const fetchData = useCallback(async (force = false) => {
    if (!enabled) return;

    // Проверяем кэш
    const cached = cacheRef.current.get(cacheKey);
    if (!force && cached && Date.now() - cached.timestamp < cacheTime) {
      setData(cached.data);
      setError(null);
      if (onSuccess) onSuccess(cached.data);
      return cached.data;
    }

    // Отменяем предыдущий запрос
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    abortControllerRef.current = new AbortController();
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(url, {
        headers: {
          'Authorization': `Bearer ${tokenManager.getAccessToken()}`,
          'Content-Type': 'application/json'
        },
        signal: abortControllerRef.current.signal
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();

      // Сохраняем в кэш
      cacheRef.current.set(cacheKey, {
        data: result,
        timestamp: Date.now()
      });

      setData(result);
      if (onSuccess) onSuccess(result);
      return result;

    } catch (err) {
      if (err.name !== 'AbortError') {
        setError(err.message);
        if (onError) onError(err);
      }
    } finally {
      setLoading(false);
    }
  }, [url, cacheKey, cacheTime, enabled, onSuccess, onError]);

  // Дебаунсированная загрузка
  const debouncedFetch = useCallback((force = false) => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    debounceRef.current = setTimeout(() => {
      fetchData(force);
    }, debounceTime);
  }, [fetchData, debounceTime]);

  // Эффект для автозагрузки
  useEffect(() => {
    fetchData();
  }, [fetchData, ...dependencies]);

  // Очистка при размонтировании
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, []);

  return {
    data,
    loading,
    error,
    refetch: () => fetchData(true),
    debouncedRefetch: () => debouncedFetch(true),
    clearCache: () => cacheRef.current.delete(cacheKey)
  };
};

/**
 * Хук для пагинации с виртуализацией
 */
export const usePaginatedData = (url, options = {}) => {
  const {
    pageSize = 50,
    searchTerm = '',
    filters = {},
    sortBy = '',
    sortOrder = 'asc'
  } = options;

  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);

  // Строим URL с параметрами
  const buildUrl = useCallback(() => {
    const params = new URLSearchParams({
      page: page.toString(),
      limit: pageSize.toString(),
      ...filters
    });

    if (searchTerm) params.set('search', searchTerm);
    if (sortBy) {
      params.set('sort_by', sortBy);
      params.set('sort_order', sortOrder);
    }

    return `${url}?${params.toString()}`;
  }, [url, page, pageSize, searchTerm, filters, sortBy, sortOrder]);

  const { data, loading, error, refetch } = useOptimizedData(buildUrl(), {
    dependencies: [page, searchTerm, JSON.stringify(filters), sortBy, sortOrder],
    cacheTime: 2 * 60 * 1000, // 2 минуты для пагинированных данных
    onSuccess: (result) => {
      if (result.total_pages) setTotalPages(result.total_pages);
      if (result.total_items) setTotalItems(result.total_items);
    }
  });

  const goToPage = (newPage) => {
    if (newPage >= 1 && newPage <= totalPages) {
      setPage(newPage);
    }
  };

  const nextPage = () => goToPage(page + 1);
  const prevPage = () => goToPage(page - 1);
  const firstPage = () => goToPage(1);
  const lastPage = () => goToPage(totalPages);

  return {
    data: data?.items || data || [],
    loading,
    error,
    refetch,
    pagination: {
      page,
      totalPages,
      totalItems,
      pageSize,
      hasNext: page < totalPages,
      hasPrev: page > 1,
      goToPage,
      nextPage,
      prevPage,
      firstPage,
      lastPage
    }
  };
};

/**
 * Хук для виртуализации больших списков
 */
export const useVirtualList = (items, itemHeight = 50, containerHeight = 400) => {
  const [scrollTop, setScrollTop] = useState(0);
  const [containerRef, setContainerRef] = useState(null);

  const startIndex = Math.floor(scrollTop / itemHeight);
  const endIndex = Math.min(
    startIndex + Math.ceil(containerHeight / itemHeight) + 1,
    items.length
  );

  const visibleItems = items.slice(startIndex, endIndex).map((item, index) => ({
    ...item,
    index: startIndex + index
  }));

  const totalHeight = items.length * itemHeight;
  const offsetY = startIndex * itemHeight;

  const handleScroll = (e) => {
    setScrollTop(e.target.scrollTop);
  };

  return {
    visibleItems,
    totalHeight,
    offsetY,
    containerRef: setContainerRef,
    handleScroll,
    startIndex,
    endIndex
  };
};

/**
 * Хук для lazy loading изображений
 */
export const useLazyImage = (src, placeholder = '/static/placeholder.png') => {
  const [imageSrc, setImageSrc] = useState(placeholder);
  const [isLoaded, setIsLoaded] = useState(false);
  const [isError, setIsError] = useState(false);
  const imgRef = useRef();

  useEffect(() => {
    if (!src) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const img = new Image();
            img.onload = () => {
              setImageSrc(src);
              setIsLoaded(true);
              setIsError(false);
            };
            img.onerror = () => {
              setIsError(true);
              setIsLoaded(false);
            };
            img.src = src;
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.1 }
    );

    if (imgRef.current) {
      observer.observe(imgRef.current);
    }

    return () => observer.disconnect();
  }, [src]);

  return { imageSrc, isLoaded, isError, imgRef };
};
