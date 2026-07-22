import PropTypes from 'prop-types';
import { Input } from './ui/macos';
import type { CSSProperties, ChangeEvent, FocusEvent } from 'react';
import React from 'react';

interface TimeInputProps {
  value?: string;
  onChange?: (value: string) => void;
  disabled?: boolean;
  style?: CSSProperties;
  ariaLabel?: string;
}

/**
 * TimeInput — контрол ввода времени HH:MM с простейшей валидацией.
 * Props:
 *  - value: "HH:MM"
 *  - onChange: (value) => void
 *  - disabled?: boolean
 *  - style?: object
 */
export default function TimeInput({
  value = '09:00',
  onChange = () => {},
  disabled = false,
  style = {},
  ariaLabel = 'Время в формате часы и минуты',
}: TimeInputProps) {
  function onInput(e: ChangeEvent<HTMLInputElement>) {
    const raw = e.target.value;
    const cleaned = raw.replace(/[^\d:]/g, '').slice(0, 5);
    onChange(cleaned);
  }

  function onBlur() {
    const m = /^(\d{1,2}):(\d{1,2})$/.exec(String(value || ''));
    if (!m) return;
    const hh = Math.max(0, Math.min(23, parseInt(m[1], 10) || 0));
    const mm = Math.max(0, Math.min(59, parseInt(m[2], 10) || 0));
    const fixed = `${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}`;
    if (fixed !== value) onChange(fixed);
  }

  const baseStyle: CSSProperties = {
    padding: 8,
    borderRadius: 8,
    border: '1px solid #ddd',
    width: 100,
    fontVariantNumeric: 'tabular-nums',
    ...style,
  };

  return (
    <Input
      aria-label={ariaLabel}
      type="text"
      placeholder="HH:MM"
      value={value}
      onChange={onInput as unknown as React.ChangeEventHandler<HTMLInputElement>}
      onBlur={onBlur as unknown as React.FocusEventHandler<HTMLInputElement>}
      disabled={disabled}
      inputMode="numeric"
      pattern="^\d{2}:\d{2}$"
      style={baseStyle}
    />
  );
}


TimeInput.propTypes = {
  ...(TimeInput.propTypes || {}),
  disabled: PropTypes.any,
  ariaLabel: PropTypes.string,
  onChange: PropTypes.any,
  style: PropTypes.any,
  value: PropTypes.any,
};
