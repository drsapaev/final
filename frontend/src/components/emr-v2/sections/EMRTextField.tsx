
/**
 * EMRTextField - Base text input/textarea for EMR sections
 * 
 * Rules (Phase 4):
 * - No internal state (controlled only)
 * - No AI logic here (passed via props if needed)
 * - Just a styled input that calls onChange
 */
import PropTypes from 'prop-types';
import './EMRTextField.css';
import { Input } from '../../ui/macos';

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
/**
 * Event-like object for EMRTextField's legacy `onChange`.
 * @deprecated Use `onValueChange` for new code.
 */
export interface EMRTextFieldChangeEvent {
  target: { value: string; name?: string };
}

interface EMRTextFieldProps {
  value?: string;
  /** @deprecated Use onValueChange instead. */
  onChange?: (event: EMRTextFieldChangeEvent) => void;
  /** Value-based handler — receives the string value directly. */
  onValueChange?: (value: string) => void;
  isEditable?: boolean;
  aiEnabled?: boolean;
  onRequestAI?: (text: string) => void;
  error?: string;
  autoFocus?: boolean;
  onFieldTouch?: () => void;
  onBlur?: () => void;
  label?: string;
  placeholder?: string;
  multiline?: boolean;
  rows?: number;
  disabled?: boolean;
  required?: boolean;
  className?: string;
  id?: string;
  [key: string]: unknown;
}

export function EMRTextField({
    value = '',
    onChange,
    onValueChange,
    placeholder = '',
    multiline = false,
    rows = 3,
    disabled = false,
    label,
    required = false,
    className = '',
    id,
    ...rest
}: EMRTextFieldProps) {
    const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
        const val = e.target.value;
        onValueChange?.(val);
        onChange?.({ target: { value: val } });
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
                <Input type="text" {...inputProps} />
            )}
        </div>
    );
}

EMRTextField.propTypes = {
    value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    onChange: PropTypes.func,
    placeholder: PropTypes.string,
    multiline: PropTypes.bool,
    rows: PropTypes.number,
    disabled: PropTypes.bool,
    label: PropTypes.node,
    required: PropTypes.bool,
    className: PropTypes.string,
    id: PropTypes.string,
};

export default EMRTextField;
