import { useState, useEffect, useCallback } from 'react';
import { toast } from 'react-toastify';
import { CreditCard, DollarSign, Receipt, Clock, CheckCircle, X } from 'lucide-react';
import PaymentClick from './PaymentClick';
import PaymentPayMe from './PaymentPayMe';
import {
  getPendingInvoices,
  createPaymentInvoice,
  formatUZS,
  normalizePaymentAmount,
  isValidPaymentAmount,
} from '../../api/payments';
import logger from '../../utils/logger';
import './PaymentManager.css';
import PropTypes from 'prop-types';
import { Input } from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';

// UX Audit Stage 3 (Payment issue 8.1):
// Удалён `const API_BASE = '/api/v1'` и `import { tokenManager }` —
// все 3 raw fetch() заменены на централизованный payments API client
// из api/payments.js, который использует axios-interceptor из api/client.js.

const getInvoiceId = (invoice) => invoice?.invoice_id ?? invoice?.id ?? null;

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

function getInvoiceStatusLabel(status, t) {
  const key = INVOICE_STATUS_KEYS[status];
  return key ? t(key) : status;
}

const PaymentManager = ({
  isOpen,
  onClose,
  invoiceId = null,
  initialAmount = null,
  patientInfo = null
}) => {
  const { t } = useTranslation();
  // Состояние компонента
  const [selectedProvider, setSelectedProvider] = useState('click');
  const [paymentAmount, setPaymentAmount] = useState(initialAmount || 0);
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(false);
  const [createdInvoiceId, setCreatedInvoiceId] = useState(invoiceId);

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
      toast.error(error?.message || t('payment.pay_mgr_error_loading'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      void loadPendingInvoices();
    }
  }, [isOpen, loadPendingInvoices]);

  // UX Audit Stage 3 (Payment issue 8.2):
  // ESC-close для модального окна.
  // Раньше модалка закрывалась только по кнопке «✕».
  useEffect(() => {
    if (!isOpen) return undefined;

    const handleEscape = (event) => {
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
        patient_info: patientInfo,
      });
      setCreatedInvoiceId(result.invoice_id);

      // Открываем соответствующий диалог оплаты
      if (selectedProvider === 'click') {
        setShowClickPayment(true);
      } else if (selectedProvider === 'payme') {
        setShowPayMePayment(true);
      }

      toast.success(t('payment.pay_mgr_invoice_created'));
    } catch (error) {
      logger.error('Ошибка создания счета:', error);
      toast.error(t('payment.pay_mgr_invoice_create_error', { error: error?.message || t('payment.unknown_error') }));
    } finally {
      setLoading(false);
    }
  };

  // Инициация оплаты существующего счета
  const payExistingInvoice = (invoice) => {
    setCreatedInvoiceId(getInvoiceId(invoice));
    setPaymentAmount(invoice.amount);

    if (invoice.provider === 'click') {
      setShowClickPayment(true);
    } else if (invoice.provider === 'payme') {
      setShowPayMePayment(true);
    }
  };

  // Обработчики успешной оплаты
  const handlePaymentSuccess = (paymentData) => {
    toast.success(t('payment.pay_mgr_payment_success'));
    setShowClickPayment(false);
    setShowPayMePayment(false);
    loadPendingInvoices(); // Обновляем список счетов

    // Уведомляем родительский компонент
    if (onClose) {
      onClose({ success: true, paymentData });
    }
  };

  const handlePaymentError = (error) => {
    toast.error(t('payment.pay_mgr_payment_error', { error: error?.message || t('payment.unknown_error') }));
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
  const handleOverlayClick = (event) => {
    // Если клик был именно по overlay, а не по дочернему элементу
    if (event.target === event.currentTarget && !showClickPayment && !showPayMePayment) {
      if (onClose) onClose({ success: false });
    }
  };

  // UX Audit Stage 3 (Payment issue 8.2):
  // Нормализация ввода суммы через normalizePaymentAmount.
  // Раньше было `Number(e.target.value)` — давало NaN при пустом/нечисловом вводе.
  const handleAmountChange = (event) => {
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

          <div className="payment-manager-content">
            {/* Создание новой оплаты */}
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
                    <label className="radio-option">
                      <input
                        type="radio"
                        name="provider"
                        value="click"
                        aria-label={t('payment.pay_mgr_provider_click_aria')}
                        checked={selectedProvider === 'click'}
                        onChange={(e) => setSelectedProvider(e.target.value)}
                      />
                      <span>Click</span>
                    </label>

                    <label className="radio-option">
                      <input
                        type="radio"
                        name="provider"
                        value="payme"
                        aria-label={t('payment.pay_mgr_provider_payme_aria')}
                        checked={selectedProvider === 'payme'}
                        onChange={(e) => setSelectedProvider(e.target.value)}
                      />
                      <span>PayMe</span>
                    </label>
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
                  disabled={loading || !isValidPaymentAmount(paymentAmount)}
                  type="button"
                >
                  {loading ? t('payment.pay_mgr_creating') : t('payment.pay_mgr_create_btn')}
                </button>
              </div>
            </div>

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
                  {invoices.map((invoice) => (
                    <div key={getInvoiceId(invoice)} className="invoice-item">
                      <div className="invoice-info">
                        {/* UX Audit Stage 3 (Payment issue 8.2):
                            Заменён toLocaleString() без локали на formatUZS() с ru-RU. */}
                        <div className="invoice-amount">
                          {formatUZS(invoice.amount)}
                        </div>
                        <div className="invoice-details">
                          <span className="invoice-id">№{getInvoiceId(invoice)}</span>
                          <span className="invoice-provider">{invoice.provider}</span>
                          {/* UX Audit Stage 3: локализация статуса */}
                          <span className="invoice-status">
                            {getInvoiceStatusLabel(invoice.status, t)}
                          </span>
                        </div>
                        {invoice.description && (
                          <div className="invoice-description">
                            {invoice.description}
                          </div>
                        )}
                      </div>

                      <button
                        className="pay-invoice-btn"
                        onClick={() => payExistingInvoice(invoice)}
                        disabled={loading}
                        type="button"
                      >
                        {t('payment.pay_mgr_pay_btn')}
                      </button>
                    </div>
                  ))}
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
        invoiceId={createdInvoiceId}
        totalAmount={paymentAmount}
        currency="UZS"
        onSuccess={handlePaymentSuccess}
        onError={handlePaymentError}
      />

      <PaymentPayMe
        isOpen={showPayMePayment}
        onClose={handlePaymentClose}
        invoiceId={createdInvoiceId}
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
PaymentManager.propTypes = {
  initialAmount: PropTypes.number,
  invoiceId: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  isOpen: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  patientInfo: PropTypes.shape({
    fio: PropTypes.string,
    phone: PropTypes.string,
  }),
};

export default PaymentManager;
