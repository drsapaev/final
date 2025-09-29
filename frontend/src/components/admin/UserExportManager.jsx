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
import { Card, Button, Badge, Input, Select, Label, Skeleton } from '../ui/native';
import { useTheme } from '../../contexts/ThemeContext';
import { toast } from 'react-toastify';
import api from '../../utils/api';

const UserExportManager = () => {
  const { theme, getColor, getSpacing } = useTheme();
  
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
    if (filename.endsWith('.csv')) return <FileText size={20} color={getColor('green', 600)} />;
    if (filename.endsWith('.xlsx')) return <FileSpreadsheet size={20} color={getColor('blue', 600)} />;
    if (filename.endsWith('.json')) return <FileJson size={20} color={getColor('orange', 600)} />;
    if (filename.endsWith('.pdf')) return <FilePdf size={20} color={getColor('red', 600)} />;
    return <File size={20} color={getColor('gray', 600)} />;
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
    padding: getSpacing('lg'),
    minHeight: '100vh',
    backgroundColor: theme === 'light' ? getColor('gray', 50) : getColor('gray', 900)
  };

  const tabStyle = (isActive) => ({
    padding: `${getSpacing('sm')} ${getSpacing('md')}`,
    backgroundColor: isActive 
      ? (theme === 'light' ? getColor('blue', 500) : getColor('blue', 600))
      : 'transparent',
    color: isActive 
      ? 'white' 
      : (theme === 'light' ? getColor('gray', 700) : getColor('gray', 300)),
    border: 'none',
    borderRadius: '8px',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    display: 'flex',
    alignItems: 'center',
    gap: getSpacing('xs')
  });

  const renderExportTab = () => (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: getSpacing('lg') }}>
      {/* Левая панель - настройки экспорта */}
      <Card style={{ padding: getSpacing('lg') }}>
        <h3 style={{ margin: `0 0 ${getSpacing('lg')} 0`, display: 'flex', alignItems: 'center', gap: getSpacing('xs') }}>
          <Settings size={20} />
          Настройки экспорта
        </h3>

        {/* Формат экспорта */}
        <div style={{ marginBottom: getSpacing('md') }}>
          <Label>Формат файла:</Label>
          <Select
            value={exportForm.format}
            onChange={(e) => setExportForm(prev => ({ ...prev, format: e.target.value }))}
          >
            <option value="csv">CSV</option>
            <option value="excel">Excel (XLSX)</option>
            <option value="json">JSON</option>
            <option value="pdf">PDF</option>
          </Select>
        </div>

        {/* Поля для экспорта */}
        <div style={{ marginBottom: getSpacing('md') }}>
          <Label>Поля для экспорта (оставьте пустым для всех полей):</Label>
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', 
            gap: getSpacing('xs'),
            marginTop: getSpacing('sm'),
            maxHeight: '200px',
            overflowY: 'auto',
            padding: getSpacing('sm'),
            border: `1px solid ${theme === 'light' ? getColor('gray', 300) : getColor('gray', 600)}`,
            borderRadius: '6px'
          }}>
            {availableFields.map(field => (
              <label key={field.value} style={{ display: 'flex', alignItems: 'center', gap: getSpacing('xs'), cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={exportForm.fields.includes(field.value)}
                  onChange={() => handleFieldToggle(field.value)}
                />
                <span style={{ fontSize: '0.875rem' }}>{field.label}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Дополнительные данные */}
        <div style={{ marginBottom: getSpacing('md') }}>
          <Label>Дополнительные данные:</Label>
          <div style={{ display: 'flex', flexDirection: 'column', gap: getSpacing('xs'), marginTop: getSpacing('sm') }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: getSpacing('xs'), cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={exportForm.include_profile}
                onChange={(e) => setExportForm(prev => ({ ...prev, include_profile: e.target.checked }))}
              />
              <span>Включить профили пользователей</span>
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: getSpacing('xs'), cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={exportForm.include_preferences}
                onChange={(e) => setExportForm(prev => ({ ...prev, include_preferences: e.target.checked }))}
              />
              <span>Включить настройки пользователей</span>
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: getSpacing('xs'), cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={exportForm.include_audit_logs}
                onChange={(e) => setExportForm(prev => ({ ...prev, include_audit_logs: e.target.checked }))}
              />
              <span>Включить журнал аудита</span>
            </label>
          </div>
        </div>
      </Card>

      {/* Правая панель - фильтры */}
      <Card style={{ padding: getSpacing('lg') }}>
        <h3 style={{ margin: `0 0 ${getSpacing('lg')} 0`, display: 'flex', alignItems: 'center', gap: getSpacing('xs') }}>
          <Filter size={20} />
          Фильтры
        </h3>

        <div style={{ display: 'flex', flexDirection: 'column', gap: getSpacing('md') }}>
          <div>
            <Label>Имя пользователя:</Label>
            <Input
              placeholder="Поиск по имени пользователя"
              value={exportForm.filters.username}
              onChange={(e) => setExportForm(prev => ({
                ...prev,
                filters: { ...prev.filters, username: e.target.value }
              }))}
            />
          </div>

          <div>
            <Label>Email:</Label>
            <Input
              placeholder="Поиск по email"
              value={exportForm.filters.email}
              onChange={(e) => setExportForm(prev => ({
                ...prev,
                filters: { ...prev.filters, email: e.target.value }
              }))}
            />
          </div>

          <div>
            <Label>Роль:</Label>
            <Select
              value={exportForm.filters.role}
              onChange={(e) => setExportForm(prev => ({
                ...prev,
                filters: { ...prev.filters, role: e.target.value }
              }))}
            >
              {userRoles.map(role => (
                <option key={role.value} value={role.value}>{role.label}</option>
              ))}
            </Select>
          </div>

          <div>
            <Label>Статус:</Label>
            <Select
              value={exportForm.filters.is_active === null ? '' : exportForm.filters.is_active.toString()}
              onChange={(e) => setExportForm(prev => ({
                ...prev,
                filters: { 
                  ...prev.filters, 
                  is_active: e.target.value === '' ? null : e.target.value === 'true'
                }
              }))}
            >
              <option value="">Все пользователи</option>
              <option value="true">Только активные</option>
              <option value="false">Только неактивные</option>
            </Select>
          </div>

          <div>
            <Label>Дата создания (от):</Label>
            <Input
              type="date"
              value={exportForm.filters.created_from}
              onChange={(e) => setExportForm(prev => ({
                ...prev,
                filters: { ...prev.filters, created_from: e.target.value }
              }))}
            />
          </div>

          <div>
            <Label>Дата создания (до):</Label>
            <Input
              type="date"
              value={exportForm.filters.created_to}
              onChange={(e) => setExportForm(prev => ({
                ...prev,
                filters: { ...prev.filters, created_to: e.target.value }
              }))}
            />
          </div>
        </div>

        {/* Кнопка экспорта */}
        <div style={{ marginTop: getSpacing('lg') }}>
          <Button
            onClick={handleExport}
            disabled={loading}
            style={{ width: '100%' }}
          >
            {loading ? (
              <>
                <RefreshCw size={16} style={{ animation: 'spin 1s linear infinite' }} />
                Экспорт...
              </>
            ) : (
              <>
                <Download size={16} />
                Запустить экспорт
              </>
            )}
          </Button>
        </div>
      </Card>
    </div>
  );

  const renderFilesTab = () => (
    <Card style={{ padding: getSpacing('lg') }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: getSpacing('lg') }}>
        <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: getSpacing('xs') }}>
          <FileText size={20} />
          Файлы экспорта
        </h3>
        <Button onClick={loadExportFiles} disabled={loading}>
          <RefreshCw size={16} />
          Обновить
        </Button>
      </div>

      {loading ? (
        <div>
          <Skeleton height="60px" style={{ marginBottom: getSpacing('sm') }} />
          <Skeleton height="60px" style={{ marginBottom: getSpacing('sm') }} />
          <Skeleton height="60px" />
        </div>
      ) : exportFiles.length === 0 ? (
        <div style={{ textAlign: 'center', padding: getSpacing('xl'), color: getColor('gray', 500) }}>
          <FileText size={48} style={{ marginBottom: getSpacing('md') }} />
          <p>Нет файлов экспорта</p>
          <p>Создайте экспорт на вкладке "Экспорт"</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: getSpacing('sm') }}>
          {exportFiles.map((file, index) => (
            <div
              key={index}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: getSpacing('md'),
                backgroundColor: theme === 'light' ? getColor('gray', 100) : getColor('gray', 800),
                borderRadius: '8px',
                border: `1px solid ${theme === 'light' ? getColor('gray', 200) : getColor('gray', 700)}`
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: getSpacing('md') }}>
                {getFileIcon(file.filename)}
                <div>
                  <div style={{ fontWeight: 'bold', fontSize: '0.875rem' }}>
                    {file.filename}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: getColor('gray', 600) }}>
                    Размер: {formatFileSize(file.size)} | 
                    Создан: {new Date(file.created_at).toLocaleString('ru-RU')}
                  </div>
                </div>
              </div>
              
              <div style={{ display: 'flex', gap: getSpacing('xs') }}>
                <Button
                  size="sm"
                  onClick={() => handleDownload(file.filename)}
                >
                  <Download size={14} />
                  Скачать
                </Button>
                <Button
                  size="sm"
                  variant="danger"
                  onClick={() => handleDeleteFile(file.filename)}
                >
                  <Trash2 size={14} />
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
      <div style={{ marginBottom: getSpacing('lg') }}>
        <h1 style={{ 
          margin: 0, 
          fontSize: '1.875rem', 
          fontWeight: 'bold',
          color: theme === 'light' ? getColor('gray', 900) : getColor('gray', 100),
          display: 'flex',
          alignItems: 'center',
          gap: getSpacing('sm')
        }}>
          <Users size={32} />
          Экспорт пользователей
        </h1>
        <p style={{ 
          margin: `${getSpacing('sm')} 0 0 0`, 
          color: getColor('gray', 600) 
        }}>
          Экспорт данных пользователей в различных форматах
        </p>
      </div>

      {/* Табы */}
      <div style={{ 
        display: 'flex', 
        gap: getSpacing('sm'), 
        marginBottom: getSpacing('lg'),
        borderBottom: `1px solid ${theme === 'light' ? getColor('gray', 200) : getColor('gray', 700)}`,
        paddingBottom: getSpacing('sm')
      }}>
        <button
          style={tabStyle(activeTab === 'export')}
          onClick={() => setActiveTab('export')}
        >
          <Download size={16} />
          Экспорт
        </button>
        <button
          style={tabStyle(activeTab === 'files')}
          onClick={() => setActiveTab('files')}
        >
          <FileText size={16} />
          Файлы ({exportFiles.length})
        </button>
      </div>

      {/* Содержимое табов */}
      {activeTab === 'export' && renderExportTab()}
      {activeTab === 'files' && renderFilesTab()}
    </div>
  );
};

export default UserExportManager;
