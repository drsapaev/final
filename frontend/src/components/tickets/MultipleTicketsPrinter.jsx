import React, { useState, useEffect } from 'react';
import { Printer, CheckCircle, Clock, X } from 'lucide-react';
import './MultipleTicketsPrinter.css';

const MultipleTicketsPrinter = ({ tickets, onClose, onAllPrinted }) => {
  const [printedTickets, setPrintedTickets] = useState(new Set());
  const [currentPrinting, setCurrentPrinting] = useState(null);
  const [countdown, setCountdown] = useState(0);

  // Функция печати одного талона
  const printSingleTicket = (ticket) => {
    setCurrentPrinting(ticket.queue_id);
    
    // Формируем содержимое талона
    const printContent = `
      ═══════════════════════════════════
           ТАЛОН НА ПРИЁМ
      ═══════════════════════════════════
      
      Пациент: ${ticket.patient_name || 'Не указан'}
      
      Очередь: ${ticket.queue_name}
      Номер: ${ticket.queue_number}
      
      ${ticket.doctor_name !== 'Без врача' ? `Врач: ${ticket.doctor_name}` : ''}
      
      Дата: ${new Date(ticket.visit_date).toLocaleDateString('ru-RU')}
      Время: ${ticket.visit_time || 'Не указано'}
      
      ═══════════════════════════════════
      Сохраните талон до приёма
      ═══════════════════════════════════
    `;

    // Создаем новое окно для печати
    const printWindow = window.open('', '_blank', 'width=400,height=600');
    printWindow.document.write(`
      <html>
        <head>
          <title>Талон ${ticket.queue_name} №${ticket.queue_number}</title>
          <style>
            body {
              font-family: 'Courier New', monospace;
              font-size: 12px;
              line-height: 1.4;
              margin: 20px;
              white-space: pre-line;
            }
            @media print {
              body { margin: 0; }
            }
          </style>
        </head>
        <body>
          ${printContent}
        </body>
      </html>
    `);
    
    printWindow.document.close();
    
    // Автоматическая печать через небольшую задержку
    setTimeout(() => {
      printWindow.print();
      printWindow.close();
      
      // Отмечаем талон как напечатанный
      setPrintedTickets(prev => new Set([...prev, ticket.queue_id]));
      setCurrentPrinting(null);
      
      // Проверяем, все ли талоны напечатаны
      if (printedTickets.size + 1 >= tickets.length) {
        setTimeout(() => {
          onAllPrinted && onAllPrinted();
        }, 1000);
      }
    }, 500);
  };

  // Печать всех талонов с интервалом
  const printAllTickets = () => {
    let delay = 0;
    tickets.forEach((ticket, index) => {
      if (!printedTickets.has(ticket.queue_id)) {
        setTimeout(() => {
          printSingleTicket(ticket);
        }, delay);
        delay += 2000; // 2 секунды между печатью каждого талона
      }
    });
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
  const hasUnprinted = tickets.some(ticket => !printedTickets.has(ticket.queue_id));

  return (
    <div className="multiple-tickets-printer">
      <div className="printer-header">
        <h3>Печать талонов ({tickets.length})</h3>
        <button className="close-btn" onClick={onClose}>
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
              className={`ticket-card ${isPrinted ? 'printed' : ''} ${isPrinting ? 'printing' : ''}`}
            >
              <div className="ticket-header">
                <span className="queue-name">{ticket.queue_name}</span>
                <span className="queue-number">№{ticket.queue_number}</span>
              </div>
              
              <div className="ticket-details">
                <div className="patient-name">{ticket.patient_name || 'Пациент'}</div>
                {ticket.doctor_name !== 'Без врача' && (
                  <div className="doctor-name">{ticket.doctor_name}</div>
                )}
                <div className="visit-info">
                  {new Date(ticket.visit_date).toLocaleDateString('ru-RU')} • {ticket.visit_time}
                </div>
              </div>

              <div className="ticket-actions">
                {isPrinted ? (
                  <div className="printed-status">
                    <CheckCircle size={16} />
                    <span>Напечатан</span>
                  </div>
                ) : isPrinting ? (
                  <div className="printing-status">
                    <Clock size={16} className="spinning" />
                    <span>Печать...</span>
                  </div>
                ) : (
                  <button 
                    className="print-single-btn"
                    onClick={() => printSingleTicket(ticket)}
                  >
                    <Printer size={16} />
                    <span>Печать</span>
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="printer-footer">
        {allPrinted ? (
          <div className="all-printed">
            <CheckCircle size={20} />
            <span>Все талоны напечатаны</span>
          </div>
        ) : (
          <div className="print-all-section">
            {countdown > 0 ? (
              <button className="print-all-btn countdown" disabled>
                <Clock size={16} />
                Печать через {countdown}с
              </button>
            ) : hasUnprinted ? (
              <button 
                className="print-all-btn"
                onClick={startCountdown}
              >
                <Printer size={16} />
                Печать всех ({tickets.length - printedTickets.size})
              </button>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
};

export default MultipleTicketsPrinter;

