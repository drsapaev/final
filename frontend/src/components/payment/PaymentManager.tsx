
import { useState, useEffect, useCallback, useRef } from 'react';
import { toast } from 'react-toastify';
import { CreditCard, Receipt, Clock, CheckCircle, X } from 'lucide-react';
import PaymentClick from './PaymentClick';
import PaymentPayMe from './PaymentPayMe';
// ADR-0015: use usePaymentsApi hook instead of importing api/payments directly.
import { usePaymentsApi } from '../../hooks/usePaymentsApi';
import type { Invoice, PaymentInvoiceAction } from '../../types/domain/billing';
import logger from '../../utils/logger';
import './PaymentManager.css';
import { useTranslation } from '../../i18n/useTranslation';

interface PaymentManagerProps {
  isOpen: boolean;
  onClose?: (result?: { success?: boolean; paymentData?: unknown }) => void;
  invoiceId?: string | number | null;
  initialAmount?: number | null;
}

// UX Audit Stage 3 (Payment issue 8.1):
// Удалён `const API_BASE = '/api/v1'` и `import { tokenManager }` —
// все 3 raw fetch() заменены на централизованный payments API client
// из api/payments.js, который использует axios-interceptor из api/client.js.

const getInvoiceId = (invoice: Invoice | null | undefined): string | number | null =>
  (invoice?.invoice_id as string | number | undefined) ?? invoice?.id ?? null;

const getProviderLabel = (provider: string): string => {
  const code = provider;
  if (code.toLowerCase() === 'payme') return 'PayMe';
  if (code.toLowerCase() === 'click') return 'Click';
  if (code.toLowerCase() === 'kaspi') return 'Kaspi';
  return provider;
};

const getOnlinePaymentActions = (invoice: Invoice): PaymentInvoiceAction[] =>
  (invoice.available_actions ?? []).filter((action) => {
    const provider = action.provider.trim().toLowerCase();
    return action.action === 'start_online_payment' && ['click', 'payme'].includes(provider);
  });

const ONLINE_PAYMENT_BLOCK_REASON_KEYS: Record<string, string> = {
  invoice_not_pending: 'payment.pay_mgr_block_refresh',
  invoice_settled: 'payment.pay_mgr_block_refresh',
  invoice_not_linked: 'payment.pay_mgr_block_support',
  invoice_allocation_mismatch: 'payment.pay_mgr_block_support',
  invoice_amount_mismatch: 'payment.pay_mgr_block_support',
  invoice_payment_in_progress: 'payment.pay_mgr_block_in_progress',
  role_not_allowed: 'payment.pay_mgr_block_role',
  partial_online_payment_not_supported: 'payment.pay_mgr_block_partial',
};

// UX Audit Stage 3 (Payment issue 8.2):
// Локализация статусов счетов для русского UI.
// Раньше отображались английские «pending», «paid», «failed».
// i18n: keys are translated at call time via getInvoiceStatusLabel(status, t).
const INVOICE_STATUS_KEYS = {
  pending: 'payment.pay_mgr_status_pending',
  paid: 'payment.pay_mgr_status_paid',
  failed: 'payment.pay_mgr_status_failed',
  cancelled: 'payment.pay_mgr_status_cancelled',
  expired: 'payment.pay_mgr_status_expired',
};

function getInvoiceStatusLabel(status: string | undefined, t: (key: string, options?: Record<string, unknown>) => string): string {
  if (!status) return '';
  const key = INVOICE_STATUS_KEYS[status as keyof typeof INVOICE_STATUS_KEYS];
  return key ? t(key) : status;
}

const PaymentManager = ({
  isOpen,
  onClose,
  invoiceId = null,
  initialAmount = null
}: PaymentManagerProps) => {
  const { t: rawT } = useTranslation(); const t = rawT;
  const tRef = useRef(t);
  tRef.current = t;
  // ADR-0015: payments API accessed via hook.
  const {
    getPendingInvoices,
    formatUZS,
  } = usePaymentsApi();
  // Состояние компонента
  const [paymentAmount, setPaymentAmount] = useState(initialAmount || 0);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(false);
  const [createdInvoiceId, setCreatedInvoiceId] = useState<string | number | null>(invoiceId);

  // Состояние диалогов оплаты
  const [showClickPayment, setShowClickPayment] = useState(false);
  const [showPayMePayment, setShowPayMePayment] = useState(false);

  // UX Audit Stage 3 (Payment issue 8.2):
  // Унифицированное состояние активного провайдера вместо двух булевых.
  // Раньше было showClickPayment + showPayMePayment — два state для одной цели.
  // Оставлены для backward-compat с PaymentClick/PaymentPayMe компонентами.
  // const [activeProvider, setActiveProvider] = useState(null);

  // Загрузка списка неоплаченных счетов
  // UX Audit Stage 3 (Payment issue 8.1):
  // Заменён raw fetch() на getPendingInvoices() из api/payments.
  const loadPendingInvoices = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getPendingInvoices();
      setInvoices(Array.isArray(data) ? data : []);
    } catch (error) {
      logger.error('Ошибка загрузки счетов:', error);
      toast.error(
        (error as { message?: string })?.message ||
          tRef.current('payment.pay_mgr_error_loading')
      );
    } finally {
      setLoading(false);
    }
  }, [getPendingInvoices]);

  useEffect(() => {
    if (isOpen) {
      void loadPendingInvoices();
    }
  }, [isOpen, loadPendingInvoices]);

  const getProviderBlockReason = (invoice: Invoice): string => {
    if (invoice.online_payment_block_reason === 'provider_unavailable') {
      if (!invoice.provider) {
        return t('payment.pay_mgr_no_providers');
      }
      return t('payment.pay_mgr_provider_unavailable', {
        provider: getProviderLabel(invoice.provider),
      });
    }

    const messageKey = invoice.online_payment_block_reason
      ? ONLINE_PAYMENT_BLOCK_REASON_KEYS[invoice.online_payment_block_reason]
      : undefined;
    return t(messageKey || 'payment.pay_mgr_block_unknown');
  };

  // UX Audit Stage 3 (Payment issue 8.2):
  // ESC-close для модального окна.
  // Раньше модалка закрывалась только по кнопке «✕».
  useEffect(() => {
    if (!isOpen) return undefined;

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !showClickPayment && !showPayMePayment) {
        // Не закрываем основной модал, если открыт провайдер-диалог
        if (onClose) onClose({ success: false });
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isOpen, showClickPayment, showPayMePayment, onClose]);

  // Инициация оплаты существующего счета
  const payExistingInvoice = (invoice: Invoice, action: PaymentInvoiceAction) => {
    const providerCode = action.provider.trim().toLowerCase();
    setCreatedInvoiceId(getInvoiceId(invoice));
    setPaymentAmount(invoice.remaining_amount ?? invoice.amount ?? 0);

    if (providerCode === 'click') {
      setShowClickPayment(true);
    } else if (providerCode === 'payme') {
      setShowPayMePayment(true);
    } else {
      toast.error(getProviderBlockReason(invoice));
    }
  };

  // Обработчики успешной оплаты
  const handlePaymentSuccess = (paymentData: unknown) => {
    toast.success(t('payment.pay_mgr_payment_success'));
    setShowClickPayment(false);
    setShowPayMePayment(false);
    loadPendingInvoices(); // Обновляем список счетов

    // Уведомляем родительский компонент
    if (onClose) {
      onClose({ success: true, paymentData });
    }
  };

  const handlePaymentError = (error: unknown) => {
    const errMsg = (error as { message?: string })?.message || t('payment.unknown_error');
    toast.error(t('payment.pay_mgr_payment_error', { error: errMsg }));
    setShowClickPayment(false);
    setShowPayMePayment(false);
  };

  const handlePaymentClose = () => {
    setShowClickPayment(false);
    setShowPayMePayment(false);
  };

  // UX Audit Stage 3 (Payment issue 8.2):
  // Click-outside для модального окна.
  // Клик по overlay (но не по содержимому) закрывает модал.
  const handleOverlayClick = (event: React.MouseEvent<HTMLDivElement>) => {
    // Если клик был именно по overlay, а не по дочернему элементу
    if (event.target === event.currentTarget && !showClickPayment && !showPayMePayment) {
      if (onClose) onClose({ success: false });
    }
  };

  if (!isOpen) return null;

  return (
    <>
      <div
        className="payment-manager-overlay"
        onClick={handleOverlayClick}
        role="presentation"
      >
        <div
          className="payment-manager-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="payment-manager-title"
        >
          <div className="payment-manager-header">
            <h2 id="payment-manager-title">
              <CreditCard size={24} aria-hidden="true" />
              {t('payment.pay_mgr_module_title')}
            </h2>
            <button
              className="close-btn"
              onClick={() => onClose && onClose({ success: false })}
              aria-label={t('payment.pay_mgr_close_aria')}
              title={t('payment.pay_mgr_close_title')}
              type="button"
            >
              <X size={20} aria-hidden="true" />
            </button>
          </div>

          <div className="payment-manager-content payment-manager-content--settlement-only">
            {/* Список неоплаченных счетов */}
            <div className="invoices-section">
              <h3>
                <Receipt size={20} aria-hidden="true" />
                {t('payment.pay_mgr_unpaid_invoices')}
              </h3>

              {loading ? (
                <div className="loading-state">
                  <Clock size={20} aria-hidden="true" />
                  {t('payment.pay_mgr_loading')}
                </div>
              ) : invoices.length === 0 ? (
                <div className="empty-state">
                  <CheckCircle size={24} aria-hidden="true" />
                  {t('payment.pay_mgr_no_unpaid')}
                </div>
              ) : (
                <div className="invoices-list">
                  {invoices.map((invoice) => {
                    const invoiceIdValue = getInvoiceId(invoice);
                    const paymentActions = getOnlinePaymentActions(invoice);
                    const providerLabels = paymentActions
                      .map((action) => getProviderLabel(action.provider))
                      .join(', ');

                    return (
                      <div key={invoiceIdValue} className="invoice-item">
                        <div className="invoice-info">
                          {/* UX Audit Stage 3 (Payment issue 8.2):
                              Заменён toLocaleString() без локали на formatUZS() с ru-RU. */}
                          <div className="invoice-amount">
                            {formatUZS(invoice.remaining_amount ?? invoice.amount ?? 0)}
                          </div>
                          <div className="invoice-details">
                            <span className="invoice-id">№{String(invoiceIdValue ?? '')}</span>
                            <span className="invoice-provider">
                              {String(invoice.provider || providerLabels)}
                            </span>
                            {/* UX Audit Stage 3: локализация статуса */}
                            <span className="invoice-status">
                              {String(getInvoiceStatusLabel(invoice.status as string | undefined, t))}
                            </span>
                          </div>
                          {Boolean(invoice.description) && (
                            <div className="invoice-description">
                              {String(invoice.description)}
                            </div>
                          )}
                          {paymentActions.length === 0 && (
                            <div className="invoice-provider-warning">
                              {getProviderBlockReason(invoice)}
                            </div>
                          )}
                        </div>

                        {paymentActions.length === 0 ? (
                          <button
                            className="pay-invoice-btn"
                            disabled
                            aria-label={getProviderBlockReason(invoice)}
                            type="button"
                          >
                            {t('payment.pay_mgr_pay_btn')}
                          </button>
                        ) : paymentActions.map((action) => (
                          <button
                            key={`${action.action}:${action.provider}`}
                            className="pay-invoice-btn"
                            onClick={() => payExistingInvoice(invoice, action)}
                            disabled={loading}
                            aria-label={t('payment.pay_mgr_provider_aria', {
                              provider: getProviderLabel(action.provider),
                            })}
                            type="button"
                          >
                            {t('payment.pay_mgr_pay_btn')} · {getProviderLabel(action.provider)}
                          </button>
                        ))}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Диалоги оплаты */}
      <PaymentClick
        isOpen={showClickPayment}
        onClose={handlePaymentClose}
        invoiceId={createdInvoiceId as string | number}
        totalAmount={paymentAmount}
        currency="UZS"
        onSuccess={handlePaymentSuccess}
        onError={handlePaymentError}
      />

      <PaymentPayMe
        isOpen={showPayMePayment}
        onClose={handlePaymentClose}
        invoiceId={createdInvoiceId as string | number}
        totalAmount={paymentAmount}
        currency="UZS"
        onSuccess={handlePaymentSuccess}
        onError={handlePaymentError}
      />
    </>
  );
};

// UX Audit Stage 3 (Payment issue 8.4):
// Почищены propTypes-артефакты из codemod-sweep.

export default PaymentManager;
