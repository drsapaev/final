
import { useBreakpoint } from '../../hooks/useEnhancedMediaQuery';
import { Input } from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';

interface ResponsiveFormProps {
  children?: React.ReactNode;
  onSubmit?: (e: React.FormEvent<HTMLFormElement>) => void;
  className?: string;
  style?: React.CSSProperties;
}

const ResponsiveForm = ({
  children,
  onSubmit,
  className = '',
  style = {}
}: ResponsiveFormProps) => {
  const { isMobile } = useBreakpoint();

  return (
    <form
      onSubmit={onSubmit}
      className={`responsive-form ${className}`}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: isMobile ? '16px' : '20px',
        ...style
      }}>
      
      {children}
    </form>);

};

// Компонент для группы полей
interface FormGroupProps {
  children?: React.ReactNode;
  label?: React.ReactNode;
  error?: React.ReactNode;
  required?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

const FormGroup = ({
  children,
  label,
  error,
  required = false,
  className = '',
  style = {}
}: FormGroupProps) => {
  const { isMobile } = useBreakpoint();

  return (
    <div
      className={`form-group ${className}`}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: isMobile ? '6px' : '8px',
        ...style
      }}>
      
      {label &&
      <label
        style={{
          fontSize: isMobile ? '14px' : '16px',
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--mac-text-primary)'
        }}>
        
          {label}
          {required && <span style={{ color: 'var(--mac-error)', marginLeft: 'var(--mac-spacing-1)' }}>*</span>}
        </label>
      }
      {children}
      {error &&
      <span
        style={{
          fontSize: isMobile ? '12px' : '14px',
          color: 'var(--mac-error)'
        }}>
        
          {error}
        </span>
      }
    </div>);

};

// Компонент для поля ввода
interface FormInputProps {
  type?: string;
  placeholder?: string;
  value?: string | number;
  onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
  disabled?: boolean;
  required?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

const FormInput = ({
  type = 'text',
  placeholder,
  value,
  onChange,
  disabled = false,
  required = false,
  className = '',
  style = {}
}: FormInputProps) => {
  const { isMobile } = useBreakpoint();

  return (
    <Input
      type={type}
      placeholder={placeholder}
      aria-label={placeholder || 'Form input'}
      value={value}
      onChange={onChange}
      disabled={disabled}
      required={required}
      className={className}
      style={{
        padding: isMobile ? '12px' : '16px',
        border: '1px solid var(--mac-border)',
        borderRadius: isMobile ? '8px' : '12px',
        fontSize: isMobile ? '16px' : '16px', // Предотвращает zoom на iOS
        fontFamily: 'inherit',
        transition: 'border-color 0.2s ease, box-shadow 0.2s ease',
        outline: 'none',
        ...style
      }}
      onFocus={(e: React.FocusEvent<HTMLElement>) => {
        e.target.style.borderColor = 'var(--mac-accent-blue)';
        e.target.style.boxShadow = '0 0 0 3px rgba(59, 130, 246, 0.1)';
      }}
      onBlur={(e: React.FocusEvent<HTMLElement>) => {
        e.target.style.borderColor = 'var(--mac-border)';
        e.target.style.boxShadow = 'none';
      }} />);


};

// Компонент для селекта
interface FormSelectProps {
  value?: string | number;
  onChange?: (e: React.ChangeEvent<HTMLSelectElement>) => void;
  children?: React.ReactNode;
  disabled?: boolean;
  required?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

const FormSelect = ({
  value,
  onChange,
  children,
  disabled = false,
  required = false,
  className = '',
  style = {}
}: FormSelectProps) => {
  const { isMobile } = useBreakpoint();

  return (
    <select
      value={value}
      onChange={onChange}
      disabled={disabled}
      required={required}
      className={className}
      style={{
        padding: isMobile ? '12px' : '16px',
        border: '1px solid var(--mac-border)',
        borderRadius: isMobile ? '8px' : '12px',
        fontSize: isMobile ? '16px' : '16px',
        fontFamily: 'inherit',
        backgroundColor: 'var(--mac-bg-primary)',  // PR-42 / Medium-F: was 'white' (broke dark mode)
        transition: 'border-color 0.2s ease, box-shadow 0.2s ease',
        outline: 'none',
        ...style
      }}
      onFocus={(e: React.FocusEvent<HTMLElement>) => {
        e.target.style.borderColor = 'var(--mac-accent-blue)';
        e.target.style.boxShadow = '0 0 0 3px rgba(59, 130, 246, 0.1)';
      }}
      onBlur={(e: React.FocusEvent<HTMLElement>) => {
        e.target.style.borderColor = 'var(--mac-border)';
        e.target.style.boxShadow = 'none';
      }}>
      
      {children}
    </select>);

};

// Компонент для textarea
interface FormTextareaProps {
  placeholder?: string;
  value?: string | number;
  onChange?: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
  disabled?: boolean;
  required?: boolean;
  rows?: number;
  className?: string;
  style?: React.CSSProperties;
}

const FormTextarea = ({
  placeholder,
  value,
  onChange,
  disabled = false,
  required = false,
  rows = 4,
  className = '',
  style = {}
}: FormTextareaProps) => {
  const { isMobile } = useBreakpoint();

  return (
    <textarea
      placeholder={placeholder}
      aria-label={placeholder || 'Form text'}
      value={value}
      onChange={onChange}
      disabled={disabled}
      required={required}
      rows={rows}
      className={className}
      style={{
        padding: isMobile ? '12px' : '16px',
        border: '1px solid var(--mac-border)',
        borderRadius: isMobile ? '8px' : '12px',
        fontSize: isMobile ? '16px' : '16px',
        fontFamily: 'inherit',
        resize: 'vertical',
        minHeight: isMobile ? '80px' : '100px',
        transition: 'border-color 0.2s ease, box-shadow 0.2s ease',
        outline: 'none',
        ...style
      }}
      onFocus={(e: React.FocusEvent<HTMLElement>) => {
        e.target.style.borderColor = 'var(--mac-accent-blue)';
        e.target.style.boxShadow = '0 0 0 3px rgba(59, 130, 246, 0.1)';
      }}
      onBlur={(e: React.FocusEvent<HTMLElement>) => {
        e.target.style.borderColor = 'var(--mac-border)';
        e.target.style.boxShadow = 'none';
      }} />);


};

// Компонент для кнопок формы
interface FormActionsProps {
  children?: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}

const FormActions = ({
  children,
  className = '',
  style = {}
}: FormActionsProps) => {
  const { isMobile } = useBreakpoint();

  return (
    <div
      className={`form-actions ${className}`}
      style={{
        display: 'flex',
        gap: isMobile ? '12px' : '16px',
        justifyContent: isMobile ? 'stretch' : 'flex-end',
        marginTop: isMobile ? '20px' : '24px',
        ...style
      }}>
      
      {children}
    </div>);

};

// Экспортируем все компоненты
ResponsiveForm.Group = FormGroup;
ResponsiveForm.Input = FormInput;
ResponsiveForm.Select = FormSelect;
ResponsiveForm.Textarea = FormTextarea;
ResponsiveForm.Actions = FormActions;







export default ResponsiveForm;
