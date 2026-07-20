import PropTypes from 'prop-types';
import { Button } from '../ui/macos';
import type { ReactNode, CSSProperties, MouseEvent } from 'react';

interface IconButtonProps {
  label: string;
  tone?: 'default' | 'danger';
  onClick: (e: MouseEvent<HTMLButtonElement>) => void;
  children: ReactNode;
}

const IconButton = ({ label, tone = 'default', onClick, children }: IconButtonProps) => (
  <Button
    type="button"
    variant="ghost"
    size="small"
    onClick={onClick}
    aria-label={label}
    title={label}
    className="admin-w-32-h-32-p-0-radius-var-mac-radius-sm-col-dyn"
    style={{ '--admin-col0': tone === 'danger' ? 'var(--mac-error)' : 'var(--mac-text-secondary)' } as CSSProperties}
  >
    {children}
  </Button>
);

IconButton.propTypes = {
  children: PropTypes.node.isRequired,
  label: PropTypes.string.isRequired,
  onClick: PropTypes.func.isRequired,
  tone: PropTypes.oneOf(['default', 'danger']),
};

export default IconButton;
