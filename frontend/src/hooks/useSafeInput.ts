/**
 * React hook для безопасной работы с пользовательским вводом.
 * XSS Protection для форм.
 */
import { useCallback, useState } from 'react';
import { sanitizeInput, sanitizeEmail, sanitizePhone } from '../utils/sanitizer';
import logger from '../utils/logger';

type CustomValidator = (value: string) => string | null;

interface SafeInputOptions {
  maxLength?: number;
  required?: boolean;
  type?: string;
  allowNewlines?: boolean;
  allowSpecialChars?: boolean;
  customValidator?: CustomValidator | null;
}

type SafeInputReturn = [string, (newValue: string) => void, string];

/**
 * Hook для безопасной работы с input полями.
 */
export function useSafeInput(
  initialValue: string = '',
  options: SafeInputOptions = {},
): SafeInputReturn {
  const {
    maxLength = 10000,
    required = false,
    type = 'text',
    allowNewlines = true,
    allowSpecialChars = true,
    customValidator = null,
  } = options;

  const [value, setValueInternal] = useState<string>(initialValue);
  const [error, setError] = useState<string>('');

  const setValue = useCallback(
    (newValue: string): void => {
      if (newValue === null || newValue === undefined) {
        setValueInternal('');
        setError('');
        return;
      }

      const input = String(newValue);
      let sanitized = '';
      let validationError = '';

      switch (type) {
        case 'phone':
          sanitized = sanitizePhone(input);
          break;

        case 'email': {
          const emailResult = sanitizeEmail(input);
          if (emailResult === null && input.trim().length > 0) {
            validationError = 'Невалидный email адрес';
            sanitized = input;
          } else {
            sanitized = emailResult || '';
          }
          break;
        }

        case 'text':
        default:
          sanitized = sanitizeInput(input, {
            maxLength,
            allowNewlines,
          } as Record<string, unknown>);
          break;
      }

      if (required && !sanitized.trim()) {
        validationError = 'Поле обязательно для заполнения';
      }

      if (customValidator && !validationError) {
        const customError = customValidator(sanitized);
        if (customError) {
          validationError = customError;
        }
      }

      if (sanitized !== input) {
        logger.warn('Input был санитизирован:', {
          original: input.substring(0, 50),
          sanitized: sanitized.substring(0, 50),
        });
      }

      setValueInternal(sanitized);
      setError(String(validationError));
    },
    [type, maxLength, required, allowNewlines, allowSpecialChars, customValidator],
  );

  return [value, setValue, error];
}

// ============================================================================
// useSafeForm
// ============================================================================

interface FieldValidationRules {
  required?: boolean;
  maxLength?: number;
  minLength?: number;
  type?: string;
  pattern?: RegExp | null;
  customValidator?: CustomValidator | null;
  allowNewlines?: boolean;
  allowSpecialChars?: boolean;
  errorMessage?: string;
}

interface FieldValidationResult {
  sanitized: string;
  error: string;
}

interface SafeFormReturn {
  values: Record<string, unknown>;
  errors: Record<string, string>;
  touched: Record<string, boolean>;
  handleChange: (fieldName: string) => (event: unknown) => void;
  handleBlur: (fieldName: string) => () => void;
  isValid: () => boolean;
  reset: () => void;
  setValue: (fieldName: string, value: string) => void;
}

/**
 * Hook для безопасной работы с объектом формы.
 */
export function useSafeForm(
  initialState: Record<string, unknown> = {},
  validationRules: Record<string, FieldValidationRules> = {},
): SafeFormReturn {
  const [values, setValues] = useState<Record<string, unknown>>(initialState);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  const validateField = useCallback(
    (fieldName: string, value: string): FieldValidationResult => {
      const rules = validationRules[fieldName] || {};
      const {
        required = false,
        maxLength = 10000,
        minLength = 0,
        type = 'text',
        pattern = null,
        customValidator = null,
      } = rules;

      let sanitized = value;
      let error = '';

      switch (type) {
        case 'phone':
          sanitized = sanitizePhone(value);
          break;

        case 'email': {
          const emailResult = sanitizeEmail(value);
          if (emailResult === null && value.trim().length > 0) {
            error = 'Невалидный email адрес';
          }
          sanitized = emailResult || value;
          break;
        }

        case 'text':
        default:
          sanitized = sanitizeInput(value, {
            maxLength,
            allowNewlines: rules.allowNewlines !== false,
          } as Record<string, unknown>);
          break;
      }

      if (!error) {
        if (required && !sanitized.trim()) {
          error = rules.errorMessage || 'Поле обязательно для заполнения';
        } else if (sanitized.length < minLength) {
          error = `Минимальная длина: ${minLength} символов`;
        } else if (sanitized.length > maxLength) {
          error = `Максимальная длина: ${maxLength} символов`;
        } else if (pattern && !pattern.test(sanitized)) {
          error = rules.errorMessage || 'Неверный формат';
        } else if (customValidator) {
          error = customValidator(sanitized) || '';
        }
      }

      return { sanitized, error };
    },
    [validationRules],
  );

  const handleChange = useCallback(
    (fieldName: string) => (event: unknown): void => {
      const rawValue =
        (event as { target?: { value?: string } })?.target?.value ?? String(event);
      const { sanitized, error } = validateField(fieldName, rawValue);

      setValues((prev) => ({ ...prev, [fieldName]: sanitized }));
      setErrors((prev) => ({ ...prev, [fieldName]: error }));
    },
    [validateField],
  );

  const handleBlur = useCallback(
    (fieldName: string) => (): void => {
      setTouched((prev) => ({ ...prev, [fieldName]: true }));

      const currentValue = String(values[fieldName] || '');
      const { error } = validateField(fieldName, currentValue);
      setErrors((prev) => ({ ...prev, [fieldName]: error }));
    },
    [values, validateField],
  );

  const isValid = useCallback((): boolean => {
    const allErrors: Record<string, string> = {};
    let hasErrors = false;

    Object.keys(validationRules).forEach((fieldName) => {
      const { error } = validateField(fieldName, String(values[fieldName] || ''));
      if (error) {
        allErrors[fieldName] = error;
        hasErrors = true;
      }
    });

    if (hasErrors) {
      setErrors(allErrors);
      setTouched(
        Object.keys(validationRules).reduce(
          (acc: Record<string, boolean>, key: string) => {
            acc[key] = true;
            return acc;
          },
          {},
        ),
      );
    }

    return !hasErrors;
  }, [values, validationRules, validateField]);

  const reset = useCallback((): void => {
    setValues(initialState);
    setErrors({});
    setTouched({});
  }, [initialState]);

  const setValue = useCallback(
    (fieldName: string, value: string): void => {
      const { sanitized, error } = validateField(fieldName, value);
      setValues((prev) => ({ ...prev, [fieldName]: sanitized }));
      setErrors((prev) => ({ ...prev, [fieldName]: error }));
    },
    [validateField],
  );

  return {
    values,
    errors,
    touched,
    handleChange,
    handleBlur,
    isValid,
    reset,
    setValue,
  };
}

// ============================================================================
// useSafeTextarea
// ============================================================================

interface SafeTextareaReturn {
  value: string;
  setValue: (newValue: string) => void;
  sanitizedPreview: string;
  error: string;
  isDifferent: boolean;
}

/**
 * Hook для безопасного textarea с предпросмотром санитизации.
 */
export function useSafeTextarea(
  initialValue: string = '',
  options: SafeInputOptions = {},
): SafeTextareaReturn {
  const [rawValue, setRawValue] = useState<string>(initialValue);
  const [value, setValue, error] = useSafeInput(initialValue, {
    ...options,
    allowNewlines: true,
  });

  const sanitizedPreview = sanitizeInput(rawValue, {
    maxLength: options.maxLength || 10000,
    allowNewlines: true,
  } as Record<string, unknown>);

  const handleChange = useCallback(
    (newValue: string): void => {
      setRawValue(newValue);
      setValue(newValue);
    },
    [setValue],
  );

  return {
    value,
    setValue: handleChange,
    sanitizedPreview,
    error,
    isDifferent: sanitizedPreview !== rawValue,
  };
}

export default useSafeInput;
