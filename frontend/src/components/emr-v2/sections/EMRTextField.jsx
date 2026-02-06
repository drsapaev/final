/**
 * EMRTextField - Base text input/textarea for EMR sections
 * 
 * Rules (Phase 4):
 * - No internal state (controlled only)
 * - No AI logic here (passed via props if needed)
 * - Just a styled input that calls onChange
 */

import React from 'react';
import './EMRTextField.css';

/**
 * EMRTextField Component
 * 
 * @param {Object} props
 * @param {string} props.value - Current value
 * @param {Function} props.onChange - Change handler (receives value, not event)
 * @param {string} props.placeholder - Placeholder text
 * @param {boolean} props.multiline - Use textarea instead of input
 * @param {number} props.rows - Number of rows for textarea
 * @param {boolean} props.disabled - Disable input
 * @param {string} props.label - Optional label
 * @param {boolean} props.required - Show required indicator
 * @param {string} props.className - Additional CSS class
 * @param {string} props.id - Input ID
 */
export function EMRTextField({
    value = '',
    onChange,
    placeholder = '',
    multiline = false,
    rows = 3,
    disabled = false,
    label,
    required = false,
    className = '',
    id,
    ...rest
}) {
    const handleChange = (e) => {
        onChange?.(e.target.value);
    };

    const inputId = id || `emr-field-${Math.random().toString(36).substr(2, 9)}`;

    const inputProps = {
        id: inputId,
        className: `emr-textfield__input ${className}`,
        value: value || '',
        onChange: handleChange,
        placeholder,
        disabled,
        ...rest,
    };

    return (
        <div className="emr-textfield">
            {label && (
                <label htmlFor={inputId} className="emr-textfield__label">
                    {label}
                    {required && <span className="emr-textfield__required">*</span>}
                </label>
            )}

            {multiline ? (
                <textarea {...inputProps} rows={rows} />
            ) : (
                <input type="text" {...inputProps} />
            )}
        </div>
    );
}

export default EMRTextField;
