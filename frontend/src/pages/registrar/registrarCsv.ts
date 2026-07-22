/**
 * CSV generation and download utilities for Registrar Panel.
 *
 * UX Audit Registrar #14: extracted from RegistrarPanel.jsx (lines 1330-1389).
 * Pure functions, no React dependencies.
 *
 * Security:
 * - R-05: phone numbers are masked in CSV export (PHI protection).
 * - R-23: CSV injection protection (CWE-1236) — dangerous characters
 *   (=, +, -, @) are prefixed with single quote to prevent formula injection.
 */

/**
 * Mask phone number for CSV export (PHI protection).
 * Example: +998 90 123 45 67 → +998 ***-**-67
 */
function maskPhoneForCSV(phone: unknown): string {
  if (!phone) return '';
  const phoneStr = String(phone);
  const digits = phoneStr.replace(/\D/g, '');
  if (digits.length < 4) return '***';
  const lastTwo = digits.slice(-2);
  const countryMatch = phoneStr.match(/^\+\d{1,3}/);
  const country = countryMatch ? countryMatch[0] : '+';
  return `${country} ***-**-${lastTwo}`;
}

/**
 * Generate CSV string from appointment rows.
 * @param {Array} data - appointment rows
 * @param {Object} options - export options
 * @param {boolean} options.maskPhone - mask phone numbers for PHI protection (default: true)
 * @param {boolean} options.includeAddress - include address column (default: false)
 * @param {boolean} options.includeTimestamps - include date/time/changed columns (default: false)
 * @returns {string} CSV content with BOM-safe headers
 */
export function generateCSV(data: Record<string, unknown>[], options: Record<string, unknown> = {}) {
  const {
    maskPhone = true,
    includeAddress = false,
    includeTimestamps = false,
  } = options as { maskPhone?: boolean; includeAddress?: boolean; includeTimestamps?: boolean };

  // UX Audit R-3.1: unified CSV generation with PHI masking.
  // Раньше: handleExport в EnhancedAppointmentsTable использовал formatPhoneNumber
  // (БЕЗ маски) — PHI leak. Теперь: единая функция с maskPhone=true по умолчанию.
  const phoneFormatter = maskPhone
    ? (p: unknown) => maskPhoneForCSV(p)
    : (p: unknown) => (p ? String(p) : '');

  const headers = ['№', 'ФИО', 'Год рождения', 'Телефон'];
  if (includeAddress) headers.push('Адрес');
  headers.push('Услуги', 'Тип обращения', 'Вид оплаты');
  if (includeTimestamps) headers.push('Дата', 'Время', 'Изменено');
  headers.push('Статус', 'Стоимость');

  const rows = data.map((row, index) => {
    const baseRow = [
      index + 1,
      row.patient_fio || '',
      row.patient_birth_year || '',
      // R-05 fix: маскируем телефон в CSV-экспорте
      phoneFormatter(row.patient_phone || ''),
    ];
    if (includeAddress) baseRow.push(row.address || '');
    baseRow.push(
      Array.isArray(row.services) ? row.services.join('; ') : row.services || '',
      row.visit_type || '',
      row.payment_type || '',
    );
    if (includeTimestamps) {
      baseRow.push(
        row.appointment_date || String(row.created_at ?? '').split('T')[0] || '',
        row.appointment_time || '',
        row.updated_at ? String(row.updated_at).split('T')[0] : '',
      );
    }
    baseRow.push(row.status || '', row.cost || row.total_amount || '');
    return baseRow;
  });

  // R-23 fix: CSV injection protection (CWE-1236).
  const escapeCSVCell = (value: unknown) => {
    const str = String(value ?? '');
    let escaped = str.replace(/"/g, '""');
    if (/^[=+\-@]/.test(escaped)) {
      escaped = '\'' + escaped;
    }
    return `"${escaped}"`;
  };

  const csvContent = [
    headers.join(','),
    ...rows.map((row) => row.map(escapeCSVCell).join(',')),
  ].join('\n');

  return csvContent;
}

/**
 * Trigger browser download of CSV file.
 * @param {string} content - CSV content string
 * @param {string} filename - download filename
 */
export function downloadCSV(content: string, filename: string) {
  const blob = new Blob(['\ufeff' + content], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  const url = URL.createObjectURL(blob);
  link.setAttribute('href', url);
  link.setAttribute('download', filename);
  link.style.visibility = 'hidden';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

export default { generateCSV, downloadCSV };
