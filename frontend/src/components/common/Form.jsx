// Система форм с валидацией
import React, { useState, useCallback, useRef } from 'react';
import { useTheme } from '../../contexts/ThemeContext';

/**
 * Контекст для форм
 */
const FormContext = React.createContext();

/**
 * Провайдер контекста форм
 */
export function FormProvider({ children }) {
  const [forms, setForms] = useState({});

  const registerForm = useCallback((formId, initialValues = {}) => {
    setForms(prev => ({
      ...prev,
      [formId]: {
        values: initialValues,
        errors: {},
        touched: {},
        isSubmitting: false
      }
    }));
  }, []);

  const updateForm = useCallback((formId, updates) => {
    setForms(prev => ({
      ...prev,
      [formId]: {
        ...prev[formId],
        ...updates
      }
    }));
  }, []);

  const getForm = useCallback((formId) => {
    return forms[formId] || null;
  }, [forms]);

  const value = {
    forms,
    registerForm,
    updateForm,
    getForm
  };

  return (
    <FormContext.Provider value={value}>
      {children}
    </FormContext.Provider>
  );
}

/**
 * Хук для использования форм
 */
export function useForm(formId, initialValues = {}) {
  const context = React.useContext(FormContext);
  if (!context) {
    throw new Error('useForm must be used within a FormProvider');
  }

  const { registerForm, updateForm, getForm } = context;
  const form = getForm(formId);

  React.useEffect(() => {
    if (!form) {
      registerForm(formId, initialValues);
    }
  }, [formId, initialValues, form, registerForm]);

  const setValue = useCallback((name, value) => {
    updateForm(formId, {
      values: {
        ...form?.values,
        [name]: value
      }
    });
  }, [formId, form?.values, updateForm]);

  const setError = useCallback((name, error) => {
    updateForm(formId, {
      errors: {
        ...form?.errors,
        [name]: error
      }
    });
  }, [formId, form?.errors, updateForm]);

  const setTouched = useCallback((name, touched = true) => {
    updateForm(formId, {
      touched: {
        ...form?.touched,
        [name]: touched
      }
    });
  }, [formId, form?.touched, updateForm]);

  const setSubmitting = useCallback((isSubmitting) => {
    updateForm(formId, { isSubmitting });
  }, [formId, updateForm]);

  const resetForm = useCallback(() => {
    updateForm(formId, {
      values: initialValues,
      errors: {},
      touched: {},
      isSubmitting: false
    });
  }, [formId, initialValues, updateForm]);

  const validateForm = useCallback((validationRules) => {
    const errors = {};
    const values = form?.values || {};

    Object.entries(validationRules).forEach(([name, rules]) => {
      const value = values[name];
      
      if (rules.required && (!value || value.toString().trim() === '')) {
        errors[name] = rules.required;
        return;
      }

      if (value && rules.minLength && value.length < rules.minLength) {
        errors[name] = rules.minLength;
        return;
      }

      if (value && rules.maxLength && value.length > rules.maxLength) {
        errors[name] = rules.maxLength;
        return;
      }

      if (value && rules.pattern && !rules.pattern.test(value)) {
        errors[name] = rules.pattern;
        return;
      }

      if (value && rules.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
        errors[name] = rules.email;
        return;
      }

      if (value && rules.phone && !/^[\+]?[1-9][\d]{0,15}$/.test(value.replace(/\s/g, ''))) {
        errors[name] = rules.phone;
        return;
      }

      if (value && rules.custom && !rules.custom(value)) {
        errors[name] = rules.custom;
        return;
      }
    });

    updateForm(formId, { errors });
    return Object.keys(errors).length === 0;
  }, [formId, form?.values, updateForm]);

  return {
    form,
    setValue,
    setError,
    setTouched,
    setSubmitting,
    resetForm,
    validateForm
  };
}

/**
 * Компонент формы
 */
export function Form({ 
  formId, 
  initialValues = {}, 
  onSubmit, 
  validationRules = {},
  children,
  ...props 
}) {
  const { form, setSubmitting, validateForm } = useForm(formId, initialValues);

  const handleSubmit = useCallback(async (e) => {
    e.preventDefault();
    
    if (Object.keys(validationRules).length > 0) {
      const isValid = validateForm(validationRules);
      if (!isValid) return;
    }

    setSubmitting(true);
    try {
      await onSubmit?.(form?.values, form);
    } finally {
      setSubmitting(false);
    }
  }, [form, onSubmit, validateForm, setSubmitting]);

  return (
    <form onSubmit={handleSubmit} {...props}>
      {children}
    </form>
  );
}

/**
 * Компонент поля ввода
 */
export function FormField({ 
  name, 
  label, 
  type = 'text',
  placeholder,
  required = false,
  validationRules = {},
  formId,
  ...props 
}) {
  const { form, setValue, setTouched, setError } = useForm(formId);
  const theme = useTheme();
  const { getColor, getSpacing, getFontSize } = theme;

  const value = form?.values?.[name] || '';
  const error = form?.errors?.[name];
  const touched = form?.touched?.[name];

  const handleChange = useCallback((e) => {
    const newValue = e.target.value;
    setValue(name, newValue);
    
    // Очищаем ошибку при изменении
    if (error) {
      setError(name, null);
    }
  }, [name, setValue, error, setError]);

  const handleBlur = useCallback(() => {
    setTouched(name, true);
    
    // Валидация при потере фокуса
    if (Object.keys(validationRules).length > 0) {
      const rules = validationRules;
      
      if (rules.required && (!value || value.toString().trim() === '')) {
        setError(name, rules.required);
        return;
      }

      if (value && rules.minLength && value.length < rules.minLength) {
        setError(name, rules.minLength);
        return;
      }

      if (value && rules.maxLength && value.length > rules.maxLength) {
        setError(name, rules.maxLength);
        return;
      }

      if (value && rules.pattern && !rules.pattern.test(value)) {
        setError(name, rules.pattern);
        return;
      }

      if (value && rules.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
        setError(name, rules.email);
        return;
      }

      if (value && rules.phone && !/^[\+]?[1-9][\d]{0,15}$/.test(value.replace(/\s/g, ''))) {
        setError(name, rules.phone);
        return;
      }

      if (value && rules.custom && !rules.custom(value)) {
        setError(name, rules.custom);
        return;
      }
    }
  }, [name, value, validationRules, setTouched, setError]);

  const containerStyle = {
    marginBottom: getSpacing('md')
  };

  const labelStyle = {
    display: 'block',
    fontSize: getFontSize('sm'),
    fontWeight: '500',
    color: getColor('text', 'primary'),
    marginBottom: getSpacing('xs')
  };

  const inputStyle = {
    width: '100%',
    padding: getSpacing('sm'),
    fontSize: getFontSize('md'),
    border: `1px solid ${error && touched ? getColor('error', 'main') : getColor('border', 'main')}`,
    borderRadius: '6px',
    backgroundColor: getColor('background', 'primary'),
    color: getColor('text', 'primary'),
    transition: 'border-color 0.2s ease',
    ...props.style
  };

  const errorStyle = {
    fontSize: getFontSize('sm'),
    color: getColor('error', 'main'),
    marginTop: getSpacing('xs')
  };

  const requiredStyle = {
    color: getColor('error', 'main')
  };

  return (
    <div style={containerStyle}>
      {label && (
        <label style={labelStyle}>
          {label}
          {required && <span style={requiredStyle}> *</span>}
        </label>
      )}
      
      <input
        type={type}
        name={name}
        value={value}
        placeholder={placeholder}
        onChange={handleChange}
        onBlur={handleBlur}
        style={inputStyle}
        {...props}
      />
      
      {error && touched && (
        <div style={errorStyle}>{error}</div>
      )}
    </div>
  );
}

/**
 * Компонент текстовой области
 */
export function FormTextArea({ 
  name, 
  label, 
  placeholder,
  required = false,
  validationRules = {},
  formId,
  rows = 4,
  ...props 
}) {
  const { form, setValue, setTouched, setError } = useForm(formId);
  const theme = useTheme();
  const { getColor, getSpacing, getFontSize } = theme;

  const value = form?.values?.[name] || '';
  const error = form?.errors?.[name];
  const touched = form?.touched?.[name];

  const handleChange = useCallback((e) => {
    const newValue = e.target.value;
    setValue(name, newValue);
    
    if (error) {
      setError(name, null);
    }
  }, [name, setValue, error, setError]);

  const handleBlur = useCallback(() => {
    setTouched(name, true);
    
    if (Object.keys(validationRules).length > 0) {
      const rules = validationRules;
      
      if (rules.required && (!value || value.toString().trim() === '')) {
        setError(name, rules.required);
        return;
      }

      if (value && rules.minLength && value.length < rules.minLength) {
        setError(name, rules.minLength);
        return;
      }

      if (value && rules.maxLength && value.length > rules.maxLength) {
        setError(name, rules.maxLength);
        return;
      }
    }
  }, [name, value, validationRules, setTouched, setError]);

  const containerStyle = {
    marginBottom: getSpacing('md')
  };

  const labelStyle = {
    display: 'block',
    fontSize: getFontSize('sm'),
    fontWeight: '500',
    color: getColor('text', 'primary'),
    marginBottom: getSpacing('xs')
  };

  const textareaStyle = {
    width: '100%',
    padding: getSpacing('sm'),
    fontSize: getFontSize('md'),
    border: `1px solid ${error && touched ? getColor('error', 'main') : getColor('border', 'main')}`,
    borderRadius: '6px',
    backgroundColor: getColor('background', 'primary'),
    color: getColor('text', 'primary'),
    resize: 'vertical',
    minHeight: `${rows * 1.5}em`,
    transition: 'border-color 0.2s ease',
    ...props.style
  };

  const errorStyle = {
    fontSize: getFontSize('sm'),
    color: getColor('error', 'main'),
    marginTop: getSpacing('xs')
  };

  const requiredStyle = {
    color: getColor('error', 'main')
  };

  return (
    <div style={containerStyle}>
      {label && (
        <label style={labelStyle}>
          {label}
          {required && <span style={requiredStyle}> *</span>}
        </label>
      )}
      
      <textarea
        name={name}
        value={value}
        placeholder={placeholder}
        onChange={handleChange}
        onBlur={handleBlur}
        rows={rows}
        style={textareaStyle}
        {...props}
      />
      
      {error && touched && (
        <div style={errorStyle}>{error}</div>
      )}
    </div>
  );
}

/**
 * Компонент селекта
 */
export function FormSelect({ 
  name, 
  label, 
  options = [],
  placeholder = 'Выберите...',
  required = false,
  validationRules = {},
  formId,
  ...props 
}) {
  const { form, setValue, setTouched, setError } = useForm(formId);
  const theme = useTheme();
  const { getColor, getSpacing, getFontSize } = theme;

  const value = form?.values?.[name] || '';
  const error = form?.errors?.[name];
  const touched = form?.touched?.[name];

  const handleChange = useCallback((e) => {
    const newValue = e.target.value;
    setValue(name, newValue);
    
    if (error) {
      setError(name, null);
    }
  }, [name, setValue, error, setError]);

  const handleBlur = useCallback(() => {
    setTouched(name, true);
    
    if (Object.keys(validationRules).length > 0) {
      const rules = validationRules;
      
      if (rules.required && (!value || value === '')) {
        setError(name, rules.required);
        return;
      }
    }
  }, [name, value, validationRules, setTouched, setError]);

  const containerStyle = {
    marginBottom: getSpacing('md')
  };

  const labelStyle = {
    display: 'block',
    fontSize: getFontSize('sm'),
    fontWeight: '500',
    color: getColor('text', 'primary'),
    marginBottom: getSpacing('xs')
  };

  const selectStyle = {
    width: '100%',
    padding: getSpacing('sm'),
    fontSize: getFontSize('md'),
    border: `1px solid ${error && touched ? getColor('error', 'main') : getColor('border', 'main')}`,
    borderRadius: '6px',
    backgroundColor: getColor('background', 'primary'),
    color: getColor('text', 'primary'),
    transition: 'border-color 0.2s ease',
    ...props.style
  };

  const errorStyle = {
    fontSize: getFontSize('sm'),
    color: getColor('error', 'main'),
    marginTop: getSpacing('xs')
  };

  const requiredStyle = {
    color: getColor('error', 'main')
  };

  return (
    <div style={containerStyle}>
      {label && (
        <label style={labelStyle}>
          {label}
          {required && <span style={requiredStyle}> *</span>}
        </label>
      )}
      
      <select
        name={name}
        value={value}
        onChange={handleChange}
        onBlur={handleBlur}
        style={selectStyle}
        {...props}
      >
        <option value="">{placeholder}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      
      {error && touched && (
        <div style={errorStyle}>{error}</div>
      )}
    </div>
  );
}

/**
 * Компонент кнопки отправки
 */
export function SubmitButton({ 
  children = 'Отправить', 
  formId,
  ...props 
}) {
  const { form } = useForm(formId);
  const theme = useTheme();
  const { getColor, getSpacing, getFontSize } = theme;

  const buttonStyle = {
    padding: `${getSpacing('sm')} ${getSpacing('lg')}`,
    fontSize: getFontSize('md'),
    fontWeight: '500',
    backgroundColor: getColor('primary', 'main'),
    color: getColor('primary', 'contrast'),
    border: 'none',
    borderRadius: '6px',
    cursor: form?.isSubmitting ? 'not-allowed' : 'pointer',
    opacity: form?.isSubmitting ? 0.7 : 1,
    transition: 'all 0.2s ease',
    ...props.style
  };

  return (
    <button
      type="submit"
      disabled={form?.isSubmitting}
      style={buttonStyle}
      {...props}
    >
      {form?.isSubmitting ? 'Отправка...' : children}
    </button>
  );
}

