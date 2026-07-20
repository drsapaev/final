/**
 * Улучшенная система утилит для медицинских интерфейсов
 * Основана на принципах производительности и медицинских стандартах
 */

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';

import logger from '../utils/logger';
// Хук для дебаунса
export const useDebounce = <T,>(value: T, delay: number) => {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
};

// Хук для троттлинга
export const useThrottle = <T,>(value: T, delay: number) => {
  const [throttledValue, setThrottledValue] = useState(value);
  const lastExecuted = useRef(Date.now());

  useEffect(() => {
    if (Date.now() >= lastExecuted.current + delay) {
      lastExecuted.current = Date.now();
      setThrottledValue(value);
    } else {
      const timer = setTimeout(() => {
        lastExecuted.current = Date.now();
        setThrottledValue(value);
      }, delay);

      return () => clearTimeout(timer);
    }
  }, [value, delay]);

  return throttledValue;
};

// Хук для предыдущего значения
export const usePrevious = <T,>(value: T) => {
  const ref = useRef<T | undefined>(undefined);
  
  useEffect(() => {
    ref.current = value;
  });
  
  return ref.current;
};

// Хук для проверки первого рендера
export const useIsFirstRender = (): boolean => {
  const isFirstRender = useRef(true);
  
  useEffect(() => {
    isFirstRender.current = false;
  }, []);
  
  return isFirstRender.current;
};

// Хук для проверки монтирования
export const useIsMounted = () => {
  const isMounted = useRef(false);
  
  useEffect(() => {
    isMounted.current = true;
    return () => {
      isMounted.current = false;
    };
  }, []);
  
  return isMounted.current;
};

// Хук для локального хранилища
export const useLocalStorage = <T,>(key: string, initialValue: T) => {
  const [storedValue, setStoredValue] = useState(() => {
    try {
      const item = window.localStorage.getItem(key);
      return item ? JSON.parse(item) : initialValue;
    } catch (error) {
      logger.error(`Error reading localStorage key "${key}":`, error);
      return initialValue;
    }
  });

  const setValue = useCallback((value) => {
    try {
      const valueToStore = value instanceof Function ? value(storedValue) : value;
      setStoredValue(valueToStore);
      window.localStorage.setItem(key, JSON.stringify(valueToStore));
    } catch (error) {
      logger.error(`Error setting localStorage key "${key}":`, error);
    }
  }, [key, storedValue]);

  return [storedValue, setValue];
};

// Хук для сессионного хранилища
export const useSessionStorage = <T,>(key: string, initialValue: T) => {
  const [storedValue, setStoredValue] = useState(() => {
    try {
      const item = window.sessionStorage.getItem(key);
      return item ? JSON.parse(item) : initialValue;
    } catch (error) {
      logger.error(`Error reading sessionStorage key "${key}":`, error);
      return initialValue;
    }
  });

  const setValue = useCallback((value) => {
    try {
      const valueToStore = value instanceof Function ? value(storedValue) : value;
      setStoredValue(valueToStore);
      window.sessionStorage.setItem(key, JSON.stringify(valueToStore));
    } catch (error) {
      logger.error(`Error setting sessionStorage key "${key}":`, error);
    }
  }, [key, storedValue]);

  return [storedValue, setValue];
};

// Хук для копирования в буфер обмена
export const useClipboard = () => {
  const [copied, setCopied] = useState<boolean>(false);
  const [error, setError] = useState<unknown>(null);

  const copyToClipboard = useCallback(async (text) => {
    try {
      await navigator.clipboard.writeText(String(text));
      setCopied(true);
      setError(null);
      
      // Сброс состояния через 2 секунды
      setTimeout(() => {
        setCopied(false);
      }, 2000);
    } catch (err: unknown) {
      setError((err as unknown as Error).message);
      setCopied(false);
    }
  }, []);

  return { copied, error, copyToClipboard };
};

// Хук для геолокации
export const useGeolocation = () => {
  const [location, setLocation] = useState<unknown>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState<boolean>(false);

  const getCurrentPosition = useCallback(() => {
    if (!navigator.geolocation) {
      setError('Геолокация не поддерживается');
      return;
    }

    setLoading(true);
    setError(null);

    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLocation({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracy: position.coords.accuracy,
          timestamp: position.timestamp
        });
        setLoading(false);
      },
      (err) => {
        setError((err as unknown as Error).message);
        setLoading(false);
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 300000
      }
    );
  }, []);

  return { location, error, loading, getCurrentPosition };
};

// Хук для онлайн статуса
export const useOnlineStatus = (): boolean => {
  const [isOnline, setIsOnline] = useState(navigator.onLine);

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  return isOnline;
};

// Хук для видимости страницы
export const usePageVisibility = (): boolean => {
  const [isVisible, setIsVisible] = useState(!document.hidden);

  useEffect(() => {
    const handleVisibilityChange = () => {
      setIsVisible(!document.hidden);
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, []);

  return isVisible;
};

// Хук для размера окна
export const useWindowSize = () => {
  const [windowSize, setWindowSize] = useState<{ width: number; height: number }>({
    width: window.innerWidth,
    height: window.innerHeight
  });

  useEffect(() => {
    const handleResize = (): void => {
      setWindowSize({
        width: window.innerWidth,
        height: window.innerHeight
      });
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  return windowSize;
};

// Хук для прокрутки
export const useScroll = () => {
  const [scrollPosition, setScrollPosition] = useState({
    x: window.pageXOffset,
    y: window.pageYOffset
  });

  useEffect(() => {
    const handleScroll = (): void => {
      setScrollPosition({
        x: window.pageXOffset,
        y: window.pageYOffset
      });
    };

    window.addEventListener('scroll', handleScroll);

    return () => {
      window.removeEventListener('scroll', handleScroll);
    };
  }, []);

  return scrollPosition;
};

// Хук для фокуса элемента
export const useFocus = () => {
  const [isFocused, setIsFocused] = useState<boolean>(false);
  const ref = useRef<HTMLElement | null>(null);

  const focus = useCallback(() => {
    if (ref.current) {
      (ref.current as HTMLElement).focus();
    }
  }, []);

  const blur = useCallback(() => {
    if (ref.current) {
      (ref.current as HTMLElement).blur();
    }
  }, []);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    const handleFocus = () => setIsFocused(true);
    const handleBlur = () => setIsFocused(false);

    element.addEventListener('focus', handleFocus);
    element.addEventListener('blur', handleBlur);

    return () => {
      element.removeEventListener('focus', handleFocus);
      element.removeEventListener('blur', handleBlur);
    };
  }, []);

  return { ref, isFocused, focus, blur };
};

// Хук для ховера элемента
export const useHover = () => {
  const [isHovered, setIsHovered] = useState<boolean>(false);
  const ref = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    const handleMouseEnter = (): void => setIsHovered(true);
    const handleMouseLeave = (): void => setIsHovered(false);

    element.addEventListener('mouseenter', handleMouseEnter);
    element.addEventListener('mouseleave', handleMouseLeave);

    return () => {
      element.removeEventListener('mouseenter', handleMouseEnter);
      element.removeEventListener('mouseleave', handleMouseLeave);
    };
  }, []);

  return { ref, isHovered };
};

// Хук для клика вне элемента
export const useClickOutside = (callback: () => void) => {
  const ref = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        callback();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [callback]);

  return ref;
};

// Хук для клавиш
export const useKeyPress = (targetKey: string, callback: () => void) => {
  useEffect(() => {
    const handleKeyPress = (event: KeyboardEvent) => {
      if (event.key === targetKey) {
        callback();
      }
    };

    document.addEventListener('keydown', handleKeyPress);

    return () => {
      document.removeEventListener('keydown', handleKeyPress);
    };
  }, [targetKey, callback]);
};

// Хук для комбинации клавиш
export const useKeyCombo = (keys: string[], callback: () => void) => {
  const [pressedKeys, setPressedKeys] = useState(new Set());

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      setPressedKeys(prev => new Set([...prev, event.key]));
    };

    const handleKeyUp = (event: KeyboardEvent) => {
      setPressedKeys(prev => {
        const newSet = new Set(prev);
        newSet.delete(event.key);
        return newSet;
      });
    };

    document.addEventListener('keydown', handleKeyDown);
    document.addEventListener('keyup', handleKeyUp);

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.removeEventListener('keyup', handleKeyUp);
    };
  }, []);

  useEffect(() => {
    const isComboPressed = keys.every(key => pressedKeys.has(key));
    if (isComboPressed && pressedKeys.size === keys.length) {
      callback();
    }
  }, [pressedKeys, keys, callback]);
};

// Хук для интервала
export const useInterval = (callback: () => void, delay: number | null) => {
  const savedCallback = useRef<(() => void) | null>(null);

  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  useEffect(() => {
    if (delay === null) return;

    const id = setInterval(() => {
      savedCallback.current?.();
    }, delay);

    return () => clearInterval(id);
  }, [delay]);
};

// Хук для таймаута
export const useTimeout = (callback: () => void, delay: number) => {
  const savedCallback = useRef<(() => void) | null>(null);

  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  useEffect(() => {
    if (delay === null) return;

    const id = setTimeout(() => {
      savedCallback.current?.();
    }, delay);

    return () => clearTimeout(id);
  }, [delay]);
};

// Хук для асинхронной функции
export const useAsync = (asyncFunction, _dependencies: unknown[] = []) => {
  void _dependencies;
  const [state, setState] = useState({
    data: null,
    loading: false,
    error: null
  });

  const execute = useCallback(async (...args) => {
    setState(prev => ({ ...prev, loading: true, error: null }));

    try {
      const data = await asyncFunction(...args);
      setState({ data, loading: false, error: null });
      return data;
    } catch (error) {
      setState({ data: null, loading: false, error: error.message });
      throw error;
    }
  }, [asyncFunction]);

  return { ...state, execute };
};

// Хук для мемоизации
export const useMemoizedCallback = (callback, _dependencies: unknown[] = []) => {
  void _dependencies;
  const memoizedCallback = useCallback((...args) => callback(...args), [callback]);
  return memoizedCallback;
};

// Хук для мемоизации значения
export const useMemoizedValue = (value, _dependencies: unknown[] = []) => {
  void _dependencies;
  const memoizedValue = useMemo(() => value, [value]);
  return memoizedValue;
};

// Утилиты для работы с датами
export const useDateUtils = () => {
  const formatDate = useCallback((date, format = 'DD.MM.YYYY') => {
    if (!date) return '';
    
    const d = new Date(date);
    const day = String(d.getDate()).padStart(2, '0');
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const year = d.getFullYear();
    const hours = String(d.getHours()).padStart(2, '0');
    const minutes = String(d.getMinutes()).padStart(2, '0');
    
    return format
      .replace('DD', day)
      .replace('MM', month)
      .replace('YYYY', String(year))
      .replace('HH', hours)
      .replace('mm', minutes);
  }, []);

  const getRelativeTime = useCallback((date: string | Date) => {
    if (!date) return '';
    
    const now = new Date();
    const target = new Date(date);
    const diff = now.getTime() - target.getTime();
    
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);
    
    if (days > 0) return `${days} дн. назад`;
    if (hours > 0) return `${hours} ч. назад`;
    if (minutes > 0) return `${minutes} мин. назад`;
    return 'только что';
  }, []);

  const isToday = useCallback((date) => {
    if (!date) return false;
    
    const today = new Date();
    const target = new Date(date);
    
    return today.toDateString() === target.toDateString();
  }, []);

  const isYesterday = useCallback((date) => {
    if (!date) return false;
    
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    const target = new Date(date);
    
    return yesterday.toDateString() === target.toDateString();
  }, []);

  return {
    formatDate,
    getRelativeTime,
    isToday,
    isYesterday
  };
};

// Утилиты для работы с числами
export const useNumberUtils = () => {
  const formatNumber = useCallback((number, options: Record<string, unknown> = {}) => {
    if (number === null || number === undefined) return '';
    
    const {
      decimals = 2,
      thousandsSeparator = ' ' as string,
      decimalSeparator = ',' as string
    } = options;
    
    const parts = Number(number).toFixed(Number(decimals)).split('.');
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, String(thousandsSeparator));
    
    return parts.join(String(decimalSeparator));
  }, []);

  const formatCurrency = useCallback((amount, currency = 'UZS') => {
    if (amount === null || amount === undefined) return '';
    
    const formatted = formatNumber(amount, { decimals: 0 });
    return `${formatted} ${currency}`;
  }, [formatNumber]);

  const formatPercentage = useCallback((value, decimals = 1) => {
    if (value === null || value === undefined) return '';
    
    return `${formatNumber(value, { decimals })}%`;
  }, [formatNumber]);

  return {
    formatNumber,
    formatCurrency,
    formatPercentage
  };
};

export default useDebounce;
