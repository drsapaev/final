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
interface PaymentClickProps {
  isOpen: boolean;
  onClose: () => void;
  invoiceId: string | number;
  totalAmount: number;
  currency?: string;
  onSuccess?: (...args: unknown[]) => void;
  onError?: (...args: unknown[]) => void;
}

const PaymentClick = ({
  isOpen,
  onClose,
  invoiceId,
  totalAmount,
  currency = 'UZS',
  onSuccess,
  onError
}: PaymentClickProps) => (
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


export default PaymentClick;
