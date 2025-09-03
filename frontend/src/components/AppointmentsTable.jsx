import React, { useState } from 'react';
import { Printer, X, Calendar, CreditCard } from 'lucide-react';
import { Button, Badge } from './ui';
import { useTheme } from '../contexts/ThemeContext';

const AppointmentsTable = ({
  appointments = [],
  appointmentsSelected = new Set(),
  setAppointmentsSelected,
  updateAppointmentStatus,
  setShowWizard,
  headerHeight
}) => {
  const [activeRow, setActiveRow] = useState(null); // <--- ДОБАВЛЕНО: состояние для активной строки
  const { isDark, isLight, getColor, getSpacing } = useTheme();

  // Показывать ли пустые строки (можно сделать настраиваемым)
  const showEmptyRows = true;
  const emptyRowsCount = 3; // <--- ИЗМЕНЕНО: с 10 на 3
  const buttonStyle = {
    width: '36px',
    height: '36px',
    border: 'none',
    borderRadius: '8px',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '16px',
    transition: 'all 0.2s',
    boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
  };

  const buttonSecondaryStyle = {
    ...buttonStyle,
    backgroundColor: '#6c757d',
    color: 'white'
  };

  const buttonSuccessStyle = {
    ...buttonStyle,
    backgroundColor: '#28a745',
    color: 'white'
  };

  const buttonDangerStyle = {
    ...buttonStyle,
    backgroundColor: '#dc3545',
    color: 'white'
  };

  const buttonWarningStyle = {
    ...buttonStyle,
    backgroundColor: '#ffc107',
    color: '#212529'
  };

  const buttonInfoStyle = {
    ...buttonStyle,
    backgroundColor: '#6f42c1',
    color: 'white'
  };

  // Стили для статусов
  const getStatusStyle = (status) => {
    const statusStyles = {
      'plan': { background: '#e3f2fd', color: '#1976d2' },
      'confirmed': { background: '#e8f5e8', color: '#388e3c' },
      'queued': { background: '#fff3e0', color: '#f57c00' },
      'in_cabinet': { background: '#f3e5f5', color: '#7b1fa2' },
      'done': { background: '#e8f5e8', color: '#388e3c' },
      'cancelled': { background: '#ffebee', color: '#d32f2f' },
      'no_show': { background: '#fff8e1', color: '#fbc02d' },
      'paid_pending': { background: '#fff3e0', color: '#f57c00' },
      'paid': { background: '#e8f5e8', color: '#388e3c' }
    };
    return statusStyles[status] || { background: '#607d8b', color: '#fff' };
  };

  // Варианты для Badge компонента
  const getStatusVariant = (status) => {
    const variantMap = {
      'plan': 'primary',
      'confirmed': 'success',
      'queued': 'warning',
      'in_cabinet': 'purple',
      'done': 'success',
      'cancelled': 'danger',
      'no_show': 'orange',
      'paid_pending': 'warning',
      'paid': 'success'
    };
    return variantMap[status] || 'default';
  };

  // Стили для типов обращения
  const getVisitTypeStyle = (type) => {
    const typeStyles = {
      'paid': { background: '#e8f5e8', color: '#388e3c' },
      'repeat': { background: '#e3f2fd', color: '#1976d2' },
      'free': { background: '#fff3e0', color: '#f57c00' }
    };
    return typeStyles[type] || { background: '#e9ecef', color: '#495057' };
  };

  // Стили для способов оплаты с централизованной темой
  const getPaymentTypeStyle = (type) => {
    const paymentStyles = {
      'cash': { background: getColor('success', 100), color: getColor('success', 700) },
      'card': { background: getColor('info', 100), color: getColor('info', 700) },
      'online': { background: getColor('warning', 100), color: getColor('warning', 700) }
    };
    return paymentStyles[type] || { 
      background: isLight ? getColor('secondary', 100) : getColor('secondary', 800), 
      color: isLight ? getColor('secondary', 700) : getColor('secondary', 200) 
    };
  };

  // Стили для услуг с использованием централизованной темы  
  const getServiceStyle = (service) => {
    const serviceStyles = {
      'derm': { background: getColor('info', 100), color: getColor('info', 700) },
      'cosmetology': { background: getColor('primary', 100), color: getColor('primary', 700) },
      'cardio': { background: getColor('danger', 100), color: getColor('danger', 700) },
      'ecg': { background: getColor('success', 100), color: getColor('success', 700) },
      'echo': { background: getColor('warning', 100), color: getColor('warning', 700) },
      'stomatology': { background: getColor('secondary', 100), color: getColor('secondary', 700) },
      'lab': { background: getColor('info', 100), color: getColor('info', 700) }
    };
    return serviceStyles[service] || { 
      background: isLight ? getColor('secondary', 100) : getColor('secondary', 800), 
      color: isLight ? getColor('secondary', 700) : getColor('secondary', 200) 
    };
  };

  // Константы ширин и позиций для фиксированных колонок
  const COL_WIDTHS = {
    num: 60,
    fio: 200,
    phone: 140,
    actions: 140
  };

  const STICKY_POS = {
    fio: `${COL_WIDTHS.num}px`,
    phone: `${COL_WIDTHS.num + COL_WIDTHS.fio}px`
  };

  const headerStickyStyle = {
    position: 'sticky',
    zIndex: 800,
    background: `linear-gradient(135deg, ${getColor('secondary', 600)} 0%, ${getColor('secondary', 500)} 100%)`,
    boxShadow: '2px 0 5px rgba(0,0,0,0.1)'
  };

  const cellStickyStyle = {
    position: 'sticky',
    zIndex: 750,
    boxShadow: '2px 0 5px rgba(0,0,0,0.1)'
  };

  return (
    <div style={{ overflowX: 'auto', overflowY: 'auto', maxHeight: `calc(100vh - ${headerHeight}px)` }}>
      <table style={{
        width: '100%',
        borderCollapse: 'collapse',
        fontSize: '14px',
        fontFamily: 'Segoe UI, Tahoma, Geneva, Verdana, sans-serif'
      }}>
                 <thead>
           <tr style={{
             background: 'linear-gradient(135deg, #495057 0%, #6c757d 100%)',
             color: 'white',
             position: 'sticky',
             top: 0,
             zIndex: 700
           }}>
                         <th style={{
               padding: '15px 12px',
               textAlign: 'left',
               fontWeight: '500',
               position: 'sticky',
               left: 0,
               zIndex: 800,
               minWidth: `${COL_WIDTHS.num}px`,
               width: `${COL_WIDTHS.num}px`,
               background: 'linear-gradient(135deg, #495057 0%, #6c757d 100%)',
               boxShadow: '2px 0 5px rgba(0,0,0,0.1)',
               borderRight: '2px solid #495057'
             }}>№</th>
                         <th style={{
               padding: '15px 12px',
               textAlign: 'left',
               fontWeight: '500',
               position: 'sticky',
               left: STICKY_POS.fio,
               zIndex: 800,
               minWidth: `${COL_WIDTHS.fio}px`,
               width: `${COL_WIDTHS.fio}px`,
               background: 'linear-gradient(135deg, #495057 0%, #6c757d 100%)',
               boxShadow: '2px 0 5px rgba(0,0,0,0.1)',
               borderRight: '2px solid #495057'
             }}>ФИО</th>
            <th style={{
              padding: '15px 12px',
              textAlign: 'center',
              fontWeight: '500',
              minWidth: '100px'
            }}>Год рождения</th>
                         <th style={{
               padding: '15px 12px',
               textAlign: 'left',
               fontWeight: '500',
               position: 'sticky',
               left: STICKY_POS.phone,
               zIndex: 800,
               minWidth: `${COL_WIDTHS.phone}px`,
               width: `${COL_WIDTHS.phone}px`,
               background: 'linear-gradient(135deg, #495057 0%, #6c757d 100%)',
               boxShadow: '2px 0 5px rgba(0,0,0,0.1)',
               borderRight: '2px solid #495057'
             }}>Телефон</th>

            <th style={{
              padding: '15px 12px',
              textAlign: 'left',
              fontWeight: '500',
              minWidth: '120px'
            }}>Услуги</th>
            <th style={{
              padding: '15px 12px',
              textAlign: 'center',
              fontWeight: '500',
              minWidth: '120px'
            }}>Тип обращения</th>
            <th style={{
              padding: '15px 12px',
              textAlign: 'center',
              fontWeight: '500',
              minWidth: '120px'
            }}>Вид оплаты</th>
            <th style={{
              padding: '15px 12px',
              textAlign: 'right',
              fontWeight: '500',
              minWidth: '100px'
            }}>Стоимость</th>
            <th style={{
              padding: '15px 12px',
              textAlign: 'center',
              fontWeight: '500',
              minWidth: '100px'
            }}>Статус</th>
                         <th style={{
               padding: '15px 12px',
               textAlign: 'center',
               fontWeight: '500',
               position: 'sticky',
               right: 0,
               zIndex: 800,
               minWidth: `${COL_WIDTHS.actions}px`,
               background: 'linear-gradient(135deg, #495057 0%, #6c757d 100%)',
               boxShadow: '-2px 0 5px rgba(0,0,0,0.1)',
               borderLeft: '2px solid #495057'
             }}>Действия</th>
          </tr>
        </thead>
        <tbody>
                  {/* Пустые строки для начала рабочего дня */}
        {showEmptyRows && Array.from({ length: emptyRowsCount }, (_, i) => {
          const isEmptyActive = activeRow === `empty-${i}`;
          const emptyRowBgColor = isEmptyActive 
            ? '#dbeafe' // Цвет для активной пустой строки
            : (i % 2 === 0 ? '#fff' : '#f8f9fa'); // Чередующийся цвет
          const emptyHoverBgColor = '#e3f2fd'; // Цвет при наведении

          return (
            <tr
              key={`empty-${i}`}
              onClick={() => setActiveRow(`empty-${i}`)} // <--- ИСПРАВЛЕНО: установка активной строки
              style={{
                borderBottom: '1px solid #e9ecef',
                backgroundColor: emptyRowBgColor,
                transition: 'background-color 0.2s',
                cursor: 'pointer'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = emptyHoverBgColor;
                Array.from(e.currentTarget.querySelectorAll('td'))
                  .forEach(cell => {
                    cell.style.backgroundColor = emptyHoverBgColor;
                    cell.style.setProperty('background-color', emptyHoverBgColor, 'important');
                  });
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = emptyRowBgColor;
                Array.from(e.currentTarget.querySelectorAll('td'))
                  .forEach(cell => {
                    cell.style.backgroundColor = emptyRowBgColor;
                    cell.style.setProperty('background-color', emptyRowBgColor, 'important');
                  });
              }}
            >
                             <td style={{
                padding: '12px',
                textAlign: 'center',
                position: 'sticky',
                left: 0,
                zIndex: 750,
                minWidth: `${COL_WIDTHS.num}px`,
                width: `${COL_WIDTHS.num}px`,
                backgroundColor: emptyRowBgColor + ' !important',
                fontWeight: '500',
                color: '#6c757d',
                boxShadow: '2px 0 5px rgba(0,0,0,0.1)',
                borderRight: '2px solid #dee2e6'
              }}>
               {i + 1}
             </td>
                             <td style={{
                padding: '12px',
                position: 'sticky',
                left: STICKY_POS.fio,
                zIndex: 750,
                minWidth: `${COL_WIDTHS.fio}px`,
                width: `${COL_WIDTHS.fio}px`,
                backgroundColor: emptyRowBgColor + ' !important',
                color: '#6c757d',
                fontStyle: 'italic',
                boxShadow: '2px 0 5px rgba(0,0,0,0.1)',
                borderRight: '2px solid #dee2e6'
              }}>
               <span style={{ color: '#6c757d', fontStyle: 'italic' }}>Ожидает записи...</span>
             </td>
             <td style={{ 
               padding: '12px', 
               textAlign: 'center', 
               color: '#6c757d',
               backgroundColor: emptyRowBgColor + ' !important'
             }}>
               -
             </td>
                             <td style={{
                padding: '12px',
                position: 'sticky',
                left: STICKY_POS.phone,
                zIndex: 750,
                minWidth: `${COL_WIDTHS.phone}px`,
                width: `${COL_WIDTHS.phone}px`,
                backgroundColor: emptyRowBgColor + ' !important',
                color: '#6c757d',
                boxShadow: '2px 0 5px rgba(0,0,0,0.1)',
                borderRight: '2px solid #dee2e6'
              }}>
               -
             </td>
             <td style={{ 
               padding: '12px', 
               color: '#6c757d',
               backgroundColor: emptyRowBgColor + ' !important'
             }}>
               -
             </td>
             <td style={{ 
               padding: '12px', 
               textAlign: 'center', 
               color: '#6c757d',
               backgroundColor: emptyRowBgColor + ' !important'
             }}>
               -
             </td>
             <td style={{ 
               padding: '12px', 
               textAlign: 'center', 
               color: '#6c757d',
               backgroundColor: emptyRowBgColor + ' !important'
             }}>
               -
             </td>
             <td style={{
               padding: '12px',
               textAlign: 'right',
               color: '#6c757d',
               backgroundColor: emptyRowBgColor + ' !important'
             }}>
               -
             </td>
             <td style={{ 
               padding: '12px', 
               textAlign: 'center', 
               color: '#6c757d',
               backgroundColor: emptyRowBgColor + ' !important'
             }}>
               -
             </td>
                             <td style={{
                padding: '12px',
                textAlign: 'center',
                position: 'sticky',
                right: 0,
                zIndex: 750,
                backgroundColor: emptyRowBgColor + ' !important',
                boxShadow: '-2px 0 5px rgba(0,0,0,0.1)',
                borderLeft: '2px solid #dee2e6'
              }}>
               <div style={{ display: 'flex', gap: '6px', justifyContent: 'center' }}>
                 <Button
                   variant="primary"
                   size="sm"
                   title="Печать талона"
                   style={{ width: '36px', height: '36px', padding: '0' }}
                 >
                   <Printer size={16} />
                 </Button>
                 <Button
                   variant="danger"
                   size="sm"
                   title="Отмена"
                   style={{ width: '36px', height: '36px', padding: '0' }}
                 >
                   <X size={16} />
                 </Button>
                 <Button
                   variant="warning"
                   size="sm"
                   title="Перенос"
                   style={{ width: '36px', height: '36px', padding: '0' }}
                 >
                   <Calendar size={16} />
                 </Button>
                 <Button
                   variant="info"
                   size="sm"
                   title="Оплата"
                   style={{ width: '36px', height: '36px', padding: '0' }}
                 >
                   <CreditCard size={16} />
                 </Button>
               </div>
             </td>
           </tr>
          );
        })}

          {/* Реальные записи */}
          {appointments.map((appointment, index) => {
            const isActive = activeRow === appointment.id;
            // Определяем цвет фона для всей строки
            const rowBgColor = isActive 
              ? '#dbeafe' // Цвет для активной строки
              : (index % 2 === 0 ? '#fff' : '#f8f9fa'); // Чередующийся цвет
            const hoverBgColor = '#e3f2fd'; // Цвет при наведении

            return (
              <tr 
                key={appointment.id || `row-${index}`} 
                style={{
                  borderBottom: '1px solid #e9ecef',
                  backgroundColor: rowBgColor,
                  transition: 'background-color 0.2s'
                }}
                onMouseEnter={(e) => {
                  // Подсвечиваем всю строку при наведении
                  e.currentTarget.style.backgroundColor = hoverBgColor;
                  // Подсвечиваем все ячейки в строке
                  Array.from(e.currentTarget.querySelectorAll('td'))
                    .forEach(cell => {
                      cell.style.backgroundColor = hoverBgColor;
                      cell.style.setProperty('background-color', hoverBgColor, 'important');
                    });
                }}
                onMouseLeave={(e) => {
                  // Возвращаем правильный цвет для всей строки
                  e.currentTarget.style.backgroundColor = rowBgColor;
                  // Возвращаем правильный цвет для всех ячеек
                  Array.from(e.currentTarget.querySelectorAll('td'))
                    .forEach(cell => {
                      cell.style.backgroundColor = rowBgColor;
                      cell.style.setProperty('background-color', rowBgColor, 'important');
                    });
                }}
                onClick={() => setActiveRow(appointment.id)}
              >
                <td data-sticky="true" style={{
                  ...cellStickyStyle,
                  left: 0,
                  width: `${COL_WIDTHS.num}px`,
                  minWidth: `${COL_WIDTHS.num}px`,
                  backgroundColor: rowBgColor + ' !important', // <--- ИСПРАВЛЕНО
                  fontWeight: '500',
                  borderRight: '2px solid #dee2e6',
                  textAlign: 'center'
                }}>
                  {index + 1}
                </td>
                <td data-sticky="true" style={{
                  ...cellStickyStyle,
                  left: STICKY_POS.fio,
                  width: `${COL_WIDTHS.fio}px`,
                  minWidth: `${COL_WIDTHS.fio}px`,
                  backgroundColor: rowBgColor + ' !important', // <--- ИСПРАВЛЕНО
                  borderRight: '2px solid #dee2e6'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                 <input
                   type="checkbox"
                   checked={appointmentsSelected.has(appointment.id)}
                   onChange={(e)=>{
                     const next = new Set(appointmentsSelected);
                     if (e.target.checked) next.add(appointment.id); else next.delete(appointment.id);
                     setAppointmentsSelected(next);
                   }}
                   style={{ width: 'auto', margin: 0 }}
                 />
                 <span style={{
                   cursor: 'pointer',
                   fontWeight: '500',
                   color: '#007bff',
                   textDecoration: 'underline'
                 }}>
                   {appointment.patient_fio || `Пациент #${appointment.id}`}
                 </span>
               </div>
             </td>
             <td style={{ 
               padding: '12px', 
               textAlign: 'center', 
               backgroundColor: rowBgColor + ' !important'
             }}>
               {appointment.patient_birth_year || '-'}
             </td>
                <td data-sticky="true" style={{
                  ...cellStickyStyle,
                  left: STICKY_POS.phone,
                  width: `${COL_WIDTHS.phone}px`,
                  minWidth: `${COL_WIDTHS.phone}px`,
                  backgroundColor: rowBgColor + ' !important', // <--- ИСПРАВЛЕНО
                  fontFamily: 'Courier New, monospace',
                  borderRight: '2px solid #dee2e6'
                }}>
               {appointment.isEmpty ? '-' : (
                 <span style={{
                   cursor: 'pointer',
                   color: '#007bff'
                 }}>
                   {appointment.patient_phone || '-'}
                 </span>
               )}
             </td>

             <td style={{ 
               padding: '12px', 
               backgroundColor: rowBgColor + ' !important'
             }}>
               <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                 {(appointment.services || []).map((service, i) => (
                   <span
                     key={i}
                     style={{
                       ...getServiceStyle(service),
                       padding: '2px 6px',
                       borderRadius: '10px',
                       fontSize: '12px',
                       fontWeight: '500'
                     }}
                   >
                     {service}
                   </span>
                 ))}
                 {(!appointment.services || appointment.services.length === 0) && '-'}
               </div>
             </td>
             <td style={{ 
               padding: '12px', 
               textAlign: 'center', 
               backgroundColor: rowBgColor + ' !important'
             }}>
               <span style={{
                 ...getVisitTypeStyle(appointment.visit_type),
                 padding: '4px 8px',
                 borderRadius: '6px',
                 fontSize: '12px',
                 fontWeight: '500',
                 display: 'inline-block'
               }}>
                 {appointment.visit_type || 'Платный'}
               </span>
             </td>
             <td style={{ 
               padding: '12px', 
               textAlign: 'center', 
               backgroundColor: rowBgColor + ' !important'
             }}>
               <span style={{
                 ...getPaymentTypeStyle(appointment.payment_type),
                 padding: '4px 8px',
                 borderRadius: '6px',
                 fontSize: '12px',
                 fontWeight: '500',
                 display: 'inline-block'
               }}>
                 {appointment.payment_type || '-'}
               </span>
             </td>
             <td style={{
               padding: '12px',
               textAlign: 'right',
               fontWeight: '600',
               color: '#28a745',
               backgroundColor: rowBgColor + ' !important'
             }}>
               {appointment.cost ? `${appointment.cost.toLocaleString()} ₽` : '-'}
             </td>
             <td style={{ 
               padding: '12px', 
               textAlign: 'center', 
               backgroundColor: rowBgColor + ' !important'
             }}>
               <Badge 
                 variant={getStatusVariant(appointment.status)}
                 size="md"
                 style={{ minWidth: '80px' }}
               >
                 {appointment.status || 'scheduled'}
               </Badge>
             </td>
                <td data-sticky="true" style={{
                  ...cellStickyStyle,
                  right: 0,
                  width: `${COL_WIDTHS.actions}px`,
                  minWidth: `${COL_WIDTHS.actions}px`,
                  backgroundColor: rowBgColor + ' !important', // <--- ИСПРАВЛЕНО
                  boxShadow: '-2px 0 5px rgba(0,0,0,0.1)',
                  borderLeft: '2px solid #dee2e6',
                  textAlign: 'center'
                }}>
               <div style={{ display: 'flex', gap: '6px', justifyContent: 'center' }}>
                 <Button
                   variant="primary"
                   size="sm"
                   title="Печать талона"
                   style={{ width: '36px', height: '36px', padding: '0' }}
                 >
                   <Printer size={16} />
                 </Button>
                 <Button
                   variant="danger"
                   size="sm"
                   title="Отмена"
                   style={{ width: '36px', height: '36px', padding: '0' }}
                 >
                   <X size={16} />
                 </Button>
                 <Button
                   variant="warning"
                   size="sm"
                   title="Перенос"
                   style={{ width: '36px', height: '36px', padding: '0' }}
                 >
                   <Calendar size={16} />
                 </Button>
                 <Button
                   variant="info"
                   size="sm"
                   title="Оплата"
                   style={{ width: '36px', height: '36px', padding: '0' }}
                 >
                   <CreditCard size={16} />
                 </Button>
               </div>
             </td>
           </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export default AppointmentsTable;
