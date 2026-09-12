/**
 * RQ-26.a — CSV round-trip helpers for the queue-profiles admin surface (F-22).
 *
 * Pure module (no React/DOM) so the contract is testable in isolation.
 * No external CSV library — plan stop condition for this slice.
 *
 * Defects addressed (audit F-22):
 * - the previous export dropped `department_key` and `show_on_qr_page`;
 * - the previous import used a naive `split(',')` parser, so quoted commas,
 *   quotes and newlines in titles shifted columns silently;
 * - nothing was validated before the first API call, so a broken file could
 *   update half of the profiles before surfacing an error.
 *
 * Backend contract (reference-only):
 * `backend/app/api/v1/endpoints/registrar_integration/_queue_profiles.py` —
 * POST create requires `key` + `title`; PUT update uses
 * `exclude_unset=True` (partial update), therefore optional fields that are
 * omitted from the payload keep their stored values. Empty CSV cells map to
 * "not provided" (omit) instead of empty strings, so a round-trip of a
 * profile with `department_key: null` does not rewrite NULL as ''.
 */

export const QUEUE_PROFILES_CSV_HEADERS = [
  'key',
  'title',
  'title_ru',
  'queue_tags',
  'department_key',
  'icon',
  'color',
  'display_order',
  'is_active',
  'show_on_qr_page',
] as const;

export type QueueProfileCsvHeader = (typeof QUEUE_PROFILES_CSV_HEADERS)[number];

export type QueueProfilesCsvIssueCode =
  | 'empty_file'
  | 'missing_column'
  | 'unknown_column'
  | 'column_mismatch'
  | 'missing_key'
  | 'missing_title'
  | 'duplicate_key'
  | 'invalid_display_order'
  | 'invalid_boolean'
  | 'unknown_department';

export interface QueueProfilesCsvIssue {
  code: QueueProfilesCsvIssueCode;
  /** 1-based data row number (header excluded); 0 = file-level issue. */
  row: number;
  /** Profile key when known, '' otherwise. */
  key: string;
  column?: string;
}

/** Blocking issues abort the whole import before any API call. */
export const QUEUE_PROFILES_CSV_BLOCKING_ISSUES: ReadonlySet<QueueProfilesCsvIssueCode> = new Set([
  'empty_file',
  'missing_column',
  'column_mismatch',
  'missing_key',
  'missing_title',
  'duplicate_key',
  'invalid_display_order',
  'invalid_boolean',
]);

export interface QueueProfilesCsvRow {
  key: string;
  title: string;
  titleRu?: string;
  /** Parsed tag list; undefined when the file has no queue_tags column. */
  queueTags?: string[];
  departmentKey?: string;
  icon?: string;
  color?: string;
  displayOrder?: number;
  isActive?: boolean;
  showOnQrPage?: boolean;
}

export interface QueueProfileCsvSource {
  key?: string;
  title?: string;
  title_ru?: string;
  queue_tags?: string[];
  department_key?: string | null;
  icon?: string | null;
  color?: string | null;
  display_order?: number | string;
  /** API returns display_order under the `order` alias for compatibility. */
  order?: number | string;
  is_active?: boolean;
  show_on_qr_page?: boolean;
}

export interface QueueProfilesCsvParseOptions {
  /** When non-empty, department keys outside this set produce warnings. */
  knownDepartmentKeys?: ReadonlySet<string>;
}

export interface QueueProfilesCsvParseResult {
  rows: QueueProfilesCsvRow[];
  issues: QueueProfilesCsvIssue[];
}

const BOOLEAN_TRUE = new Set(['true', '1', 'yes']);
const BOOLEAN_FALSE = new Set(['false', '0', 'no']);
const INTEGER_PATTERN = /^-?\d+$/;

/**
 * RFC-4180-style tokenizer: quoted fields, doubled quotes inside quotes,
 * commas and CR/LF/CRLF newlines inside quoted fields. Blank (unquoted)
 * records are skipped. Unterminated quotes flush the pending field (lenient).
 */
export function parseCsvRecords(text: string): string[][] {
  const records: string[][] = [];
  let row: string[] = [];
  let field = '';
  let fieldQuoted = false;
  let inQuotes = false;
  let sawAnyChar = false;

  const pushField = () => {
    row.push(field);
    field = '';
    fieldQuoted = false;
  };
  const pushRecord = () => {
    pushField();
    // Skip blank unquoted records (empty lines).
    if (row.length === 1 && row[0] === '' && !fieldQuoted) {
      row = [];
      return;
    }
    records.push(row);
    row = [];
  };

  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    sawAnyChar = true;
    if (inQuotes) {
      if (ch === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i++;
        } else {
          inQuotes = false;
          fieldQuoted = true;
        }
      } else {
        field += ch;
      }
      continue;
    }
    if (ch === '"' && field === '' && !fieldQuoted) {
      inQuotes = true;
      continue;
    }
    if (ch === ',') {
      pushField();
      continue;
    }
    if (ch === '\r' || ch === '\n') {
      if (ch === '\r' && text[i + 1] === '\n') i++;
      pushRecord();
      continue;
    }
    field += ch;
  }
  if (field !== '' || row.length > 0 || inQuotes) {
    pushRecord();
  }
  void sawAnyChar;
  return records;
}

const escapeCsvField = (value: string): string => `"${value.replace(/"/g, '""')}"`;

/**
 * Serialize profiles to CSV covering the full current contract (all
 * QUEUE_PROFILES_CSV_HEADERS). Every field is quoted, so commas, quotes and
 * newlines inside values cannot shift columns.
 */
export function buildQueueProfilesCsv(profiles: readonly QueueProfileCsvSource[]): string {
  const headerLine = QUEUE_PROFILES_CSV_HEADERS.join(',');
  const lines = profiles.map((profile) => {
    const displayOrderRaw = profile.display_order ?? profile.order ?? 0;
    const displayOrder = Number.parseInt(String(displayOrderRaw), 10);
    const cells: unknown[] = [
      profile.key || '',
      profile.title || '',
      profile.title_ru || '',
      (profile.queue_tags || []).join(';'),
      profile.department_key || '',
      profile.icon || '',
      profile.color || '',
      Number.isNaN(displayOrder) ? 0 : displayOrder,
      profile.is_active !== false,
      profile.show_on_qr_page !== false,
    ];
    return cells.map((cell) => escapeCsvField(String(cell))).join(',');
  });
  return [headerLine, ...lines].join('\n');
}

/**
 * Parse and validate a queue-profiles CSV file. Blocking issues are collected
 * instead of throwing so the caller can show the full picture BEFORE writing
 * anything. `unknown_department` and `unknown_column` are warnings: the row
 * is still returned.
 */
export function parseQueueProfilesCsv(
  text: string,
  options: QueueProfilesCsvParseOptions = {}
): QueueProfilesCsvParseResult {
  const issues: QueueProfilesCsvIssue[] = [];
  const records = parseCsvRecords(text);

  if (records.length === 0) {
    issues.push({ code: 'empty_file', row: 0, key: '' });
    return { rows: [], issues };
  }

  const headers = records[0].map((header) => header.trim());
  for (const header of headers) {
    if (!(QUEUE_PROFILES_CSV_HEADERS as readonly string[]).includes(header)) {
      issues.push({ code: 'unknown_column', row: 0, key: '', column: header });
    }
  }
  for (const required of ['key', 'title'] as const) {
    if (!headers.includes(required)) {
      issues.push({ code: 'missing_column', row: 0, key: '', column: required });
    }
  }
  if (issues.some((issue) => issue.code === 'missing_column')) {
    return { rows: [], issues };
  }

  const columnIndex = new Map<string, number>();
  headers.forEach((header, index) => {
    if (!columnIndex.has(header)) columnIndex.set(header, index);
  });
  const cellOf = (record: string[], name: QueueProfileCsvHeader): string | undefined => {
    const index = columnIndex.get(name);
    return index === undefined ? undefined : record[index];
  };

  const knownDepartments = options.knownDepartmentKeys;
  const seenKeys = new Set<string>();
  const rows: QueueProfilesCsvRow[] = [];

  for (let rowIndex = 1; rowIndex < records.length; rowIndex++) {
    const record = records[rowIndex];
    const rowNumber = rowIndex; // data rows start at 1 (header excluded)

    const rawKey = cellOf(record, 'key') ?? '';
    const key = rawKey.trim();

    if (record.length > headers.length) {
      issues.push({ code: 'column_mismatch', row: rowNumber, key });
      continue;
    }
    if (!key) {
      issues.push({ code: 'missing_key', row: rowNumber, key: '' });
      continue;
    }

    const title = cellOf(record, 'title') ?? '';
    if (!title.trim()) {
      issues.push({ code: 'missing_title', row: rowNumber, key });
      continue;
    }
    if (seenKeys.has(key)) {
      issues.push({ code: 'duplicate_key', row: rowNumber, key });
      continue;
    }

    const optionalString = (name: QueueProfileCsvHeader): string | undefined => {
      const value = (cellOf(record, name) ?? '').trim();
      return value === '' ? undefined : value;
    };

    const displayOrderCell = (cellOf(record, 'display_order') ?? '').trim();
    let displayOrder: number | undefined;
    if (displayOrderCell !== '') {
      if (!INTEGER_PATTERN.test(displayOrderCell)) {
        issues.push({ code: 'invalid_display_order', row: rowNumber, key, column: 'display_order' });
        continue;
      }
      displayOrder = Number.parseInt(displayOrderCell, 10);
    }

    const parseBooleanCell = (
      name: QueueProfileCsvHeader
    ): { value?: boolean; invalid?: boolean } => {
      const value = (cellOf(record, name) ?? '').trim().toLowerCase();
      if (value === '') return { value: undefined };
      if (BOOLEAN_TRUE.has(value)) return { value: true };
      if (BOOLEAN_FALSE.has(value)) return { value: false };
      return { invalid: true };
    };

    const isActiveResult = parseBooleanCell('is_active');
    if (isActiveResult.invalid) {
      issues.push({ code: 'invalid_boolean', row: rowNumber, key, column: 'is_active' });
      continue;
    }
    const showOnQrResult = parseBooleanCell('show_on_qr_page');
    if (showOnQrResult.invalid) {
      issues.push({ code: 'invalid_boolean', row: rowNumber, key, column: 'show_on_qr_page' });
      continue;
    }

    const departmentKey = optionalString('department_key');
    if (
      departmentKey &&
      knownDepartments &&
      knownDepartments.size > 0 &&
      !knownDepartments.has(departmentKey)
    ) {
      issues.push({ code: 'unknown_department', row: rowNumber, key, column: 'department_key' });
    }

    seenKeys.add(key);
    rows.push({
      key,
      title,
      titleRu: optionalString('title_ru'),
      queueTags:
        columnIndex.has('queue_tags')
          ? (cellOf(record, 'queue_tags') ?? '')
              .split(';')
              .map((tag) => tag.trim())
              .filter(Boolean)
          : undefined,
      departmentKey,
      icon: optionalString('icon'),
      color: optionalString('color'),
      displayOrder,
      isActive: isActiveResult.value,
      showOnQrPage: showOnQrResult.value,
    });
  }

  return { rows, issues };
}

/**
 * Build the POST/PUT payload for one parsed row. Only fields provided by the
 * file are included: with the backend `exclude_unset=True` update contract,
 * omitted optional fields keep their stored values (old-format files never
 * wipe department_key/show_on_qr_page).
 */
export function queueProfileToCsvPayload(row: QueueProfilesCsvRow): Record<string, unknown> {
  const payload: Record<string, unknown> = { key: row.key, title: row.title };
  if (row.titleRu !== undefined) payload.title_ru = row.titleRu;
  if (row.queueTags !== undefined) payload.queue_tags = row.queueTags;
  if (row.departmentKey !== undefined) payload.department_key = row.departmentKey;
  if (row.icon !== undefined) payload.icon = row.icon;
  if (row.color !== undefined) payload.color = row.color;
  if (row.displayOrder !== undefined) payload.display_order = row.displayOrder;
  if (row.isActive !== undefined) payload.is_active = row.isActive;
  if (row.showOnQrPage !== undefined) payload.show_on_qr_page = row.showOnQrPage;
  return payload;
}
