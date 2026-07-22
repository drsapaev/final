import { useTranslation } from '../../i18n/useTranslation';
import { useState, useEffect, useRef } from 'react';
import {
  CreditCard,
  ExternalLink,
  CheckCircle,
  XCircle,
  Clock,
  AlertCircle,
  RefreshCw,
  Printer } from
'lucide-react';
import MultipleTicketsPrinter from '../tickets/MultipleTicketsPrinter';
import { useAsyncAction } from '../../hooks/useAsyncAction';
import { api } from '../../api/client';
import ModernDialog from '../dialogs/ModernDialog';
import logger from '../../utils/logger';
import { printPanelTicketInBrowser } from '../../services/panelPrint';
import notify from '../../services/notify';
import PropTypes from 'prop-types';

/**
 * PaymentProviderDialog — unified hosted-payment provider dialog.
 *
 * HIGH #5 fix: PaymentClick.jsx and PaymentPayMe.jsx were 99% identical
 * (1120 duplicated lines, only ~12 lines differed by provider string/labels).
 * This component is the single source of truth; PaymentClick/PaymentPayMe
 * are now thin wrappers that pass `provider="click"|"payme"`.
 *
 * Contract preserved (HostedPaymentProviders.contract.test.jsx):
 *   - Uses authenticated `api` client (not raw fetch) for
 *     /registrar/invoice/init-payment and /registrar/invoice/{id}/status.
 *   - Renders only backend-provided tickets from `data.print_tickets`.
 *
 * MEDIUM #10 fix: removed `void useState(null)` artifact that broke
 * rules-of-hooks if the line was edited.
 */
const PaymentProviderDialog = ({
  isOpen,
  onClose,
  invoiceId,
  totalAmount,
  currency = 'UZS',
  provider, // 'click' | 'payme'
  providerLabel, // 'Click' | 'PayMe' — used in titles, buttons, instructions
  cssClassName, // 'payment-click-dialog' | 'payment-payme-dialog'
  onSuccess,
  onError
}) => {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const { executeAction, loading } = useAsyncAction();

  const [paymentState, setPaymentState] = useState('init'); // init|processing|polling|success|failed
  const [paymentUrl, setPaymentUrl] = useState(null);
  const [, setProviderPaymentId] = useState(null);
  const [error, setError] = useState(null);
  const [pollingAttempts, setPollingAttempts] = useState(0);
  const [printTickets, setPrintTickets] = useState([]);
  const [showTicketPrinter, setShowTicketPrinter] = useState(false);

  const maxPollingAttempts = 60; // 5 минут при интервале 5 сек
  const pollingIntervalMs = 5000; // 5 секунд

  // Refs для управления polling
  const pollingRef = useRef(null);
  const attemptsRef = useRef(0);

  const clearPolling = () => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  };

  const resetState = () => {
    setPaymentState('init');
    setPaymentUrl(null);
    setProviderPaymentId(null);
    setError(null);
    setPollingAttempts(0);
    setPrintTickets([]);
    attemptsRef.current = 0;
  };

  // Очистка при закрытии
  useEffect(() => {
    if (!isOpen) {
      clearPolling();
      resetState();
    }
  }, [isOpen]);

  // Очистка polling при размонтировании
  useEffect(() => {
    return () => clearPolling();
  }, []);

  // ===================== ИНИЦИАЦИЯ ПЛАТЕЖА =====================

  const initPayment = async () => {
    if (!invoiceId) {
      setError(t('payment.pay_dlg_no_invoice_id'));
      return;
    }

    await executeAction(
      async () => {
        const response = await api.post('/registrar/invoice/init-payment', {
          invoice_id: invoiceId,
          provider,
          return_url: `${window.location.origin}/payment/success`,
          cancel_url: `${window.location.origin}/payment/cancel`
        }) as import('axios').AxiosResponse<Record<string, unknown>>;

        const data = response.data;

        if (data.success) {
          setPaymentUrl(String(data.payment_url));
          setProviderPaymentId(data.provider_payment_id);
          setPaymentState('processing');

          // Автоматически открываем ссылку на оплату
          if (String(data.payment_url)) {
            window.open(String(data.payment_url), '_blank');

            // Начинаем polling через 10 секунд
            setTimeout(() => {
              startPolling();
            }, 10000);
          }
        } else {
          throw new Error(String(data.error_message) || t('payment.pay_dlg_create_payment_failed'));
        }

        return data;
      },
      {
        loadingMessage: t('payment.pay_dlg_loading_init'),
        successMessage: t('payment.pay_dlg_success_created'),
        errorMessage: t('payment.pay_dlg_error_create'),
        onError: (err: { message?: string }) => {
          setError(err?.message || '');
          setPaymentState('failed');
        }
      }
    );
  };

  // ===================== POLLING СТАТУСА =====================

  const startPolling = () => {
    setPaymentState('polling');
    attemptsRef.current = 0;

    pollingRef.current = setInterval(async () => {
      attemptsRef.current += 1;
      setPollingAttempts(attemptsRef.current);

      try {
        await checkPaymentStatus();
      } catch (error) {
        logger.error('Polling error:', error);
      }

      // Останавливаем polling после максимального количества попыток
      if (attemptsRef.current >= maxPollingAttempts) {
        clearPolling();
        setPaymentState('failed');
        setError(t('payment.pay_dlg_timeout'));
        notify.error(t('payment.timeout'));
      }
    }, pollingIntervalMs);
  };

  const checkPaymentStatus = async () => {
    const response = (await api.get(`/registrar/invoice/${invoiceId}/status`)) as import('axios').AxiosResponse<Record<string, unknown>>;

    if (response.status >= 200 && response.status < 300) {
      const data = response.data;

      if (data.status === 'paid') {
        clearPolling();
        setPaymentState('success');

        // Получаем данные для печати талонов
        const tickets = Array.isArray(data.print_tickets) ? data.print_tickets : [];
        setPrintTickets(tickets);

        notify.success(t('payment.payment_success'));

        // Показываем принтер талонов если есть талоны для печати
        setShowTicketPrinter(tickets.length > 0);

        if (onSuccess) {
          onSuccess(data);
        }
      } else if (data.status === 'failed' || data.status === 'cancelled') {
        clearPolling();
        setPaymentState('failed');
        setError(data.status === 'failed' ? t('payment.pay_dlg_payment_failed') : t('payment.pay_dlg_payment_cancelled'));

        if (onError) {
          onError(new Error(`Payment ${data.status}`));
        }
      }
      // Если статус pending/processing - продолжаем polling
    } else {
      logger.error('Error checking payment status:', response.statusText);
    }
  };

  // ===================== ПЕЧАТЬ ТАЛОНОВ =====================

  const printTicket = (ticket) => {
    const opened = printPanelTicketInBrowser({
      ...ticket,
      specialty_name: ticket.department || ticket.specialty || ticket.queue_name || t('payment.pay_dlg_queue'),
      source: 'payment',
    });

    if (!opened) {
      logger.warn('Browser popup blocked for payment ticket print', ticket);
    }
    return opened;
  };

  const printAllTickets = () => {
    printTickets.forEach((ticket) => {
      setTimeout(() => printTicket(ticket), 500); // Небольшая задержка между печатью
    });
  };

  // ===================== РУЧНАЯ ПРОВЕРКА =====================

  const manualCheck = async () => {
    await executeAction(
      () => checkPaymentStatus(),
      {
        loadingMessage: t('payment.pay_dlg_loading_check'),
        errorMessage: t('payment.pay_dlg_error_check')
      }
    );
  };

  // ===================== ДЕЙСТВИЯ ДИАЛОГА =====================

  const getActions = () => {
    switch (paymentState) {
      case 'init':
        return [
        {
          label: t('payment.pay_dlg_cancel'),
          onClick: onClose,
          variant: 'secondary'
        },
        {
          label: t('payment.pay_dlg_pay_via', { provider: providerLabel }),
          onClick: initPayment,
          variant: 'primary',
          icon: <CreditCard size={16} />,
          disabled: loading || !invoiceId
        }];


      case 'processing':
        return [
        {
          label: t('payment.pay_dlg_cancel'),
          onClick: onClose,
          variant: 'secondary'
        },
        {
          label: t('payment.pay_dlg_reopen_link'),
          onClick: () => paymentUrl && window.open(paymentUrl, '_blank'),
          variant: 'primary',
          icon: <ExternalLink size={16} />,
          disabled: !paymentUrl
        },
        {
          label: t('payment.pay_dlg_start_tracking'),
          onClick: startPolling,
          variant: 'primary',
          icon: <Clock size={16} />
        }];


      case 'polling':
        return [
        {
          label: t('payment.pay_dlg_stop_tracking'),
          onClick: () => {
            clearPolling();
            setPaymentState('processing');
          },
          variant: 'secondary'
        },
        {
          label: t('payment.pay_dlg_check_now'),
          onClick: manualCheck,
          variant: 'primary',
          icon: <RefreshCw size={16} />,
          disabled: loading
        }];


      case 'success':
        return [
        {
          label: t('payment.pay_dlg_close'),
          onClick: onClose,
          variant: 'secondary'
        },
        printTickets.length > 0 && {
          label: t('payment.pay_dlg_print_tickets'),
          onClick: printAllTickets,
          variant: 'primary',
          icon: <Printer size={16} />
        }].
        filter(Boolean);

      case 'failed':
        return [
        {
          label: t('payment.pay_dlg_close'),
          onClick: onClose,
          variant: 'secondary'
        },
        {
          label: t('payment.pay_dlg_try_again'),
          onClick: () => {
            resetState();
            initPayment();
          },
          variant: 'primary',
          icon: <RefreshCw size={16} />
        },
        {
          label: t('payment.pay_dlg_check_status'),
          onClick: manualCheck,
          variant: 'outline',
          icon: <RefreshCw size={16} />,
          disabled: loading
        }];


      default:
        return [
        {
          label: t('payment.pay_dlg_close'),
          onClick: onClose,
          variant: 'secondary'
        }];

    }
  };

  // ===================== РЕНДЕР КОНТЕНТА =====================

  const renderContent = () => {
    switch (paymentState) {
      case 'init':
        return (
          <div className="payment-init">
            <div className="payment-header">
              <CreditCard size={48} className={`payment-icon ${provider}`} />
              <h3>{t('payment.pay_dlg_title_pay_via', { provider: providerLabel })}</h3>
            </div>

            <div className="payment-details">
              <div className="detail-row">
                <span className="detail-label">{t('payment.pay_dlg_amount_due')}</span>
                <span className="detail-value">
                  {totalAmount?.toLocaleString()} {currency}
                </span>
              </div>
              <div className="detail-row">
                <span className="detail-label">{t('payment.pay_dlg_payment_method')}</span>
                <span className="detail-value">{t('payment.pay_dlg_method_online', { provider: providerLabel })}</span>
              </div>
            </div>

            <div className="payment-info">
              <p>{t('payment.pay_dlg_init_hint_1', { provider: providerLabel })}</p>
              <p>{t('payment.pay_dlg_init_hint_2')}</p>
            </div>
          </div>);


      case 'processing':
        return (
          <div className="payment-processing">
            <div className="payment-header">
              <ExternalLink size={48} className="payment-icon processing" />
              <h3>{t('payment.pay_dlg_processing_title')}</h3>
            </div>

            <div className="payment-info">
              <p>{t('payment.pay_dlg_processing_hint_1', { provider: providerLabel })}</p>
              <p>{t('payment.pay_dlg_processing_hint_2')}</p>
            </div>

            {paymentUrl &&
            <div className="payment-link">
                <a
                href={paymentUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="payment-url">

                  {t('payment.pay_dlg_open_payment_page')}
                </a>
              </div>
            }

            <div className="payment-instructions">
              <p><strong>{t('payment.pay_dlg_after_completion')}</strong></p>
              <ul>
                <li>{t('payment.pay_dlg_instruction_1')}</li>
                <li>{t('payment.pay_dlg_instruction_2', { provider: providerLabel })}</li>
              </ul>
            </div>
          </div>);


      case 'polling':
        return (
          <div className="payment-polling">
            <div className="payment-header">
              <Clock size={48} className="payment-icon polling" />
              <h3>{t('payment.pay_dlg_waiting_title')}</h3>
            </div>

            <div className="polling-status">
              <div className="polling-indicator">
                <div className="spinner"></div>
                <span>{t('payment.pay_dlg_checking_status')}</span>
              </div>

              <div className="polling-info">
                <p>{t('payment.pay_dlg_attempt_of', { current: pollingAttempts, max: maxPollingAttempts })}</p>
                <p>{t('payment.pay_dlg_check_every', { seconds: pollingIntervalMs / 1000 })}</p>
              </div>
            </div>

            <div className="payment-info">
              <p>{t('payment.pay_dlg_polling_hint_1')}</p>
              <p>{t('payment.pay_dlg_polling_hint_2', { provider: providerLabel })}</p>
            </div>
          </div>);


      case 'success':
        return (
          <div className="payment-success">
            <div className="payment-header">
              <CheckCircle size={48} className="payment-icon success" />
              <h3>{t('payment.pay_dlg_success_title')}</h3>
            </div>

            <div className="success-info">
              <p>{t('payment.pay_dlg_success_info_1')}</p>
              <p>{t('payment.pay_dlg_success_info_2')}</p>
            </div>

            {printTickets.length > 0 &&
            <div className="print-tickets">
                <h4>{t('payment.pay_dlg_tickets_for_print')}</h4>
                <div className="tickets-list">
                  {printTickets.map((ticket, index) =>
                <div key={index} className="ticket-item">
                      <div className="ticket-info">
                        <div className="ticket-patient">{ticket.patient_name}</div>
                        <div className="ticket-details">
                          {ticket.doctor_name} • {t('payment.pay_dlg_queue_label', { number: ticket.queue_number })}
                        </div>
                      </div>
                      <button
                    className="print-ticket-btn"
                    aria-label={t('payment.pay_dlg_print_ticket_aria', { patient: ticket.patient_name })}
                    onClick={() => printTicket(ticket)}>

                        <Printer size={16} />
                      </button>
                    </div>
                )}
                </div>
              </div>
            }
          </div>);


      case 'failed':
        return (
          <div className="payment-failed">
            <div className="payment-header">
              <XCircle size={48} className="payment-icon failed" />
              <h3>{t('payment.pay_dlg_failed_title')}</h3>
            </div>

            {error &&
            <div className="error-info">
                <AlertCircle size={20} />
                <span>{error}</span>
              </div>
            }

            <div className="failure-info">
              <p>{t('payment.pay_dlg_failed_info_1')}</p>
              <p>{t('payment.pay_dlg_failed_info_2')}</p>
              <ul>
                <li>{t('payment.pay_dlg_failed_action_retry')}</li>
                <li>{t('payment.pay_dlg_failed_action_check')}</li>
                <li>{t('payment.pay_dlg_failed_action_admin')}</li>
              </ul>
            </div>
          </div>);


      default:
        return null;
    }
  };

  return (
    <>
    <ModernDialog
        isOpen={isOpen}
        onClose={onClose}
        title={t('payment.pay_dlg_title_pay_via', { provider: providerLabel })}
        actions={getActions()}
        maxWidth="32rem"
        closeOnBackdrop={false}
        closeOnEscape={paymentState === 'init' || paymentState === 'success' || paymentState === 'failed'}
        className={cssClassName}>

      <div className={`payment-${provider}-container`}>
        {renderContent()}
      </div>
    </ModernDialog>

    {/* Принтер множественных талонов */}
    {showTicketPrinter && printTickets.length > 0 &&
      <ModernDialog
        isOpen={showTicketPrinter}
        onClose={() => setShowTicketPrinter(false)}
        title={t('payment.pay_dlg_print_tickets')}
        maxWidth="50rem"
        closeOnBackdrop={false}
        className="ticket-printer-dialog">

        <MultipleTicketsPrinter
          tickets={printTickets}
          onClose={() => setShowTicketPrinter(false)}
          onAllPrinted={() => {
            setShowTicketPrinter(false);
            notify.success(t('payment.all_receipts_printed'));
          }} />

      </ModernDialog>
      }
  </>);

};


PaymentProviderDialog.propTypes = {
  ...(PaymentProviderDialog.propTypes || {}),
  currency: PropTypes.any,
  invoiceId: PropTypes.any,
  isOpen: PropTypes.any,
  onClose: PropTypes.any,
  onError: PropTypes.any,
  onSuccess: PropTypes.any,
  toLocaleString: PropTypes.any,
  totalAmount: PropTypes.any,
  provider: PropTypes.oneOf(['click', 'payme']).isRequired,
  providerLabel: PropTypes.string.isRequired,
  cssClassName: PropTypes.string.isRequired,
};

export default PaymentProviderDialog;
