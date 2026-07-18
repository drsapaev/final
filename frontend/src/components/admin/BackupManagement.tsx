import { useState, useEffect, useCallback } from 'react';
import type { CSSProperties } from 'react';
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
  Button as RawButton,
  Badge as RawBadge,
  Input,
  Select as RawSelect,
  Textarea as RawTextarea,
  Checkbox as RawCheckbox,
  Skeleton as RawSkeleton,
  MacOSEmptyState as RawMacOSEmptyState,
  Alert as RawAlert,
} from '../ui/macos';
const Button = RawButton as unknown as React.ComponentType<Record<string, unknown>>;
const Badge = RawBadge as unknown as React.ComponentType<Record<string, unknown>>;
const Select = RawSelect as unknown as React.ComponentType<Record<string, unknown>>;
const Textarea = RawTextarea as unknown as React.ComponentType<Record<string, unknown>>;
const Checkbox = RawCheckbox as unknown as React.ComponentType<Record<string, unknown>>;
const Skeleton = RawSkeleton as unknown as React.ComponentType<Record<string, unknown>>;
const MacOSEmptyState = RawMacOSEmptyState as unknown as React.ComponentType<Record<string, unknown>>;
const Alert = RawAlert as unknown as React.ComponentType<Record<string, unknown>>;
import { api } from '../../api/client';

import logger from '../../utils/logger';
import { useTranslation } from '../../i18n/useTranslation';

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

const defaultBackupForm: Record<string, unknown> = {
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
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;

  // Форма резервной копии
  const [formData, setFormData] = useState(defaultBackupForm);

  const statusOptions = [
  { value: 'pending', label: t('admin2.bk_status_pending'), color: 'gray' },
  { value: 'in_progress', label: t('admin2.bk_status_in_progress'), color: 'warning' },
  { value: 'completed', label: t('admin2.bk_status_completed'), color: 'success' },
  { value: 'failed', label: t('admin2.bk_status_failed'), color: 'error' },
  { value: 'cancelled', label: t('admin2.bk_status_cancelled'), color: 'gray' }];


  const typeOptions = [
  { value: 'full', label: t('admin2.bk_type_full') },
  { value: 'incremental', label: t('admin2.bk_type_incremental') },
  { value: 'differential', label: t('admin2.bk_type_differential') },
  { value: 'database', label: t('admin2.bk_type_database') },
  { value: 'files', label: t('admin2.bk_type_files') }];


  const scheduleOptions = [
  { value: 'manual', label: t('admin2.bk_schedule_manual') },
  { value: 'daily', label: t('admin2.bk_schedule_daily') },
  { value: 'weekly', label: t('admin2.bk_schedule_weekly') },
  { value: 'monthly', label: t('admin2.bk_schedule_monthly') }];


  const loadBackups = useCallback(async () => {
    try {
      setLoading(true);
      const response = await api.get('/clinic/backups') as any;
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
        setMessage({ type: 'success', text: t('admin2.bk_msg_updated') });
      } else {
        await api.post('/clinic/backups', formData);
        setMessage({ type: 'success', text: t('admin2.bk_msg_created') });
      }

      setShowAddForm(false);
      setEditingBackup(null);
      resetForm();
      loadBackups();
    } catch {
      setMessage({ type: 'error', text: t('admin2.bk_msg_save_error') });
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
      setMessage({ type: 'success', text: t('admin2.bk_msg_deleted') });
      loadBackups();
    } catch {
      setMessage({ type: 'error', text: t('admin2.bk_msg_delete_error') });
    }
  };

  const handleCleanupExpired = async () => {
    try {
      const response = await api.post('/clinic/backups/cleanup') as any;
      const cleanedCount = response.data?.cleaned_count ?? 0;
      setMessage({
        type: 'success',
        text: t('admin2.bk_msg_cleanup_success', { count: cleanedCount })
      });
      loadBackups();
    } catch {
      setMessage({ type: 'error', text: t('admin2.bk_msg_cleanup_error') });
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
  const backupEmptyTitle = hasBackupFilters ? t('admin2.bk_empty_title_filtered') : t('admin2.bk_empty_title_initial');
  const backupEmptyDescription = hasBackupFilters ?
  t('admin2.bk_empty_desc_filtered') :
  t('admin2.bk_empty_desc_initial');

  return (
    <div className="admin-d-flex-fd-column-gap-24-ov-hidden-2">
      {/* Заголовок и статистика */}
      <div className="admin-d-flex-jc-between-ai-center-fw-wrap-gap-16-2">
        <div>
          <h2 className="admin-fs-2xl-fw-bold-primary-m-0-0-8px-0-2">
            {t('admin2.bk_page_title')}
          </h2>
          <p className="admin-secondary-fs-sm-m-0-4">
            {t('admin2.bk_page_subtitle')}
          </p>
        </div>
        {stats &&
        <div className="admin-d-flex-gap-24-fw-wrap-2">
            <div className="text-center">
              <div className="admin-fs-2xl-fw-bold-blue-mb-4-2">
                {stats.total_backups}
              </div>
              <div className="text-sm text-[var(--mac-text-secondary)]">
                {t('admin2.bk_stat_total')}
              </div>
            </div>
            <div className="text-center">
              <div className="admin-fs-2xl-fw-bold-success-mb-4-2">
                {stats.completed_backups}
              </div>
              <div className="text-sm text-[var(--mac-text-secondary)]">
                {t('admin2.bk_status_completed')}
              </div>
            </div>
            <div className="text-center">
              <div className="admin-fs-2xl-fw-bold-warning-mb-4">
                {formatFileSize(stats.total_size)}
              </div>
              <div className="text-sm text-[var(--mac-text-secondary)]">
                {t('admin2.bk_stat_size')}
              </div>
            </div>
          </div>
        }
      </div>

      {/* Сообщения */}
      {message.text &&
      <Alert
        type={message.type === 'success' ? 'success' : 'error'}
        title={message.type === 'success' ? t('admin2.bk_alert_success') : t('admin2.bk_alert_error')}
        message={message.text} />

      }

      {/* Фильтры и поиск */}
      <MacOSCard className="p-6">
        <div className="admin-d-flex-fd-column-gap-16-fw-wrap-2">
          <div className="admin-flex-1-pos-relative">
            <Input
              type="text"
              aria-label={t('admin2.bk_search_aria')}
              placeholder={t('admin2.bk_search_placeholder')}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="admin-pl-40" />
            
            <Search aria-hidden="true" className="admin-pos-absolute-left-12-top-50pct-tf-translateY-50-tertiary-w-16-h-16-2" />
          </div>
          <div className="admin-d-flex-gap-12-fw-wrap-2">
            <Select
              aria-label={t('admin2.bk_filter_status_aria')}
              value={statusFilter}
              onChange={(v: unknown) => setStatusFilter(String(v))}
              options={[
                { value: 'all', label: t('admin2.bk_filter_all_statuses') },
                ...statusOptions.map((option) => ({ value: option.value, label: option.label }))
              ]}
              size="large"
              className="admin-minw-150" />
            <Select
              aria-label={t('admin2.bk_filter_type_aria')}
              value={typeFilter}
              onChange={(v: unknown) => setTypeFilter(String(v))}
              options={[
                { value: 'all', label: t('admin2.bk_filter_all_types') },
                ...typeOptions.map((option) => ({ value: option.value, label: option.label }))
              ]}
              size="large"
              className="admin-minw-150" />
            <Button
              onClick={() => setShowAddForm(true)}
              className="admin-d-flex-ai-center-gap-8-bgc-blue-bd-none-p-8px-16px-2">
              
              <Plus aria-hidden="true" className="w-4 h-4" />
              <span>{t('admin2.bk_btn_create')}</span>
            </Button>
            <Button
              type="button"
              aria-label={t('admin2.bk_btn_cleanup_aria')}
              onClick={handleCleanupExpired}
              variant="outline"
              className="flex items-center justify-center gap-2">
              <RefreshCw aria-hidden="true" className="w-4 h-4" />
              <span>{t('admin2.bk_btn_cleanup')}</span>
            </Button>
          </div>
        </div>
      </MacOSCard>

      {/* Форма создания/редактирования */}
      {showAddForm &&
      <MacOSCard className="admin-p-24-ov-hidden-2">
          <div className="admin-d-flex-jc-between-ai-center-mb-16-4">
            <h3 className="admin-fs-lg-fw-semi-primary-m-0-3">
              {editingBackup ? t('admin2.bk_form_edit_title') : t('admin2.bk_form_create_title')}
            </h3>
            <Button
            variant="outline"
            type="button"
            aria-label={editingBackup ? t('admin2.bk_form_close_edit_aria') : t('admin2.bk_form_close_create_aria')}
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
                  {t('admin2.bk_field_name')}
                </label>
                <Input
                type="text"
                required
                value={formData.name as string}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder={t('admin2.bk_field_name_placeholder')} />
              
              </div>
              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-4-20">
                  {t('admin2.bk_field_type')}
                </label>
                <Select
                aria-label={t('admin2.bk_field_type_aria')}
                value={formData.backup_type as string}
                onChange={(value) => setFormData({ ...formData, backup_type: value })}
                options={typeOptions.map((option) => ({ value: option.value, label: option.label }))}
                size="large" />
              </div>
              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-4-19">
                  {t('admin2.bk_field_schedule')}
                </label>
                <Select
                aria-label={t('admin2.bk_field_schedule_aria')}
                value={formData.schedule as string}
                onChange={(value) => setFormData({ ...formData, schedule: value })}
                options={scheduleOptions.map((option) => ({ value: option.value, label: option.label }))}
                size="large" />
              </div>
              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-4-18">
                  {t('admin2.bk_field_retention')}
                </label>
                <Input
                type="number"
                min="1"
                value={formData.retention_days as number}
                onChange={(e) => setFormData({ ...formData, retention_days: parseInt(e.target.value) })}
                placeholder={t('admin2.bk_field_retention_placeholder')} />
              
              </div>
            </div>

            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8-15">
                {t('admin2.bk_field_description')}
              </label>
              <Textarea
              value={formData.description as string}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder={t('admin2.bk_field_description_placeholder')}
              rows={3} />
            
            </div>

            <div className="flex flex-col gap-3">
              <div className="admin-flex-center-12">
                <Checkbox
                checked={formData.compression}
                onChange={(checked) => setFormData({ ...formData, compression: checked })} />
              
                <span className="admin-fs-sm-primary-2">
                  {t('admin2.bk_field_compression')}
                </span>
              </div>
              <div className="admin-flex-center-12">
                <Checkbox
                checked={formData.encryption}
                onChange={(checked) => setFormData({ ...formData, encryption: checked })} />
              
                <span className="admin-fs-sm-primary-1">
                  {t('admin2.bk_field_encryption')}
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

                {t('admin2.cancel')}
              </Button>
              <Button
              type="submit"
              disabled={saving}
              aria-label={editingBackup ? 'Update backup configuration' : 'Create backup configuration'}
              className="admin-d-flex-ai-center-gap-8-bgc-blue-bd-none-2">
              
                {saving ?
              <>
                    <RefreshCw aria-hidden="true" className="admin-w-16-h-16-anim-spin-1s-linear-infin-2" />
                    {t('admin2.bk_btn_saving')}
                  </> :

              <>
                    <Save aria-hidden="true" className="w-4 h-4" />
                    {editingBackup ? t('admin2.bk_btn_update') : t('admin2.bk_btn_create_submit')}
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
              {t('admin2.bk_btn_create')}
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
                    {getTypeLabel(backup.backup_type)} • {t('admin2.bk_retention_inline', { days: backup.retention_days })}
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
                  <span>{t('admin2.bk_retention_label', { days: backup.retention_days })}</span>
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
              aria-label={t('admin2.bk_row_edit_aria', { name: backup.name })}
              onClick={() => handleEdit(backup)}
              className="admin-p-6px-12px-2">
              
                  <Edit aria-hidden="true" className="w-4 h-4" />
                </Button>
                <Button
              type="button"
              variant="outline"
              aria-label={t('admin2.bk_row_delete_aria', { name: backup.name })}
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
