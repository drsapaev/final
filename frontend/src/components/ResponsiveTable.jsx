import React, { useState } from 'react';
import { useBreakpoint } from '../hooks/useMediaQuery';
import { Button, Badge } from './ui';

const ResponsiveTable = ({
  data = [],
  columns = [],
  onRowClick,
  selectedRows = new Set(),
  onRowSelect,
  actions = [],
  className = '',
  style = {}
}) => {
  const { isMobile, isTablet } = useBreakpoint();
  const [sortField, setSortField] = useState(null);
  const [sortDirection, setSortDirection] = useState('asc');

  // Сортировка данных
  const sortedData = React.useMemo(() => {
    if (!sortField) return data;

    return [...data].sort((a, b) => {
      const aVal = a[sortField];
      const bVal = b[sortField];
      
      if (aVal < bVal) return sortDirection === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    });
  }, [data, sortField, sortDirection]);

  const handleSort = (field) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  // Мобильный вид - карточки
  if (isMobile) {
    return (
      <div className={`responsive-table-container ${className}`} style={style}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', padding: '16px' }}>
          {sortedData.map((row, index) => (
            <div
              key={index}
              style={{
                background: 'white',
                borderRadius: '12px',
                padding: '16px',
                boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                border: selectedRows.has(index) ? '2px solid #3b82f6' : '1px solid #e5e7eb',
                cursor: onRowClick ? 'pointer' : 'default'
              }}
              onClick={() => onRowClick?.(row, index)}
            >
              {/* Заголовок карточки */}
              <div style={{ 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'center',
                marginBottom: '12px'
              }}>
                <div style={{ fontWeight: '600', fontSize: '16px' }}>
                  {row.name || row.fio || `Запись ${index + 1}`}
                </div>
                {onRowSelect && (
                  <input
                    type="checkbox"
                    checked={selectedRows.has(index)}
                    onChange={(e) => onRowSelect(index, e.target.checked)}
                    style={{ transform: 'scale(1.2)' }}
                  />
                )}
              </div>

              {/* Основная информация */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {columns
                  .filter(col => !col.mobileHidden)
                  .map((column, colIndex) => (
                    <div key={colIndex} style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: '#6b7280', fontSize: '14px' }}>
                        {column.label}:
                      </span>
                      <span style={{ fontWeight: '500', fontSize: '14px' }}>
                        {column.render ? column.render(row[column.key], row) : row[column.key]}
                      </span>
                    </div>
                  ))}
              </div>

              {/* Действия */}
              {actions.length > 0 && (
                <div style={{ 
                  display: 'flex', 
                  gap: '8px', 
                  marginTop: '12px',
                  justifyContent: 'flex-end'
                }}>
                  {actions.map((action, actionIndex) => (
                    <Button
                      key={actionIndex}
                      variant={action.variant || 'primary'}
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        action.onClick(row, index);
                      }}
                      style={{ minWidth: 'auto' }}
                    >
                      {action.icon}
                    </Button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  }

  // Планшетный и десктопный вид - таблица
  return (
    <div className={`responsive-table-container ${className}`} style={style}>
      <table className="responsive-table" style={{ borderCollapse: 'collapse', width: '100%' }}>
        <thead>
          <tr style={{ background: '#f8fafc', borderBottom: '2px solid #e5e7eb' }}>
            {onRowSelect && (
              <th style={{ padding: '12px', textAlign: 'center', width: '50px' }}>
                <input
                  type="checkbox"
                  checked={selectedRows.size === data.length && data.length > 0}
                  onChange={(e) => {
                    data.forEach((_, index) => onRowSelect(index, e.target.checked));
                  }}
                />
              </th>
            )}
            {columns.map((column, index) => (
              <th
                key={index}
                style={{
                  padding: '12px',
                  textAlign: column.align || 'left',
                  fontWeight: '600',
                  fontSize: '14px',
                  color: '#374151',
                  cursor: column.sortable ? 'pointer' : 'default',
                  userSelect: 'none',
                  minWidth: column.minWidth || '120px'
                }}
                onClick={() => column.sortable && handleSort(column.key)}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  {column.label}
                  {column.sortable && (
                    <span style={{ fontSize: '12px', opacity: 0.6 }}>
                      {sortField === column.key ? (sortDirection === 'asc' ? '↑' : '↓') : '↕'}
                    </span>
                  )}
                </div>
              </th>
            ))}
            {actions.length > 0 && (
              <th style={{ padding: '12px', textAlign: 'center', width: '200px' }}>
                Действия
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {sortedData.map((row, index) => (
            <tr
              key={index}
              style={{
                borderBottom: '1px solid #e5e7eb',
                cursor: onRowClick ? 'pointer' : 'default',
                background: selectedRows.has(index) ? '#eff6ff' : 'white',
                transition: 'background-color 0.2s ease'
              }}
              onClick={() => onRowClick?.(row, index)}
              onMouseEnter={(e) => {
                if (!selectedRows.has(index)) {
                  e.target.style.background = '#f9fafb';
                }
              }}
              onMouseLeave={(e) => {
                if (!selectedRows.has(index)) {
                  e.target.style.background = 'white';
                }
              }}
            >
              {onRowSelect && (
                <td style={{ padding: '12px', textAlign: 'center' }}>
                  <input
                    type="checkbox"
                    checked={selectedRows.has(index)}
                    onChange={(e) => {
                      e.stopPropagation();
                      onRowSelect(index, e.target.checked);
                    }}
                  />
                </td>
              )}
              {columns.map((column, colIndex) => (
                <td
                  key={colIndex}
                  style={{
                    padding: '12px',
                    textAlign: column.align || 'left',
                    fontSize: '14px',
                    color: '#374151'
                  }}
                >
                  {column.render ? column.render(row[column.key], row) : row[column.key]}
                </td>
              ))}
              {actions.length > 0 && (
                <td style={{ padding: '12px', textAlign: 'center' }}>
                  <div style={{ display: 'flex', gap: '4px', justifyContent: 'center' }}>
                    {actions.map((action, actionIndex) => (
                      <Button
                        key={actionIndex}
                        variant={action.variant || 'primary'}
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          action.onClick(row, index);
                        }}
                        style={{ minWidth: 'auto' }}
                        title={action.title}
                      >
                        {action.icon}
                      </Button>
                    ))}
                  </div>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default ResponsiveTable;
