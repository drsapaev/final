// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import PropTypes from 'prop-types';
import { Button } from '../ui/macos';

/**
 * IconButton — shared icon-only button for admin tables (P2 dedup, Sprint 4).
 *
 * Replaces 3 byte-identical copies that lived in AdminAppointments,
 * AdminDoctors, and AdminPatients. Keeps the same className/style/props
 * so behavior is unchanged.
 */
const IconButton = ({ label, tone = 'default', onClick, children }) => (
  <Button
    type="button"
    variant="ghost"
    size="small"
    onClick={onClick}
    aria-label={label}
    title={label}
    className="admin-w-32-h-32-p-0-radius-var-mac-radius-sm-col-dyn"
    style={{ '--admin-col0': tone === 'danger' ? 'var(--mac-error)' : 'var(--mac-text-secondary)' }}
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
