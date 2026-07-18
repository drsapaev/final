import { useState, useEffect, useCallback } from 'react';
import type { CSSProperties } from 'react';
import {
  Key,
  Plus,
  Search,

  Edit,
  Trash2,
  Save,
  X,
  RefreshCw,
  Calendar,
  DollarSign,
  AlertTriangle,


  Shield,
  Copy,
  Eye,
  EyeOff } from
'lucide-react';
import {
  MacOSCard,
  Button as RawButton,
  Badge as RawBadge,
  Input as RawInput,
  Select as RawSelect,
  Textarea as RawTextarea,
  Skeleton as RawSkeleton,
  MacOSEmptyState as RawMacOSEmptyState,
  Alert as RawAlert,
} from '../ui/macos';
const Button = RawButton as unknown as React.ComponentType<Record<string, unknown>>;
const Badge = RawBadge as unknown as React.ComponentType<Record<string, unknown>>;
const Input = RawInput as unknown as React.ComponentType<Record<string, unknown>>;
const Select = RawSelect as unknown as React.ComponentType<Record<string, unknown>>;
const Textarea = RawTextarea as unknown as React.ComponentType<Record<string, unknown>>;
const Skeleton = RawSkeleton as unknown as React.ComponentType<Record<string, unknown>>;
const MacOSEmptyState = RawMacOSEmptyState as unknown as React.ComponentType<Record<string, unknown>>;
const Alert = RawAlert as unknown as React.ComponentType<Record<string, unknown>>;
import { api } from '../../api/client';

import logger from '../../utils/logger';
import { useTranslation } from '../../i18n/useTranslation';

const emptyLicenseStats = {
  total_licenses: 0,
  active_licenses: 0,
  expired_licenses: 0,
  expiring_licenses: 0
};

const deriveLicenseStats = (licenseList) => {
  const nextLicenses = Array.isArray(licenseList) ? licenseList : [];
  return {
    total_licenses: nextLicenses.length,
    active_licenses: nextLicenses.filter((license) => license.status === 'active').length,
    expired_licenses: nextLicenses.filter((license) => license.status === 'expired').length,
    expiring_licenses: nextLicenses.filter((license) => license.status === 'expiring').length
  };
};

const LicenseManagement = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [licenses, setLicenses] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [typeFilter, setTypeFilter] = useState('all');
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingLicense, setEditingLicense] = useState(null);
  const [message, setMessage] = useState({ type: '', text: '' });
  const [stats, setStats] = useState(null);
  const [showKeys, setShowKeys] = useState({});
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;

  // Форма лицензии
  const [formData, setFormData] = useState({
    name: '',
    type: '',
    license_key: '',
    vendor: '',
    status: 'active',
    purchase_date: '',
    expiry_date: '',
    cost: 0,
    seats: 1,
    description: ''
  } as any);

  const statusOptions = [
  { value: 'active', label: t('admin2.lm_status_active'), color: 'success' },
  { value: 'expired', label: t('admin2.lm_status_expired'), color: 'error' },
  { value: 'expiring', label: t('admin2.lm_status_expiring'), color: 'warning' },
  { value: 'suspended', label: t('admin2.lm_status_suspended'), color: 'gray' }];


  const typeOptions = [
  { value: 'software', label: t('admin2.lm_type_software') },
  { value: 'subscription', label: t('admin2.lm_type_subscription') },
  { value: 'perpetual', label: t('admin2.lm_type_perpetual') },
  { value: 'trial', label: t('admin2.lm_type_trial') },
  { value: 'academic', label: t('admin2.lm_type_academic') },
  { value: 'enterprise', label: t('admin2.lm_type_enterprise') }];


  const loadLicenses = useCallback(async () => {
    try {
      setLoading(true);
      const response = await api.get('/clinic/licenses') as any;
      const nextLicenses = Array.isArray(response.data)
        ? response.data
        : response.data?.licenses || [];
      setLicenses(nextLicenses);
      setStats(deriveLicenseStats(nextLicenses));
    } catch (error) {
      logger.error('Ошибка загрузки лицензий:', error);
      setLicenses([]);
      setStats(emptyLicenseStats);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadLicenses();
  }, [loadLicenses]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.name.trim() || !formData.type || !formData.license_key.trim()) {
      setMessage({ type: 'error', text: t('admin2.lm_msg_required') });
      return;
    }

    try {
      setSaving(true);

      if (editingLicense) {
        await api.put(`/clinic/licenses/${editingLicense.id}`, formData);
        setMessage({ type: 'success', text: t('admin2.lm_msg_updated') });
      } else {
        await api.post('/clinic/licenses', formData);
        setMessage({ type: 'success', text: t('admin2.lm_msg_created') });
      }

      setShowAddForm(false);
      setEditingLicense(null);
      resetForm();
      loadLicenses();
    } catch {
      setMessage({ type: 'error', text: t('admin2.lm_msg_save_error') });
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (license) => {
    setFormData(license);
    setEditingLicense(license);
    setShowAddForm(true);
  };

  const handleDelete = async (licenseId) => {
    try {
      await api.delete(`/clinic/licenses/${licenseId}`);
      setMessage({ type: 'success', text: t('admin2.lm_msg_deleted') });
      loadLicenses();
    } catch {
      setMessage({ type: 'error', text: t('admin2.lm_msg_delete_error') });
    }
  };

  const toggleKeyVisibility = (licenseId) => {
    setShowKeys((prev) => ({
      ...prev,
      [licenseId]: !prev[licenseId]
    }));
  };

  const copyKey = (key) => {
    navigator.clipboard.writeText(key);
    setMessage({ type: 'success', text: t('admin2.lm_msg_copied') });
  };

  const resetForm = () => {
    setFormData({
      name: '',
      type: '',
      license_key: '',
      vendor: '',
      status: 'active',
      purchase_date: '',
      expiry_date: '',
      cost: 0,
      seats: 1,
      description: ''
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

  const getTypeLabel = (type: string) => {
    const typeOption = typeOptions.find((t) => t.value === type);
    return typeOption ? typeOption.label : type;
  };

  const isExpiringSoon = (expiryDate) => {
    const expiry = new Date(expiryDate);
    const now = new Date();
    const diffTime = expiry.getTime() - now.getTime();
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return diffDays <= 30 && diffDays > 0;
  };

  const filteredLicenses = licenses.filter((license) => {
    const matchesSearch = license.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    license.vendor?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    license.license_key?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || license.status === statusFilter;
    const matchesType = typeFilter === 'all' || license.type === typeFilter;
    return matchesSearch && matchesStatus && matchesType;
  });
  const hasLicenseFilters = searchTerm.trim() !== '' || statusFilter !== 'all' || typeFilter !== 'all';
  const licenseEmptyTitle = hasLicenseFilters ? t('admin2.lm_empty_title_filtered') : t('admin2.lm_empty_title_initial');
  const licenseEmptyDescription = hasLicenseFilters ?
  t('admin2.lm_empty_desc_filtered') :
  t('admin2.lm_empty_desc_initial');

  return (
    <div className="admin-flex-col-gap-24-overflow-hidden">
      {/* Заголовок и статистика */}
      <div className="admin-flex-jc-between-ai-center-wrap-gap-16">
        <div>
          <h2 className="admin-2xl-bold-primary-m-008px0">
            {t('admin2.lm_page_title')}
          </h2>
          <p className="admin-secondary-sm-m-0">
            {t('admin2.lm_page_subtitle')}
          </p>
        </div>
        {stats &&
        <div className="admin-flex-gap-24-wrap">
            <div className="text-center">
              <div className="admin-2xl-bold-blue-mb-4">
                {stats.total_licenses}
              </div>
              <div className="text-sm text-[var(--mac-text-secondary)]">
                {t('admin2.lm_stat_total')}
              </div>
            </div>
            <div className="text-center">
              <div className="admin-2xl-bold-success-mb-4">
                {stats.active_licenses}
              </div>
              <div className="text-sm text-[var(--mac-text-secondary)]">
                {t('admin2.lm_stat_active')}
              </div>
            </div>
          </div>
        }
      </div>

      {/* Сообщения */}
      {message.text &&
      <Alert
        type={message.type === 'success' ? 'success' : 'error'}
        title={message.type === 'success' ? t('admin2.lm_alert_success') : t('admin2.lm_alert_error')}
        message={message.text} />

      }

      {/* Фильтры и поиск */}
      <MacOSCard className="p-6">
        <div className="admin-flex-col-gap-16-wrap">
          <div className="admin-flex-1-pos-relative">
            <Input
              type="text"
              aria-label={t('admin2.lm_search_aria')}
              placeholder={t('admin2.lm_search_placeholder')}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="admin-pl-40" />
            
            <Search aria-hidden="true" className="admin-pos-absolute-left-12-top-50pct-transform-translateY-50-tertiary-w-16-h-16" />
          </div>
          <div className="admin-flex-gap-12-wrap">
            <Select
              aria-label={t('admin2.lm_filter_status_aria')}
              value={statusFilter}
              onChange={(v: unknown) => setStatusFilter(String(v))}
              options={[
                { value: 'all', label: t('admin2.lm_filter_all_statuses') },
                ...statusOptions.map((option) => ({ value: option.value, label: option.label }))
              ]}
              size="large"
              className="admin-minw-150" />
            <Select
              aria-label={t('admin2.lm_filter_type_aria')}
              value={typeFilter}
              onChange={(v: unknown) => setTypeFilter(String(v))}
              options={[
                { value: 'all', label: t('admin2.lm_filter_all_types') },
                ...typeOptions.map((option) => ({ value: option.value, label: option.label }))
              ]}
              size="large"
              className="admin-minw-150" />
            <Button
              onClick={() => setShowAddForm(true)}
              className="admin-flex-ai-center-gap-8-bg-blue-bd-none-p-8px16">
              
              <Plus aria-hidden="true" className="w-4 h-4" />
              <span>{t('admin2.lm_btn_add')}</span>
            </Button>
          </div>
        </div>
      </MacOSCard>

      {/* Форма добавления/редактирования */}
      {showAddForm &&
      <MacOSCard className="admin-p-24-overflow-hidden">
          <div className="admin-flex-jc-between-ai-center-mb-16">
            <h3 className="admin-lg-semi-primary-m-0">
              {editingLicense ? t('admin2.lm_form_edit_title') : t('admin2.lm_form_create_title')}
            </h3>
            <Button
            variant="outline"
            type="button"
            aria-label={editingLicense ? t('admin2.lm_form_close_edit_aria') : t('admin2.lm_form_close_create_aria')}
            onClick={() => {
              setShowAddForm(false);
              setEditingLicense(null);
              resetForm();
            }}
            className="p-2">
            
              <X aria-hidden="true" className="w-4 h-4" />
            </Button>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="admin-grid-gtc-rauto-fitcminmax300pxc1fr-gap-16">
              <div>
                <label className="admin-block-sm-med-primary-mb-4">
                  {t('admin2.lm_field_name')}
                </label>
                <Input
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder={t('admin2.lm_field_name_placeholder')} />
              
              </div>
              <div>
                <label className="admin-block-sm-med-primary-mb-4">
                  {t('admin2.lm_field_type')}
                </label>
                <Select
                aria-label={t('admin2.lm_field_type_aria')}
                value={formData.type}
                onChange={(value: unknown) => setFormData({ ...formData, type: String(value) })}
                options={[
                  { value: '', label: t('admin2.lm_field_type_select_option') },
                  ...typeOptions.map((option) => ({ value: option.value, label: option.label }))
                ]}
                size="large" />
              </div>
              <div>
                <label className="admin-block-sm-med-primary-mb-4">
                  {t('admin2.lm_field_license_key')}
                </label>
                <Input
                type="text"
                required
                value={formData.license_key}
                onChange={(e) => setFormData({ ...formData, license_key: e.target.value })}
                placeholder={t('admin2.lm_field_license_key_placeholder')} />
              
              </div>
              <div>
                <label className="admin-block-sm-med-primary-mb-4">
                  {t('admin2.lm_field_vendor')}
                </label>
                <Input
                type="text"
                value={formData.vendor}
                onChange={(e) => setFormData({ ...formData, vendor: e.target.value })}
                placeholder={t('admin2.lm_field_vendor_placeholder')} />
              
              </div>
              <div>
                <label className="admin-block-sm-med-primary-mb-4">
                  {t('admin2.lm_field_status')}
                </label>
                <Select
                aria-label={t('admin2.lm_field_status_aria')}
                value={formData.status}
                onChange={(value: unknown) => setFormData({ ...formData, status: String(value) })}
                options={statusOptions.map((option) => ({ value: option.value, label: option.label }))}
                size="large" />
              </div>
              <div>
                <label className="admin-block-sm-med-primary-mb-4">
                  {t('admin2.lm_field_purchase_date')}
                </label>
                <Input
                type="date"
                value={formData.purchase_date}
                onChange={(e) => setFormData({ ...formData, purchase_date: e.target.value })} />
              
              </div>
              <div>
                <label className="admin-block-sm-med-primary-mb-4">
                  {t('admin2.lm_field_expiry_date')}
                </label>
                <Input
                type="date"
                value={formData.expiry_date}
                onChange={(e) => setFormData({ ...formData, expiry_date: e.target.value })} />
              
              </div>
              <div>
                <label className="admin-block-sm-med-primary-mb-4">
                  {t('admin2.lm_field_cost')}
                </label>
                <Input
                type="number"
                value={formData.cost}
                onChange={(e) => setFormData({ ...formData, cost: parseFloat(e.target.value) })}
                placeholder={t('admin2.lm_field_cost_placeholder')} />
              
              </div>
              <div>
                <label className="admin-block-sm-med-primary-mb-4">
                  {t('admin2.lm_field_seats')}
                </label>
                <Input
                type="number"
                min="1"
                value={formData.seats}
                onChange={(e) => setFormData({ ...formData, seats: parseInt(e.target.value) })}
                placeholder={t('admin2.lm_field_seats_placeholder')} />
              
              </div>
            </div>

            <div>
              <label className="admin-block-sm-med-primary-mb-4">
                {t('admin2.lm_field_description')}
              </label>
              <Textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder={t('admin2.lm_field_description_placeholder')}
              rows={3} />
            
            </div>

            <div className="admin-flex-jc-end-gap-12">
              <Button
              type="button"
              variant="outline"
              onClick={() => {
                setShowAddForm(false);
                setEditingLicense(null);
                resetForm();
              }}
              disabled={saving}>
              
                {t('admin2.cancel')}
              </Button>
              <Button
              type="submit"
              disabled={saving}
              aria-label={editingLicense ? 'Update license' : 'Add license'}
              className="admin-flex-ai-center-gap-8-bg-blue-bd-none">
              
                {saving ?
              <>
                    <RefreshCw aria-hidden="true" className="admin-w-16-h-16-anim-spin1slinearinfinite" />
                    {t('admin2.lm_btn_saving')}
                  </> :

              <>
                    <Save aria-hidden="true" className="w-4 h-4" />
                    {editingLicense ? t('admin2.lm_btn_update') : t('admin2.lm_btn_add_submit')}
                  </>
              }
              </Button>
            </div>
          </form>
        </MacOSCard>
      }

      {/* Список лицензий */}
      {loading ?
      <div className="admin-grid-gtc-rauto-fitcminmax300pxc1fr-gap-24-overflow-hidden">
          {[1, 2, 3].map((i) =>
        <MacOSCard key={i} className="p-6">
              <Skeleton height="200px" />
            </MacOSCard>
        )}
        </div> :
      filteredLicenses.length === 0 ?
      <MacOSEmptyState
        icon={Key}
        title={licenseEmptyTitle}
        description={licenseEmptyDescription}
        action={
        <Button onClick={() => setShowAddForm(true)} variant="primary">
              <Plus aria-hidden="true" focusable="false" className="w-4 h-4 mr-2" />
              {t('admin2.lm_btn_add')}
            </Button>
        } /> :


      <div className="admin-grid-gtc-rauto-fitcminmax300pxc1fr-gap-24-overflow-hidden">
          {filteredLicenses.map((license) =>
        <MacOSCard key={license.id} className="p-6">
              <div className="admin-flex-jc-between-ai-start-mb-16">
                <div>
                  <h3 className="admin-lg-semi-primary-m-004px0">
                    {license.name}
                  </h3>
                  <p className="admin-sm-secondary-m-0">
                    {license.vendor} • {getTypeLabel(license.type)}
                  </p>
                </div>
                <Badge
              variant={getStatusColor(license.status)}
              text={getStatusLabel(license.status)} />
            
              </div>

              <div className="admin-flex-col-gap-8-mb-16">
                <div className="admin-flex-ai-center-gap-8-sm-secondary">
                  <Key aria-hidden="true" className="w-4 h-4" />
                  <span className="admin-fontfamily-e89ae9-bg-bg-secondary-p-2px6-radius-4-xs">
                    {showKeys[license.id] ? license.license_key : '••••••••••••••••'}
                  </span>
                  <Button
                type="button"
                variant="outline"
                aria-label={showKeys[license.id] ? t('admin2.lm_key_hide_aria', { name: license.name }) : t('admin2.lm_key_show_aria', { name: license.name })}
                onClick={() => toggleKeyVisibility(license.id)}
                className="admin-p-2px6-minw-auto">
                
                    {showKeys[license.id] ?
                <EyeOff aria-hidden="true" className="admin-w-12-h-12" /> :

                <Eye aria-hidden="true" className="admin-w-12-h-12" />
                }
                  </Button>
                  <Button
                type="button"
                variant="outline"
                aria-label={t('admin2.lm_key_copy_aria', { name: license.name })}
                onClick={() => copyKey(license.license_key)}
                className="admin-p-2px6-minw-auto">
                
                    <Copy aria-hidden="true" className="admin-w-12-h-12" />
                  </Button>
                </div>
                {license.cost > 0 &&
            <div className="admin-flex-ai-center-gap-8-sm-secondary">
                    <DollarSign aria-hidden="true" className="w-4 h-4" />
                    <span>{t('admin2.lm_cost_display', { cost: license.cost.toLocaleString() })}</span>
                  </div>
            }
                <div className="admin-flex-ai-center-gap-8-sm-secondary">
                  <Shield aria-hidden="true" className="w-4 h-4" />
                  <span>{t('admin2.lm_seats_count', { count: license.seats })}</span>
                </div>
                {license.expiry_date &&
            <div className="admin-flex-ai-center-gap-8-sm" style={{ '--admin-color': isExpiringSoon(license.expiry_date) ? 'var(--mac-warning)' : 'var(--mac-text-secondary)' } as CSSProperties}>
                    <Calendar aria-hidden="true" className="w-4 h-4" />
                    <span>{t('admin2.lm_expiry_label', { date: new Date(license.expiry_date).toLocaleDateString() })}</span>
                    {isExpiringSoon(license.expiry_date) &&
              <AlertTriangle aria-hidden="true" className="w-3.5 h-3.5" />
              }
                  </div>
            }
              </div>

              {license.description &&
          <div className="mb-4">
                  <p className="admin-sm-secondary-m-0-lh-14">
                    {license.description}
                  </p>
                </div>
          }

              <div className="admin-flex-jc-end-gap-8">
                <Button
              type="button"
              variant="outline"
              aria-label={t('admin2.lm_row_edit_aria', { name: license.name })}
              onClick={() => handleEdit(license)}
              className="admin-p-6px12">
              
                  <Edit aria-hidden="true" className="w-4 h-4" />
                </Button>
                <Button
              type="button"
              variant="outline"
              aria-label={t('admin2.lm_row_delete_aria', { name: license.name })}
              onClick={() => handleDelete(license.id)}
              className="admin-p-6px12-error-bd-error">
              
                  <Trash2 aria-hidden="true" className="w-4 h-4" />
                </Button>
              </div>
            </MacOSCard>
        )}
        </div>
      }
    </div>);

};

export default LicenseManagement;
