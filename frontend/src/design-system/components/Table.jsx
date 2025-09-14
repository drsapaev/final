/**
 * Унифицированный компонент Table
 * Согласно MASTER_TODO_LIST строка 218
 */
import React from 'react';
import { colors, typography, spacing, breakpoints } from '../theme';

const Table = ({
  columns = [],
  data = [],
  loading = false,
  error = null,
  emptyMessage = 'Нет данных',
  responsive = true,
  striped = true,
  hoverable = true,
  size = 'medium',
  variant = 'default',
  className = '',
  style = {},
  onRowClick,
  ...props
}) => {
  // Размеры
  const sizes = {
    small: {
      cellPadding: spacing.spacing[2],
      fontSize: typography.fontSizes.sm,
    },
    medium: {
      cellPadding: spacing.spacing[3],
      fontSize: typography.fontSizes.base,
    },
    large: {
      cellPadding: spacing.spacing[4],
      fontSize: typography.fontSizes.lg,
    },
  };

  // Варианты стилей
  const variants = {
    default: {
      border: `1px solid ${colors.neutral.gray[200]}`,
      borderRadius: '8px',
    },
    minimal: {
      border: 'none',
      borderRadius: '0',
    },
    elevated: {
      border: 'none',
      borderRadius: '12px',
      boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
    },
  };

  const sizeStyles = sizes[size];
  const variantStyles = variants[variant];

  const tableStyles = {
    width: '100%',
    borderCollapse: 'collapse',
    fontFamily: typography.fontFamilies.primary,
    fontSize: sizeStyles.fontSize,
    ...variantStyles,
    ...style,
  };

  const headerStyles = {
    backgroundColor: colors.neutral.gray[50],
    borderBottom: `2px solid ${colors.neutral.gray[200]}`,
  };

  const headerCellStyles = {
    padding: sizeStyles.cellPadding,
    textAlign: 'left',
    fontWeight: typography.fontWeights.semibold,
    color: colors.neutral.gray[700],
    fontSize: typography.fontSizes.sm,
    textTransform: 'uppercase',
    letterSpacing: typography.letterSpacings.wide,
  };

  const rowStyles = {
    borderBottom: `1px solid ${colors.neutral.gray[100]}`,
    transition: 'background-color 200ms ease',
    
    ...(striped && {
      '&:nth-child(even)': {
        backgroundColor: colors.neutral.gray[25],
      },
    }),
    
    ...(hoverable && {
      '&:hover': {
        backgroundColor: colors.brand.primary[50],
        cursor: onRowClick ? 'pointer' : 'default',
      },
    }),
  };

  const cellStyles = {
    padding: sizeStyles.cellPadding,
    color: colors.neutral.gray[900],
    verticalAlign: 'middle',
  };

  const loadingStyles = {
    textAlign: 'center',
    padding: spacing.spacing[8],
    color: colors.neutral.gray[500],
  };

  const errorStyles = {
    textAlign: 'center',
    padding: spacing.spacing[8],
    color: colors.brand.error[600],
    backgroundColor: colors.brand.error[50],
  };

  const emptyStyles = {
    textAlign: 'center',
    padding: spacing.spacing[8],
    color: colors.neutral.gray[500],
  };

  // Рендер загрузки
  if (loading) {
    return (
      <div style={loadingStyles}>
        <div>Загрузка данных...</div>
      </div>
    );
  }

  // Рендер ошибки
  if (error) {
    return (
      <div style={errorStyles}>
        <div>Ошибка: {error}</div>
      </div>
    );
  }

  // Рендер пустой таблицы
  if (!data || data.length === 0) {
    return (
      <div style={emptyStyles}>
        <div>{emptyMessage}</div>
      </div>
    );
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={tableStyles} className={className} {...props}>
        {/* Заголовок */}
        <thead style={headerStyles}>
          <tr>
            {columns.map((column, index) => (
              <th
                key={column.key || column.dataKey || index}
                style={{
                  ...headerCellStyles,
                  width: column.width,
                  minWidth: column.minWidth,
                  textAlign: column.align || 'left',
                }}
              >
                {column.title || column.label}
              </th>
            ))}
          </tr>
        </thead>
        
        {/* Тело таблицы */}
        <tbody>
          {data.map((row, rowIndex) => (
            <tr
              key={row.id || rowIndex}
              style={rowStyles}
              onClick={() => onRowClick && onRowClick(row, rowIndex)}
            >
              {columns.map((column, colIndex) => {
                const cellValue = column.render 
                  ? column.render(row[column.dataKey], row, rowIndex)
                  : row[column.dataKey];

                return (
                  <td
                    key={column.key || column.dataKey || colIndex}
                    style={{
                      ...cellStyles,
                      textAlign: column.align || 'left',
                    }}
                  >
                    {cellValue}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default Table;
