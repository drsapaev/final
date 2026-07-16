// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import React, { useState } from 'react';
import { useBreakpoint } from '../hooks/useEnhancedMediaQuery';
import { Button } from './ui';
import PropTypes from 'prop-types';
import { Checkbox } from './ui/macos';

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
  const { isMobile } = useBreakpoint();
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
  const handleActivationKeyDown = (event, onActivate) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onActivate();
    }
  };

  // Предварительно вычисляем оффсеты для фиксированных колонок (для планшета/десктопа)
  // Должно быть до любого условного return
  const visibleColumns = React.useMemo(() => columns.filter((c) => !c.hidden), [columns]);
  const selectionOffset = onRowSelect ? 50 : 0; // ширина колонки чекбокса
  const leftOffsets = React.useMemo(() => {
    let currentLeft = selectionOffset;
    return visibleColumns.map((col) => {
      const left = col.fixed ? currentLeft : null;
      const widthValue = typeof col.minWidth === 'string' ? parseInt(col.minWidth, 10) : col.minWidth || 120;
      if (col.fixed) currentLeft += widthValue;
      return left;
    });
  }, [visibleColumns, selectionOffset]);

  // Мобильный вид - карточки
  if (isMobile) {
    return (
      <div className={`responsive-table-container ${className}`} style={style}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-3)', padding: 'var(--mac-spacing-4)' }}>
          {sortedData.map((row, index) =>
          <div
            key={index}
            role="button"
            aria-disabled={!onRowClick}
            tabIndex={onRowClick ? 0 : -1}
            style={{
              background: 'white',
              borderRadius: 'var(--mac-radius-lg)',
              padding: 'var(--mac-spacing-4)',
              boxShadow: 'var(--mac-shadow-sm)',
              border: selectedRows.has(index) ? '2px solid var(--mac-accent-blue)' : '1px solid var(--mac-border)',
              cursor: onRowClick ? 'pointer' : 'default'
            }}
            onClick={() => onRowClick?.(row, index)}
            onKeyDown={onRowClick ? (event) => handleActivationKeyDown(event, () => onRowClick(row, index)) : undefined}>
            
              {/* Заголовок карточки */}
              <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 'var(--mac-spacing-3)'
            }}>
                <div style={{ fontWeight: 'var(--mac-font-weight-semibold)', fontSize: 'var(--mac-font-size-lg)' }}>
                  {row.name || row.fio || `Запись ${index + 1}`}
                </div>
                {onRowSelect &&
              <Checkbox aria-label={`Select ${row.name || row.fio || `record ${index + 1}`}`} checked={selectedRows.has(index)} onChange={(e) => onRowSelect(index, e.target.checked)}
                style={{ transform: 'scale(1.2)' }} />

              }
              </div>

              {/* Основная информация */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-2)' }}>
                {columns.
              filter((col) => !col.mobileHidden && !col.hidden).
              map((column, colIndex) => {
                // Получаем значение для отображения
                let displayValue;
                if (column.render) {
                  displayValue = column.render(row[column.key], row, index);
                } else {
                  displayValue = row[column.key];
                }

                // Проверяем на NaN и другие некорректные значения
                if (typeof displayValue === 'number' && isNaN(displayValue)) {
                  displayValue = '';
                }

                return (
                  <div key={colIndex} style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-base)' }}>
                          {column.label}:
                        </span>
                        <span style={{ fontWeight: 'var(--mac-font-weight-medium)', fontSize: 'var(--mac-font-size-base)' }}>
                          {displayValue}
                        </span>
                      </div>);

              })}
              </div>

              {/* Действия */}
              {actions.length > 0 &&
            <div style={{
              display: 'flex',
              gap: 'var(--mac-spacing-2)',
              marginTop: 'var(--mac-spacing-3)',
              justifyContent: 'flex-end'
            }}>
                  {actions.map((action, actionIndex) => {
                // Проверяем видимость действия
                if (action.visible && !action.visible(row)) {
                  return null;
                }

                return (
                  action.className ?
                  <button
                    key={actionIndex}
                    className={action.className}
                    style={action.style}
                    onClick={(e) => {e.stopPropagation();action.onClick(row, index);}}
                    title={action.title}>
                    
                          {action.icon || action.title}
                        </button> :

                  <Button
                    key={actionIndex}
                    variant={action.variant || 'primary'}
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      action.onClick(row, index);
                    }}
                    style={{ minWidth: 'auto', ...(action.style || {}) }}
                    title={action.title}>
                    
                          {action.icon}
                        </Button>);


              })}
                </div>
            }
            </div>
          )}
        </div>
      </div>);

  }

  // Планшетный и десктопный вид - таблица
  return (
    <div className={`responsive-table-container ${className}`} style={style}>
      {/* Отладочная информация */}
      
      <table className="responsive-table" style={{
        borderCollapse: 'collapse',
        width: '100%',
        position: 'relative'
      }}>
        <style>{`
          .responsive-table thead th {
            display: table-cell !important;
            visibility: visible !important;
            opacity: 1 !important;
            background: var(--mac-bg-secondary) !important;
            color: var(--mac-text-primary) !important;
            font-weight: 600 !important;
            font-size: 14px !important;
            padding: 12px !important;
            border-bottom: 2px solid var(--mac-border) !important;
            position: relative !important;
            z-index: 10 !important;
          }
          
          .responsive-table thead tr {
            display: table-row !important;
            visibility: visible !important;
            opacity: 1 !important;
            background: var(--mac-bg-secondary) !important;
          }
          
          .responsive-table thead {
            display: table-header-group !important;
            visibility: visible !important;
            opacity: 1 !important;
          }
        `}</style>
        <thead>
          <tr style={{
            background: 'var(--mac-bg-secondary)',
            borderBottom: '2px solid var(--mac-border)',
            position: 'relative',
            zIndex: 10
          }}>
            {onRowSelect &&
            <th style={{
              padding: 'var(--mac-spacing-3)',
              textAlign: 'center',
              width: '50px',
              background: 'var(--mac-bg-secondary) !important',
              position: 'sticky',
              top: 0,
              zIndex: 11,
              display: 'table-cell !important',
              visibility: 'visible !important',
              opacity: '1 !important',
              color: 'var(--mac-text-primary) !important'
            }} aria-label="Row selection">
                <Checkbox aria-label="Select all rows" checked={selectedRows.size === data.length && data.length > 0}
                onChange={(e) => {
                  data.forEach((_, index) => onRowSelect(index, e.target.checked));
                }} />
              
              </th>
            }
            {visibleColumns.map((column, index) => {
              return (
                <th
                  key={index}
                  style={{
                    padding: 'var(--mac-spacing-3)',
                    textAlign: column.align || 'left',
                    fontWeight: 'var(--mac-font-weight-semibold)',
                    fontSize: 'var(--mac-font-size-base)',
                    color: 'var(--mac-text-primary) !important',
                    cursor: column.sortable ? 'pointer' : 'default',
                    userSelect: 'none',
                    minWidth: column.minWidth || '120px',
                    background: 'var(--mac-bg-secondary) !important',
                    position: column.fixed ? 'sticky' : 'relative',
                    left: column.fixed ? leftOffsets[index] : 'auto',
                    top: 0,
                    zIndex: column.fixed ? 12 : 11,
                    borderBottom: '2px solid var(--mac-border)',
                    display: 'table-cell !important',
                    visibility: 'visible !important',
                    opacity: '1 !important'
                  }}
                  onClick={() => column.sortable && handleSort(column.key)}>
                  
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-1)' }}>
                    {column.label}
                    {column.sortable &&
                    <span style={{ fontSize: 'var(--mac-font-size-xs)', opacity: 0.6 }}>
                        {sortField === column.key ? sortDirection === 'asc' ? '↑' : '↓' : '↕'}
                      </span>
                    }
                  </div>
                </th>);

            })}
            {actions.length > 0 &&
            <th style={{
              padding: 'var(--mac-spacing-3)',
              textAlign: 'center',
              width: '200px',
              background: 'var(--mac-bg-secondary) !important',
              position: 'sticky',
              top: 0,
              zIndex: 11,
              borderBottom: '2px solid var(--mac-border)',
              display: 'table-cell !important',
              visibility: 'visible !important',
              opacity: '1 !important',
              color: 'var(--mac-text-primary) !important'
            }}>
                Действия
              </th>
            }
          </tr>
        </thead>
        <tbody>
          {sortedData.map((row, index) =>
          <tr
            key={index}
            style={{
              borderBottom: '1px solid var(--mac-border)',
              cursor: onRowClick ? 'pointer' : 'default',
              background: selectedRows.has(index) ? 'var(--mac-accent-bg)' : 'white',
              transition: 'background-color 0.2s ease'
            }}
            onClick={() => onRowClick?.(row, index)}
            onMouseEnter={(e) => {
              if (!selectedRows.has(index)) {
                e.target.style.background = 'var(--mac-bg-secondary)';
              }
            }}
            onMouseLeave={(e) => {
              if (!selectedRows.has(index)) {
                e.target.style.background = 'white';
              }
            }}>

              {onRowSelect &&
            <td style={{ padding: 'var(--mac-spacing-3)', textAlign: 'center' }} aria-label={`Select ${row.name || row.fio || `record ${index + 1}`}`}>
                  <Checkbox aria-label={`Select ${row.name || row.fio || `record ${index + 1}`}`} checked={selectedRows.has(index)} onChange={(e) => {
                  e.stopPropagation();
                  onRowSelect(index, e.target.checked);
                }} />
              
                </td>
            }
              {visibleColumns.map((column, colIndex) => {
              // Получаем значение для отображения
              let displayValue;
              if (column.render) {
                // Передаем три параметра: value, row, index
                displayValue = column.render(row[column.key], row, index);
              } else {
                displayValue = row[column.key];
              }

              // Проверяем на NaN и другие некорректные значения
              if (typeof displayValue === 'number' && isNaN(displayValue)) {
                displayValue = '';
              }

              // Обработка кликабельных колонок
              const handleClick = column.clickable && column.onClick ?
              (e) => {
                e.stopPropagation();
                column.onClick(row);
              } : undefined;

              return (
                <td
                  key={colIndex}
                  style={{
                    padding: 'var(--mac-spacing-3)',
                    textAlign: column.align || 'left',
                    fontSize: 'var(--mac-font-size-base)',
                    color: 'var(--mac-text-primary)',
                    cursor: column.clickable ? 'pointer' : 'inherit',
                    textDecoration: column.clickable ? 'underline' : 'none',
                    position: column.fixed ? 'sticky' : 'relative',
                    left: column.fixed ? leftOffsets[colIndex] : 'auto',
                    background: column.fixed ? 'white' : 'inherit',
                    zIndex: column.fixed ? 1 : 'auto'
                  }}
                  onClick={handleClick}>
                  
                    {displayValue}
                  </td>);

            })}
              {actions.length > 0 &&
            <td style={{ padding: 'var(--mac-spacing-3)', textAlign: 'center' }}>
                  <div style={{ display: 'flex', gap: 'var(--mac-spacing-1)', justifyContent: 'center' }}>
                    {actions.map((action, actionIndex) => {
                  // Проверяем видимость действия
                  if (action.visible && !action.visible(row)) {
                    return null;
                  }

                  return (
                    action.className ?
                    <button
                      key={actionIndex}
                      className={action.className}
                      style={action.style}
                      onClick={(e) => {e.stopPropagation();action.onClick(row, index);}}
                      title={action.title}>
                      
                            {action.icon || action.title}
                          </button> :

                    <Button
                      key={actionIndex}
                      variant={action.variant || 'primary'}
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        action.onClick(row, index);
                      }}
                      style={{ minWidth: 'auto', ...(action.style || {}) }}
                      title={action.title}>
                      
                            {action.icon}
                          </Button>);


                })}
                  </div>
                </td>
            }
            </tr>
          )}
        </tbody>
      </table>
    </div>);

};


ResponsiveTable.propTypes = {
  ...(ResponsiveTable.propTypes || {}),
  actions: PropTypes.any,
  className: PropTypes.any,
  columns: PropTypes.any,
  data: PropTypes.any,
  onRowClick: PropTypes.any,
  onRowSelect: PropTypes.any,
  selectedRows: PropTypes.any,
  style: PropTypes.any,
};

export default ResponsiveTable;
