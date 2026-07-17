/**
 * Хук для оптимизированной загрузки данных с кэшированием и дебаунсингом.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import tokenManager from '../utils/tokenManager';

interface CacheEntry {
  data: unknown;
  timestamp: number;
}

export interface UseOptimizedDataOptions {
  dependencies?: unknown[];
  cacheKey?: string;
  cacheTime?: number;
  debounceTime?: number;
  enabled?: boolean;
  onError?: (err: unknown) => void;
  onSuccess?: (data: unknown) => void;
}

export interface UseOptimizedDataReturn {
  data: unknown;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<unknown>;
  debouncedRefetch: () => void;
  clearCache: () => void;
}

export const useOptimizedData = (
  url: string,
  options: UseOptimizedDataOptions = {},
): UseOptimizedDataReturn => {
  const {
    dependencies = [],
    cacheKey = url,
    cacheTime = 5 * 60 * 1000,
    debounceTime = 300,
    enabled = true,
    onError,
    onSuccess,
  } = options;

  const [data, setData] = useState<unknown>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const cacheRef = useRef<Map<string, CacheEntry>>(new Map());
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const onErrorRef = useRef(onError);
  const onSuccessRef = useRef(onSuccess);

  useEffect(() => {
    onErrorRef.current = onError;
    onSuccessRef.current = onSuccess;
  });

  const fetchData = useCallback(
    async (force: boolean = false): Promise<unknown> => {
      if (!enabled) return;

      const cached = cacheRef.current.get(cacheKey);
      if (!force && cached && Date.now() - cached.timestamp < cacheTime) {
        setData(cached.data);
        setError(null);
        onSuccessRef.current?.(cached.data);
        return cached.data;
      }

      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      abortControllerRef.current = new AbortController();
      setLoading(true);
      setError(null);

      try {
        const response = await fetch(url, {
          headers: {
            Authorization: `Bearer ${tokenManager.getAccessToken()}`,
            'Content-Type': 'application/json',
          },
          signal: abortControllerRef.current.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const result: unknown = await response.json();

        cacheRef.current.set(cacheKey, {
          data: result,
          timestamp: Date.now(),
        });

        setData(result);
        onSuccessRef.current?.(result);
        return result;
      } catch (err) {
        const errorObj = err as Error;
        if (errorObj.name !== 'AbortError') {
          setError(errorObj.message);
          onErrorRef.current?.(err);
        }
      } finally {
        setLoading(false);
      }
    },
    [url, cacheKey, cacheTime, enabled],
  );

  const debouncedFetch = useCallback(
    (force: boolean = false): void => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
      debounceRef.current = setTimeout(() => {
        fetchData(force);
      }, debounceTime);
    },
    [fetchData, debounceTime],
  );

  const dependenciesKey = JSON.stringify(dependencies);

  useEffect(() => {
    fetchData();
  }, [fetchData, dependenciesKey]);

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
    clearCache: () => cacheRef.current.delete(cacheKey),
  };
};

// ============================================================================
// usePaginatedData
// ============================================================================

export interface UsePaginatedDataOptions {
  pageSize?: number;
  searchTerm?: string;
  filters?: Record<string, string>;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
}

export interface PaginationInfo {
  page: number;
  totalPages: number;
  totalItems: number;
  pageSize: number;
  hasNext: boolean;
  hasPrev: boolean;
  goToPage: (page: number) => void;
  nextPage: () => void;
  prevPage: () => void;
  firstPage: () => void;
  lastPage: () => void;
}

export interface UsePaginatedDataReturn {
  data: unknown[];
  loading: boolean;
  error: string | null;
  refetch: () => Promise<unknown>;
  pagination: PaginationInfo;
}

export const usePaginatedData = (
  url: string,
  options: UsePaginatedDataOptions = {},
): UsePaginatedDataReturn => {
  const {
    pageSize = 50,
    searchTerm = '',
    filters = {},
    sortBy = '',
    sortOrder = 'asc',
  } = options;

  const [page, setPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [totalItems, setTotalItems] = useState<number>(0);

  const buildUrl = useCallback((): string => {
    const params = new URLSearchParams({
      page: page.toString(),
      limit: pageSize.toString(),
      ...(filters as Record<string, string>),
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
    cacheTime: 2 * 60 * 1000,
    onSuccess: (result) => {
      const r = result as Record<string, unknown>;
      if (r?.total_pages) setTotalPages(r.total_pages as number);
      if (r?.total_items) setTotalItems(r.total_items as number);
    },
  });

  const goToPage = (newPage: number): void => {
    if (newPage >= 1 && newPage <= totalPages) {
      setPage(newPage);
    }
  };

  const nextPage = (): void => goToPage(page + 1);
  const prevPage = (): void => goToPage(page - 1);
  const firstPage = (): void => goToPage(1);
  const lastPage = (): void => goToPage(totalPages);

  const items = (data as Record<string, unknown> | null)?.items;
  const dataArray = Array.isArray(items) ? items : Array.isArray(data) ? data : [];

  return {
    data: dataArray,
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
      lastPage,
    },
  };
};

// ============================================================================
// useVirtualList
// ============================================================================

export interface UseVirtualListReturn {
  visibleItems: unknown[];
  totalHeight: number;
  offsetY: number;
  containerRef: (el: HTMLElement | null) => void;
  handleScroll: (e: React.UIEvent<HTMLElement>) => void;
  startIndex: number;
  endIndex: number;
}

export const useVirtualList = (
  items: unknown[],
  itemHeight: number = 50,
  containerHeight: number = 400,
): UseVirtualListReturn => {
  const [scrollTop, setScrollTop] = useState<number>(0);
  const [, setContainerRef] = useState<HTMLElement | null>(null);

  const startIndex = Math.floor(scrollTop / itemHeight);
  const endIndex = Math.min(
    startIndex + Math.ceil(containerHeight / itemHeight) + 1,
    items.length,
  );

  const visibleItems = items.slice(startIndex, endIndex).map((item, index) => ({
    ...(item as Record<string, unknown>),
    index: startIndex + index,
  }));

  const totalHeight = items.length * itemHeight;
  const offsetY = startIndex * itemHeight;

  const handleScroll = (e: React.UIEvent<HTMLElement>): void => {
    setScrollTop(e.currentTarget.scrollTop);
  };

  return {
    visibleItems,
    totalHeight,
    offsetY,
    containerRef: setContainerRef,
    handleScroll,
    startIndex,
    endIndex,
  };
};

// ============================================================================
// useLazyImage
// ============================================================================

export interface UseLazyImageReturn {
  imageSrc: string;
  isLoaded: boolean;
  isError: boolean;
  imgRef: React.RefObject<HTMLImageElement | null>;
}

export const useLazyImage = (
  src: string,
  placeholder: string = '/static/placeholder.png',
): UseLazyImageReturn => {
  const [imageSrc, setImageSrc] = useState<string>(placeholder);
  const [isLoaded, setIsLoaded] = useState<boolean>(false);
  const [isError, setIsError] = useState<boolean>(false);
  const imgRef = useRef<HTMLImageElement>(null);

  useEffect(() => {
    if (!src) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const img = new Image();
            img.onload = (): void => {
              setImageSrc(src);
              setIsLoaded(true);
              setIsError(false);
            };
            img.onerror = (): void => {
              setIsError(true);
              setIsLoaded(false);
            };
            img.src = src;
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.1 },
    );

    if (imgRef.current) {
      observer.observe(imgRef.current);
    }

    return (): void => observer.disconnect();
  }, [src]);

  return { imageSrc, isLoaded, isError, imgRef };
};
