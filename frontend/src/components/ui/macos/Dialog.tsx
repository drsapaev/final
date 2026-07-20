// Minimal macOS-style Dialog components to replace MUI Dialog API used in CashierPanel
// Props compatibility: open, onClose, maxWidth, fullWidth, children
import PropTypes from 'prop-types';
import { useTranslation } from '../../../i18n/useTranslation';
import type { ReactNode, CSSProperties, MouseEvent } from 'react';

type DialogMaxWidth = 'xs' | 'sm' | 'md' | 'lg' | 'xl';
type DialogAlign = 'left' | 'center' | 'right';

interface DialogProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'children' | 'style'> {
  open?: boolean;
  onClose?: (e: MouseEvent<HTMLButtonElement>) => void;
  maxWidth?: DialogMaxWidth | string | number;
  fullWidth?: boolean;
  children?: ReactNode;
  style?: CSSProperties;
  overlayStyle?: CSSProperties;
}

interface DialogPartProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'children' | 'style'> {
  children?: ReactNode;
  style?: CSSProperties;
}

interface DialogActionsProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'children' | 'style'> {
  children?: ReactNode;
  style?: CSSProperties;
  align?: DialogAlign;
}

const overlayStyleBase: CSSProperties = {
  position: 'fixed',
  inset: 0,
  background: 'rgba(0,0,0,0.45)',
  backdropFilter: 'var(--mac-blur-light)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 1000
};

const dialogStyleBase: CSSProperties = {
  background: 'var(--mac-bg-primary)',
  color: 'var(--mac-text-primary)',
  borderRadius: '12px',
  boxShadow: 'var(--mac-shadow-xl)',
  border: '1px solid var(--mac-border)',
  width: '100%',
  maxWidth: '720px'
};

const sizeMap: Record<DialogMaxWidth, string> = {
  xs: '360px',
  sm: '480px',
  md: '720px',
  lg: '960px',
  xl: '1200px'
};

const Dialog = ({ open, onClose, maxWidth = 'md', fullWidth = true, children, style = {}, overlayStyle = {}, ...props }: DialogProps) => {
  const { t } = useTranslation();
  void t;
  if (!open) return null;
  const maxW = typeof maxWidth === 'string' ? (sizeMap[maxWidth as DialogMaxWidth] || sizeMap.md) : maxWidth;
  const backdropStyle: CSSProperties = {
    position: 'absolute',
    inset: 0,
    border: 'none',
    margin: 0,
    padding: 0,
    background: 'transparent'
  };

  return (
    <div style={{ ...overlayStyleBase, ...overlayStyle }}>
      <button
        type="button"
        style={backdropStyle}
        onClick={(e) => onClose?.(e)}
        tabIndex={-1}
        aria-label="Закрыть диалог"
      />
      <div
        role="dialog"
        aria-modal="true"
        style={{ ...dialogStyleBase, maxWidth: fullWidth ? maxW : undefined, ...style, position: 'relative', zIndex: 1 } as CSSProperties}
        {...props}>
        {children}
      </div>
    </div>
  );
};

export const DialogTitle = ({ children, style = {}, ...props }: DialogPartProps) => (
  <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--mac-border)', fontSize: '17px', fontWeight: 600, ...style } as CSSProperties} {...props}>
    {children}
  </div>
);

export const DialogContent = ({ children, style = {}, ...props }: DialogPartProps) => (
  <div style={{ padding: '16px 20px', ...style } as CSSProperties} {...props}>
    {children}
  </div>
);

export const DialogActions = ({ children, style = {}, align = 'right', ...props }: DialogActionsProps) => (
  <div style={{ display: 'flex', gap: 8, justifyContent: align === 'left' ? 'flex-start' : align === 'center' ? 'center' : 'flex-end', padding: '12px 20px', borderTop: '1px solid var(--mac-border)', background: 'var(--mac-bg-secondary)', ...style } as CSSProperties} {...props}>
    {children}
  </div>
);

Dialog.propTypes = {
  open: PropTypes.bool,
  onClose: PropTypes.func,
  maxWidth: PropTypes.oneOfType([PropTypes.oneOf(['xs', 'sm', 'md', 'lg', 'xl']), PropTypes.number, PropTypes.string]),
  fullWidth: PropTypes.bool,
  children: PropTypes.node,
  style: PropTypes.object,
  overlayStyle: PropTypes.object
};

DialogTitle.propTypes = {
  children: PropTypes.node,
  style: PropTypes.object
};

DialogContent.propTypes = {
  children: PropTypes.node,
  style: PropTypes.object
};

DialogActions.propTypes = {
  children: PropTypes.node,
  style: PropTypes.object,
  align: PropTypes.oneOf(['left', 'center', 'right'])
};

export default Dialog;
