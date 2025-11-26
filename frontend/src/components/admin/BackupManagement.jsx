import React, { useState, useEffect } from 'react';
import { 
  HardDrive, 
  Plus, 
  Search, 
  Filter, 
  Download, 
  Trash2, 
  Save, 
  X,
  RefreshCw,
  Calendar,
  Clock,
  AlertTriangle,
  CheckCircle,
  Play,
  Database,
  Archive,
  FileText,
  Edit
} from 'lucide-react';
import { 
  MacOSCard, 
  MacOSButton, 
  MacOSBadge,
  MacOSInput,
  MacOSSelect,
  MacOSTextarea,
  MacOSCheckbox,
  MacOSLoadingSkeleton,
  MacOSEmptyState,
  MacOSAlert,
  MacOSModal
} from '../ui/macos';
import { api } from '../../api/client';

const BackupManagement = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [backups, setBackups] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [typeFilter, setTypeFilter] = useState('all');
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingBackup, setEditingBackup] = useState(null);
  const [message, setMessage] = useState({ type: '', text: '' });
  const [stats, setStats] = useState(null);

  // Форма резервной копии
  const [formData, setFormData] = useState({
    name: '',
    backup_type: 'full',
    description: '',
    schedule: 'manual',
    retention_days: 30,
    compression: true,
    encryption: false
  });

  const statusOptions = [
    { value: 'completed', label: 'Завершено', color: 'success' },
    { value: 'running', label: 'Выполняется', color: 'warning' },
    { value: 'failed', label: 'Ошибка', color: 'error' },
    { value: 'scheduled', label: 'Запланировано', color: 'gray' }
  ];

  const typeOptions = [
    { value: 'full', label: 'Полная копия' },
    { value: 'incremental', label: 'Инкрементальная' },
    { value: 'differential', label: 'Дифференциальная' },
    { value: 'database', label: 'База данных' },
    { value: 'files', label: 'Файлы' }
  ];

  const scheduleOptions = [
    { value: 'manual', label: 'Вручную' },
    { value: 'daily', label: 'Ежедневно' },
    { value: 'weekly', label: 'Еженедельно' },
    { value: 'monthly', label: 'Ежемесячно' }
  ];

  useEffect(() => {
    loadBackups();
    loadStats();
  }, []);

  const loadBackups = async () => {
    try {
      setLoading(true);
      const response = await api.get('/backups');
      setBackups(response.data.backups || []);
    } catch (error) {
      console.error('Ошибка загрузки резервных копий:', error);
      // Fallback данные
      setBackups([
        {
          id: 1,
          name: 'Полная копия БД',
          backup_type: 'full',
          status: 'completed',
          created_at: '2024-01-15T10:30:00Z',
          size: 1024000000,
          description: 'Полная резервная копия базы данных',
          schedule: 'daily',
          retention_days: 30
        },
        {
          id: 2,
          name: 'Инкрементальная копия',
          backup_type: 'incremental',
          status: 'completed',
          created_at: '2024-01-15T18:00:00Z',
          size: 51200000,
          description: 'Инкрементальная копия изменений',
          schedule: 'daily',
          retention_days: 7
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const response = await api.get('/backups/stats');
      setStats(response.data);
    } catch (error) {
      console.error('Ошибка загрузки статистики:', error);
      setStats({
        total_backups: 2,
        completed_backups: 2,
        failed_backups: 0,
        total_size: 1075200000
      });
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      setSaving(true);
      
      if (editingBackup) {
        await api.put(`/backups/${editingBackup.id}`, formData);
        setMessage({ type: 'success', text: 'Настройки обновлены' });
      } else {
        await api.post('/backups', formData);
        setMessage({ type: 'success', text: 'Резервная копия создана' });
      }
      
      setShowAddForm(false);
      setEditingBackup(null);
      resetForm();
      loadBackups();
      loadStats();
    } catch (error) {
      setMessage({ type: 'error', text: 'Ошибка сохранения резервной копии' });
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (backup) => {
    setFormData(backup);
    setEditingBackup(backup);
    setShowAddForm(true);
  };

  const handleDelete = async (backupId) => {
    try {
      await api.delete(`/backups/${backupId}`);
      setMessage({ type: 'success', text: 'Резервная копия удалена' });
      loadBackups();
      loadStats();
    } catch (error) {
      setMessage({ type: 'error', text: 'Ошибка удаления резервной копии' });
    }
  };

  const handleDownload = async (backupId) => {
    try {
      const response = await api.get(`/backups/${backupId}/download`, {
        responseType: 'blob'
      });
      
      const blob = new Blob([response.data]);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `backup_${backupId}.zip`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      setMessage({ type: 'success', text: 'Резервная копия скачана' });
    } catch (error) {
      setMessage({ type: 'error', text: 'Ошибка скачивания резервной копии' });
    }
  };

  const handleRunBackup = async (backupId) => {
    try {
      await api.post(`/backups/${backupId}/run`);
      setMessage({ type: 'success', text: 'Резервная копия запущена' });
      loadBackups();
      loadStats();
    } catch (error) {
      setMessage({ type: 'error', text: 'Ошибка запуска резервной копии' });
    }
  };

  const resetForm = () => {
    setFormData({
      name: '',
      backup_type: 'full',
      description: '',
      schedule: 'manual',
      retention_days: 30,
      compression: true,
      encryption: false
    });
  };

  const getStatusColor = (status) => {
    const statusOption = statusOptions.find(s => s.value === status);
    return statusOption ? statusOption.color : 'gray';
  };

  const getStatusLabel = (status) => {
    const statusOption = statusOptions.find(s => s.value === status);
    return statusOption ? statusOption.label : status;
  };

  const getTypeLabel = (type) => {
    const typeOption = typeOptions.find(t => t.value === type);
    return typeOption ? typeOption.label : type;
  };

  const getScheduleLabel = (schedule) => {
    const scheduleOption = scheduleOptions.find(s => s.value === schedule);
    return scheduleOption ? scheduleOption.label : schedule;
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const filteredBackups = backups.filter(backup => {
    const matchesSearch = backup.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         backup.description?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || backup.status === statusFilter;
    const matchesType = typeFilter === 'all' || backup.backup_type === typeFilter;
    return matchesSearch && matchesStatus && matchesType;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', overflow: 'hidden' }}>
      {/* Заголовок и статистика */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '16px'
      }}>
        <div>
          <h2 style={{ 
            fontSize: 'var(--mac-font-size-2xl)', 
            fontWeight: 'var(--mac-font-weight-bold)', 
            color: 'var(--mac-text-primary)',
            margin: '0 0 8px 0'
          }}>
            Управление резервными копиями
          </h2>
          <p style={{ 
            color: 'var(--mac-text-secondary)',
            fontSize: 'var(--mac-font-size-sm)',
            margin: 0
          }}>
            Создание и управление резервными копиями системы
          </p>
        </div>
        {stats && (
          <div style={{ 
            display: 'flex', 
            gap: '24px',
            flexWrap: 'wrap'
          }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ 
                fontSize: 'var(--mac-font-size-2xl)', 
                fontWeight: 'var(--mac-font-weight-bold)', 
                color: 'var(--mac-accent-blue)',
                marginBottom: '4px'
              }}>
                {stats.total_backups}
              </div>
              <div style={{ 
                fontSize: 'var(--mac-font-size-sm)', 
                color: 'var(--mac-text-secondary)' 
              }}>
                Всего копий
              </div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ 
                fontSize: 'var(--mac-font-size-2xl)', 
                fontWeight: 'var(--mac-font-weight-bold)', 
                color: 'var(--mac-success)',
                marginBottom: '4px'
              }}>
                {stats.completed_backups}
              </div>
              <div style={{ 
                fontSize: 'var(--mac-font-size-sm)', 
                color: 'var(--mac-text-secondary)' 
              }}>
                Завершено
              </div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ 
                fontSize: 'var(--mac-font-size-2xl)', 
                fontWeight: 'var(--mac-font-weight-bold)', 
                color: 'var(--mac-warning)',
                marginBottom: '4px'
              }}>
                {formatFileSize(stats.total_size)}
              </div>
              <div style={{ 
                fontSize: 'var(--mac-font-size-sm)', 
                color: 'var(--mac-text-secondary)' 
              }}>
                Общий размер
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Сообщения */}
      {message.text && (
        <MacOSAlert
          type={message.type === 'success' ? 'success' : 'error'}
          title={message.type === 'success' ? 'Успешно' : 'Ошибка'}
          message={message.text}
        />
      )}

      {/* Фильтры и поиск */}
      <MacOSCard style={{ padding: '24px' }}>
        <div style={{ 
          display: 'flex', 
          flexDirection: 'column', 
          gap: '16px',
          flexWrap: 'wrap'
        }}>
          <div style={{ flex: 1, position: 'relative' }}>
            <MacOSInput
              type="text"
              placeholder="Поиск по названию или описанию..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{ paddingLeft: '40px' }}
            />
            <Search style={{ 
              position: 'absolute', 
              left: '12px', 
              top: '50%', 
              transform: 'translateY(-50%)', 
              color: 'var(--mac-text-tertiary)', 
              width: '16px', 
              height: '16px' 
            }} />
          </div>
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            <MacOSSelect
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{ minWidth: '150px' }}
            >
              <option value="all">Все статусы</option>
              {statusOptions.map(option => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </MacOSSelect>
            <MacOSSelect
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              style={{ minWidth: '150px' }}
            >
              <option value="all">Все типы</option>
              {typeOptions.map(option => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </MacOSSelect>
            <MacOSButton
              onClick={() => setShowAddForm(true)}
              style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '8px',
                backgroundColor: 'var(--mac-accent-blue)',
                border: 'none',
                padding: '8px 16px'
              }}
            >
              <Plus style={{ width: '16px', height: '16px' }} />
              <span>Создать копию</span>
            </MacOSButton>
          </div>
        </div>
      </MacOSCard>

      {/* Форма создания/редактирования */}
      {showAddForm && (
        <MacOSCard style={{ padding: '24px', overflow: 'hidden' }}>
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center', 
            marginBottom: '16px' 
          }}>
            <h3 style={{ 
              fontSize: 'var(--mac-font-size-lg)', 
              fontWeight: 'var(--mac-font-weight-semibold)', 
              color: 'var(--mac-text-primary)',
              margin: 0
            }}>
              {editingBackup ? 'Редактировать резервную копию' : 'Создать резервную копию'}
            </h3>
            <MacOSButton
              variant="outline"
              onClick={() => {
                setShowAddForm(false);
                setEditingBackup(null);
                resetForm();
              }}
              style={{ padding: '8px' }}
            >
              <X style={{ width: '16px', height: '16px' }} />
            </MacOSButton>
          </div>

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ 
              display: 'grid', 
              gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', 
              gap: '16px' 
            }}>
              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)', 
                  marginBottom: '4px' 
                }}>
                  Название *
                </label>
                <MacOSInput
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="Введите название резервной копии"
                />
              </div>
              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)', 
                  marginBottom: '4px' 
                }}>
                  Тип копии *
                </label>
                <MacOSSelect
                  required
                  value={formData.backup_type}
                  onChange={(e) => setFormData({ ...formData, backup_type: e.target.value })}
                >
                  {typeOptions.map(option => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </MacOSSelect>
              </div>
              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)', 
                  marginBottom: '4px' 
                }}>
                  Расписание
                </label>
                <MacOSSelect
                  value={formData.schedule}
                  onChange={(e) => setFormData({ ...formData, schedule: e.target.value })}
                >
                  {scheduleOptions.map(option => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </MacOSSelect>
              </div>
              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)', 
                  marginBottom: '4px' 
                }}>
                  Хранение (дни)
                </label>
                <MacOSInput
                  type="number"
                  min="1"
                  value={formData.retention_days}
                  onChange={(e) => setFormData({ ...formData, retention_days: parseInt(e.target.value) })}
                  placeholder="Введите количество дней"
                />
              </div>
            </div>

            <div>
              <label style={{ 
                display: 'block', 
                fontSize: 'var(--mac-font-size-sm)', 
                fontWeight: 'var(--mac-font-weight-medium)', 
                color: 'var(--mac-text-primary)', 
                marginBottom: '8px' 
              }}>
                Описание
              </label>
              <MacOSTextarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Введите описание резервной копии"
                rows={3}
              />
            </div>

            <div style={{ 
              display: 'flex', 
              flexDirection: 'column', 
              gap: '12px' 
            }}>
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '12px' 
              }}>
                <MacOSCheckbox
                  checked={formData.compression}
                  onChange={(checked) => setFormData({ ...formData, compression: checked })}
                />
                <span style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  color: 'var(--mac-text-primary)' 
                }}>
                  Сжатие архива
                </span>
              </div>
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '12px' 
              }}>
                <MacOSCheckbox
                  checked={formData.encryption}
                  onChange={(checked) => setFormData({ ...formData, encryption: checked })}
                />
                <span style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  color: 'var(--mac-text-primary)' 
                }}>
                  Шифрование архива
                </span>
              </div>
            </div>

            <div style={{ 
              display: 'flex', 
              justifyContent: 'flex-end', 
              gap: '12px' 
            }}>
              <MacOSButton
                type="button"
                variant="outline"
                onClick={() => {
                  setShowAddForm(false);
                  setEditingBackup(null);
                  resetForm();
                }}
                disabled={saving}
              >
                Отмена
              </MacOSButton>
              <MacOSButton
                type="submit"
                disabled={saving}
                style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '8px',
                  backgroundColor: 'var(--mac-accent-blue)',
                  border: 'none'
                }}
              >
                {saving ? (
                  <>
                    <RefreshCw style={{ 
                      width: '16px', 
                      height: '16px',
                      animation: 'spin 1s linear infinite'
                    }} />
                    Сохранение...
                  </>
                ) : (
                  <>
                    <Save style={{ width: '16px', height: '16px' }} />
                    {editingBackup ? 'Обновить' : 'Создать'}
                  </>
                )}
              </MacOSButton>
            </div>
          </form>
        </MacOSCard>
      )}

      {/* Список резервных копий */}
      {loading ? (
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', 
          gap: '24px',
          overflow: 'hidden'
        }}>
          {[1, 2, 3].map(i => (
            <MacOSCard key={i} style={{ padding: '24px' }}>
              <MacOSLoadingSkeleton height="200px" />
            </MacOSCard>
          ))}
        </div>
      ) : filteredBackups.length === 0 ? (
        <MacOSEmptyState
          icon={HardDrive}
          title="Резервные копии не найдены"
          description="Создайте первую резервную копию или измените фильтры поиска"
          action={
            <MacOSButton onClick={() => setShowAddForm(true)} variant="primary">
              <Plus style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Создать копию
            </MacOSButton>
          }
        />
      ) : (
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', 
          gap: '24px',
          overflow: 'hidden'
        }}>
          {filteredBackups.map(backup => (
            <MacOSCard key={backup.id} style={{ padding: '24px' }}>
              <div style={{ 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'flex-start', 
                marginBottom: '16px' 
              }}>
                <div>
                  <h3 style={{ 
                    fontSize: 'var(--mac-font-size-lg)', 
                    fontWeight: 'var(--mac-font-weight-semibold)', 
                    color: 'var(--mac-text-primary)',
                    margin: '0 0 4px 0'
                  }}>
                    {backup.name}
                  </h3>
                  <p style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    color: 'var(--mac-text-secondary)',
                    margin: 0
                  }}>
                    {getTypeLabel(backup.backup_type)} • {getScheduleLabel(backup.schedule)}
                  </p>
                </div>
                <MacOSBadge
                  variant={getStatusColor(backup.status)}
                  text={getStatusLabel(backup.status)}
                />
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '16px' }}>
                <div style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '8px',
                  fontSize: 'var(--mac-font-size-sm)', 
                  color: 'var(--mac-text-secondary)' 
                }}>
                  <HardDrive style={{ width: '16px', height: '16px' }} />
                  <span>{formatFileSize(backup.size)}</span>
                </div>
                <div style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '8px',
                  fontSize: 'var(--mac-font-size-sm)', 
                  color: 'var(--mac-text-secondary)' 
                }}>
                  <Calendar style={{ width: '16px', height: '16px' }} />
                  <span>{new Date(backup.created_at).toLocaleString()}</span>
                </div>
                <div style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '8px',
                  fontSize: 'var(--mac-font-size-sm)', 
                  color: 'var(--mac-text-secondary)' 
                }}>
                  <Clock style={{ width: '16px', height: '16px' }} />
                  <span>Хранение: {backup.retention_days} дней</span>
                </div>
              </div>

              {backup.description && (
                <div style={{ marginBottom: '16px' }}>
                  <p style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    color: 'var(--mac-text-secondary)',
                    margin: 0,
                    lineHeight: '1.4'
                  }}>
                    {backup.description}
                  </p>
                </div>
              )}

              <div style={{ 
                display: 'flex', 
                justifyContent: 'flex-end', 
                gap: '8px' 
              }}>
                {backup.status === 'completed' && (
                  <MacOSButton
                    variant="outline"
                    onClick={() => handleDownload(backup.id)}
                    style={{ padding: '6px 12px' }}
                  >
                    <Download style={{ width: '16px', height: '16px' }} />
                  </MacOSButton>
                )}
                <MacOSButton
                  variant="outline"
                  onClick={() => handleRunBackup(backup.id)}
                  style={{ padding: '6px 12px' }}
                >
                  <Play style={{ width: '16px', height: '16px' }} />
                </MacOSButton>
                <MacOSButton
                  variant="outline"
                  onClick={() => handleEdit(backup)}
                  style={{ padding: '6px 12px' }}
                >
                  <Edit style={{ width: '16px', height: '16px' }} />
                </MacOSButton>
                <MacOSButton
                  variant="outline"
                  onClick={() => handleDelete(backup.id)}
                  style={{ 
                    padding: '6px 12px',
                    color: 'var(--mac-error)',
                    borderColor: 'var(--mac-error)'
                  }}
                >
                  <Trash2 style={{ width: '16px', height: '16px' }} />
                </MacOSButton>
              </div>
            </MacOSCard>
          ))}
        </div>
      )}
    </div>
  );
};

export default BackupManagement;