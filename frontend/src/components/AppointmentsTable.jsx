import React from 'react';

const AppointmentsTable = ({ 
  appointments = [], 
  appointmentsSelected = new Set(),
  setAppointmentsSelected,
  updateAppointmentStatus,
  setShowWizard 
}) => {
  // Показывать ли пустые строки (можно сделать настраиваемым)
  const showEmptyRows = true;
  const emptyRowsCount = 10;
  const buttonStyle = {
    width: '32px',
    height: '32px',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '14px',
    transition: 'all 0.2s'
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

  // Стили для типов обращения
  const getVisitTypeStyle = (type) => {
    const typeStyles = {
      'paid': { background: '#e8f5e8', color: '#388e3c' },
      'repeat': { background: '#e3f2fd', color: '#1976d2' },
      'free': { background: '#fff3e0', color: '#f57c00' }
    };
    return typeStyles[type] || { background: '#e9ecef', color: '#495057' };
  };

  // Стили для способов оплаты
  const getPaymentTypeStyle = (type) => {
    const paymentStyles = {
      'cash': { background: '#e8f5e8', color: '#388e3c' },
      'card': { background: '#e3f2fd', color: '#1976d2' },
      'online': { background: '#fff3e0', color: '#f57c00' }
    };
    return paymentStyles[type] || { background: '#e9ecef', color: '#495057' };
  };

  // Стили для услуг
  const getServiceStyle = (service) => {
    const serviceStyles = {
      'derm': { background: '#e3f2fd', color: '#1976d2' },
      'cosmetology': { background: '#fce4ec', color: '#c2185b' },
      'cardio': { background: '#ffebee', color: '#d32f2f' },
      'ecg': { background: '#e8f5e8', color: '#388e3c' },
      'echo': { background: '#fff3e0', color: '#f57c00' },
      'stomatology': { background: '#f3e5f5', color: '#7b1fa2' },
      'lab': { background: '#e0f2f1', color: '#00695c' }
    };
    return serviceStyles[service] || { background: '#e9ecef', color: '#495057' };
  };

  return (
    <div style={{ overflowX: 'auto', overflowY: 'auto', maxHeight: 'calc(100vh - 350px)' }}>
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
             zIndex: 500
           }}>
                         <th style={{ 
               padding: '15px 12px', 
               textAlign: 'left', 
               fontWeight: '500',
               position: 'sticky',
               left: 0,
               zIndex: 600,
               minWidth: '60px',
               background: 'linear-gradient(135deg, #495057 0%, #6c757d 100%)',
               boxShadow: '2px 0 5px rgba(0,0,0,0.1)',
               borderRight: '2px solid #495057'
             }}>№</th>
                         <th style={{ 
               padding: '15px 12px', 
               textAlign: 'left', 
               fontWeight: '500',
               position: 'sticky',
               left: '60px',
               zIndex: 600,
               minWidth: '200px',
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
               left: '260px',
               zIndex: 600,
               minWidth: '140px',
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
               zIndex: 600,
               minWidth: '140px',
               background: 'linear-gradient(135deg, #495057 0%, #6c757d 100%)',
               boxShadow: '-2px 0 5px rgba(0,0,0,0.1)',
               borderLeft: '2px solid #495057'
             }}>Действия</th>
          </tr>
        </thead>
        <tbody>
          {/* Пустые строки для начала рабочего дня */}
          {showEmptyRows && Array.from({ length: emptyRowsCount }, (_, i) => (
            <tr key={`empty-${i}`} style={{ 
              borderBottom: '1px solid #e9ecef',
              backgroundColor: i % 2 === 0 ? '#fff' : '#f8f9fa',
              transition: 'background-color 0.2s'
            }}>
                             <td style={{ 
                 padding: '12px', 
                 textAlign: 'center', 
                 position: 'sticky',
                 left: 0,
                 zIndex: 550,
                 background: i % 2 === 0 ? '#fff' : '#f8f9fa',
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
                 left: '60px',
                 zIndex: 550,
                 background: i % 2 === 0 ? '#fff' : '#f8f9fa',
                 color: '#6c757d',
                 fontStyle: 'italic',
                 boxShadow: '2px 0 5px rgba(0,0,0,0.1)',
                 borderRight: '2px solid #dee2e6'
               }}>
                <span style={{ color: '#6c757d', fontStyle: 'italic' }}>Ожидает записи...</span>
              </td>
              <td style={{ padding: '12px', textAlign: 'center', color: '#6c757d' }}>
                -
              </td>
                             <td style={{ 
                 padding: '12px', 
                 position: 'sticky',
                 left: '260px',
                 zIndex: 550,
                 background: i % 2 === 0 ? '#fff' : '#f8f9fa',
                 color: '#6c757d',
                 boxShadow: '2px 0 5px rgba(0,0,0,0.1)',
                 borderRight: '2px solid #dee2e6'
               }}>
                -
              </td>
              <td style={{ padding: '12px', color: '#6c757d' }}>
                -
              </td>
              <td style={{ padding: '12px', textAlign: 'center', color: '#6c757d' }}>
                -
              </td>
              <td style={{ padding: '12px', textAlign: 'center', color: '#6c757d' }}>
                -
              </td>
              <td style={{ 
                padding: '12px', 
                textAlign: 'right',
                color: '#6c757d'
              }}>
                -
              </td>
              <td style={{ padding: '12px', textAlign: 'center', color: '#6c757d' }}>
                -
              </td>
                             <td style={{ 
                 padding: '12px', 
                 textAlign: 'center',
                 position: 'sticky',
                 right: 0,
                 zIndex: 550,
                 background: i % 2 === 0 ? '#fff' : '#f8f9fa',
                 color: '#6c757d',
                 boxShadow: '-2px 0 5px rgba(0,0,0,0.1)',
                 borderLeft: '2px solid #dee2e6'
               }}>
                -
              </td>
            </tr>
          ))}

          {/* Реальные записи */}
          {appointments.map((appointment, index) => (
            <tr key={appointment.id || `row-${index}`} style={{ 
              borderBottom: '1px solid #e9ecef',
              backgroundColor: index % 2 === 0 ? '#fff' : '#f8f9fa',
              transition: 'background-color 0.2s'
            }}
            onMouseEnter={(e) => {
              e.target.closest('tr').style.backgroundColor = '#e3f2fd';
            }}
            onMouseLeave={(e) => {
              e.target.closest('tr').style.backgroundColor = index % 2 === 0 ? '#fff' : '#f8f9fa';
            }}>
                             <td style={{ 
                 padding: '12px', 
                 textAlign: 'center', 
                 position: 'sticky',
                 left: 0,
                 zIndex: 550,
                 background: index % 2 === 0 ? '#fff' : '#f8f9fa',
                 fontWeight: '500',
                 boxShadow: '2px 0 5px rgba(0,0,0,0.1)',
                 borderRight: '2px solid #dee2e6'
               }}>
                 {index + 1}
               </td>
                             <td style={{ 
                 padding: '12px', 
                 position: 'sticky',
                 left: '60px',
                 zIndex: 550,
                 background: index % 2 === 0 ? '#fff' : '#f8f9fa',
                 boxShadow: '2px 0 5px rgba(0,0,0,0.1)',
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
              <td style={{ padding: '12px', textAlign: 'center' }}>
                {appointment.patient_birth_year || '-'}
              </td>
                             <td style={{ 
                 padding: '12px', 
                 position: 'sticky',
                 left: '260px',
                 zIndex: 550,
                 background: index % 2 === 0 ? '#fff' : '#f8f9fa',
                 fontFamily: 'Courier New, monospace',
                 boxShadow: '2px 0 5px rgba(0,0,0,0.1)',
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

              <td style={{ padding: '12px' }}>
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
              <td style={{ padding: '12px', textAlign: 'center' }}>
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
              <td style={{ padding: '12px', textAlign: 'center' }}>
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
                color: '#28a745'
              }}>
                {appointment.cost ? `${appointment.cost.toLocaleString()} ₽` : '-'}
              </td>
              <td style={{ padding: '12px', textAlign: 'center' }}>
                <span style={{
                  ...getStatusStyle(appointment.status),
                  padding: '4px 8px',
                  borderRadius: '12px',
                  fontSize: '12px',
                  fontWeight: '500',
                  display: 'inline-block',
                  minWidth: '80px'
                }}>
                  {appointment.status || 'scheduled'}
                </span>
              </td>
                             <td style={{ 
                 padding: '12px', 
                 textAlign: 'center',
                 position: 'sticky',
                 right: 0,
                 zIndex: 550,
                 background: index % 2 === 0 ? '#fff' : '#f8f9fa',
                 boxShadow: '-2px 0 5px rgba(0,0,0,0.1)',
                 borderLeft: '2px solid #dee2e6'
               }}>
                <div style={{ display: 'flex', gap: '4px', justifyContent: 'center' }}>
                  <button 
                    style={{...buttonStyle, backgroundColor: '#007bff'}} 
                    title="Печать талона"
                  >
                    🖨️
                  </button>
                  <button 
                    style={{...buttonDangerStyle}} 
                    title="Отмена"
                  >
                    ❌
                  </button>
                  <button 
                    style={{...buttonWarningStyle}} 
                    title="Перенос"
                  >
                    📅
                  </button>
                  <button 
                    style={{...buttonInfoStyle}} 
                    title="Оплата"
                  >
                    💳
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default AppointmentsTable;
