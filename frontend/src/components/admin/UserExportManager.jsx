import React, { useState, useEffect } from 'react';
import { 
  Users, 
  Download, 
  FileText, 
  Filter,
  Calendar,
  CheckCircle,
  XCircle,
  RefreshCw,
  Trash2,
  Eye,
  Settings,
  FileSpreadsheet,
  FileJson,
  FileText as FilePdf,
  File
} from 'lucide-react';
import { Card, Button, Badge, MacOSInput, MacOSSelect, MacOSCheckbox, Skeleton } from '../ui/macos';
import { toast } from 'react-toastify';
import { api } from '../../utils/api';

const UserExportManager = () => {
  // Состояние
  const [activeTab, setActiveTab] = useState('export');
  const [loading, setLoading] = useState(false);
  const [exportFiles, setExportFiles] = useState([]);
  
  // Форма экспорта
  const [exportForm, setExportForm] = useState({
    format: 'csv',
    fields: [],
    filters: {
      username: '',
      email: '',
      role: '',
      is_active: null,
      created_from: '',
      created_to: ''
    },
    include_profile: false,
    include_preferences: false,
    include_audit_logs: false
  });

  // Доступные поля для экспорта
  const availableFields = [
    { value: 'id', label: 'ID' },
    { value: 'username', label: 'Имя пользователя' },
    { value: 'email', label: 'Email' },
    { value: 'role', label: 'Роль' },
    { value: 'is_active', label: 'Активен' },
    { value: 'created_at', label: 'Дата создания' },
    { value: 'updated_at', label: 'Дата обновления' },
    { value: 'last_login', label: 'Последний вход' },
    { value: 'full_name', label: 'ФИО' },
    { value: 'phone', label: 'Телефон' },
    { value: 'birth_date', label: 'Дата рождения' },
    { value: 'gender', label: 'Пол' },
    { value: 'address', label: 'Адрес' }
  ];

  // Роли пользователей
  const userRoles = [
    { value: '', label: 'Все роли' },
    { value: 'Admin', label: 'Администратор' },
    { value: 'Doctor', label: 'Врач' },
    { value: 'Registrar', label: 'Регистратор' },
    { value: 'Patient', label: 'Пациент' },
    { value: 'Cashier', label: 'Кассир' },
    { value: 'Lab', label: 'Лаборант' }
  ];

  // Загрузка данных
  useEffect(() => {
    if (activeTab === 'files') {
      loadExportFiles();
    }
  }, [activeTab]);

  const loadExportFiles = async () => {
    setLoading(true);
    try {
      const response = await api.get('/user-management/users/export/files');
      setExportFiles(response.data.files || []);
    } catch (error) {
      console.error('Ошибка загрузки файлов экспорта:', error);
      toast.error('Ошибка загрузки файлов экспорта');
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async () => {
    setLoading(true);
    try {
      // Подготавливаем данные для экспорта
      const exportData = {
        format: exportForm.format,
        fields: exportForm.fields.length > 0 ? exportForm.fields : null,
        filters: Object.keys(exportForm.filters).reduce((acc, key) => {
          const value = exportForm.filters[key];
          if (value !== '' && value !== null) {
            acc[key] = value;
          }
          return acc;
        }, {}),
        include_profile: exportForm.include_profile,
        include_preferences: exportForm.include_preferences,
        include_audit_logs: exportForm.include_audit_logs
      };

      const response = await api.post('/user-management/users/export', exportData);
      
      if (response.data.success) {
        toast.success(response.data.message);
        // Переключаемся на вкладку файлов и обновляем список
        setActiveTab('files');
        setTimeout(() => {
          loadExportFiles();
        }, 2000); // Даем время на создание файла
      } else {
        toast.error(response.data.message);
      }
    } catch (error) {
      console.error('Ошибка экспорта:', error);
      toast.error(error.response?.data?.detail || 'Ошибка экспорта пользователей');
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (filename) => {
    try {
      const response = await api.get(`/user-management/users/export/download/${filename}`, {
        responseType: 'blob'
      });
      
      // Создаем ссылку для скачивания
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      
      toast.success(`Файл ${filename} скачан`);
    } catch (error) {
      console.error('Ошибка скачивания:', error);
      toast.error('Ошибка скачивания файла');
    }
  };

  const handleDeleteFile = async (filename) => {
    if (!confirm(`Удалить файл ${filename}?`)) return;
    
    try {
      await api.delete(`/user-management/users/export/files/${filename}`);
      toast.success(`Файл ${filename} удален`);
      loadExportFiles();
    } catch (error) {
      console.error('Ошибка удаления:', error);
      toast.error('Ошибка удаления файла');
    }
  };

  const handleFieldToggle = (field) => {
    setExportForm(prev => ({
      ...prev,
      fields: prev.fields.includes(field)
        ? prev.fields.filter(f => f !== field)
        : [...prev.fields, field]
    }));
  };

  const getFileIcon = (filename) => {
    if (filename.endsWith('.csv')) return <FileText style={{ width: '20px', height: '20px', color: 'var(--mac-success)' }} />;
    if (filename.endsWith('.xlsx')) return <FileSpreadsheet style={{ width: '20px', height: '20px', color: 'var(--mac-accent-blue)' }} />;
    if (filename.endsWith('.json')) return <FileJson style={{ width: '20px', height: '20px', color: 'var(--mac-warning)' }} />;
    if (filename.endsWith('.pdf')) return <FilePdf style={{ width: '20px', height: '20px', color: 'var(--mac-error)' }} />;
    return <File style={{ width: '20px', height: '20px', color: 'var(--mac-text-tertiary)' }} />;
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  // Стили
  const containerStyle = {
    padding: '24px',
    minHeight: '100vh',
    backgroundColor: 'var(--mac-bg-primary)'
  };

  const tabStyle = (isActive) => ({
    padding: '12px 16px',
    backgroundColor: isActive ? 'var(--mac-accent-blue)' : 'transparent',
    color: isActive ? 'white' : 'var(--mac-text-secondary)',
    border: 'none',
    borderRadius: 'var(--mac-radius-sm)',
    cursor: 'pointer',
    transition: 'all var(--mac-duration-normal) var(--mac-ease)',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontSize: 'var(--mac-font-size-sm)',
    fontWeight: isActive ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-normal)'
  });

  const renderExportTab = () => (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
      {/* Левая панель - настройки экспорта */}
      <Card style={{ padding: '24px' }}>
        <h3 style={{ 
          margin: '0 0 24px 0', 
          display: 'flex', 
          alignItems: 'center', 
          gap: '8px',
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--mac-text-primary)'
        }}>
          <Settings style={{ width: '20px', height: '20px' }} />
          Настройки экспорта
        </h3>

        {/* Формат экспорта */}
        <div style={{ marginBottom: '16px' }}>
          <label style={{ 
            display: 'block', 
            fontSize: 'var(--mac-font-size-sm)', 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-text-primary)', 
            marginBottom: '8px' 
          }}>
            Формат файла:
          </label>
          <MacOSSelect
            value={exportForm.format}
            onChange={(e) => setExportForm(prev => ({ ...prev, format: e.target.value }))}
            options={[
              { value: 'csv', label: 'CSV' },
              { value: 'excel', label: 'Excel (XLSX)' },
              { value: 'json', label: 'JSON' },
              { value: 'pdf', label: 'PDF' }
            ]}
            style={{ width: '100%' }}
          />
        </div>

        {/* Поля для экспорта */}
        <div style={{ marginBottom: '16px' }}>
          <label style={{ 
            display: 'block', 
            fontSize: 'var(--mac-font-size-sm)', 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-text-primary)', 
            marginBottom: '8px' 
          }}>
            Поля для экспорта (оставьте пустым для всех полей):
          </label>
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', 
            gap: '8px',
            marginTop: '8px',
            maxHeight: '200px',
            overflowY: 'auto',
            padding: '12px',
            border: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-sm)',
            backgroundColor: 'var(--mac-bg-secondary)'
          }}>
            {availableFields.map(field => (
              <label key={field.value} style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '8px', 
                cursor: 'pointer',
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-primary)'
              }}>
                <MacOSCheckbox
                  checked={exportForm.fields.includes(field.value)}
                  onChange={(checked) => {
                    if (checked) {
                      setExportForm(prev => ({ ...prev, fields: [...prev.fields, field.value] }));
                    } else {
                      setExportForm(prev => ({ ...prev, fields: prev.fields.filter(f => f !== field.value) }));
                    }
                  }}
                  style={{ marginRight: '8px' }}
                />
                <span>{field.label}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Дополнительные данные */}
        <div style={{ marginBottom: '16px' }}>
          <label style={{ 
            display: 'block', 
            fontSize: 'var(--mac-font-size-sm)', 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-text-primary)', 
            marginBottom: '8px' 
          }}>
            Дополнительные данные:
          </label>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '8px' }}>
            <label style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '8px', 
              cursor: 'pointer',
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-primary)'
            }}>
              <MacOSCheckbox
                checked={exportForm.include_profile}
                onChange={(checked) => setExportForm(prev => ({ ...prev, include_profile: checked }))}
                style={{ marginRight: '8px' }}
              />
              <span>Включить профили пользователей</span>
            </label>
            <label style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '8px', 
              cursor: 'pointer',
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-primary)'
            }}>
              <MacOSCheckbox
                checked={exportForm.include_preferences}
                onChange={(checked) => setExportForm(prev => ({ ...prev, include_preferences: checked }))}
                style={{ marginRight: '8px' }}
              />
              <span>Включить настройки пользователей</span>
            </label>
            <label style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '8px', 
              cursor: 'pointer',
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-primary)'
            }}>
              <MacOSCheckbox
                checked={exportForm.include_audit_logs}
                onChange={(checked) => setExportForm(prev => ({ ...prev, include_audit_logs: checked }))}
                style={{ marginRight: '8px' }}
              />
              <span>Включить журнал аудита</span>
            </label>
          </div>
        </div>
      </Card>

      {/* Правая панель - фильтры */}
      <Card style={{ padding: '24px' }}>
        <h3 style={{ 
          margin: '0 0 24px 0', 
          display: 'flex', 
          alignItems: 'center', 
          gap: '8px',
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--mac-text-primary)'
        }}>
          <Filter style={{ width: '20px', height: '20px' }} />
          Фильтры
        </h3>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '8px' 
            }}>
              Имя пользователя:
            </label>
            <MacOSInput
              placeholder="Поиск по имени пользователя"
              value={exportForm.filters.username}
              onChange={(e) => setExportForm(prev => ({
                ...prev,
                filters: { ...prev.filters, username: e.target.value }
              }))}
              style={{ width: '100%' }}
            />
          </div>

          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '8px' 
            }}>
              Email:
            </label>
            <MacOSInput
              placeholder="Поиск по email"
              value={exportForm.filters.email}
              onChange={(e) => setExportForm(prev => ({
                ...prev,
                filters: { ...prev.filters, email: e.target.value }
              }))}
              style={{ width: '100%' }}
            />
          </div>

          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '8px' 
            }}>
              Роль:
            </label>
            <MacOSSelect
              value={exportForm.filters.role}
              onChange={(e) => setExportForm(prev => ({
                ...prev,
                filters: { ...prev.filters, role: e.target.value }
              }))}
              options={userRoles}
              style={{ width: '100%' }}
            />
          </div>

          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '8px' 
            }}>
              Статус:
            </label>
            <MacOSSelect
              value={exportForm.filters.is_active === null ? '' : exportForm.filters.is_active.toString()}
              onChange={(e) => setExportForm(prev => ({
                ...prev,
                filters: { 
                  ...prev.filters, 
                  is_active: e.target.value === '' ? null : e.target.value === 'true'
                }
              }))}
              options={[
                { value: '', label: 'Все пользователи' },
                { value: 'true', label: 'Только активные' },
                { value: 'false', label: 'Только неактивные' }
              ]}
              style={{ width: '100%' }}
            />
          </div>

          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '8px' 
            }}>
              Дата создания (от):
            </label>
            <MacOSInput
              type="date"
              value={exportForm.filters.created_from}
              onChange={(e) => setExportForm(prev => ({
                ...prev,
                filters: { ...prev.filters, created_from: e.target.value }
              }))}
              style={{ width: '100%' }}
            />
          </div>

          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '8px' 
            }}>
              Дата создания (до):
            </label>
            <MacOSInput
              type="date"
              value={exportForm.filters.created_to}
              onChange={(e) => setExportForm(prev => ({
                ...prev,
                filters: { ...prev.filters, created_to: e.target.value }
              }))}
              style={{ width: '100%' }}
            />
          </div>
        </div>

        {/* Кнопка экспорта */}
        <div style={{ marginTop: '24px' }}>
          <Button
            onClick={handleExport}
            disabled={loading}
            style={{ width: '100%' }}
          >
            {loading ? (
              <>
                <RefreshCw style={{ width: '16px', height: '16px', animation: 'spin 1s linear infinite' }} />
                Экспорт...
              </>
            ) : (
              <>
                <Download style={{ width: '16px', height: '16px' }} />
                Запустить экспорт
              </>
            )}
          </Button>
        </div>
      </Card>
    </div>
  );

  const renderFilesTab = () => (
    <Card style={{ padding: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h3 style={{ 
          margin: 0, 
          display: 'flex', 
          alignItems: 'center', 
          gap: '8px',
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--mac-text-primary)'
        }}>
          <FileText style={{ width: '20px', height: '20px' }} />
          Файлы экспорта
        </h3>
        <Button onClick={loadExportFiles} disabled={loading}>
          <RefreshCw style={{ width: '16px', height: '16px' }} />
          Обновить
        </Button>
      </div>

      {loading ? (
        <div>
          <Skeleton height="60px" style={{ marginBottom: '8px' }} />
          <Skeleton height="60px" style={{ marginBottom: '8px' }} />
          <Skeleton height="60px" />
        </div>
      ) : exportFiles.length === 0 ? (
        <div style={{ 
          textAlign: 'center', 
          padding: '32px', 
          color: 'var(--mac-text-secondary)',
          fontSize: 'var(--mac-font-size-sm)'
        }}>
          <FileText style={{ width: '48px', height: '48px', marginBottom: '16px', color: 'var(--mac-text-tertiary)' }} />
          <p style={{ margin: 0 }}>Нет файлов экспорта</p>
          <p style={{ margin: '8px 0 0 0' }}>Создайте экспорт на вкладке "Экспорт"</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {exportFiles.map((file, index) => (
            <div
              key={index}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '16px',
                backgroundColor: 'var(--mac-bg-secondary)',
                borderRadius: 'var(--mac-radius-md)',
                border: '1px solid var(--mac-border)'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                {getFileIcon(file.filename)}
                <div>
                  <div style={{ 
                    fontWeight: 'var(--mac-font-weight-semibold)', 
                    fontSize: 'var(--mac-font-size-sm)',
                    color: 'var(--mac-text-primary)'
                  }}>
                    {file.filename}
                  </div>
                  <div style={{ 
                    fontSize: 'var(--mac-font-size-xs)', 
                    color: 'var(--mac-text-secondary)' 
                  }}>
                    Размер: {formatFileSize(file.size)} | 
                    Создан: {new Date(file.created_at).toLocaleString('ru-RU')}
                  </div>
                </div>
              </div>
              
              <div style={{ display: 'flex', gap: '8px' }}>
                <Button
                  size="sm"
                  onClick={() => handleDownload(file.filename)}
                >
                  <Download style={{ width: '14px', height: '14px' }} />
                  Скачать
                </Button>
                <Button
                  size="sm"
                  variant="danger"
                  onClick={() => handleDeleteFile(file.filename)}
                >
                  <Trash2 style={{ width: '14px', height: '14px' }} />
                  Удалить
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );

  return (
    <div style={containerStyle}>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ 
          margin: 0, 
          fontSize: 'var(--mac-font-size-2xl)', 
          fontWeight: 'var(--mac-font-weight-semibold)',
          color: 'var(--mac-text-primary)',
          display: 'flex',
          alignItems: 'center',
          gap: '12px'
        }}>
          <Users style={{ width: '32px', height: '32px' }} />
          Экспорт пользователей
        </h1>
        <p style={{ 
          margin: '8px 0 0 0', 
          color: 'var(--mac-text-secondary)',
          fontSize: 'var(--mac-font-size-sm)'
        }}>
          Экспорт данных пользователей в различных форматах
        </p>
      </div>

      {/* Табы */}
      <div style={{ 
        display: 'flex', 
        marginBottom: '24px'
      }}>
        <button
          onClick={() => setActiveTab('export')}
          style={{
            padding: '12px 20px',
            border: 'none',
            background: 'transparent',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            color: activeTab === 'export' ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)',
            fontWeight: activeTab === 'export' ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-normal)',
            fontSize: 'var(--mac-font-size-sm)',
            transition: 'all var(--mac-duration-normal) var(--mac-ease)',
            position: 'relative',
            marginBottom: '-1px'
          }}
          onMouseEnter={(e) => {
            if (activeTab !== 'export') {
              e.target.style.color = 'var(--mac-text-primary)';
            }
          }}
          onMouseLeave={(e) => {
            if (activeTab !== 'export') {
              e.target.style.color = 'var(--mac-text-secondary)';
            }
          }}
        >
          <Download style={{ 
            width: '16px', 
            height: '16px',
            color: activeTab === 'export' ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)'
          }} />
          Экспорт
          {activeTab === 'export' && (
            <div style={{
              position: 'absolute',
              bottom: '0',
              left: '0',
              right: '0',
              height: '3px',
              backgroundColor: 'var(--mac-accent-blue)',
              borderRadius: '2px 2px 0 0'
            }} />
          )}
        </button>
        <button
          onClick={() => setActiveTab('files')}
          style={{
            padding: '12px 20px',
            border: 'none',
            background: 'transparent',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            color: activeTab === 'files' ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)',
            fontWeight: activeTab === 'files' ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-normal)',
            fontSize: 'var(--mac-font-size-sm)',
            transition: 'all var(--mac-duration-normal) var(--mac-ease)',
            position: 'relative',
            marginBottom: '-1px'
          }}
          onMouseEnter={(e) => {
            if (activeTab !== 'files') {
              e.target.style.color = 'var(--mac-text-primary)';
            }
          }}
          onMouseLeave={(e) => {
            if (activeTab !== 'files') {
              e.target.style.color = 'var(--mac-text-secondary)';
            }
          }}
        >
          <FileText style={{ 
            width: '16px', 
            height: '16px',
            color: activeTab === 'files' ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)'
          }} />
          Файлы ({exportFiles.length})
          {activeTab === 'files' && (
            <div style={{
              position: 'absolute',
              bottom: '0',
              left: '0',
              right: '0',
              height: '3px',
              backgroundColor: 'var(--mac-accent-blue)',
              borderRadius: '2px 2px 0 0'
            }} />
          )}
        </button>
      </div>
      
      {/* Разделительная линия */}
      <div style={{ 
        borderBottom: '1px solid var(--mac-border)',
        marginBottom: '24px'
      }} />

      {/* Содержимое табов */}
      {activeTab === 'export' && renderExportTab()}
      {activeTab === 'files' && renderFilesTab()}
    </div>
  );
};

export default UserExportManager;
