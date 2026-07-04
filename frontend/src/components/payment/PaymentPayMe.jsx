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
import './PaymentPayMe.css';
import PropTypes from 'prop-types';

const PaymentPayMe = ({
  isOpen,
  onClose,
  invoiceId,
  totalAmount,
  currency = 'UZS',
  onSuccess,
  onError
}) => {
  const { executeAction, loading } = useAsyncAction();

  const [paymentState, setPaymentState] = useState('init'); // init|processing|polling|success|failed
  const [paymentUrl, setPaymentUrl] = useState(null);
  const [, setProviderPaymentId] = useState(null);
  const [error, setError] = useState(null);
  useState(null);
  const [pollingAttempts, setPollingAttempts] = useState(0);
  const [printTickets, setPrintTickets] = useState([]);
  const [showTicketPrinter, setShowTicketPrinter] = useState(false);

  const maxPollingAttempts = 60; // 5 минут при интервале 5 сек
  const pollingIntervalMs = 5000; // 5 секунд

  // Refs для управления polling
  const pollingRef = useRef(null);
  const attemptsRef = useRef(0);

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

  // ===================== ИНИЦИАЦИЯ ПЛАТЕЖА =====================

  const initPayment = async () => {
    if (!invoiceId) {
      setError('ID invoice не указан');
      return;
    }

    await executeAction(
      async () => {
        const response = await api.post('/registrar/invoice/init-payment', {
          invoice_id: invoiceId,
          provider: 'payme',
          return_url: `${window.location.origin}/payment/success`,
          cancel_url: `${window.location.origin}/payment/cancel`
        });

        const data = response.data;

        if (data.success) {
          setPaymentUrl(data.payment_url);
          setProviderPaymentId(data.provider_payment_id);
          setPaymentState('processing');

          // Автоматически открываем ссылку на оплату
          if (data.payment_url) {
            window.open(data.payment_url, '_blank');

            // Начинаем polling через 10 секунд
            setTimeout(() => {
              startPolling();
            }, 10000);
          }
        } else {
          throw new Error(data.error_message || 'Не удалось создать платёж');
        }

        return data;
      },
      {
        loadingMessage: 'Инициация платежа...',
        successMessage: 'Платёж создан. Переходите по ссылке для оплаты.',
        errorMessage: 'Ошибка создания платежа',
        onError: (err) => {
          setError(err.message);
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
        setError('Время ожидания оплаты истекло. Проверьте статус платежа вручную.');
        notify.error('Время ожидания истекло');
      }
    }, pollingIntervalMs);
  };

  const checkPaymentStatus = async () => {
    const response = await api.get(`/registrar/invoice/${invoiceId}/status`);

    if (response.status >= 200 && response.status < 300) {
      const data = response.data;

      if (data.status === 'paid') {
        clearPolling();
        setPaymentState('success');

        // Получаем данные для печати талонов
        const tickets = Array.isArray(data.print_tickets) ? data.print_tickets : [];
        setPrintTickets(tickets);

        notify.success('Платёж успешно завершён!');

        // Показываем принтер талонов если есть талоны для печати
        setShowTicketPrinter(tickets.length > 0);

        if (onSuccess) {
          onSuccess(data);
        }
      } else if (data.status === 'failed' || data.status === 'cancelled') {
        clearPolling();
        setPaymentState('failed');
        setError(`Платёж ${data.status === 'failed' ? 'не прошёл' : 'отменён'}`);

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
      specialty_name: ticket.department || ticket.specialty || ticket.queue_name || 'Очередь',
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
        loadingMessage: 'Проверка статуса...',
        errorMessage: 'Ошибка проверки статуса'
      }
    );
  };

  // ===================== ДЕЙСТВИЯ ДИАЛОГА =====================

  const getActions = () => {
    switch (paymentState) {
      case 'init':
        return [
        {
          label: 'Отмена',
          onClick: onClose,
          variant: 'secondary'
        },
        {
          label: 'Оплатить через PayMe',
          onClick: initPayment,
          variant: 'primary',
          icon: <CreditCard size={16} />,
          disabled: loading || !invoiceId
        }];


      case 'processing':
        return [
        {
          label: 'Отмена',
          onClick: onClose,
          variant: 'secondary'
        },
        {
          label: 'Открыть ссылку повторно',
          onClick: () => paymentUrl && window.open(paymentUrl, '_blank'),
          variant: 'primary',
          icon: <ExternalLink size={16} />,
          disabled: !paymentUrl
        },
        {
          label: 'Начать отслеживание',
          onClick: startPolling,
          variant: 'primary',
          icon: <Clock size={16} />
        }];


      case 'polling':
        return [
        {
          label: 'Остановить отслеживание',
          onClick: () => {
            clearPolling();
            setPaymentState('processing');
          },
          variant: 'secondary'
        },
        {
          label: 'Проверить сейчас',
          onClick: manualCheck,
          variant: 'primary',
          icon: <RefreshCw size={16} />,
          disabled: loading
        }];


      case 'success':
        return [
        {
          label: 'Закрыть',
          onClick: onClose,
          variant: 'secondary'
        },
        printTickets.length > 0 && {
          label: 'Печать талонов',
          onClick: printAllTickets,
          variant: 'primary',
          icon: <Printer size={16} />
        }].
        filter(Boolean);

      case 'failed':
        return [
        {
          label: 'Закрыть',
          onClick: onClose,
          variant: 'secondary'
        },
        {
          label: 'Попробовать снова',
          onClick: () => {
            resetState();
            initPayment();
          },
          variant: 'primary',
          icon: <RefreshCw size={16} />
        },
        {
          label: 'Проверить статус',
          onClick: manualCheck,
          variant: 'outline',
          icon: <RefreshCw size={16} />,
          disabled: loading
        }];


      default:
        return [
        {
          label: 'Закрыть',
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
              <CreditCard size={48} className="payment-icon payme" />
              <h3>Оплата через PayMe</h3>
            </div>
            
            <div className="payment-details">
              <div className="detail-row">
                <span className="detail-label">Сумма к оплате:</span>
                <span className="detail-value">
                  {totalAmount?.toLocaleString()} {currency}
                </span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Способ оплаты:</span>
                <span className="detail-value">PayMe (онлайн)</span>
              </div>
            </div>
            
            <div className="payment-info">
              <p>После нажатия кнопки «Оплатить» откроется страница PayMe для завершения платежа.</p>
              <p>Не закрывайте это окно до завершения оплаты.</p>
            </div>
          </div>);


      case 'processing':
        return (
          <div className="payment-processing">
            <div className="payment-header">
              <ExternalLink size={48} className="payment-icon processing" />
              <h3>Переход к оплате</h3>
            </div>
            
            <div className="payment-info">
              <p>Страница оплаты PayMe должна открыться в новом окне.</p>
              <p>Если окно не открылось, нажмите кнопку ниже.</p>
            </div>
            
            {paymentUrl &&
            <div className="payment-link">
                <a
                href={paymentUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="payment-url">
                
                  Открыть страницу оплаты
                </a>
              </div>
            }
            
            <div className="payment-instructions">
              <p><strong>После завершения оплаты:</strong></p>
              <ul>
                <li>Нажмите «Начать отслеживание» для автоматической проверки</li>
                <li>Или закройте окно PayMe и вернитесь сюда</li>
              </ul>
            </div>
          </div>);


      case 'polling':
        return (
          <div className="payment-polling">
            <div className="payment-header">
              <Clock size={48} className="payment-icon polling" />
              <h3>Ожидание оплаты</h3>
            </div>
            
            <div className="polling-status">
              <div className="polling-indicator">
                <div className="spinner"></div>
                <span>Проверяем статус платежа...</span>
              </div>
              
              <div className="polling-info">
                <p>Попытка {pollingAttempts} из {maxPollingAttempts}</p>
                <p>Проверка каждые {pollingIntervalMs / 1000} секунд</p>
              </div>
            </div>
            
            <div className="payment-info">
              <p>Система автоматически проверяет статус вашего платежа.</p>
              <p>Вы можете закрыть окно PayMe и дождаться подтверждения здесь.</p>
            </div>
          </div>);


      case 'success':
        return (
          <div className="payment-success">
            <div className="payment-header">
              <CheckCircle size={48} className="payment-icon success" />
              <h3>Оплата успешна!</h3>
            </div>
            
            <div className="success-info">
              <p>Платёж успешно обработан.</p>
              <p>Визиты созданы и добавлены в очередь.</p>
            </div>
            
            {printTickets.length > 0 &&
            <div className="print-tickets">
                <h4>Талоны для печати:</h4>
                <div className="tickets-list">
                  {printTickets.map((ticket, index) =>
                <div key={index} className="ticket-item">
                      <div className="ticket-info">
                        <div className="ticket-patient">{ticket.patient_name}</div>
                        <div className="ticket-details">
                          {ticket.doctor_name} • Очередь #{ticket.queue_number}
                        </div>
                      </div>
                      <button
                    className="print-ticket-btn"
                    aria-label={`Печать талона для ${ticket.patient_name}`}
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
              <h3>Ошибка оплаты</h3>
            </div>
            
            {error &&
            <div className="error-info">
                <AlertCircle size={20} />
                <span>{error}</span>
              </div>
            }
            
            <div className="failure-info">
              <p>Платёж не был завершён успешно.</p>
              <p>Вы можете:</p>
              <ul>
                <li>Попробовать оплатить снова</li>
                <li>Проверить статус платежа</li>
                <li>Обратиться к администратору</li>
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
        title="Оплата через PayMe"
        actions={getActions()}
        maxWidth="32rem"
        closeOnBackdrop={false}
        closeOnEscape={paymentState === 'init' || paymentState === 'success' || paymentState === 'failed'}
        className="payment-payme-dialog">
        
      <div className="payment-payme-container">
        {renderContent()}
      </div>
    </ModernDialog>

    {/* Принтер множественных талонов */}
    {showTicketPrinter && printTickets.length > 0 &&
      <ModernDialog
        isOpen={showTicketPrinter}
        onClose={() => setShowTicketPrinter(false)}
        title="Печать талонов"
        maxWidth="50rem"
        closeOnBackdrop={false}
        className="ticket-printer-dialog">
        
        <MultipleTicketsPrinter
          tickets={printTickets}
          onClose={() => setShowTicketPrinter(false)}
          onAllPrinted={() => {
            setShowTicketPrinter(false);
            notify.success('Все талоны напечатаны!');
          }} />
        
      </ModernDialog>
      }
  </>);

};


PaymentPayMe.propTypes = {
  ...(PaymentPayMe.propTypes || {}),
  currency: PropTypes.any,
  invoiceId: PropTypes.any,
  isOpen: PropTypes.any,
  onClose: PropTypes.any,
  onError: PropTypes.any,
  onSuccess: PropTypes.any,
  toLocaleString: PropTypes.any,
  totalAmount: PropTypes.any,
};

export default PaymentPayMe;
