import PropTypes from 'prop-types';
import { RefreshCw } from 'lucide-react';
import {
  Badge, Button,
} from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';
import type { CSSProperties, ComponentType } from 'react';

const summaryBarStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'flex-end',
  gap: 'var(--mac-spacing-2)',
  flexWrap: 'wrap',
  minWidth: 0
};

const refreshButtonStyle: CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 'var(--mac-spacing-2)',
  flexShrink: 0
};

interface SummaryItem {
  key: string;
  label: string;
  value: string | number;
  variant: string;
}

interface AppointmentSummaryBarProps {
  ariaLabel: string;
  items: SummaryItem[];
  onRefresh: () => void;
  refreshDisabled?: boolean;
  refreshLabel?: string;
  BadgeComponent?: ComponentType<React.HTMLAttributes<HTMLSpanElement> & { variant?: string; children?: React.ReactNode }>;
  ButtonComponent?: ComponentType<React.ButtonHTMLAttributes<HTMLButtonElement> & { children?: React.ReactNode }>;
  buttonProps?: { style?: CSSProperties; [key: string]: unknown };
}

export default function AppointmentSummaryBar({
  ariaLabel,
  items,
  onRefresh,
  refreshDisabled = false,
  refreshLabel = 'Обновить',
  BadgeComponent = Badge,
  ButtonComponent = Button,
  buttonProps = {}
}: AppointmentSummaryBarProps) {
  const { t: rawT } = useTranslation();
  void rawT;
  return (
    <div style={summaryBarStyle} role="list" aria-label={ariaLabel}>
      {items.map((item) => (
        <BadgeComponent
          key={item.key}
          role="listitem"
          variant={item.variant}
          aria-label={`${item.label}: ${item.value}`}
        >
          {item.label}: {item.value}
        </BadgeComponent>
      ))}

      <ButtonComponent
        {...buttonProps}
        onClick={onRefresh}
        disabled={refreshDisabled}
        style={{
          ...refreshButtonStyle,
          ...buttonProps.style
        }}
      >
        <RefreshCw size={16} />
        {refreshLabel}
      </ButtonComponent>
    </div>
  );
}

AppointmentSummaryBar.propTypes = {
  ariaLabel: PropTypes.string.isRequired,
  BadgeComponent: PropTypes.elementType,
  ButtonComponent: PropTypes.elementType,
  buttonProps: PropTypes.object,
  items: PropTypes.arrayOf(PropTypes.shape({
    key: PropTypes.string.isRequired,
    label: PropTypes.string.isRequired,
    value: PropTypes.oneOfType([PropTypes.number, PropTypes.string]).isRequired,
    variant: PropTypes.string.isRequired
  })).isRequired,
  onRefresh: PropTypes.func.isRequired,
  refreshDisabled: PropTypes.bool,
  refreshLabel: PropTypes.string
};
