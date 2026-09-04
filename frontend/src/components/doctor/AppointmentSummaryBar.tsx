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
  // PR-UI-05: Button is ForwardRefExoticComponent
  ButtonComponent?: React.ComponentType<any>;
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
  // AXE-EXP-5: the refresh Button used to be a DIRECT child of the
  // role="list" container — a list may only own listitem children
  // (axe aria-required-children, flagged on doctor-cardiology and
  // doctor-dermatology). The list now owns only the badges and uses
  // display:contents, so the badges keep participating in the outer
  // flex row exactly as before (zero pixel delta) while the Button
  // becomes a list sibling.
  return (
    <div style={summaryBarStyle}>
      <div role="list" aria-label={ariaLabel} style={{ display: 'contents' }}>
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
      </div>

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

