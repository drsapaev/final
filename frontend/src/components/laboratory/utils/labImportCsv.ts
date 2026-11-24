import type { LabImportEntry } from '../../../api/labOperations';

const requiredHeaders = [
  'message_id', 'report_instance_id', 'specimen_barcode', 'analyte_code', 'unit_code', 'value',
];

export const LAB_IMPORT_CSV_HEADER = [...requiredHeaders, 'method_code', 'observed_at'].join(',');

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
  if (!headers || !requiredHeaders.every((name) => headers.includes(name))) throw new Error('csv');

  const entries = new Map<string, LabImportEntry>();
  for (const record of records) {
    if (record.length !== headers.length) throw new Error('csv');
    const cells = Object.fromEntries(headers.map((name, index) => [name, record[index]]));
    const reportId = Number(cells.report_instance_id);
    if (!Number.isSafeInteger(reportId) || reportId <= 0 || !cells.message_id ||
      !cells.specimen_barcode || !cells.analyte_code || !cells.value) throw new Error('csv');
    const current = entries.get(cells.message_id) ?? {
      message_id: cells.message_id,
      report_instance_id: reportId,
      specimen_barcode: cells.specimen_barcode,
      method_code: cells.method_code || undefined,
      observed_at: cells.observed_at || undefined,
      values: [],
    };
    if (current.report_instance_id !== reportId || current.specimen_barcode !== cells.specimen_barcode ||
      current.method_code !== (cells.method_code || undefined) ||
      current.observed_at !== (cells.observed_at || undefined)) throw new Error('csv');
    current.values.push({
      analyte_code: cells.analyte_code,
      unit_code: cells.unit_code || null,
      value_text: cells.value,
    });
    if (current.values.length > 100) throw new Error('csv');
    entries.set(cells.message_id, current);
  }
  if (!entries.size || entries.size > 100) throw new Error('csv');
  return [...entries.values()];
}
