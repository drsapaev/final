import type { LabImportEntry } from '../../../api/labOperations';

const requiredHeaders = [
  'message_id', 'report_instance_id', 'specimen_barcode', 'analyte_code', 'unit_code', 'value',
];

export const LAB_IMPORT_CSV_HEADER = [...requiredHeaders, 'method_code', 'observed_at', 'instrument_flags'].join(',');

export function parseLabImportReportId(value: string): number {
  const id = /^[0-9]+$/.test(value) ? Number(value) : 0;
  return id > 0 && id <= 2_147_483_647 ? id : 0;
}

function parseInstrumentFlags(value: string | undefined): string[] | null {
  if (!value) return [];
  try {
    const flags: unknown = JSON.parse(value);
    if (Array.isArray(flags) && flags.every((flag) => typeof flag === 'string')) return flags;
  } catch {
    return null;
  }
  return null;
}

function parseRows(input: string): string[][] {
  const output: string[][] = [];
  let fields: string[] = [];
  let field = '';
  let quoted = false;
  let quoteClosed = false;
  for (let index = 0; index < input.length; index += 1) {
    const char = input[index];
    if (char === '"' && quoted && input[index + 1] === '"') {
      field += '"';
      index += 1;
    } else if (char === '"' && quoted) {
      quoted = false;
      quoteClosed = true;
    } else if (char === '"' && !field && !quoteClosed) {
      quoted = true;
    } else if (!quoted && (char === ',' || char === '\n' || char === '\r')) {
      fields.push(field.trim());
      field = '';
      quoteClosed = false;
      if (char !== ',') {
        if (fields.some(Boolean)) output.push(fields);
        fields = [];
        if (char === '\r' && input[index + 1] === '\n') index += 1;
      }
    } else if (!quoteClosed && char !== '"') {
      field += char;
    } else {
      throw new Error('csv');
    }
  }
  if (quoted) throw new Error('csv');
  fields.push(field.trim());
  if (fields.some(Boolean)) output.push(fields);
  return output;
}

export function parseLabImportCsv(text: string): LabImportEntry[] {
  const [headers, ...records] = parseRows(text.replace(/^\uFEFF/, ''));
  if (!headers || new Set(headers).size !== headers.length ||
      !requiredHeaders.every((name) => headers.includes(name))) throw new Error('csv');

  const entries = new Map<string | number, LabImportEntry>();
  const invalidMessages = new Set<string | number>();
  for (const [index, record] of records.entries()) {
    const cells = Object.fromEntries(headers.map((name, index) => [name, record[index]]));
    const messageId = cells.message_id?.toLowerCase() || '';
    const key = messageId || index;
    if (invalidMessages.has(key)) continue;
    const reportId = parseLabImportReportId(cells.report_instance_id ?? '');
    const barcode = cells.specimen_barcode ?? '';
    const method = cells.method_code || undefined;
    const observedAt = cells.observed_at || undefined;
    const flags = parseInstrumentFlags(cells.instrument_flags);
    const current = entries.get(key) ?? {
      message_id: messageId,
      report_instance_id: reportId,
      specimen_barcode: barcode,
      method_code: method,
      observed_at: observedAt,
      values: [],
    };
    const sameTarget = current.report_instance_id === reportId && current.specimen_barcode === barcode;
    if (record.length !== headers.length || !messageId || !reportId || !barcode || !cells.analyte_code || !cells.value ||
        flags == null || !sameTarget ||
        current.method_code !== method || current.observed_at !== observedAt || current.values.length >= 100) {
      // The API returns invalid_row for an empty message. Keep its position
      // in preview and quarantine all its analytes together.
      entries.set(key, { ...current, report_instance_id: sameTarget ? reportId : 0, values: [] });
      invalidMessages.add(key);
      continue;
    }
    current.values.push({
      analyte_code: cells.analyte_code,
      unit_code: cells.unit_code || null,
      value_text: cells.value,
      ...(flags.length > 0 ? { instrument_flags: flags } : {}),
    });
    entries.set(key, current);
  }
  if (!entries.size || entries.size > 100) throw new Error('csv');
  return [...entries.values()];
}
