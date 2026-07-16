import { useState, useEffect } from 'react';
import { Printer, CheckCircle, Clock, X } from 'lucide-react';
import './MultipleTicketsPrinter.css';
import { buildPanelTicketPayload, printPanelTicketInBrowserAsync } from '../../services/panelPrint';
import logger from '../../utils/logger';
import PropTypes from 'prop-types';
import { useTranslation } from '../../i18n/useTranslation';

const MultipleTicketsPrinter = ({ tickets, onClose, onAllPrinted }) => {
  const { t } = useTranslation();
  const [printedTickets, setPrintedTickets] = useState(new Set());
  const [currentPrinting, setCurrentPrinting] = useState(null);
  const [countdown, setCountdown] = useState(0);

  // Функция печати одного талона
  const printSingleTicket = async (ticket) => {
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

  // Печать всех талонов с интервалом
  const printAllTickets = async () => {
    let allSucceeded = true;

    for (const ticket of tickets) {
      if (!printedTickets.has(ticket.queue_id)) {
        // Небольшая пауза между печатью талонов, чтобы не перегружать принтер
        // и сохранить предсказуемый порядок печати.
        await new Promise((resolve) => setTimeout(resolve, 800));
        const success = await printSingleTicket(ticket);
        if (success) {
          setPrintedTickets((prev) => new Set([...prev, ticket.queue_id]));
        } else {
          allSucceeded = false;
        }
      }
    }

    if (allSucceeded) {
      onAllPrinted && onAllPrinted();
    }
  };

  // Обратный отсчет для кнопки "Печать всех"
  useEffect(() => {
    if (countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [countdown]);

  const startCountdown = () => {
    setCountdown(5);
    setTimeout(() => {
      printAllTickets();
    }, 5000);
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
                  {new Date(ticket.visit_date).toLocaleDateString('ru-RU')} • {ticket.visit_time}
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


MultipleTicketsPrinter.propTypes = {
  ...(MultipleTicketsPrinter.propTypes || {}),
  forEach: PropTypes.any,
  length: PropTypes.any,
  map: PropTypes.any,
  onAllPrinted: PropTypes.any,
  onClose: PropTypes.any,
  some: PropTypes.any,
  tickets: PropTypes.any,
};

export default MultipleTicketsPrinter;
