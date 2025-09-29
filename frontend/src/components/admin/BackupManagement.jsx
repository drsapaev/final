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
  FileText
} from 'lucide-react';
import { Card, Button, Badge } from '../ui/native';

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
    retention_days: 30,
    notes: ''
  });

  const statusOptions = [
    { value: 'pending', label: 'Ожидает', color: 'blue' },
    { value: 'in_progress', label: 'Выполняется', color: 'yellow' },
    { value: 'completed', label: 'Завершена', color: 'green' },
    { value: 'failed', label: 'Ошибка', color: 'red' },
    { value: 'cancelled', label: 'Отменена', color: 'gray' }
  ];

  const typeOptions = [
    { value: 'full', label: 'Полная копия', icon: '💾', description: 'Полное резервное копирование всех данных' },
    { value: 'incremental', label: 'Инкрементальная', icon: '📈', description: 'Копирование только изменений с последней копии' },
    { value: 'differential', label: 'Дифференциальная', icon: '📊', description: 'Копирование изменений с последней полной копии' },
    { value: 'manual', label: 'Ручная', icon: '✋', description: 'Ручное создание резервной копии' }
  ];

  useEffect(() => {
    loadBackups();
    loadStats();
  }, []);

  const loadBackups = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (searchTerm) params.append('search', searchTerm);
      if (statusFilter !== 'all') params.append('status', statusFilter);
      if (typeFilter !== 'all') params.append('backup_type', typeFilter);
      
      const response = await fetch(`/api/v1/clinic/backups?${params}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        setBackups(data);
      } else {
        throw new Error('Ошибка загрузки резервных копий');
      }
    } catch (error) {
      setMessage({ type: 'error', text: error.message });
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const response = await fetch('/api/v1/clinic/stats', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (error) {
      console.error('Ошибка загрузки статистики:', error);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    
    try {
      const url = editingBackup 
        ? `/api/v1/clinic/backups/${editingBackup.id}`
        : '/api/v1/clinic/backups';
      
      const method = editingBackup ? 'PUT' : 'POST';
      
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(formData)
      });
      
      if (response.ok) {
        setMessage({ type: 'success', text: editingBackup ? 'Резервная копия обновлена' : 'Задача резервного копирования создана' });
        setShowAddForm(false);
        setEditingBackup(null);
        resetForm();
        loadBackups();
        loadStats();
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Ошибка сохранения');
      }
    } catch (error) {
      setMessage({ type: 'error', text: error.message });
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (backup) => {
    setEditingBackup(backup);
    setFormData({
      name: backup.name,
      backup_type: backup.backup_type,
      retention_days: backup.retention_days,
      notes: backup.notes || ''
    });
    setShowAddForm(true);
  };

  const handleDelete = async (backupId) => {
    if (!window.confirm('Вы уверены, что хотите удалить эту резервную копию?')) return;
    
    try {
      const response = await fetch(`/api/v1/clinic/backups/${backupId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      
      if (response.ok) {
        setMessage({ type: 'success', text: 'Резервная копия удалена' });
        loadBackups();
        loadStats();
      } else {
        throw new Error('Ошибка удаления резервной копии');
      }
    } catch (error) {
      setMessage({ type: 'error', text: error.message });
    }
  };

  const handleCreateFullBackup = async () => {
    try {
      const response = await fetch('/api/v1/clinic/backups/full', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      
      if (response.ok) {
        setMessage({ type: 'success', text: 'Задача полного резервного копирования создана' });
        loadBackups();
        loadStats();
      } else {
        throw new Error('Ошибка создания полной резервной копии');
      }
    } catch (error) {
      setMessage({ type: 'error', text: error.message });
    }
  };

  const handleCreateIncrementalBackup = async () => {
    try {
      const response = await fetch('/api/v1/clinic/backups/incremental', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      
      if (response.ok) {
        setMessage({ type: 'success', text: 'Задача инкрементального резервного копирования создана' });
        loadBackups();
        loadStats();
      } else {
        throw new Error('Ошибка создания инкрементальной резервной копии');
      }
    } catch (error) {
      setMessage({ type: 'error', text: error.message });
    }
  };

  const handleCleanupExpired = async () => {
    try {
      const response = await fetch('/api/v1/clinic/backups/cleanup', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        setMessage({ type: 'success', text: `Очищено ${data.cleaned_count} истекших резервных копий` });
        loadBackups();
        loadStats();
      } else {
        throw new Error('Ошибка очистки истекших копий');
      }
    } catch (error) {
      setMessage({ type: 'error', text: error.message });
    }
  };

  const resetForm = () => {
    setFormData({
      name: '',
      backup_type: 'full',
      retention_days: 30,
      notes: ''
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

  const getTypeIcon = (type) => {
    const typeOption = typeOptions.find(t => t.value === type);
    return typeOption ? typeOption.icon : '💾';
  };

  const getTypeLabel = (type) => {
    const typeOption = typeOptions.find(t => t.value === type);
    return typeOption ? typeOption.label : type;
  };

  const formatFileSize = (bytes) => {
    if (!bytes) return 'Неизвестно';
    const sizes = ['Б', 'КБ', 'МБ', 'ГБ', 'ТБ'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
  };

  const formatDuration = (started, completed) => {
    if (!started || !completed) return 'Неизвестно';
    const duration = new Date(completed) - new Date(started);
    const minutes = Math.floor(duration / 60000);
    const seconds = Math.floor((duration % 60000) / 1000);
    return `${minutes}м ${seconds}с`;
  };

  const isExpired = (backup) => {
    if (!backup.expires_at) return false;
    const expiresDate = new Date(backup.expires_at);
    const now = new Date();
    return expiresDate < now;
  };

  const filteredBackups = backups.filter(backup => {
    const matchesSearch = backup.name.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || backup.status === statusFilter;
    const matchesType = typeFilter === 'all' || backup.backup_type === typeFilter;
    return matchesSearch && matchesStatus && matchesType;
  });

  return (
    <div className="space-y-6">
      {/* Заголовок и статистика */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Управление резервными копиями</h2>
          <p className="text-gray-600">Создание и управление резервными копиями системы</p>
        </div>
        {stats && (
          <div className="flex space-x-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">{stats.total_backups}</div>
              <div className="text-sm text-gray-600">Всего копий</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">{stats.recent_backups}</div>
              <div className="text-sm text-gray-600">За неделю</div>
            </div>
          </div>
        )}
      </div>

      {/* Сообщения */}
      {message.text && (
        <div className={`p-4 rounded-lg flex items-center space-x-2 ${
          message.type === 'success' ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
        }`}>
          {message.type === 'success' ? <CheckCircle className="w-5 h-5" /> : <AlertTriangle className="w-5 h-5" />}
          <span>{message.text}</span>
        </div>
      )}

      {/* Быстрые действия */}
      <Card className="p-4">
        <div className="flex flex-wrap gap-3">
          <Button
            onClick={handleCreateFullBackup}
            className="flex items-center space-x-2"
          >
            <Database className="w-4 h-4" />
            <span>Полная копия</span>
          </Button>
          <Button
            onClick={handleCreateIncrementalBackup}
            variant="outline"
            className="flex items-center space-x-2"
          >
            <Archive className="w-4 h-4" />
            <span>Инкрементальная</span>
          </Button>
          <Button
            onClick={handleCleanupExpired}
            variant="outline"
            className="flex items-center space-x-2 text-red-600"
          >
            <Trash2 className="w-4 h-4" />
            <span>Очистить истекшие</span>
          </Button>
        </div>
      </Card>

      {/* Фильтры и поиск */}
      <Card className="p-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
            <input
              type="text"
              placeholder="Поиск резервных копий..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="all">Все статусы</option>
            {statusOptions.map(option => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="all">Все типы</option>
            {typeOptions.map(option => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </div>
        <div className="mt-4 flex justify-end">
          <Button
            onClick={() => setShowAddForm(true)}
            className="flex items-center space-x-2"
          >
            <Plus className="w-4 h-4" />
            <span>Создать задачу</span>
          </Button>
        </div>
      </Card>

      {/* Форма добавления/редактирования */}
      {showAddForm && (
        <Card className="p-6">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-semibold">
              {editingBackup ? 'Редактировать резервную копию' : 'Создать задачу резервного копирования'}
            </h3>
            <Button
              variant="outline"
              onClick={() => {
                setShowAddForm(false);
                setEditingBackup(null);
                resetForm();
              }}
            >
              <X className="w-4 h-4" />
            </Button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Название *
                </label>
                <input
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => setFormData({...formData, name: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Тип копии *
                </label>
                <select
                  required
                  value={formData.backup_type}
                  onChange={(e) => setFormData({...formData, backup_type: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  {typeOptions.map(option => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Срок хранения (дни)
                </label>
                <input
                  type="number"
                  min="1"
                  max="365"
                  value={formData.retention_days}
                  onChange={(e) => setFormData({...formData, retention_days: parseInt(e.target.value)})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Примечания
              </label>
              <textarea
                value={formData.notes}
                onChange={(e) => setFormData({...formData, notes: e.target.value})}
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            <div className="flex justify-end space-x-3">
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setShowAddForm(false);
                  setEditingBackup(null);
                  resetForm();
                }}
              >
                Отмена
              </Button>
              <Button
                type="submit"
                disabled={saving}
                className="flex items-center space-x-2"
              >
                {saving ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <Save className="w-4 h-4" />
                )}
                <span>{saving ? 'Сохранение...' : 'Сохранить'}</span>
              </Button>
            </div>
          </form>
        </Card>
      )}

      {/* Список резервных копий */}
      <div className="space-y-4">
        {loading ? (
          Array.from({ length: 5 }).map((_, i) => (
            <Card key={i} className="p-6">
              <div className="animate-pulse">
                <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
                <div className="h-3 bg-gray-200 rounded w-1/2 mb-4"></div>
                <div className="h-3 bg-gray-200 rounded w-full mb-2"></div>
                <div className="h-3 bg-gray-200 rounded w-2/3"></div>
              </div>
            </Card>
          ))
        ) : filteredBackups.length === 0 ? (
          <div className="text-center py-12">
            <HardDrive className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Резервные копии не найдены</h3>
            <p className="text-gray-600">Создайте первую резервную копию или измените фильтры поиска</p>
          </div>
        ) : (
          filteredBackups.map(backup => (
            <Card key={backup.id} className="p-6 hover:shadow-lg transition-shadow">
              <div className="flex justify-between items-start mb-4">
                <div className="flex items-center space-x-3">
                  <span className="text-2xl">{getTypeIcon(backup.backup_type)}</span>
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900">{backup.name}</h3>
                    <p className="text-sm text-gray-600">{getTypeLabel(backup.backup_type)}</p>
                  </div>
                </div>
                <div className="flex flex-col items-end space-y-1">
                  <Badge color={getStatusColor(backup.status)}>
                    {getStatusLabel(backup.status)}
                  </Badge>
                  {isExpired(backup) && (
                    <Badge color="red">Истекла</Badge>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
                <div className="flex items-center space-x-2 text-sm text-gray-600">
                  <Calendar className="w-4 h-4" />
                  <span>Создана: {new Date(backup.created_at).toLocaleDateString()}</span>
                </div>
                
                {backup.started_at && (
                  <div className="flex items-center space-x-2 text-sm text-gray-600">
                    <Play className="w-4 h-4" />
                    <span>Начата: {new Date(backup.started_at).toLocaleString()}</span>
                  </div>
                )}
                
                {backup.completed_at && (
                  <div className="flex items-center space-x-2 text-sm text-gray-600">
                    <CheckCircle className="w-4 h-4" />
                    <span>Завершена: {new Date(backup.completed_at).toLocaleString()}</span>
                  </div>
                )}
                
                {backup.file_size && (
                  <div className="flex items-center space-x-2 text-sm text-gray-600">
                    <FileText className="w-4 h-4" />
                    <span>Размер: {formatFileSize(backup.file_size)}</span>
                  </div>
                )}
                
                {backup.started_at && backup.completed_at && (
                  <div className="flex items-center space-x-2 text-sm text-gray-600">
                    <Clock className="w-4 h-4" />
                    <span>Длительность: {formatDuration(backup.started_at, backup.completed_at)}</span>
                  </div>
                )}
                
                <div className="flex items-center space-x-2 text-sm text-gray-600">
                  <Calendar className="w-4 h-4" />
                  <span>Хранится: {backup.retention_days} дней</span>
                </div>
                
                {backup.expires_at && (
                  <div className="flex items-center space-x-2 text-sm text-gray-600">
                    <Clock className="w-4 h-4" />
                    <span>Истекает: {new Date(backup.expires_at).toLocaleDateString()}</span>
                  </div>
                )}
              </div>

              {backup.error_message && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                  <div className="flex items-center space-x-2 text-red-800">
                    <AlertTriangle className="w-4 h-4" />
                    <span className="font-medium">Ошибка:</span>
                  </div>
                  <p className="text-sm text-red-700 mt-1">{backup.error_message}</p>
                </div>
              )}

              {backup.notes && (
                <div className="mb-4">
                  <p className="text-sm text-gray-600">{backup.notes}</p>
                </div>
              )}

              <div className="flex justify-between items-center">
                <div className="flex space-x-2">
                  {backup.file_path && backup.status === 'completed' && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => window.open(backup.file_path, '_blank')}
                    >
                      <Download className="w-4 h-4" />
                    </Button>
                  )}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleEdit(backup)}
                  >
                    <Edit className="w-4 h-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleDelete(backup.id)}
                    className="text-red-600 hover:text-red-700"
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
                
                {backup.status === 'in_progress' && (
                  <div className="flex items-center space-x-2 text-sm text-blue-600">
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Выполняется...</span>
                  </div>
                )}
              </div>
            </Card>
          ))
        )}
      </div>
    </div>
  );
};

export default BackupManagement;

