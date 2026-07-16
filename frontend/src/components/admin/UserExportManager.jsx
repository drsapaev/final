import { useTranslation } from '../../i18n/useTranslation';
import { useState, useEffect } from 'react';
import {
  Users,
  Download,
  FileText,
  Filter,



  RefreshCw,
  Trash2,

  Settings,
  FileSpreadsheet,
  FileJson,
  FileText as FilePdf,
  File } from
'lucide-react';
import {
  MacOSCard, Button, Input, Select, Checkbox, SegmentedControl, Skeleton,
} from '../ui/macos';
import { toast } from 'react-toastify';
import { api } from '../../api/client';

import logger from '../../utils/logger';
// P-013 fix: shared ConfirmDialog hook replacing native confirm() calls.
import { useConfirm } from '../common/ConfirmDialog';
const UserExportManager = () => {
  const { t } = useTranslation();
  // P-013 fix: shared ConfirmDialog hook (replaces 1 native confirm() call).
  const [confirm, confirmDialog] = useConfirm();
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
  { value: 'username', label: t('admin2.ue_field_username') },
  { value: 'email', label: 'Email' },
  { value: 'role', label: t('admin2.ue_field_role') },
  { value: 'is_active', label: t('admin2.ue_field_active') },
  { value: 'created_at', label: t('admin2.ue_field_created_at') },
  { value: 'updated_at', label: t('admin2.ue_field_updated_at') },
  { value: 'last_login', label: t('admin2.ue_field_last_login') },
  { value: 'full_name', label: t('admin2.ue_field_full_name') },
  { value: 'phone', label: t('admin2.ue_field_phone') },
  { value: 'birth_date', label: t('admin2.ue_field_birth_date') },
  { value: 'gender', label: t('admin2.ue_field_gender') },
  { value: 'address', label: t('admin2.ue_field_address') }];


  // Роли пользователей
  const userRoles = [
  { value: '', label: t('admin2.ue_role_all') },
  { value: 'Admin', label: t('admin2.ue_role_admin') },
  { value: 'Doctor', label: t('admin2.ue_role_doctor') },
  { value: 'Registrar', label: t('admin2.ue_role_registrar') },
  { value: 'Patient', label: t('admin2.ue_role_patient') },
  { value: 'Cashier', label: t('admin2.ue_role_cashier') },
  { value: 'Lab', label: t('admin2.ue_role_lab') }];


  // Загрузка данных
  useEffect(() => {
    if (activeTab === 'files') {
      loadExportFiles();
    }
  }, [activeTab]);

  const loadExportFiles = async () => {
    setLoading(true);
    try {
      const response = await api.get('/users/users/export/files');
      setExportFiles(response.data.files || []);
    } catch (error) {
      logger.error('Ошибка загрузки файлов экспорта:', error);
      toast.error(t('admin2.ue_load_error_toast'));
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

      const response = await api.post('/users/users/export', exportData);

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
      logger.error('Ошибка экспорта:', error);
      toast.error(error.response?.data?.detail || t('admin2.ue_export_error_fallback'));
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (filename) => {
    try {
      const response = await api.get(`/users/users/export/download/${filename}`, {
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

      toast.success(t('admin2.ue_download_success', { filename }));
    } catch (error) {
      logger.error('Ошибка скачивания:', error);
      toast.error(t('admin2.ue_download_error_toast'));
    }
  };

  const handleDeleteFile = async (filename) => {
    // P-013 fix: replaced native confirm() with shared useConfirm hook.
    const ok = await confirm({
      title: t('admin2.delete_file_title'),
      message: t('admin2.ue_delete_file_message', { filename }),
      description: t('admin2.ue_delete_description'),
      confirmLabel: t('admin2.delete_confirm'),
      cancelLabel: t('admin2.cancel'),
      intent: 'danger',
    });
    if (!ok) return;

    try {
      await api.delete(`/users/users/export/files/${filename}`);
      toast.success(t('admin2.ue_delete_success_toast', { filename }));
      loadExportFiles();
    } catch (error) {
      logger.error('Ошибка удаления:', error);
      toast.error(t('admin2.ue_delete_error_toast'));
    }
  };










  const getFileIcon = (filename) => {
    if (filename.endsWith('.csv')) return <FileText className="admin-w-20-h-20-success" />;
    if (filename.endsWith('.xlsx')) return <FileSpreadsheet className="admin-w-20-h-20-blue" />;
    if (filename.endsWith('.json')) return <FileJson className="admin-w-20-h-20-warning" />;
    if (filename.endsWith('.pdf')) return <FilePdf className="admin-w-20-h-20-error" />;
    return <File className="admin-w-20-h-20-tertiary" />;
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
    padding: 'var(--mac-spacing-6)',
    minHeight: '100vh',
    backgroundColor: 'var(--mac-bg-primary)'
  };
















  const renderExportTab = () =>
  <div className="admin-d-grid-gtc-1fr-1fr-gap-24">
      {/* Левая панель - настройки экспорта */}
      <MacOSCard className="admin-p-24">
        <h3 className="admin-m-0-0-24px-0-d-flex-ai-center-gap-8-fs-lg-fw-med-primary">
          <Settings className="admin-icon-20" />
          {t('admin2.ue_settings_title')}
        </h3>

        {/* Формат экспорта */}
        <div className="admin-mb-16">
          <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
            {t('admin2.ue_label_format')}
          </label>
          <Select
          value={exportForm.format}
          onChange={(value) => setExportForm((prev) => ({ ...prev, format: value }))}
          options={[
          { value: 'csv', label: 'CSV' },
          { value: 'excel', label: 'Excel (XLSX)' },
          { value: 'json', label: 'JSON' },
          { value: 'pdf', label: 'PDF' }]
          }
          size="large"
          className="admin-w-full" />

        </div>

        {/* Поля для экспорта */}
        <div className="admin-mb-16">
          <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
            {t('admin2.ue_label_fields')}
          </label>
          <div className="admin-d-grid-gtc-repeat-auto-fill-min-gap-8-mt-8-maxh-200-ovy-auto-p-12-bd-1px-solid-var-mac-bo-radius-var-mac-radius-sm-bgc-bg-secondary">
            {availableFields.map((field) =>
          <label key={field.value} className="admin-d-flex-ai-center-gap-8-cur-pointer-fs-sm-primary">
                <Checkbox
              checked={exportForm.fields.includes(field.value)}
              onChange={(checked) => {
                if (checked) {
                  setExportForm((prev) => ({ ...prev, fields: [...prev.fields, field.value] }));
                } else {
                  setExportForm((prev) => ({ ...prev, fields: prev.fields.filter((f) => f !== field.value) }));
                }
              }}
              className="admin-mr-8" />

                <span>{field.label}</span>
              </label>
          )}
          </div>
        </div>

        {/* Дополнительные данные */}
        <div className="admin-mb-16">
          <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
            {t('admin2.ue_label_extra_data')}
          </label>
          <div className="admin-d-flex-fd-column-gap-8-mt-8">
            <label className="admin-d-flex-ai-center-gap-8-cur-pointer-fs-sm-primary">
              <Checkbox
              checked={exportForm.include_profile}
              onChange={(checked) => setExportForm((prev) => ({ ...prev, include_profile: checked }))}
              className="admin-mr-8" />

              <span>{t('admin2.ue_include_profile')}</span>
            </label>
            <label className="admin-d-flex-ai-center-gap-8-cur-pointer-fs-sm-primary">
              <Checkbox
              checked={exportForm.include_preferences}
              onChange={(checked) => setExportForm((prev) => ({ ...prev, include_preferences: checked }))}
              className="admin-mr-8" />

              <span>{t('admin2.ue_include_preferences')}</span>
            </label>
            <label className="admin-d-flex-ai-center-gap-8-cur-pointer-fs-sm-primary">
              <Checkbox
              checked={exportForm.include_audit_logs}
              onChange={(checked) => setExportForm((prev) => ({ ...prev, include_audit_logs: checked }))}
              className="admin-mr-8" />

              <span>{t('admin2.ue_include_audit_logs')}</span>
            </label>
          </div>
        </div>
      </MacOSCard>

      {/* Правая панель - фильтры */}
      <MacOSCard className="admin-p-24">
        <h3 className="admin-m-0-0-24px-0-d-flex-ai-center-gap-8-fs-lg-fw-med-primary">
          <Filter className="admin-icon-20" />
          {t('admin2.ue_filters_title')}
        </h3>

        <div className="admin-flex-col-16">
          <div>
            <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
              {t('admin2.ue_label_username')}
            </label>
            <Input
            placeholder={t('admin2.ue_placeholder_username')}
            value={exportForm.filters.username}
            onChange={(e) => setExportForm((prev) => ({
              ...prev,
              filters: { ...prev.filters, username: e.target.value }
            }))}
            className="admin-w-full" />

          </div>

          <div>
            <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
              Email:
            </label>
            <Input
            placeholder={t('admin2.ue_placeholder_email')}
            value={exportForm.filters.email}
            onChange={(e) => setExportForm((prev) => ({
              ...prev,
              filters: { ...prev.filters, email: e.target.value }
            }))}
            className="admin-w-full" />

          </div>

          <div>
            <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
              {t('admin2.ue_label_role')}
            </label>
            <Select
            value={exportForm.filters.role}
            onChange={(value) => setExportForm((prev) => ({
              ...prev,
              filters: { ...prev.filters, role: value }
            }))}
            options={userRoles}
            size="large"
            className="admin-w-full" />

          </div>

          <div>
            <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
              {t('admin2.ue_label_status')}
            </label>
            <Select
            value={exportForm.filters.is_active === null ? '' : exportForm.filters.is_active.toString()}
            onChange={(value) => setExportForm((prev) => ({
              ...prev,
              filters: {
                ...prev.filters,
                is_active: value === '' ? null : value === 'true'
              }
            }))}
            options={[
            { value: '', label: t('admin2.ue_status_all') },
            { value: 'true', label: t('admin2.ue_status_active_only') },
            { value: 'false', label: t('admin2.ue_status_inactive_only') }]
            }
            size="large"
            className="admin-w-full" />

          </div>

          <div>
            <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
              {t('admin2.ue_label_created_from')}
            </label>
            <Input
            type="date"
            value={exportForm.filters.created_from}
            onChange={(e) => setExportForm((prev) => ({
              ...prev,
              filters: { ...prev.filters, created_from: e.target.value }
            }))}
            className="admin-w-full" />

          </div>

          <div>
            <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
              {t('admin2.ue_label_created_to')}
            </label>
            <Input
            type="date"
            value={exportForm.filters.created_to}
            onChange={(e) => setExportForm((prev) => ({
              ...prev,
              filters: { ...prev.filters, created_to: e.target.value }
            }))}
            className="admin-w-full" />

          </div>
        </div>

        {/* Кнопка экспорта */}
        <div className="admin-mt-24">
          <Button
          type="button"
          onClick={handleExport}
          disabled={loading}
          aria-label="Start user data export"
          className="admin-w-full">

            {loading ?
          <>
                <RefreshCw className="admin-w-16-h-16-anim-spin-1s-linear-infin" />
                {t('admin2.ue_exporting_btn')}
              </> :

          <>
                <Download className="admin-icon-16" />
                {t('admin2.ue_start_export_btn')}
              </>
          }
          </Button>
        </div>
      </MacOSCard>
    </div>;


  const renderFilesTab = () =>
  <MacOSCard className="admin-p-24">
      <div className="admin-d-flex-jc-between-ai-center-mb-24">
        <h3 className="admin-m-0-d-flex-ai-center-gap-8-fs-lg-fw-med-primary">
          <FileText className="admin-icon-20" />
          {t('admin2.ue_files_title')}
        </h3>
        <Button onClick={loadExportFiles} disabled={loading}>
          <RefreshCw className="admin-icon-16" />
          {t('admin2.ue_refresh_btn')}
        </Button>
      </div>

      {loading ?
    <div>
          <Skeleton height="60px" className="admin-mb-8" />
          <Skeleton height="60px" className="admin-mb-8" />
          <Skeleton height="60px" />
        </div> :
    exportFiles.length === 0 ?
    <div className="admin-ta-center-p-32-secondary-fs-sm">
          <FileText className="admin-w-48-h-48-mb-16-tertiary" />
          <p className="admin-m-0">{t('admin2.ue_no_files_title')}</p>
          <p className="admin-m-8px-0-0-0">{t('admin2.ue_no_files_hint')}</p>
        </div> :

    <div className="admin-flex-col-8">
          {exportFiles.map((file, index) =>
      <div
        key={index}
        className="admin-d-flex-ai-center-jc-between-p-16-bgc-bg-secondary-radius-var-mac-radius-md-bd-1px-solid-var-mac-bo">

              <div className="admin-d-flex-ai-center-gap-16">
                {getFileIcon(file.filename)}
                <div>
                  <div className="admin-fw-semi-fs-sm-primary">
                    {file.filename}
                  </div>
                  <div className="admin-fs-xs-secondary">
                    {t('admin2.ue_size_label')}{formatFileSize(file.size)} | 
                    {t('admin2.ue_created_label')}{new Date(file.created_at).toLocaleString('ru-RU')}
                  </div>
                </div>
              </div>
              
              <div className="admin-d-flex-gap-8">
                <Button
            size="sm"
            onClick={() => handleDownload(file.filename)}>

                  <Download className="admin-icon-14" />
                  {t('admin2.ue_download_btn')}
                </Button>
                <Button
            size="sm"
            variant="danger"
            onClick={() => handleDeleteFile(file.filename)}>

                  <Trash2 className="admin-icon-14" />
                  {t('admin2.ue_delete_btn')}
                </Button>
              </div>
            </div>
      )}
        </div>
    }
    </MacOSCard>;


  return (
    <div style={containerStyle}>
      <div className="admin-mb-24">
        <h1 className="admin-m-0-fs-2xl-fw-semi-primary-d-flex-ai-center-gap-12">
          <Users className="admin-w-32-h-32" />
          {t('admin2.ue_page_title')}
        </h1>
        <p className="admin-m-8px-0-0-0-secondary-fs-sm">
          {t('admin2.ue_page_subtitle')}
        </p>
      </div>

      {/* Табы */}
      <div className="admin-maxw-100pct-ovx-auto-pb-6-mb-24-scrollba-thin">
        <SegmentedControl
          aria-label={t('admin2.ue_tabs_aria')}
          value={activeTab}
          onChange={setActiveTab}
          options={[
            {
              value: 'export',
              label: (
                <span className="admin-d-inline-flex-ai-center-gap-8">
                  <Download size={14} aria-hidden="true" />
                  {t('admin2.ue_tab_export')}
                </span>
              )
            },
            {
              value: 'files',
              label: (
                <span className="admin-d-inline-flex-ai-center-gap-8">
                  <FileText size={14} aria-hidden="true" />
                  {t('admin2.ue_tab_files', { count: exportFiles.length })}
                </span>
              )
            }
          ]}
          size="large"
          className="admin-minw-max-content-bg-var-mac-gradient-sid-bd-1px-solid-var-mac-ma-radius-14-bsh-var-mac-main-shell-s" />
      </div>

      {/* Содержимое табов */}
      {activeTab === 'export' && renderExportTab()}
      {activeTab === 'files' && renderFilesTab()}
      {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
      {confirmDialog}
    </div>);

};

export default UserExportManager;
