
import { useState, useEffect, useRef } from 'react';
import { Printer, CheckCircle, Clock, X } from 'lucide-react';
import './MultipleTicketsPrinter.css';
import {
  buildPanelTicketPayload,
  printPanelTicketInBrowserAsync,
  openPanelTicketBatchWindow,
  printPanelTicketsBatchInExistingWindow
} from '../../services/panelPrint';
import logger from '../../utils/logger';
import { useTranslation } from '../../i18n/useTranslation';

type TFunc = (key: string, options?: Record<string, unknown>) => string;

interface Ticket {
  queue_id: string | number;
  queue_name?: string;
  queue_number?: string | number;
  patient_name?: string;
  doctor_name?: string;
  visit_date?: string;
  visit_time?: string;
  [key: string]: unknown;
}

const MultipleTicketsPrinter = ({ tickets, onClose, onAllPrinted }: {
  tickets: Ticket[];
  onClose: () => void;
  onAllPrinted?: () => void;
}) => {
  const { t: rawT } = useTranslation(); const t = rawT as TFunc;
  const [printedTickets, setPrintedTickets] = useState<Set<string | number>>(new Set());
  const [currentPrinting, setCurrentPrinting] = useState<string | number | null>(null);
  const [countdown, setCountdown] = useState(0);
  // CSH-FE-045 (follow-up audit 2026-11-02): окно пакетной печати открывается
  // синхронно в прямом жесте клика «Печать всех» (ДО сетевых запросов и
  // отсчёта) — иначе 5с+800мс после клика выводят window.open за пределы
  // окна доверенной активации и блокируются браузером. Окно наполняется
  // единым документом (по .ticket-page на талон) — попап на каждый талон
  // больше не открывается вовсе.
  const batchWindowRef = useRef<Window | null>(null);
  const [batchError, setBatchError] = useState<string | null>(null);

  // Функция печати одного талона (кнопка на карточке — прямой жест)
  const printSingleTicket = async (ticket: Ticket) => {
    setCurrentPrinting(ticket.queue_id);

    try {
      const result = await printPanelTicketInBrowserAsync(buildPanelTicketPayload(ticket));
      if (!result?.opened) {
        logger.warn('Browser popup blocked for ticket print', ticket);
      } else if (!result?.success) {
        logger.warn('Browser ticket preview failed', ticket);
      }
      return Boolean(result?.opened && result?.success);
    } catch (error) {
      logger.error('Browser ticket print failed', error);
      return false;
    } finally {
      setCurrentPrinting(null);
    }
  };

  // Печать всех талонов одним документом в УЖЕ открытом окне (см.
  // startCountdown: окно открыто в жесте клика). Порядок печати задаётся
  // порядком .ticket-page; искусственная пауза 800мс на талон удалена.
  const printAllTickets = async () => {
    const batchWindow = batchWindowRef.current;
    if (!batchWindow) {
      setBatchError('Окно пакетной печати не открыто — нажмите «Печать всех» ещё раз.');
      return;
    }

    const pending = tickets.filter((ticket) => !printedTickets.has(ticket.queue_id));
    if (pending.length === 0) {
      onAllPrinted && onAllPrinted();
      return;
    }

    const result = await printPanelTicketsBatchInExistingWindow(
      batchWindow,
      pending.map((ticket) => buildPanelTicketPayload(ticket))
    );

    if (result.success) {
      setPrintedTickets((prev) => new Set([...prev, ...pending.map((ticket) => ticket.queue_id)]));
      setBatchError(null);
      onAllPrinted && onAllPrinted();
    } else {
      // Честный провал: ничего не помечаем напечатанным — кнопка
      // «Печать всех» остаётся пользователю как путь восстановления.
      logger.warn('Batch ticket print failed', result.error);
      setBatchError('Не удалось подготовить печать: повторите «Печать всех» или напечатайте талоны по одному.');
    }
  };

  // Обратный отсчет для кнопки "Печать всех". Окно уже открыто в жесте —
  // отсчёт только задерживает заполнение/печать, не открытие попапа.
  useEffect(() => {
    if (countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
      return () => clearTimeout(timer);
    }
    // Отсчёт дошёл до нуля — окно уже открыто: наполняем и печатаем.
    if (countdown === 0 && batchWindowRef.current) {
      void printAllTickets();
    }
  }, [countdown]);

  const startCountdown = () => {
    // ШАГ 1 (синхронно, в жесте): открыть окно-плейсхолдер. Если браузер
    // заблокировал — честное сообщение, отсчёт не начинается.
    setBatchError(null);
    const batchWindow = openPanelTicketBatchWindow();
    if (!batchWindow) {
      logger.warn('Browser popup blocked for batch ticket print (user gesture)');
      setBatchError('Браузер заблокировал окно печати. Разрешите всплывающие окна для приложения и повторите.');
      return;
    }
    batchWindowRef.current = batchWindow;
    // ШАГ 2: отсчёт до заполнения/печати (окно уже открыто).
    setCountdown(5);
  };

  const allPrinted = printedTickets.size >= tickets.length;
  const hasUnprinted = tickets.some((ticket) => !printedTickets.has(ticket.queue_id));
  return (
    <div className="multiple-tickets-printer">
      <div className="printer-header">
        <h3>Печать талонов ({tickets.length})</h3>
        <button className="close-btn" onClick={onClose} aria-label="Close tickets printer">
          <X size={20} />
        </button>
      </div>

      <div className="tickets-grid">
        {tickets.map((ticket, index) => {
          const isPrinted = printedTickets.has(ticket.queue_id);
          const isPrinting = currentPrinting === ticket.queue_id;

          return (
            <div
              key={`${ticket.queue_id}-${index}`}
              className={`ticket-card ${isPrinted ? 'printed' : ''} ${isPrinting ? 'printing' : ''}`}>
              
              <div className="ticket-header">
                <span className="queue-name">{ticket.queue_name}</span>
                <span className="queue-number">№{ticket.queue_number}</span>
              </div>
              
              <div className="ticket-details">
                <div className="patient-name">{ticket.patient_name || t('misc.mtp_patsient')}</div>
                {ticket.doctor_name !== t('misc.mtp_bez_vracha') &&
                <div className="doctor-name">{ticket.doctor_name}</div>
                }
                <div className="visit-info">
                  {ticket.visit_date ? new Date(ticket.visit_date).toLocaleDateString('ru-RU') : ''} • {ticket.visit_time}
                </div>
              </div>

              <div className="ticket-actions">
                {isPrinted ?
                <div className="printed-status">
                    <CheckCircle size={16} />
                    <span>{t('misc.mtp_napechatan')}</span>
                  </div> :
                isPrinting ?
                <div className="printing-status">
                    <Clock size={16} className="spinning" />
                    <span>{t('misc.mtp_pechat')}</span>
                  </div> :

                <button
                  className="print-single-btn"
                  onClick={() => printSingleTicket(ticket)}>
                  
                    <Printer size={16} />
                    <span>{t('misc.mtp_pechat_2')}</span>
                  </button>
                }
              </div>
            </div>);

        })}
      </div>

      <div className="printer-footer">
        {allPrinted ?
        <div className="all-printed">
            <CheckCircle size={20} />
            <span>{t('misc.mtp_vse_talony_napechatany')}</span>
          </div> :

        <div className="print-all-section">
            {/* CSH-FE-045: честное сообщение о блокировке/провале пакетной
                печати — кнопка «Печать всех» остаётся как путь восстановления. */}
            {batchError && (
              <div className="batch-print-error" data-testid="mtp-batch-error" role="alert">
                {batchError}
              </div>
            )}
            {countdown > 0 ?
          <button className="print-all-btn countdown" disabled>
                <Clock size={16} />
                Печать через {countdown}с
              </button> :
          hasUnprinted ?
          <button
            className="print-all-btn"
            onClick={startCountdown}>
            
                <Printer size={16} />
                Печать всех ({tickets.length - printedTickets.size})
              </button> :
          null}
          </div>
        }
      </div>
    </div>);

};


// audit/strict: removed self-referencing propTypes spread

export default MultipleTicketsPrinter;
