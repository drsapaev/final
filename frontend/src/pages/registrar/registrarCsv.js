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
function maskPhoneForCSV(phone) {
  if (!phone) return '';
  const digits = phone.replace(/\D/g, '');
  if (digits.length < 4) return '***';
  const lastTwo = digits.slice(-2);
  const countryMatch = phone.match(/^\+\d{1,3}/);
  const country = countryMatch ? countryMatch[0] : '+';
  return `${country} ***-**-${lastTwo}`;
}

/**
 * Generate CSV string from appointment rows.
 * @param {Array} data - appointment rows
 * @returns {string} CSV content with BOM-safe headers
 */
export function generateCSV(data) {
  const headers = ['№', 'ФИО', 'Год рождения', 'Телефон', 'Услуги', 'Тип обращения', 'Вид оплаты', 'Стоимость', 'Статус'];
  const rows = data.map((row, index) => [
    index + 1,
    row.patient_fio || '',
    row.patient_birth_year || '',
    // R-05 fix: маскируем телефон в CSV-экспорте
    maskPhoneForCSV(row.patient_phone || ''),
    Array.isArray(row.services) ? row.services.join('; ') : row.services || '',
    row.visit_type || '',
    row.payment_type || '',
    row.cost || '',
    row.status || '',
  ]);

  // R-23 fix: CSV injection protection (CWE-1236).
  const escapeCSVCell = (value) => {
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
export function downloadCSV(content, filename) {
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
