
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

// QUEUEPRINT-FE-002 (audit group97): printed-state identity is PER-TICKET —
// the shared DailyQueue id (queue_id) collides for same-queue tickets
// ({queue_id:17,queue_number:4} vs {queue_id:17,queue_number:5}): a Set over
// queue_id produced mutually inconsistent allPrinted/hasUnprinted and could
// silently treat a new same-queue ticket as printed. Legacy payloads without
// a queue number retain their queue-level fallback.
const ticketIdentity = (ticket: Ticket): string => {
  const num = ticket.queue_number;
  const queueNumber = num === undefined || num === null || num === '' ? null : String(num);
  return JSON.stringify([String(ticket.queue_id), queueNumber]);
};

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
  const [printedTickets, setPrintedTickets] = useState<Set<string>>(new Set());
  const [currentPrinting, setCurrentPrinting] = useState<string | null>(null);
  const [batchPrinting, setBatchPrinting] = useState(false);
  const [countdown, setCountdown] = useState(0);
  // CSH-FE-045 (follow-up audit 2026-11-02): окно пакетной печати открывается
  // синхронно в прямом жесте клика «Печать всех» (ДО сетевых запросов и
  // отсчёта) — иначе 5с+800мс после клика выводят window.open за пределы
  // окна доверенной активации и блокируются браузером. Окно наполняется
  // единым документом (по .ticket-page на талон) — попап на каждый талон
  // больше не открывается вовсе.
  const batchWindowRef = useRef<Window | null>(null);
  const printInProgress = useRef(false);
  const [batchError, setBatchError] = useState<string | null>(null);
  const pendingTickets = tickets.filter((ticket) => !printedTickets.has(ticketIdentity(ticket)));

  // Функция печати одного талона (кнопка на карточке — прямой жест).
  // QUEUEPRINT-FE-001 (audit group97): успешный одиночный вывод помечает
  // ТОЛЬКО этот талон напечатанным (invocation ≠ physical delivery —
  // mark = честный сигнал браузер-уровня: окно открыто и наполнено);
  // провал оставляет талон в очереди пакетной печати.
  const printSingleTicket = async (ticket: Ticket) => {
    if (printInProgress.current) return false;
    printInProgress.current = true;
    const identity = ticketIdentity(ticket);
    setCurrentPrinting(identity);

    try {
      const result = await printPanelTicketInBrowserAsync(buildPanelTicketPayload(ticket));
      if (!result?.opened) {
        logger.warn('Browser popup blocked for ticket print', ticket);
      } else if (!result?.success) {
        logger.warn('Browser ticket preview failed', ticket);
      }
      const delivered = Boolean(result?.opened && result?.success);
      if (delivered) {
        setPrintedTickets((prev) => new Set(prev).add(identity));
      }
      return delivered;
    } catch (error) {
      logger.error('Browser ticket print failed', error);
      return false;
    } finally {
      printInProgress.current = false;
      setCurrentPrinting(null);
    }
  };

  // Печать всех талонов одним документом в УЖЕ открытом окне (см.
  // startCountdown: окно открыто в жесте клика). Порядок печати задаётся
  // порядком .ticket-page; искусственная пауза 800мс на талон удалена.
  const printAllTickets = async () => {
    const batchWindow = batchWindowRef.current;
    if (!batchWindow) return;
    batchWindowRef.current = null;

    try {
      if (pendingTickets.length === 0) {
        batchWindow.close();
        onAllPrinted?.();
        return;
      }

      const result = await printPanelTicketsBatchInExistingWindow(
        batchWindow,
        pendingTickets.map((ticket) => buildPanelTicketPayload(ticket))
      );

      if (!result.opened || !result.success) {
        throw new Error('Browser batch ticket print failed', { cause: result.error });
      }
      setPrintedTickets((prev) => new Set([...prev, ...pendingTickets.map(ticketIdentity)]));
      onAllPrinted?.();
    } catch (error) {
      logger.warn('Batch ticket print failed', error);
      setBatchError('Не удалось подготовить печать: повторите «Печать всех» или напечатайте талоны по одному.');
    } finally {
      printInProgress.current = false;
      setBatchPrinting(false);
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
    if (printInProgress.current) return;
    // ШАГ 1 (синхронно, в жесте): открыть окно-плейсхолдер. Если браузер
    // заблокировал — честное сообщение, отсчёт не начинается.
    setBatchError(null);
    const batchWindow = openPanelTicketBatchWindow();
    if (!batchWindow) {
      logger.warn('Browser popup blocked for batch ticket print (user gesture)');
      setBatchError('Браузер заблокировал окно печати. Разрешите всплывающие окна для приложения и повторите.');
      return;
    }
    printInProgress.current = true;
    batchWindowRef.current = batchWindow;
    setBatchPrinting(true);
    // ШАГ 2: отсчёт до заполнения/печати (окно уже открыто).
    setCountdown(5);
  };

  const allPrinted = tickets.length > 0 && pendingTickets.length === 0;
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
          const identity = ticketIdentity(ticket);
          const isPrinted = printedTickets.has(identity);
          const isPrinting = currentPrinting === identity;

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
                  disabled={batchPrinting || currentPrinting !== null}
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
          pendingTickets.length > 0 ?
          <button
            className="print-all-btn"
            disabled={batchPrinting || currentPrinting !== null}
            onClick={startCountdown}>
            
                <Printer size={16} />
                Печать всех ({pendingTickets.length})
              </button> :
          null}
          </div>
        }
      </div>
    </div>);

};


// audit/strict: removed self-referencing propTypes spread

export default MultipleTicketsPrinter;
