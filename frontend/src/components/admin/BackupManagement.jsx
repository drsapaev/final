import { useState, useEffect, useCallback } from 'react';
import {
  HardDrive,
  Plus,
  Search,
  Trash2,
  Save,
  X,
  RefreshCw,
  Calendar,
  Clock,
  Edit } from
'lucide-react';
import {
  MacOSCard,
  Button,
  Badge,
  Input,
  Select,
  Textarea,
  Checkbox,
  Skeleton,
  MacOSEmptyState,
  Alert,
} from '../ui/macos';
import { api } from '../../api/client';

import logger from '../../utils/logger';

const emptyBackupStats = {
  total_backups: 0,
  completed_backups: 0,
  failed_backups: 0,
  total_size: 0
};

const deriveBackupStats = (backupList) => {
  const nextBackups = Array.isArray(backupList) ? backupList : [];
  return {
    total_backups: nextBackups.length,
    completed_backups: nextBackups.filter((backup) => backup.status === 'completed').length,
    failed_backups: nextBackups.filter((backup) => backup.status === 'failed').length,
    total_size: nextBackups.reduce((sum, backup) => sum + (backup.file_size || 0), 0)
  };
};

const defaultBackupForm = {
  name: '',
  backup_type: 'full',
  status: 'pending',
  file_path: '',
  file_size: '',
  retention_days: 30,
  notes: '',
  description: '',
  schedule: 'manual',
  compression: true,
  encryption: false
};

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
  const [formData, setFormData] = useState(defaultBackupForm);

  const statusOptions = [
  { value: 'pending', label: 'Ожидает', color: 'gray' },
  { value: 'in_progress', label: 'Выполняется', color: 'warning' },
  { value: 'completed', label: 'Завершено', color: 'success' },
  { value: 'failed', label: 'Ошибка', color: 'error' },
  { value: 'cancelled', label: 'Отменено', color: 'gray' }];


  const typeOptions = [
  { value: 'full', label: 'Полная копия' },
  { value: 'incremental', label: 'Инкрементальная' },
  { value: 'differential', label: 'Дифференциальная' },
  { value: 'database', label: 'База данных' },
  { value: 'files', label: 'Файлы' }];


  const scheduleOptions = [
  { value: 'manual', label: 'Вручную' },
  { value: 'daily', label: 'Ежедневно' },
  { value: 'weekly', label: 'Еженедельно' },
  { value: 'monthly', label: 'Ежемесячно' }];


  const loadBackups = useCallback(async () => {
    try {
      setLoading(true);
      const response = await api.get('/clinic/backups');
      const nextBackups = Array.isArray(response.data)
        ? response.data
        : response.data?.backups || [];
      setBackups(nextBackups);
      setStats(deriveBackupStats(nextBackups));
    } catch (error) {
      logger.error('Ошибка загрузки резервных копий:', error);
      setBackups([]);
      setStats(emptyBackupStats);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadBackups();
  }, [loadBackups]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      setSaving(true);

      if (editingBackup) {
        await api.put(`/clinic/backups/${editingBackup.id}`, formData);
        setMessage({ type: 'success', text: 'Настройки обновлены' });
      } else {
        await api.post('/clinic/backups', formData);
        setMessage({ type: 'success', text: 'Резервная копия создана' });
      }

      setShowAddForm(false);
      setEditingBackup(null);
      resetForm();
      loadBackups();
    } catch {
      setMessage({ type: 'error', text: 'Ошибка сохранения резервной копии' });
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (backup) => {
    setFormData({
      ...defaultBackupForm,
      ...backup,
      description: backup.notes || backup.description || ''
    });
    setEditingBackup(backup);
    setShowAddForm(true);
  };

  const handleDelete = async (backupId) => {
    try {
      await api.delete(`/clinic/backups/${backupId}`);
      setMessage({ type: 'success', text: 'Резервная копия удалена' });
      loadBackups();
    } catch {
      setMessage({ type: 'error', text: 'Ошибка удаления резервной копии' });
    }
  };

  const handleCleanupExpired = async () => {
    try {
      const response = await api.post('/clinic/backups/cleanup');
      const cleanedCount = response.data?.cleaned_count ?? 0;
      setMessage({
        type: 'success',
        text: `Очищено ${cleanedCount} просроченных резервных копий`
      });
      loadBackups();
    } catch {
      setMessage({ type: 'error', text: 'Ошибка очистки просроченных резервных копий' });
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
    const statusOption = statusOptions.find((s) => s.value === status);
    return statusOption ? statusOption.color : 'gray';
  };

  const getStatusLabel = (status) => {
    const statusOption = statusOptions.find((s) => s.value === status);
    return statusOption ? statusOption.label : status;
  };

  const getTypeLabel = (type) => {
    const typeOption = typeOptions.find((t) => t.value === type);
    return typeOption ? typeOption.label : type;
  };

  const formatFileSize = (bytes) => {
    if (!bytes || bytes <= 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const filteredBackups = backups.filter((backup) => {
    const matchesSearch = backup.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    backup.description?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || backup.status === statusFilter;
    const matchesType = typeFilter === 'all' || backup.backup_type === typeFilter;
    return matchesSearch && matchesStatus && matchesType;
  });
  const hasBackupFilters = searchTerm.trim() !== '' || statusFilter !== 'all' || typeFilter !== 'all';
  const backupEmptyTitle = hasBackupFilters ? 'Резервные копии по фильтрам не найдены' : 'Резервные копии ещё не созданы';
  const backupEmptyDescription = hasBackupFilters ?
  'Измените поиск, статус или тип, чтобы увидеть другие резервные копии.' :
  'Создайте первую резервную копию, чтобы зафиксировать состояние системы.';

  return (
    <div className="admin-d-flex-fd-column-gap-24-ov-hidden-2">
      {/* Заголовок и статистика */}
      <div className="admin-d-flex-jc-between-ai-center-fw-wrap-gap-16-2">
        <div>
          <h2 className="admin-fs-2xl-fw-bold-primary-m-0-0-8px-0-2">
            Управление резервными копиями
          </h2>
          <p className="admin-secondary-fs-sm-m-0-4">
            Создание и управление резервными копиями системы
          </p>
        </div>
        {stats &&
        <div className="admin-d-flex-gap-24-fw-wrap-2">
            <div className="text-center">
              <div className="admin-fs-2xl-fw-bold-blue-mb-4-2">
                {stats.total_backups}
              </div>
              <div className="text-sm text-[var(--mac-text-secondary)]">
                Всего копий
              </div>
            </div>
            <div className="text-center">
              <div className="admin-fs-2xl-fw-bold-success-mb-4-2">
                {stats.completed_backups}
              </div>
              <div className="text-sm text-[var(--mac-text-secondary)]">
                Завершено
              </div>
            </div>
            <div className="text-center">
              <div className="admin-fs-2xl-fw-bold-warning-mb-4">
                {formatFileSize(stats.total_size)}
              </div>
              <div className="text-sm text-[var(--mac-text-secondary)]">
                Общий размер
              </div>
            </div>
          </div>
        }
      </div>

      {/* Сообщения */}
      {message.text &&
      <Alert
        type={message.type === 'success' ? 'success' : 'error'}
        title={message.type === 'success' ? 'Успешно' : 'Ошибка'}
        message={message.text} />

      }

      {/* Фильтры и поиск */}
      <MacOSCard className="p-6">
        <div className="admin-d-flex-fd-column-gap-16-fw-wrap-2">
          <div className="admin-flex-1-pos-relative">
            <Input
              type="text"
              aria-label="Поиск резервных копий по названию или описанию"
              placeholder="Поиск по названию или описанию..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="admin-pl-40" />
            
            <Search aria-hidden="true" className="admin-pos-absolute-left-12-top-50pct-tf-translateY-50-tertiary-w-16-h-16-2" />
          </div>
          <div className="admin-d-flex-gap-12-fw-wrap-2">
            <Select
              aria-label="Фильтр резервных копий по статусу"
              value={statusFilter}
              onChange={setStatusFilter}
              options={[
                { value: 'all', label: 'Все статусы' },
                ...statusOptions.map((option) => ({ value: option.value, label: option.label }))
              ]}
              size="large"
              className="admin-minw-150" />
            <Select
              aria-label="Фильтр резервных копий по типу"
              value={typeFilter}
              onChange={setTypeFilter}
              options={[
                { value: 'all', label: 'Все типы' },
                ...typeOptions.map((option) => ({ value: option.value, label: option.label }))
              ]}
              size="large"
              className="admin-minw-150" />
            <Button
              onClick={() => setShowAddForm(true)}
              className="admin-d-flex-ai-center-gap-8-bgc-blue-bd-none-p-8px-16px-2">
              
              <Plus aria-hidden="true" className="w-4 h-4" />
              <span>Создать копию</span>
            </Button>
            <Button
              type="button"
              aria-label="Очистить просроченные резервные копии"
              onClick={handleCleanupExpired}
              variant="outline"
              className="flex items-center justify-center gap-2">
              <RefreshCw aria-hidden="true" className="w-4 h-4" />
              <span>Очистить просроченные</span>
            </Button>
          </div>
        </div>
      </MacOSCard>

      {/* Форма создания/редактирования */}
      {showAddForm &&
      <MacOSCard className="admin-p-24-ov-hidden-2">
          <div className="admin-d-flex-jc-between-ai-center-mb-16-4">
            <h3 className="admin-fs-lg-fw-semi-primary-m-0-3">
              {editingBackup ? 'Редактировать резервную копию' : 'Создать резервную копию'}
            </h3>
            <Button
            variant="outline"
            type="button"
            aria-label={editingBackup ? 'Закрыть форму редактирования резервной копии' : 'Закрыть форму создания резервной копии'}
            onClick={() => {
              setShowAddForm(false);
              setEditingBackup(null);
              resetForm();
            }}
            className="p-2">
            
              <X aria-hidden="true" className="w-4 h-4" />
            </Button>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-16-4">
              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-4-21">
                  Название *
                </label>
                <Input
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="Введите название резервной копии" />
              
              </div>
              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-4-20">
                  Тип копии *
                </label>
                <Select
                aria-label="Тип резервной копии"
                value={formData.backup_type}
                onChange={(value) => setFormData({ ...formData, backup_type: value })}
                options={typeOptions.map((option) => ({ value: option.value, label: option.label }))}
                size="large" />
              </div>
              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-4-19">
                  Расписание
                </label>
                <Select
                aria-label="Расписание резервной копии"
                value={formData.schedule}
                onChange={(value) => setFormData({ ...formData, schedule: value })}
                options={scheduleOptions.map((option) => ({ value: option.value, label: option.label }))}
                size="large" />
              </div>
              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-4-18">
                  Хранение (дни)
                </label>
                <Input
                type="number"
                min="1"
                value={formData.retention_days}
                onChange={(e) => setFormData({ ...formData, retention_days: parseInt(e.target.value) })}
                placeholder="Введите количество дней" />
              
              </div>
            </div>

            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8-15">
                Описание
              </label>
              <Textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="Введите описание резервной копии"
              rows={3} />
            
            </div>

            <div className="flex flex-col gap-3">
              <div className="admin-flex-center-12">
                <Checkbox
                checked={formData.compression}
                onChange={(checked) => setFormData({ ...formData, compression: checked })} />
              
                <span className="admin-fs-sm-primary-2">
                  Сжатие архива
                </span>
              </div>
              <div className="admin-flex-center-12">
                <Checkbox
                checked={formData.encryption}
                onChange={(checked) => setFormData({ ...formData, encryption: checked })} />
              
                <span className="admin-fs-sm-primary-1">
                  Шифрование архива
                </span>
              </div>
            </div>

            <div className="admin-d-flex-jc-end-gap-12-3">
              <Button
              type="button"
              variant="outline"
              onClick={() => {
                setShowAddForm(false);
                setEditingBackup(null);
                resetForm();
              }}
              disabled={saving}>
              
                Отмена
              </Button>
              <Button
              type="submit"
              disabled={saving}
              aria-label={editingBackup ? 'Update backup configuration' : 'Create backup configuration'}
              className="admin-d-flex-ai-center-gap-8-bgc-blue-bd-none-2">
              
                {saving ?
              <>
                    <RefreshCw aria-hidden="true" className="admin-w-16-h-16-anim-spin-1s-linear-infin-2" />
                    Сохранение...
                  </> :

              <>
                    <Save aria-hidden="true" className="w-4 h-4" />
                    {editingBackup ? 'Обновить' : 'Создать'}
                  </>
              }
              </Button>
            </div>
          </form>
        </MacOSCard>
      }

      {/* Список резервных копий */}
      {loading ?
      <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-24-ov-hidden-5">
          {[1, 2, 3].map((i) =>
        <MacOSCard key={i} className="p-6">
              <Skeleton height="200px" />
            </MacOSCard>
        )}
        </div> :
      filteredBackups.length === 0 ?
      <MacOSEmptyState
        icon={HardDrive}
        title={backupEmptyTitle}
        description={backupEmptyDescription}
        action={
        <Button onClick={() => setShowAddForm(true)} variant="primary">
              <Plus aria-hidden="true" focusable="false" className="w-4 h-4 mr-2" />
              Создать копию
            </Button>
        } /> :


      <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-24-ov-hidden-4">
          {filteredBackups.map((backup) =>
        <MacOSCard key={backup.id} className="p-6">
              <div className="admin-d-flex-jc-between-ai-start-mb-16-2">
                <div>
                  <h3 className="admin-fs-lg-fw-semi-primary-m-0-0-4px-0-2">
                    {backup.name}
                  </h3>
                  <p className="admin-fs-sm-secondary-m-0-2">
                    {getTypeLabel(backup.backup_type)} • Хранение {backup.retention_days} дней
                  </p>
                </div>
                <Badge
              variant={getStatusColor(backup.status)}
              text={getStatusLabel(backup.status)} />
            
              </div>

              <div className="admin-d-flex-fd-column-gap-8-mb-16-2">
                <div className="admin-d-flex-ai-center-gap-8-fs-sm-secondary-11">
                  <HardDrive aria-hidden="true" className="w-4 h-4" />
                  <span>{formatFileSize(backup.file_size)}</span>
                </div>
                <div className="admin-d-flex-ai-center-gap-8-fs-sm-secondary-10">
                  <Calendar aria-hidden="true" className="w-4 h-4" />
                  <span>{new Date(backup.created_at).toLocaleString()}</span>
                </div>
                <div className="admin-d-flex-ai-center-gap-8-fs-sm-secondary-9">
                  <Clock aria-hidden="true" className="w-4 h-4" />
                  <span>Хранение: {backup.retention_days} дней</span>
                </div>
                {backup.file_path &&
            <div className="admin-d-flex-ai-center-gap-8-fs-sm-secondary-8">
                    <span className="admin-ff-mono">{backup.file_path}</span>
                  </div>
            }
              </div>

              {backup.notes &&
          <div className="mb-4">
                  <p className="admin-fs-sm-secondary-m-0-lh-1p4-1">
                    {backup.notes}
                  </p>
                </div>
          }

              <div className="admin-d-flex-jc-end-gap-8-4">
                <Button
              type="button"
              variant="outline"
              aria-label={`Редактировать резервную копию ${backup.name}`}
              onClick={() => handleEdit(backup)}
              className="admin-p-6px-12px-2">
              
                  <Edit aria-hidden="true" className="w-4 h-4" />
                </Button>
                <Button
              type="button"
              variant="outline"
              aria-label={`Удалить резервную копию ${backup.name}`}
              onClick={() => handleDelete(backup.id)}
              className="admin-p-6px-12px-error-bd-c-error-2">
              
                  <Trash2 aria-hidden="true" className="w-4 h-4" />
                </Button>
              </div>
            </MacOSCard>
        )}
        </div>
      }
    </div>);

};

export default BackupManagement;
