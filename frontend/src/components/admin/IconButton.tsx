import { Button, Tooltip } from '../ui/macos';
import type { ReactNode, CSSProperties, MouseEvent } from 'react';

interface IconButtonProps {
  label: string;
  tone?: 'default' | 'danger';
  onClick: (e: MouseEvent<HTMLButtonElement>) => void;
  children: ReactNode;
  disabled?: boolean;
}

const IconButton = ({ label, tone = 'default', onClick, children, disabled }: IconButtonProps) => (
  <Tooltip content={label}>
    <span style={{ display: 'inline-block' }}>
      <Button
        type="button"
        variant="ghost"
        size="small"
        onClick={onClick}
        aria-label={label}
        disabled={disabled}
        className="admin-w-32-h-32-p-0-radius-var-mac-radius-sm-col-dyn"
        style={{ '--admin-col0': tone === 'danger' ? 'var(--mac-error)' : 'var(--mac-text-secondary)' } as CSSProperties}
      >
        {children}
      </Button>
    </span>
  </Tooltip>
);

export default IconButton;
