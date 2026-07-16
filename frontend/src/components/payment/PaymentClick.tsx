// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import PropTypes from 'prop-types';
import PaymentProviderDialog from './PaymentProviderDialog';
import './PaymentClick.css';

/**
 * PaymentClick — thin wrapper around PaymentProviderDialog.
 *
 * HIGH #5 fix: this file previously duplicated ~560 lines that were 99%
 * identical to PaymentPayMe.jsx. The shared logic now lives in
 * PaymentProviderDialog.jsx. The wrapper preserves the public API
 * (same props, same CSS class) so existing call sites in
 * PaymentManager.jsx and the contract test keep working.
 *
 * MEDIUM #10 fix: removed `void useState(null)` artifact (the file no
 * longer has any useState — rules-of-hooks can no longer break).
 */
const PaymentClick = ({
  isOpen,
  onClose,
  invoiceId,
  totalAmount,
  currency = 'UZS',
  onSuccess,
  onError
}) => (
  <PaymentProviderDialog
    isOpen={isOpen}
    onClose={onClose}
    invoiceId={invoiceId}
    totalAmount={totalAmount}
    currency={currency}
    provider="click"
    providerLabel="Click"
    cssClassName="payment-click-dialog"
    onSuccess={onSuccess}
    onError={onError} />
);

PaymentClick.propTypes = {
  ...(PaymentClick.propTypes || {}),
  currency: PropTypes.any,
  invoiceId: PropTypes.any,
  isOpen: PropTypes.any,
  onClose: PropTypes.any,
  onError: PropTypes.any,
  onSuccess: PropTypes.any,
  totalAmount: PropTypes.any,
};

export default PaymentClick;
