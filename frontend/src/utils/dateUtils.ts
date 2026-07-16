// src/utils/dateUtils.ts
// Phase 1 — migrated from .js. Pure date formatters; types added.
//
// PR-40 / High-20: Locale is now dynamic via getLocale() — reads the active
// language from localStorage (set by useTranslation hook). Previously every
// function hardcoded 'ru-RU', ignoring the user's language selection.

export const REGISTRAR_TIME_ZONE = 'Asia/Tashkent';

/**
 * PR-40 / High-20: Returns the active locale based on the user's language
 * selection. Reads from the unified 'language' key (set by useTranslation).
 * Falls back to 'ru-RU' for Russian (default clinic language).
 */
export const getLocale = (): string => {
  try {
    const lang = localStorage.getItem('language')
      || localStorage.getItem('app_language')
      || 'ru';
    switch (lang) {
      case 'uz': return 'uz-UZ';
      case 'en': return 'en-US';
      case 'ru':
      default: return 'ru-RU';
    }
  } catch {
    return 'ru-RU';
  }
};

/**
 * Parses registrar timestamps using the clinic timezone contract.
 * Legacy naive timestamps are treated as Asia/Tashkent local time.
 */
export const parseRegistrarTimestamp = (value: unknown): Date | null => {
  if (!value) return null;

  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value;
  }

  const raw = String(value).trim();
  if (!raw) return null;

  let parsed: Date;
  if (/Z$|[+-]\d{2}:\d{2}$/.test(raw)) {
    parsed = new Date(raw);
  } else if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
    parsed = new Date(`${raw}T00:00:00+05:00`);
  } else {
    const normalized = raw.includes('T') ? raw : raw.replace(' ', 'T');
    parsed = new Date(`${normalized}+05:00`);
  }

  return Number.isNaN(parsed.getTime()) ? null : parsed;
};

export const formatRegistrarDate = (value: unknown, locale: string = getLocale()): string => {
  const parsed = parseRegistrarTimestamp(value);
  if (!parsed) return '';
  return parsed.toLocaleDateString(locale, {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    timeZone: REGISTRAR_TIME_ZONE,
  });
};

interface RegistrarTimeOptions {
  includeSeconds?: boolean;
}

export const formatRegistrarTime = (
  value: unknown,
  locale: string = getLocale(),
  options: RegistrarTimeOptions = {},
): string => {
  const parsed = parseRegistrarTimestamp(value);
  if (!parsed) return '';
  return parsed.toLocaleTimeString(locale, {
    hour: '2-digit',
    minute: '2-digit',
    ...(options.includeSeconds ? { second: '2-digit' } : {}),
    timeZone: REGISTRAR_TIME_ZONE,
  });
};

export const formatRegistrarDateTime = (
  value: unknown,
  locale: string = getLocale(),
  options: RegistrarTimeOptions = {},
): string => {
  const date = formatRegistrarDate(value, locale);
  const time = formatRegistrarTime(value, locale, options);
  return [date, time].filter(Boolean).join(' ');
};

const REGISTRAR_CHANGED_TIMESTAMP_THRESHOLD_MS = 60 * 1000;
const REGISTRAR_PRIMARY_TIME_KINDS = new Set(['queue_time', 'created_at']);

const timestampsDiffer = (
  a: unknown,
  b: unknown,
  thresholdMs: number = REGISTRAR_CHANGED_TIMESTAMP_THRESHOLD_MS,
): boolean => {
  const first = parseRegistrarTimestamp(a);
  const second = parseRegistrarTimestamp(b);
  if (!first || !second) return false;
  return Math.abs(first.getTime() - second.getTime()) > thresholdMs;
};

interface RegistrarTimestampRecord {
  display_time_kind?: string;
  queue_time?: string | null;
  created_at?: string | null;
  last_changed_at?: string | null;
  updated_at?: string | null;
  timezone?: string;
  [key: string]: unknown;
}

interface RegistrarTimestampDisplay {
  timeZone: string;
  primaryKind: string;
  primaryLabel: string;
  primaryValue: string | null;
  primaryDate: string;
  primaryTime: string;
  changedValue: string | null;
  showChanged: boolean;
  changedLabel: string;
  changedDate: string;
  changedTime: string;
}

export const getRegistrarTimestampDisplay = (
  record: RegistrarTimestampRecord = {},
  locale: string = getLocale(),
): RegistrarTimestampDisplay => {
  const requestedPrimaryKind = REGISTRAR_PRIMARY_TIME_KINDS.has(record.display_time_kind ?? '')
    ? record.display_time_kind
    : null;
  const primaryKind = requestedPrimaryKind || (record.queue_time ? 'queue_time' : 'created_at');
  const primaryValue = primaryKind === 'queue_time'
    ? record.queue_time || record.created_at || null
    : record.created_at || record.queue_time || null;
  const changedValue = record.last_changed_at || record.updated_at || null;
  const showChanged = Boolean(changedValue && primaryValue && timestampsDiffer(primaryValue, changedValue));

  return {
    timeZone: record.timezone || REGISTRAR_TIME_ZONE,
    primaryKind,
    primaryLabel: primaryKind === 'queue_time' ? 'Очередь' : 'Создано',
    primaryValue,
    primaryDate: formatRegistrarDate(primaryValue, locale),
    primaryTime: formatRegistrarTime(primaryValue, locale, { includeSeconds: true }),
    changedValue,
    showChanged,
    changedLabel: 'Изменено',
    changedDate: showChanged ? formatRegistrarDate(changedValue, locale) : '',
    changedTime: showChanged ? formatRegistrarTime(changedValue, locale, { includeSeconds: true }) : '',
  };
};

/**
 * Converts a Date object to YYYY-MM-DD format string.
 */
export const getLocalDateString = (date: Date = new Date()): string => {
  const d = new Date(date);
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: REGISTRAR_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(d);
  const values: Record<string, string> = Object.fromEntries(
    parts.map((part) => [part.type, part.value]),
  );
  return `${values.year}-${values.month}-${values.day}`;
};

/** Gets yesterday's date in YYYY-MM-DD format. */
export const getYesterdayDateString = (): string => {
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  return getLocalDateString(yesterday);
};

/** Gets tomorrow's date in YYYY-MM-DD format. */
export const getTomorrowDateString = (): string => {
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  return getLocalDateString(tomorrow);
};

/** Gets a date N days from now in YYYY-MM-DD format. */
export const getDateOffset = (days: number): string => {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return getLocalDateString(date);
};

/** Gets the start of the week (Monday) in YYYY-MM-DD format. */
export const getWeekStart = (date: Date = new Date()): string => {
  const d = new Date(date);
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1); // Adjust when day is Sunday
  d.setDate(diff);
  return getLocalDateString(d);
};

/** Gets the end of the week (Sunday) in YYYY-MM-DD format. */
export const getWeekEnd = (date: Date = new Date()): string => {
  const d = new Date(date);
  const day = d.getDay();
  const diff = d.getDate() + (day === 0 ? 0 : 7 - day);
  d.setDate(diff);
  return getLocalDateString(d);
};

/** Formats a date string or Date object to a localized string. */
export const formatDate = (date: string | Date, locale: string = getLocale()): string => {
  const d = typeof date === 'string' ? new Date(date) : date;
  return d.toLocaleDateString(locale, {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
};

/** Formats a date string or Date object to a localized date-time string. */
export const formatDateTime = (date: string | Date, locale: string = getLocale()): string => {
  const d = typeof date === 'string' ? new Date(date) : date;
  return d.toLocaleString(locale, {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

/** Checks if a date string is today. */
export const isToday = (dateString: string): boolean => {
  return dateString === getLocalDateString();
};

/** Checks if a date string is in the past. */
export const isPast = (dateString: string): boolean => {
  return dateString < getLocalDateString();
};

/** Checks if a date string is in the future. */
export const isFuture = (dateString: string): boolean => {
  return dateString > getLocalDateString();
};

/** Formats a date for display in a user-friendly format. */
export const formatDateDisplay = (
  date: string | Date | null | undefined,
  locale: string = getLocale(),
): string => {
  if (!date) return '';

  try {
    const d = typeof date === 'string' ? new Date(date) : date;
    return d.toLocaleDateString(locale, {
      day: '2-digit',
      month: 'long',
      year: 'numeric',
    });
  } catch {
    return '';
  }
};
