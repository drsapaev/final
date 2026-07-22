/**
 * Safely converts an unknown value to a form-compatible string.
 *
 * Unlike raw `String(value)`, this function handles null/undefined/objects
 * gracefully, preventing "undefined", "null", or "[object Object]" from
 * silently entering form state.
 *
 * @example
 * toFormValue('hello')     // 'hello'
 * toFormValue(42)          // '42'
 * toFormValue(true)        // 'true'
 * toFormValue(null)        // ''
 * toFormValue(undefined)   // ''
 * toFormValue({})          // ''
 * toFormValue({ value: 'x' }) // 'x'
 * toFormValue({ id: 1 })   // '1'
 */
export function toFormValue(value: unknown): string {
  if (value == null) {
    return '';
  }

  if (typeof value === 'string') {
    return value;
  }

  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }

  if (typeof value === 'object') {
    const obj = value as Record<string, unknown>;
    if ('value' in obj && typeof obj.value === 'string') {
      return obj.value;
    }
    if ('value' in obj && typeof obj.value === 'number') {
      return String(obj.value);
    }
    if ('id' in obj && typeof obj.id === 'string') {
      return obj.id;
    }
    if ('id' in obj && typeof obj.id === 'number') {
      return String(obj.id);
    }
    if ('label' in obj && typeof obj.label === 'string') {
      return obj.label;
    }
  }

  return '';
}
