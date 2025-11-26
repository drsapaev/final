import React, { useState, useRef, useEffect } from 'react';

/**
 * Современный компонент для ввода телефона с маской
 * Заменяет react-input-mask для избежания findDOMNode warnings
 */
const PhoneInput = ({ 
  value = '', 
  onChange, 
  placeholder = '+7 (999) 123-45-67',
  style = {},
  className = '',
  ...props 
}) => {
  const [displayValue, setDisplayValue] = useState('');
  const inputRef = useRef(null);

  // Форматирование номера телефона
  const formatPhoneNumber = (input) => {
    // Удаляем все нецифровые символы
    const numbers = input.replace(/\D/g, '');
    
    // Если начинается с 8, заменяем на 7
    let cleanNumber = numbers;
    if (cleanNumber.startsWith('8')) {
      cleanNumber = '7' + cleanNumber.slice(1);
    }
    
    // Если не начинается с 7, добавляем 7
    if (!cleanNumber.startsWith('7') && cleanNumber.length > 0) {
      cleanNumber = '7' + cleanNumber;
    }
    
    // Ограничиваем до 11 цифр
    cleanNumber = cleanNumber.slice(0, 11);
    
    // Форматируем в маску +7 (999) 999-99-99
    if (cleanNumber.length === 0) return '';
    if (cleanNumber.length <= 1) return `+${cleanNumber}`;
    if (cleanNumber.length <= 4) return `+7 (${cleanNumber.slice(1)}`;
    if (cleanNumber.length <= 7) return `+7 (${cleanNumber.slice(1, 4)}) ${cleanNumber.slice(4)}`;
    if (cleanNumber.length <= 9) return `+7 (${cleanNumber.slice(1, 4)}) ${cleanNumber.slice(4, 7)}-${cleanNumber.slice(7)}`;
    return `+7 (${cleanNumber.slice(1, 4)}) ${cleanNumber.slice(4, 7)}-${cleanNumber.slice(7, 9)}-${cleanNumber.slice(9)}`;
  };

  // Обработка изменений
  const handleChange = (e) => {
    const input = e.target.value;
    const formatted = formatPhoneNumber(input);
    
    setDisplayValue(formatted);
    
    // Извлекаем только цифры для передачи в onChange
    const numbers = input.replace(/\D/g, '');
    let cleanNumber = numbers;
    
    if (cleanNumber.startsWith('8')) {
      cleanNumber = '7' + cleanNumber.slice(1);
    }
    
    if (!cleanNumber.startsWith('7') && cleanNumber.length > 0) {
      cleanNumber = '7' + cleanNumber;
    }
    
    cleanNumber = cleanNumber.slice(0, 11);
    
    // Создаем событие с отформатированным значением
    const syntheticEvent = {
      ...e,
      target: {
        ...e.target,
        value: formatted,
        rawValue: cleanNumber
      }
    };
    
    onChange?.(syntheticEvent);
  };

  // Обработка вставки из буфера обмена
  const handlePaste = (e) => {
    e.preventDefault();
    const pastedText = e.clipboardData.getData('text');
    const formatted = formatPhoneNumber(pastedText);
    setDisplayValue(formatted);
    
    const numbers = pastedText.replace(/\D/g, '');
    let cleanNumber = numbers;
    
    if (cleanNumber.startsWith('8')) {
      cleanNumber = '7' + cleanNumber.slice(1);
    }
    
    if (!cleanNumber.startsWith('7') && cleanNumber.length > 0) {
      cleanNumber = '7' + cleanNumber;
    }
    
    cleanNumber = cleanNumber.slice(0, 11);
    
    const syntheticEvent = {
      ...e,
      target: {
        ...e.target,
        value: formatted,
        rawValue: cleanNumber
      }
    };
    
    onChange?.(syntheticEvent);
  };

  // Синхронизация с внешним value
  useEffect(() => {
    if (value !== displayValue) {
      setDisplayValue(formatPhoneNumber(value));
    }
  }, [value]);

  // Обработка клавиш
  const handleKeyDown = (e) => {
    // Разрешаем: цифры, Backspace, Delete, стрелки, Tab, Enter
    const allowedKeys = [
      'Backspace', 'Delete', 'ArrowLeft', 'ArrowRight', 
      'ArrowUp', 'ArrowDown', 'Tab', 'Enter', 'Home', 'End'
    ];
    
    if (allowedKeys.includes(e.key) || e.ctrlKey || e.metaKey) {
      return;
    }
    
    // Разрешаем только цифры
    if (!/\d/.test(e.key)) {
      e.preventDefault();
    }
  };

  return (
    <input
      ref={inputRef}
      type="tel"
      value={displayValue}
      onChange={handleChange}
      onPaste={handlePaste}
      onKeyDown={handleKeyDown}
      placeholder={placeholder}
      style={{
        width: '100%',
        padding: '12px 16px',
        border: '1px solid #d1d5db',
        borderRadius: '8px',
        fontSize: '16px',
        fontFamily: 'inherit',
        outline: 'none',
        transition: 'border-color 0.2s ease, box-shadow 0.2s ease',
        ...style
      }}
      className={className}
      {...props}
    />
  );
};

export default PhoneInput;

