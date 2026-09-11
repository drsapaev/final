
import { useState, useEffect, useCallback, useRef } from 'react';
import { toast } from 'react-toastify';
import { CreditCard, DollarSign, Receipt, Clock, CheckCircle, X } from 'lucide-react';
import PaymentClick from './PaymentClick';
import PaymentPayMe from './PaymentPayMe';
// ADR-0015: use usePaymentsApi hook instead of importing api/payments directly.
import { usePaymentsApi, type PaymentProviderInfoDto } from '../../hooks/usePaymentsApi';
import type { Invoice } from '../../types/domain/billing';
import logger from '../../utils/logger';
import './PaymentManager.css';
import { Input } from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';

interface PatientInfo {
  id?: number | string;
  patient_id?: number | string;
  fio?: string;
  phone?: string;
  [key: string]: unknown;
}

interface PaymentManagerProps {
  isOpen: boolean;
  onClose?: (result?: { success?: boolean; paymentData?: unknown }) => void;
  invoiceId?: string | number | null;
  initialAmount?: number | null;
  patientInfo?: PatientInfo | null;
}

// UX Audit Stage 3 (Payment issue 8.1):
// Удалён `const API_BASE = '/api/v1'` и `import { tokenManager }` —
// все 3 raw fetch() заменены на централизованный payments API client
// из api/payments.js, который использует axios-interceptor из api/client.js.

const getInvoiceId = (invoice: Invoice | null | undefined): string | number | null =>
  (invoice?.invoice_id as string | number | undefined) ?? invoice?.id ?? null;

const getPatientId = (patientInfo: PatientInfo | null): number | null => {
  const value = patientInfo?.patient_id ?? patientInfo?.id;
  const patientId = Number(value);
  return Number.isInteger(patientId) && patientId > 0 ? patientId : null;
};

const getProviderLabel = (provider: PaymentProviderInfoDto | string): string => {
  const code = typeof provider === 'string' ? provider : provider.code;
  if (code.toLowerCase() === 'payme') return 'PayMe';
  if (code.toLowerCase() === 'click') return 'Click';
  if (code.toLowerCase() === 'kaspi') return 'Kaspi';
  return typeof provider === 'string' ? provider : provider.name;
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
  initialAmount = null,
  patientInfo = null
}: PaymentManagerProps) => {
  const { t: rawT } = useTranslation(); const t = rawT;
  const tRef = useRef(t);
  tRef.current = t;
  // ADR-0015: payments API accessed via hook.
  const {
    getPendingInvoices,
    createPaymentInvoice,
    getPaymentProviders,
    formatUZS,
    normalizePaymentAmount,
    isValidPaymentAmount,
  } = usePaymentsApi();
  // Состояние компонента
  const [selectedProvider, setSelectedProvider] = useState('');
  const [invoiceProviders, setInvoiceProviders] = useState<PaymentProviderInfoDto[]>([]);
  const [providersLoading, setProvidersLoading] = useState(false);
  const [providersLoadFailed, setProvidersLoadFailed] = useState(false);
  const [paymentAmount, setPaymentAmount] = useState(initialAmount || 0);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(false);
  const [createdInvoiceId, setCreatedInvoiceId] = useState<string | number | null>(invoiceId);
  const patientId = getPatientId(patientInfo);

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

  const loadInvoiceProviders = useCallback(async () => {
    try {
      setProvidersLoading(true);
      setProvidersLoadFailed(false);
      const providers = await getPaymentProviders();
      const supportedProviders = providers.filter(
        (provider) =>
          provider.is_active &&
          provider.supported_currencies.includes('UZS') &&
          provider.features?.registrar_invoice_payment === true
      );
      setInvoiceProviders(supportedProviders);
      setSelectedProvider((currentProvider) =>
        supportedProviders.some((provider) => provider.code === currentProvider)
          ? currentProvider
          : supportedProviders[0]?.code ?? ''
      );
    } catch (error) {
      logger.error('Ошибка загрузки платёжных провайдеров:', error);
      setInvoiceProviders([]);
      setSelectedProvider('');
      setProvidersLoadFailed(true);
      toast.error(tRef.current('payment.pay_mgr_provider_load_error'));
    } finally {
      setProvidersLoading(false);
    }
  }, [getPaymentProviders]);

  useEffect(() => {
    if (isOpen) {
      void loadPendingInvoices();
      void loadInvoiceProviders();
    }
  }, [isOpen, loadPendingInvoices, loadInvoiceProviders]);

  const getProviderBlockReason = (providerCode: string): string =>
    providersLoadFailed
      ? t('payment.pay_mgr_provider_load_error')
      : t('payment.pay_mgr_provider_unavailable', {
          provider: getProviderLabel(providerCode || '—'),
        });

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

  // Создание нового счета для оплаты
  // UX Audit Stage 3 (Payment issue 8.1 + 8.2):
  // - Заменён raw fetch() на createPaymentInvoice() из api/payments.
  // - Добавлена NaN-валидация через isValidPaymentAmount.
  const handleCreateInvoice = async () => {
    if (patientId === null) {
      toast.error(t('payment.pay_mgr_patient_required'));
      return;
    }

    // UX Audit Stage 3 (Payment issue 8.2):
    // Раньше было `if (!paymentAmount || paymentAmount <= 0)` — пропускало NaN.
    // Теперь используем isValidPaymentAmount с проверкой Number.isFinite.
    if (!isValidPaymentAmount(paymentAmount)) {
      toast.error(t('payment.pay_mgr_invalid_amount'));
      return;
    }

    try {
      setLoading(true);
      const result = await createPaymentInvoice({
        amount: paymentAmount,
        currency: 'UZS',
        provider: selectedProvider,
        // UX Audit: защищаемся от patientInfo без fio (было «Оплата - undefined»)
        description: patientInfo?.fio
          ? t('payment.pay_mgr_description_with_patient', { patient: patientInfo.fio })
          : t('payment.pay_mgr_description'),
        patient_info: { patient_id: patientId },
      });
      setCreatedInvoiceId(result.invoice_id as string | number);

      // Открываем соответствующий диалог оплаты
      if (selectedProvider === 'click') {
        setShowClickPayment(true);
      } else if (selectedProvider === 'payme') {
        setShowPayMePayment(true);
      }

      toast.success(t('payment.pay_mgr_invoice_created'));
    } catch (error) {
      logger.error('Ошибка создания счета:', error);
      toast.error(t('payment.pay_mgr_invoice_create_error', { error: (error as { message?: string })?.message || t('payment.unknown_error') }));
    } finally {
      setLoading(false);
    }
  };

  // Инициация оплаты существующего счета
  const payExistingInvoice = (invoice: Invoice) => {
    const providerCode = String(invoice.provider ?? '').toLowerCase();
    const providerSupported = invoiceProviders.some(
      (provider) => provider.code.toLowerCase() === providerCode
    );
    if (!providerSupported) {
      toast.error(getProviderBlockReason(providerCode));
      return;
    }

    setCreatedInvoiceId(getInvoiceId(invoice));
    setPaymentAmount(invoice.amount ?? 0);

    if (providerCode === 'click') {
      setShowClickPayment(true);
    } else if (providerCode === 'payme') {
      setShowPayMePayment(true);
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

  // UX Audit Stage 3 (Payment issue 8.2):
  // Нормализация ввода суммы через normalizePaymentAmount.
  // Раньше было `Number(e.target.value)` — давало NaN при пустом/нечисловом вводе.
  const handleAmountChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setPaymentAmount(normalizePaymentAmount(event.target.value));
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

          <div
            className={`payment-manager-content${patientId === null ? ' payment-manager-content--settlement-only' : ''}`}
          >
            {/* Создание новой оплаты */}
            {patientId !== null && (
            <div className="payment-section">
              <h3>
                <DollarSign size={20} aria-hidden="true" />
                {t('payment.pay_mgr_new_payment')}
              </h3>

              <div className="payment-form">
                <div className="form-row">
                  <label htmlFor="payment-manager-amount">{t('payment.pay_mgr_amount_label')}</label>
                  <Input
                    id="payment-manager-amount"
                    type="number"
                    aria-label={t('payment.pay_mgr_amount_aria')}
                    value={paymentAmount || ''}
                    onChange={handleAmountChange}
                    placeholder={t('payment.pay_mgr_amount_placeholder')}
                    min="1"
                  />
                </div>

                <div className="form-row">
                  <label>{t('payment.pay_mgr_provider_label')}</label>
                  <div className="provider-options">
                    {providersLoading ? (
                      <span className="provider-state" role="status">
                        {t('payment.pay_mgr_loading_providers')}
                      </span>
                    ) : providersLoadFailed ? (
                      <span className="provider-state" role="status">
                        {t('payment.pay_mgr_provider_load_error')}
                      </span>
                    ) : invoiceProviders.length === 0 ? (
                      <span className="provider-state" role="status">
                        {t('payment.pay_mgr_no_providers')}
                      </span>
                    ) : invoiceProviders.map((provider) => (
                      <label className="radio-option" key={provider.code}>
                        <input
                          type="radio"
                          name="provider"
                          value={provider.code}
                          aria-label={t('payment.pay_mgr_provider_aria', {
                            provider: getProviderLabel(provider),
                          })}
                          checked={selectedProvider === provider.code}
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSelectedProvider(e.target.value)}
                        />
                        <span>{getProviderLabel(provider)}</span>
                      </label>
                    ))}
                  </div>
                </div>

                {patientInfo && (
                  <div className="patient-info">
                    {/* UX Audit Stage 3: semantic <dl> вместо <p><strong> */}
                    <dl>
                      <dt>{t('payment.pay_mgr_patient')}</dt>
                      <dd>{patientInfo.fio || '—'}</dd>
                      {patientInfo.phone && (
                        <>
                          <dt>{t('payment.pay_mgr_phone')}</dt>
                          <dd>{patientInfo.phone}</dd>
                        </>
                      )}
                    </dl>
                  </div>
                )}

                <button
                  className="create-payment-btn"
                  onClick={handleCreateInvoice}
                  disabled={loading || providersLoading || !selectedProvider || !isValidPaymentAmount(paymentAmount)}
                  type="button"
                >
                  {loading ? t('payment.pay_mgr_creating') : t('payment.pay_mgr_create_btn')}
                </button>
              </div>
            </div>
            )}

            {/* Список неоплаченных счетов */}
            <div className="invoices-section">
              <h3>
                <Receipt size={20} aria-hidden="true" />
                {t('payment.pay_mgr_unpaid_invoices')}
              </h3>

              {patientId === null && (
                <div className="payment-context-note" role="note">
                  {t('payment.pay_mgr_patient_required_hint')}
                </div>
              )}

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
                    const providerCode = String(invoice.provider ?? '').toLowerCase();
                    const providerSupported = invoiceProviders.some(
                      (provider) => provider.code.toLowerCase() === providerCode
                    );

                    return (
                      <div key={invoiceIdValue} className="invoice-item">
                        <div className="invoice-info">
                          {/* UX Audit Stage 3 (Payment issue 8.2):
                              Заменён toLocaleString() без локали на formatUZS() с ru-RU. */}
                          <div className="invoice-amount">
                            {formatUZS(invoice.amount ?? 0)}
                          </div>
                          <div className="invoice-details">
                            <span className="invoice-id">№{String(invoiceIdValue ?? '')}</span>
                            <span className="invoice-provider">{String(invoice.provider ?? '')}</span>
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
                          {!providersLoading && !providerSupported && (
                            <div className="invoice-provider-warning">
                              {getProviderBlockReason(providerCode)}
                            </div>
                          )}
                        </div>

                        <button
                          className="pay-invoice-btn"
                          onClick={() => payExistingInvoice(invoice)}
                          disabled={loading || providersLoading || !providerSupported}
                          aria-label={providerSupported
                            ? t('payment.pay_mgr_pay_btn')
                            : getProviderBlockReason(providerCode)}
                          type="button"
                        >
                          {t('payment.pay_mgr_pay_btn')}
                        </button>
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
