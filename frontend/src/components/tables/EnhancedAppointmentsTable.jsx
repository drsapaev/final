import React, { useState, useMemo, useCallback } from 'react';
import { 
  Search, 
  Filter, 
  Download, 
  ChevronUp, 
  ChevronDown, 
  Calendar, 
  Clock, 
  User, 
  Phone, 
  CreditCard,
  FileText,
  MoreHorizontal,
  Eye,
  Edit,
  Trash2,
  CheckCircle,
  XCircle,
  AlertCircle
} from 'lucide-react';
import './EnhancedAppointmentsTable.css';

const EnhancedAppointmentsTable = ({ 
  data = [], 
  loading = false, 
  onRowClick, 
  onActionClick,
  theme = 'light',
  language = 'ru',
  selectedRows: externalSelectedRows,
  onRowSelect
}) => {
  const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' });
  const [filterConfig, setFilterConfig] = useState({
    search: '',
    status: '',
    dateFrom: '',
    dateTo: '',
    doctor: '',
    department: ''
  });
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  // Используем внешнее состояние, если передано, иначе внутреннее
  const [internalSelectedRows, setInternalSelectedRows] = useState(new Set());
  const selectedRows = externalSelectedRows || internalSelectedRows;

  const isDark = theme === 'dark';
  
  // Цвета для темы
  const colors = {
    bg: isDark ? '#1f2937' : '#ffffff',
    bgSecondary: isDark ? '#374151' : '#f9fafb',
    border: isDark ? '#4b5563' : '#e5e7eb',
    text: isDark ? '#f9fafb' : '#111827',
    textSecondary: isDark ? '#d1d5db' : '#6b7280',
    accent: '#3b82f6',
    success: '#10b981',
    warning: '#f59e0b',
    error: '#ef4444'
  };

  // Переводы
  const t = {
    ru: {
      search: 'Поиск',
      filter: 'Фильтр',
      export: 'Экспорт',
      selectAll: 'Выбрать все',
      selected: 'Выбрано',
      actions: 'Действия',
      noData: 'Нет данных',
      loading: 'Загрузка...',
      page: 'Страница',
      of: 'из',
      rows: 'строк',
      // Колонки
      number: '№',
      patient: 'Пациент',
      phone: 'Телефон',
      birthYear: 'Г.р.',
      services: 'Услуги',
      doctor: 'Врач',
      date: 'Дата',
      time: 'Время',
      status: 'Статус',
      cost: 'Стоимость',
      payment: 'Оплата',
      // Статусы
      scheduled: 'Запланирован',
      confirmed: 'Подтвержден',
      queued: 'В очереди',
      in_cabinet: 'В кабинете',
      done: 'Завершен',
      cancelled: 'Отменен',
      no_show: 'Неявка',
      paid_pending: 'Ожидает оплаты',
      paid: 'Оплачен'
    }
  }[language] || {};

  // Сортировка данных
  const sortedData = useMemo(() => {
    if (!sortConfig.key) return data;
    
    return [...data].sort((a, b) => {
      const aVal = a[sortConfig.key];
      const bVal = b[sortConfig.key];
      
      if (aVal < bVal) return sortConfig.direction === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortConfig.direction === 'asc' ? 1 : -1;
      return 0;
    });
  }, [data, sortConfig]);

  // Фильтрация данных
  const filteredData = useMemo(() => {
    return sortedData.filter(row => {
      const searchMatch = !filterConfig.search || 
        Object.values(row).some(val => 
          String(val).toLowerCase().includes(filterConfig.search.toLowerCase())
        );
      
      const statusMatch = !filterConfig.status || row.status === filterConfig.status;
      const doctorMatch = !filterConfig.doctor || row.doctor_id === parseInt(filterConfig.doctor);
      const departmentMatch = !filterConfig.department || row.department === filterConfig.department;
      
      return searchMatch && statusMatch && doctorMatch && departmentMatch;
    });
  }, [sortedData, filterConfig]);

  // Пагинация
  const paginatedData = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredData.slice(start, start + pageSize);
  }, [filteredData, currentPage, pageSize]);

  const totalPages = Math.ceil(filteredData.length / pageSize);

  // Обработчик сортировки
  const handleSort = useCallback((key) => {
    setSortConfig(prev => ({
      key,
      direction: prev.key === key && prev.direction === 'asc' ? 'desc' : 'asc'
    }));
  }, []);

  // Обработчик выбора строк
  const handleRowSelect = useCallback((id, checked) => {
    if (onRowSelect) {
      // Используем внешний обработчик
      onRowSelect(id, checked);
    } else {
      // Используем внутреннее состояние
      setInternalSelectedRows(prev => {
        const newSet = new Set(prev);
        if (checked) {
          newSet.add(id);
        } else {
          newSet.delete(id);
        }
        return newSet;
      });
    }
  }, [onRowSelect]);

  // Обработчик выбора всех строк
  const handleSelectAll = useCallback((checked) => {
    if (onRowSelect) {
      // Используем внешний обработчик для каждой строки
      paginatedData.forEach(row => {
        onRowSelect(row.id, checked);
      });
    } else {
      // Используем внутреннее состояние
      if (checked) {
        setInternalSelectedRows(new Set(paginatedData.map(row => row.id)));
      } else {
        setInternalSelectedRows(new Set());
      }
    }
  }, [paginatedData, onRowSelect]);

  // Рендер статуса
  const renderStatus = useCallback((status) => {
    const statusConfig = {
      scheduled: { color: colors.accent, bg: `${colors.accent}20`, icon: Calendar },
      confirmed: { color: colors.success, bg: `${colors.success}20`, icon: CheckCircle },
      queued: { color: colors.warning, bg: `${colors.warning}20`, icon: Clock },
      in_cabinet: { color: colors.accent, bg: `${colors.accent}20`, icon: User },
      done: { color: colors.success, bg: `${colors.success}20`, icon: CheckCircle },
      cancelled: { color: colors.error, bg: `${colors.error}20`, icon: XCircle },
      no_show: { color: colors.textSecondary, bg: `${colors.textSecondary}20`, icon: AlertCircle },
      paid_pending: { color: colors.warning, bg: `${colors.warning}20`, icon: CreditCard },
      paid: { color: colors.success, bg: `${colors.success}20`, icon: CheckCircle }
    };

    const config = statusConfig[status] || statusConfig.scheduled;
    const Icon = config.icon;

    return (
      <div 
        className="status-badge"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '4px',
          padding: '4px 8px',
          borderRadius: '6px',
          backgroundColor: config.bg,
          color: config.color,
          fontSize: '12px',
          fontWeight: '500'
        }}>
        <Icon size={12} />
        {t[status] || status}
      </div>
    );
  }, [colors, t]);

  // Рендер услуг
  const renderServices = useCallback((services) => {
    if (!Array.isArray(services)) return services;
    
    return (
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
        {services.slice(0, 2).map((service, idx) => (
          <span
            key={idx}
            style={{
              padding: '2px 6px',
              borderRadius: '4px',
              fontSize: '11px',
              backgroundColor: colors.bgSecondary,
              color: colors.textSecondary,
              border: `1px solid ${colors.border}`
            }}
          >
            {service}
          </span>
        ))}
        {services.length > 2 && (
          <span style={{ fontSize: '11px', color: colors.textSecondary }}>
            +{services.length - 2}
          </span>
        )}
      </div>
    );
  }, [colors]);

  // Экспорт данных
  const handleExport = useCallback(() => {
    const csvContent = [
      // Заголовки
      [t.number, t.patient, t.phone, t.birthYear, t.services, t.date, t.time, t.status, t.cost].join(','),
      // Данные
      ...filteredData.map((row, index) => [
        index + 1,
        row.patient_fio || '',
        row.patient_phone || '',
        row.patient_birth_year || '',
        Array.isArray(row.services) ? row.services.join('; ') : row.services || '',
        row.appointment_date || '',
        row.appointment_time || '',
        t[row.status] || row.status || '',
        row.cost || ''
      ].join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `appointments_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
  }, [filteredData, t]);

  if (loading) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '60px',
        color: colors.textSecondary
      }}>
        <div style={{ textAlign: 'center' }}>
          <div 
            className="loading-spinner"
            style={{
              width: '40px',
              height: '40px',
              border: `3px solid ${colors.border}`,
              borderTop: `3px solid ${colors.accent}`,
              borderRadius: '50%',
              margin: '0 auto 16px'
            }} />
          {t.loading}
        </div>
      </div>
    );
  }

  return (
    <div 
      className={`enhanced-table ${isDark ? 'dark-theme' : ''}`}
      style={{
        backgroundColor: colors.bg,
        border: `1px solid ${colors.border}`,
        borderRadius: '12px',
        overflow: 'hidden'
      }}>
      {/* Панель инструментов */}
      <div style={{
        padding: '16px',
        borderBottom: `1px solid ${colors.border}`,
        backgroundColor: colors.bgSecondary
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          flexWrap: 'wrap'
        }}>
          {/* Поиск */}
          <div style={{ position: 'relative', minWidth: '200px', flex: 1 }}>
            <Search 
              size={16} 
              style={{
                position: 'absolute',
                left: '12px',
                top: '50%',
                transform: 'translateY(-50%)',
                color: colors.textSecondary
              }}
            />
            <input
              type="text"
              placeholder={t.search}
              value={filterConfig.search}
              onChange={(e) => setFilterConfig(prev => ({ ...prev, search: e.target.value }))}
              style={{
                width: '100%',
                padding: '8px 12px 8px 36px',
                border: `1px solid ${colors.border}`,
                borderRadius: '6px',
                backgroundColor: colors.bg,
                color: colors.text,
                fontSize: '14px'
              }}
            />
          </div>

          {/* Фильтр по статусу */}
          <select
            value={filterConfig.status}
            onChange={(e) => setFilterConfig(prev => ({ ...prev, status: e.target.value }))}
            style={{
              padding: '8px 12px',
              border: `1px solid ${colors.border}`,
              borderRadius: '6px',
              backgroundColor: colors.bg,
              color: colors.text,
              fontSize: '14px'
            }}
          >
            <option value="">{t.filter}</option>
            <option value="scheduled">{t.scheduled}</option>
            <option value="confirmed">{t.confirmed}</option>
            <option value="queued">{t.queued}</option>
            <option value="in_cabinet">{t.in_cabinet}</option>
            <option value="done">{t.done}</option>
            <option value="cancelled">{t.cancelled}</option>
            <option value="paid_pending">{t.paid_pending}</option>
            <option value="paid">{t.paid}</option>
          </select>

          {/* Экспорт */}
          <button
            onClick={handleExport}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 12px',
              border: `1px solid ${colors.border}`,
              borderRadius: '6px',
              backgroundColor: colors.bg,
              color: colors.text,
              fontSize: '14px',
              cursor: 'pointer'
            }}
          >
            <Download size={16} />
            {t.export}
          </button>

          {/* Информация о выбранных */}
          {selectedRows.size > 0 && (
            <div style={{
              padding: '8px 12px',
              backgroundColor: colors.accent + '20',
              color: colors.accent,
              borderRadius: '6px',
              fontSize: '14px',
              fontWeight: '500'
            }}>
              {t.selected}: {selectedRows.size}
            </div>
          )}
        </div>
      </div>

      {/* Таблица */}
      <div style={{ overflowX: 'auto' }}>
        <table style={{
          width: '100%',
          borderCollapse: 'collapse'
        }}>
          <thead>
            <tr style={{ backgroundColor: colors.bgSecondary }}>
              {/* Чекбокс для выбора всех */}
              <th style={{
                padding: '12px 8px',
                textAlign: 'left',
                borderBottom: `1px solid ${colors.border}`,
                width: '40px'
              }}>
                <input
                  type="checkbox"
                  checked={selectedRows.size === paginatedData.length && paginatedData.length > 0}
                  onChange={(e) => handleSelectAll(e.target.checked)}
                  style={{ cursor: 'pointer' }}
                />
              </th>

              {/* Номер */}
              <th style={{
                padding: '12px 8px',
                textAlign: 'center',
                borderBottom: `1px solid ${colors.border}`,
                color: colors.text,
                fontWeight: '600',
                fontSize: '14px',
                width: '60px'
              }}>
                {t.number}
              </th>

              {/* Пациент */}
              <th 
                onClick={() => handleSort('patient_fio')}
                style={{
                  padding: '12px 8px',
                  textAlign: 'left',
                  borderBottom: `1px solid ${colors.border}`,
                  color: colors.text,
                  fontWeight: '600',
                  fontSize: '14px',
                  cursor: 'pointer',
                  minWidth: '200px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  {t.patient}
                  {sortConfig.key === 'patient_fio' && (
                    sortConfig.direction === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />
                  )}
                </div>
              </th>

              {/* Телефон */}
              <th style={{
                padding: '12px 8px',
                textAlign: 'left',
                borderBottom: `1px solid ${colors.border}`,
                color: colors.text,
                fontWeight: '600',
                fontSize: '14px',
                minWidth: '140px'
              }}>
                {t.phone}
              </th>

              {/* Год рождения */}
              <th 
                onClick={() => handleSort('patient_birth_year')}
                style={{
                  padding: '12px 8px',
                  textAlign: 'center',
                  borderBottom: `1px solid ${colors.border}`,
                  color: colors.text,
                  fontWeight: '600',
                  fontSize: '14px',
                  cursor: 'pointer',
                  width: '80px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center' }}>
                  {t.birthYear}
                  {sortConfig.key === 'patient_birth_year' && (
                    sortConfig.direction === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />
                  )}
                </div>
              </th>

              {/* Услуги */}
              <th style={{
                padding: '12px 8px',
                textAlign: 'left',
                borderBottom: `1px solid ${colors.border}`,
                color: colors.text,
                fontWeight: '600',
                fontSize: '14px',
                minWidth: '200px'
              }}>
                {t.services}
              </th>

              {/* Дата и время */}
              <th 
                onClick={() => handleSort('appointment_date')}
                style={{
                  padding: '12px 8px',
                  textAlign: 'center',
                  borderBottom: `1px solid ${colors.border}`,
                  color: colors.text,
                  fontWeight: '600',
                  fontSize: '14px',
                  cursor: 'pointer',
                  minWidth: '120px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center' }}>
                  {t.date}
                  {sortConfig.key === 'appointment_date' && (
                    sortConfig.direction === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />
                  )}
                </div>
              </th>

              {/* Статус */}
              <th 
                onClick={() => handleSort('status')}
                style={{
                  padding: '12px 8px',
                  textAlign: 'center',
                  borderBottom: `1px solid ${colors.border}`,
                  color: colors.text,
                  fontWeight: '600',
                  fontSize: '14px',
                  cursor: 'pointer',
                  minWidth: '130px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center' }}>
                  {t.status}
                  {sortConfig.key === 'status' && (
                    sortConfig.direction === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />
                  )}
                </div>
              </th>

              {/* Стоимость */}
              <th 
                onClick={() => handleSort('cost')}
                style={{
                  padding: '12px 8px',
                  textAlign: 'right',
                  borderBottom: `1px solid ${colors.border}`,
                  color: colors.text,
                  fontWeight: '600',
                  fontSize: '14px',
                  cursor: 'pointer',
                  minWidth: '100px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'flex-end' }}>
                  {t.cost}
                  {sortConfig.key === 'cost' && (
                    sortConfig.direction === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />
                  )}
                </div>
              </th>

              {/* Действия */}
              <th style={{
                padding: '12px 8px',
                textAlign: 'center',
                borderBottom: `1px solid ${colors.border}`,
                color: colors.text,
                fontWeight: '600',
                fontSize: '14px',
                width: '100px'
              }}>
                {t.actions}
              </th>
            </tr>
          </thead>
          <tbody>
            {paginatedData.length === 0 ? (
              <tr>
                <td 
                  colSpan="10" 
                  style={{
                    padding: '40px',
                    textAlign: 'center',
                    color: colors.textSecondary,
                    fontSize: '16px'
                  }}
                >
                  {t.noData}
                </td>
              </tr>
            ) : (
              paginatedData.map((row, index) => (
                <tr 
                  key={row.id}
                  className="enhanced-table-row"
                  style={{
                    backgroundColor: selectedRows.has(row.id) ? colors.accent + '10' : 'transparent',
                    borderBottom: `1px solid ${colors.border}`,
                    cursor: 'pointer'
                  }}
                  onMouseEnter={(e) => {
                    if (!selectedRows.has(row.id)) {
                      e.target.closest('tr').style.backgroundColor = colors.bgSecondary;
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!selectedRows.has(row.id)) {
                      e.target.closest('tr').style.backgroundColor = 'transparent';
                    }
                  }}
                  onClick={() => onRowClick?.(row)}
                >
                  {/* Чекбокс */}
                  <td style={{ padding: '12px 8px' }}>
                    <input
                      type="checkbox"
                      checked={selectedRows.has(row.id)}
                      onChange={(e) => {
                        e.stopPropagation();
                        handleRowSelect(row.id, e.target.checked);
                      }}
                      style={{ cursor: 'pointer' }}
                    />
                  </td>

                  {/* Номер */}
                  <td style={{
                    padding: '12px 8px',
                    textAlign: 'center',
                    color: colors.textSecondary,
                    fontSize: '14px'
                  }}>
                    {(currentPage - 1) * pageSize + index + 1}
                  </td>

                  {/* Пациент */}
                  <td style={{
                    padding: '12px 8px',
                    color: colors.text,
                    fontSize: '14px',
                    fontWeight: '500'
                  }}>
                    <div>
                      <div>{row.patient_fio || '—'}</div>
                      {row.patient_birth_year && (
                        <div style={{
                          fontSize: '12px',
                          color: colors.textSecondary,
                          marginTop: '2px'
                        }}>
                          {new Date().getFullYear() - row.patient_birth_year} лет
                        </div>
                      )}
                    </div>
                  </td>

                  {/* Телефон */}
                  <td style={{
                    padding: '12px 8px',
                    color: colors.text,
                    fontSize: '14px'
                  }}>
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px'
                    }}>
                      <Phone size={14} style={{ color: colors.textSecondary }} />
                      {row.patient_phone || '—'}
                    </div>
                  </td>

                  {/* Год рождения */}
                  <td style={{
                    padding: '12px 8px',
                    textAlign: 'center',
                    color: colors.text,
                    fontSize: '14px'
                  }}>
                    {row.patient_birth_year || '—'}
                  </td>

                  {/* Услуги */}
                  <td style={{ padding: '12px 8px' }}>
                    {renderServices(row.services)}
                  </td>

                  {/* Дата и время */}
                  <td style={{
                    padding: '12px 8px',
                    textAlign: 'center',
                    color: colors.text,
                    fontSize: '14px'
                  }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center' }}>
                        <Calendar size={12} style={{ color: colors.textSecondary }} />
                        {row.appointment_date || '—'}
                      </div>
                      {row.appointment_time && (
                        <div style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                          justifyContent: 'center',
                          marginTop: '2px',
                          fontSize: '12px',
                          color: colors.textSecondary
                        }}>
                          <Clock size={10} />
                          {row.appointment_time}
                        </div>
                      )}
                    </div>
                  </td>

                  {/* Статус */}
                  <td style={{
                    padding: '12px 8px',
                    textAlign: 'center'
                  }}>
                    {renderStatus(row.status)}
                  </td>

                  {/* Стоимость */}
                  <td style={{
                    padding: '12px 8px',
                    textAlign: 'right',
                    color: colors.success,
                    fontSize: '14px',
                    fontWeight: '600'
                  }}>
                    {row.cost ? `${row.cost.toLocaleString()} ₽` : '—'}
                  </td>

                  {/* Действия */}
                  <td style={{
                    padding: '12px 8px',
                    textAlign: 'center'
                  }}>
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '4px',
                      flexWrap: 'wrap'
                    }}>
                      {/* Оплата */}
                      {(row.status === 'paid_pending' || row.payment_status === 'pending') && (
                        <button
                          className="action-button"
                          onMouseDown={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            onActionClick?.('payment', row, e);
                          }}
                          style={{
                            padding: '4px 8px',
                            border: 'none',
                            borderRadius: '4px',
                            backgroundColor: colors.success,
                            color: 'white',
                            cursor: 'pointer',
                            fontSize: '12px',
                            fontWeight: '500'
                          }}
                          title="Оплата"
                        >
                          💳 Оплата
                        </button>
                      )}
                      
                      {/* В кабинет */}
                      {(row.status === 'confirmed' || row.status === 'queued') && (
                        <button
                          className="action-button"
                          onMouseDown={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            onActionClick?.('in_cabinet', row, e);
                          }}
                          style={{
                            padding: '4px 8px',
                            border: `1px solid ${colors.primary}`,
                            borderRadius: '4px',
                            backgroundColor: 'transparent',
                            color: colors.primary,
                            cursor: 'pointer',
                            fontSize: '12px',
                            fontWeight: '500'
                          }}
                          title="В кабинет"
                        >
                          🚪 В кабинет
                        </button>
                      )}
                      
                      {/* Вызвать */}
                      {row.status === 'queued' && (
                        <button
                          className="action-button"
                          onMouseDown={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            onActionClick?.('call', row, e);
                          }}
                          style={{
                            padding: '4px 8px',
                            border: 'none',
                            borderRadius: '4px',
                            backgroundColor: colors.success,
                            color: 'white',
                            cursor: 'pointer',
                            fontSize: '12px',
                            fontWeight: '500'
                          }}
                          title="Вызвать"
                        >
                          📢 Вызвать
                        </button>
                      )}
                      
                      {/* Печать */}
                      {(row.payment_status === 'paid' || row.status === 'queued') && (
                        <button
                          className="action-button"
                          onMouseDown={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            onActionClick?.('print', row, e);
                          }}
                          style={{
                            padding: '4px',
                            border: 'none',
                            borderRadius: '4px',
                            backgroundColor: 'transparent',
                            color: colors.primary,
                            cursor: 'pointer',
                            pointerEvents: 'auto'
                          }}
                          title="Печать"
                        >
                          <FileText size={14} />
                        </button>
                      )}
                      
                      {/* Завершить */}
                      {row.status === 'in_cabinet' && (
                        <button
                          className="action-button"
                          onMouseDown={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            onActionClick?.('complete', row, e);
                          }}
                          style={{
                            padding: '4px 8px',
                            border: 'none',
                            borderRadius: '4px',
                            backgroundColor: colors.success,
                            color: 'white',
                            cursor: 'pointer',
                            fontSize: '12px',
                            fontWeight: '500'
                          }}
                          title="Завершить"
                        >
                          ✅ Завершить
                        </button>
                      )}
                      
                      {/* Просмотр */}
                      <button
                        className="action-button"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          onActionClick?.('view', row, e);
                        }}
                        style={{
                          padding: '4px',
                          border: 'none',
                          borderRadius: '4px',
                          backgroundColor: 'transparent',
                          color: colors.textSecondary,
                          cursor: 'pointer',
                          pointerEvents: 'auto'
                        }}
                        title="Просмотр"
                      >
                        <Eye size={14} />
                      </button>
                      
                      {/* Еще */}
                      <button
                        className="action-button"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          onActionClick?.('more', row, e);
                        }}
                        style={{
                          padding: '4px',
                          border: 'none',
                          borderRadius: '4px',
                          backgroundColor: 'transparent',
                          color: colors.textSecondary,
                          cursor: 'pointer',
                          pointerEvents: 'auto'
                        }}
                        title="Еще"
                      >
                        <MoreHorizontal size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Пагинация */}
      {totalPages > 1 && (
        <div style={{
          padding: '16px',
          borderTop: `1px solid ${colors.border}`,
          backgroundColor: colors.bgSecondary,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'between',
          gap: '16px',
          flexWrap: 'wrap'
        }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            color: colors.textSecondary,
            fontSize: '14px'
          }}>
            <span>{t.page}</span>
            <select
              value={currentPage}
              onChange={(e) => setCurrentPage(parseInt(e.target.value))}
              style={{
                padding: '4px 8px',
                border: `1px solid ${colors.border}`,
                borderRadius: '4px',
                backgroundColor: colors.bg,
                color: colors.text,
                fontSize: '14px'
              }}
            >
              {Array.from({ length: totalPages }, (_, i) => (
                <option key={i + 1} value={i + 1}>
                  {i + 1}
                </option>
              ))}
            </select>
            <span>{t.of} {totalPages}</span>
          </div>

          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            color: colors.textSecondary,
            fontSize: '14px'
          }}>
            <span>Показано: {paginatedData.length} из {filteredData.length}</span>
          </div>

          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <button
              className="pagination-button"
              onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
              disabled={currentPage === 1}
              style={{
                padding: '6px 12px',
                border: `1px solid ${colors.border}`,
                borderRadius: '6px',
                backgroundColor: colors.bg,
                color: currentPage === 1 ? colors.textSecondary : colors.text,
                fontSize: '14px',
                cursor: currentPage === 1 ? 'not-allowed' : 'pointer'
              }}
            >
              Назад
            </button>
            <button
              className="pagination-button"
              onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
              disabled={currentPage === totalPages}
              style={{
                padding: '6px 12px',
                border: `1px solid ${colors.border}`,
                borderRadius: '6px',
                backgroundColor: colors.bg,
                color: currentPage === totalPages ? colors.textSecondary : colors.text,
                fontSize: '14px',
                cursor: currentPage === totalPages ? 'not-allowed' : 'pointer'
              }}
            >
              Далее
            </button>
          </div>
        </div>
      )}

    </div>
  );
};

export default EnhancedAppointmentsTable;
