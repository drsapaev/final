import React from 'react';
import { Eye, Edit, Trash2, ChevronUp, ChevronDown } from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';

/**
 * Унифицированная медицинская таблица в стиле MediLab
 */
const MedicalTable = ({ 
  columns = [],
  data = [],
  onView,
  onEdit,
  onDelete,
  sortable = true,
  pagination = true,
  pageSize = 10,
  className = '',
  ...props 
}) => {
  const { isDark } = useTheme();
  const [sortField, setSortField] = React.useState('');
  const [sortDirection, setSortDirection] = React.useState('asc');
  const [currentPage, setCurrentPage] = React.useState(1);

  // Сортировка данных
  const sortedData = React.useMemo(() => {
    if (!sortField) return data;
    
    return [...data].sort((a, b) => {
      const aValue = a[sortField];
      const bValue = b[sortField];
      
      if (aValue < bValue) return sortDirection === 'asc' ? -1 : 1;
      if (aValue > bValue) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    });
  }, [data, sortField, sortDirection]);

  // Пагинация
  const paginatedData = React.useMemo(() => {
    if (!pagination) return sortedData;
    
    const startIndex = (currentPage - 1) * pageSize;
    const endIndex = startIndex + pageSize;
    return sortedData.slice(startIndex, endIndex);
  }, [sortedData, currentPage, pageSize, pagination]);

  const totalPages = Math.ceil(sortedData.length / pageSize);

  const handleSort = (field) => {
    if (!sortable) return;
    
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const renderSortIcon = (field) => {
    if (!sortable || sortField !== field) return null;
    
    return sortDirection === 'asc' ? 
      <ChevronUp className="h-4 w-4" /> : 
      <ChevronDown className="h-4 w-4" />;
  };

  const renderActionButtons = (row, index) => {
    const actions = [];
    
    if (onView) {
      actions.push(
        <button
          key="view"
          onClick={() => onView(row, index)}
          className="p-2 text-green-600 hover:bg-green-50 rounded-md transition-colors interactive-element hover-scale ripple-effect magnetic-hover focus-ring"
          title="View details"
        >
          <Eye className="h-4 w-4" />
        </button>
      );
    }
    
    if (onEdit) {
      actions.push(
        <button
          key="edit"
          onClick={() => onEdit(row, index)}
          className="p-2 text-blue-600 hover:bg-blue-50 rounded-md transition-colors interactive-element hover-scale ripple-effect magnetic-hover focus-ring"
          title="Edit"
        >
          <Edit className="h-4 w-4" />
        </button>
      );
    }
    
    if (onDelete) {
      actions.push(
        <button
          key="delete"
          onClick={() => onDelete(row, index)}
          className="p-2 text-red-600 hover:bg-red-50 rounded-md transition-colors interactive-element hover-scale ripple-effect magnetic-hover focus-ring"
          title="Delete"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      );
    }
    
    return actions.length > 0 ? (
      <div className="flex gap-1">
        {actions}
      </div>
    ) : null;
  };

  return (
    <div 
      className={`medical-table ${className}`}
      style={{
        backgroundColor: isDark ? '#1e293b' : '#ffffff',
        borderRadius: '8px',
        border: `1px solid ${isDark ? '#334155' : '#e2e8f0'}`,
        overflow: 'hidden',
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)'
      }}
      {...props}
    >
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead 
            style={{
              backgroundColor: isDark ? '#334155' : '#f8fafc'
            }}
          >
            <tr>
              {columns.map((column) => (
                <th
                  key={column.key}
                  className={`px-6 py-3 text-left text-xs font-medium uppercase tracking-wider ${
                    sortable ? 'cursor-pointer hover:bg-gray-100 interactive-element hover-lift ripple-effect magnetic-hover focus-ring' : ''
                  }`}
                  style={{
                    color: isDark ? '#f8fafc' : '#374151',
                    backgroundColor: isDark ? '#334155' : '#f8fafc'
                  }}
                  onClick={() => handleSort(column.key)}
                >
                  <div className="flex items-center gap-2">
                    {column.label}
                    {renderSortIcon(column.key)}
                  </div>
                </th>
              ))}
              {(onView || onEdit || onDelete) && (
                <th 
                  className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider"
                  style={{
                    color: isDark ? '#f8fafc' : '#374151',
                    backgroundColor: isDark ? '#334155' : '#f8fafc'
                  }}
                >
                  Actions
                </th>
              )}
            </tr>
          </thead>
          <tbody 
            className="divide-y"
            style={{
              backgroundColor: isDark ? '#1e293b' : '#ffffff',
              borderColor: isDark ? '#334155' : '#e2e8f0'
            }}
          >
            {paginatedData.map((row, index) => (
              <tr 
                key={index}
                className="hover:bg-gray-50 transition-colors interactive-element hover-lift ripple-effect magnetic-hover focus-ring"
                style={{
                  backgroundColor: isDark ? '#1e293b' : '#ffffff'
                }}
                onMouseEnter={(e) => {
                  e.target.style.backgroundColor = isDark ? '#475569' : '#f8fafc';
                }}
                onMouseLeave={(e) => {
                  e.target.style.backgroundColor = isDark ? '#1e293b' : '#ffffff';
                }}
              >
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className="px-6 py-4 whitespace-nowrap text-sm"
                    style={{ color: isDark ? '#f8fafc' : '#374151' }}
                  >
                    {column.render ? column.render(row[column.key], row, index) : row[column.key]}
                  </td>
                ))}
                {(onView || onEdit || onDelete) && (
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    {renderActionButtons(row, index)}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Пагинация */}
      {pagination && totalPages > 1 && (
        <div 
          className="px-6 py-3 border-t flex items-center justify-between"
          style={{
            backgroundColor: isDark ? '#1e293b' : '#ffffff',
            borderColor: isDark ? '#334155' : '#e2e8f0'
          }}
        >
          <div 
            className="text-sm"
            style={{ color: isDark ? '#94a3b8' : '#64748b' }}
          >
            Showing {((currentPage - 1) * pageSize) + 1} to {Math.min(currentPage * pageSize, sortedData.length)} of {sortedData.length} results
          </div>
          
          <div className="flex gap-2">
            <button
              onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
              disabled={currentPage === 1}
              className="px-3 py-1 text-sm border rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 interactive-element hover-lift ripple-effect magnetic-hover focus-ring"
              style={{
                color: isDark ? '#f8fafc' : '#374151',
                borderColor: isDark ? '#334155' : '#d1d5db',
                backgroundColor: isDark ? '#1e293b' : '#ffffff'
              }}
            >
              Previous
            </button>
            
            {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
              <button
                key={page}
                onClick={() => setCurrentPage(page)}
                className={`px-3 py-1 text-sm border rounded-md interactive-element hover-lift ripple-effect magnetic-hover focus-ring ${
                  page === currentPage ? 'bg-blue-500 text-white border-blue-500' : 'hover:bg-gray-50'
                }`}
                style={{
                  color: page === currentPage ? '#ffffff' : (isDark ? '#f8fafc' : '#374151'),
                  borderColor: page === currentPage ? '#3b82f6' : (isDark ? '#334155' : '#d1d5db'),
                  backgroundColor: page === currentPage ? '#3b82f6' : (isDark ? '#1e293b' : '#ffffff')
                }}
              >
                {page}
              </button>
            ))}
            
            <button
              onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
              disabled={currentPage === totalPages}
              className="px-3 py-1 text-sm border rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 interactive-element hover-lift ripple-effect magnetic-hover focus-ring"
              style={{
                color: isDark ? '#f8fafc' : '#374151',
                borderColor: isDark ? '#334155' : '#d1d5db',
                backgroundColor: isDark ? '#1e293b' : '#ffffff'
              }}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default MedicalTable;
