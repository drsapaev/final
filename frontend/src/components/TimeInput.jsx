import React from "react";

/**
 * TimeInput — контрол ввода времени HH:MM с простейшей валидацией.
 * Props:
 *  - value: "HH:MM"
 *  - onChange: (value) => void
 *  - disabled?: boolean
 *  - style?: object
 */
export default function TimeInput({ value = "09:00", onChange = () => {}, disabled = false, style = {} }) {
  function onInput(e) {
    const raw = e.target.value;
    // Нормализуем до ##:##, только цифры и двоеточие
    const cleaned = raw.replace(/[^\d:]/g, "").slice(0, 5);
    onChange(cleaned);
  }

  function onBlur() {
    // Автокоррекция "9:5" -> "09:05"
    const m = /^(\d{1,2}):(\d{1,2})$/.exec(String(value || ""));
    if (!m) return;
    let hh = Math.max(0, Math.min(23, parseInt(m[1], 10) || 0));
    let mm = Math.max(0, Math.min(59, parseInt(m[2], 10) || 0));
    const fixed = `${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}`;
    if (fixed !== value) onChange(fixed);
  }

  const baseStyle = {
    padding: 8,
    borderRadius: 8,
    border: "1px solid #ddd",
    width: 100,
    fontVariantNumeric: "tabular-nums",
    ...style,
  };

  return (
    <input
      type="text"
      placeholder="HH:MM"
      value={value}
      onChange={onInput}
      onBlur={onBlur}
      disabled={disabled}
      inputMode="numeric"
      pattern="^\d{2}:\d{2}$"
      style={baseStyle}
    />
  );
}