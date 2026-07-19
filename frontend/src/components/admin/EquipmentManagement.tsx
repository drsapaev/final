import { useState, useEffect, useCallback } from 'react';
import {
  Wrench,
  Plus,
  Search,

  Edit,
  Trash2,
  Save,
  X,
  RefreshCw,
  Calendar,
  DollarSign,




  Building2 } from
'lucide-react';
import {
  MacOSCard,
  Button,
  Badge,
  Input,
  Select,
  Textarea,
  Skeleton,
  MacOSEmptyState,
  Alert,
} from '../ui/macos';
import { api } from '../../api/client';

import logger from '../../utils/logger';
import { useTranslation } from '../../i18n/useTranslation';

const emptyEquipmentStats = {
  total_equipment: 0,
  active_equipment: 0,
  maintenance_equipment: 0,
  broken_equipment: 0
};

const deriveEquipmentStats = (equipmentList) => {
  const nextEquipment = Array.isArray(equipmentList) ? equipmentList : [];
  return {
    total_equipment: nextEquipment.length,
    active_equipment: nextEquipment.filter((item) => item.status === 'active').length,
    maintenance_equipment: nextEquipment.filter((item) => item.status === 'maintenance').length,
    broken_equipment: nextEquipment.filter((item) => item.status === 'broken').length
  };
};

const EQUIPMENT_STATUS_KEYS = [
  { value: 'active', labelKey: 'em_status_active', color: 'success' },
  { value: 'maintenance', labelKey: 'em_status_maintenance', color: 'warning' },
  { value: 'broken', labelKey: 'em_status_broken', color: 'error' },
  { value: 'retired', labelKey: 'em_status_retired', color: 'gray' }
];

const EQUIPMENT_TYPE_KEYS = [
  { value: 'medical', labelKey: 'em_type_medical' },
  { value: 'diagnostic', labelKey: 'em_type_diagnostic' },
  { value: 'surgical', labelKey: 'em_type_surgical' },
  { value: 'laboratory', labelKey: 'em_type_laboratory' },
  { value: 'imaging', labelKey: 'em_type_imaging' },
  { value: 'monitoring', labelKey: 'em_type_monitoring' },
  { value: 'other', labelKey: 'em_type_other' }
];

const getStatusOptions = (t) => EQUIPMENT_STATUS_KEYS.map((option) => ({
  value: option.value,
  label: t(`admin2.${option.labelKey}`),
  color: option.color
}));

const getTypeOptions = (t) => EQUIPMENT_TYPE_KEYS.map((option) => ({
  value: option.value,
  label: t(`admin2.${option.labelKey}`)
}));

const EquipmentManagement = () => {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [equipment, setEquipment] = useState([]);
  const [branches, setBranches] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [typeFilter, setTypeFilter] = useState('all');
  const [branchFilter, setBranchFilter] = useState('all');
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingEquipment, setEditingEquipment] = useState(null);
  const [message, setMessage] = useState({ type: '', text: '' });
  const [stats, setStats] = useState(null);

  // Форма оборудования
  const [formData, setFormData] = useState({
    name: '',
    type: '',
    model: '',
    serial_number: '',
    branch_id: null,
    status: 'active',
    purchase_date: '',
    warranty_expiry: '',
    maintenance_date: '',
    cost: 0,
    description: ''
  } as any);

  const statusOptions = getStatusOptions(t);
  const typeOptions = getTypeOptions(t);


  const loadEquipment = useCallback(async () => {
    try {
      setLoading(true);
      const response = await api.get('/clinic/equipment') as any;
      const nextEquipment = Array.isArray(response.data)
        ? response.data
        : response.data?.equipment || [];
      setEquipment(nextEquipment);
      setStats(deriveEquipmentStats(nextEquipment));
    } catch (error) {
      logger.error('Ошибка загрузки оборудования:', error);
      setEquipment([]);
      setStats(emptyEquipmentStats);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadBranches = useCallback(async () => {
    try {
      const response = await api.get('/clinic/branches') as any;
      const nextBranches = Array.isArray(response.data)
        ? response.data
        : response.data?.branches || [];
      setBranches(nextBranches);
    } catch (error) {
      logger.error('Ошибка загрузки филиалов:', error);
      setBranches([]);
    }
  }, []);

  useEffect(() => {
    loadEquipment();
    loadBranches();
  }, [loadEquipment, loadBranches]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const hasBranch = formData.branch_id !== null && formData.branch_id !== undefined && formData.branch_id !== '';
    if (!formData.name.trim() || !formData.type || !hasBranch) {
      setMessage({ type: 'error', text: t('admin2.em_required_fields') });
      return;
    }

    try {
      setSaving(true);

      if (editingEquipment) {
        await api.put(`/clinic/equipment/${editingEquipment.id}`, formData);
        setMessage({ type: 'success', text: t('admin2.em_update_success') });
      } else {
        await api.post('/clinic/equipment', formData);
        setMessage({ type: 'success', text: t('admin2.em_add_success') });
      }

      setShowAddForm(false);
      setEditingEquipment(null);
      resetForm();
      loadEquipment();
    } catch {
      setMessage({ type: 'error', text: t('admin2.em_save_error') });
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (equipmentItem) => {
    setFormData(equipmentItem);
    setEditingEquipment(equipmentItem);
    setShowAddForm(true);
  };

  const handleDelete = async (equipmentId) => {
    try {
      await api.delete(`/clinic/equipment/${equipmentId}`);
      setMessage({ type: 'success', text: t('admin2.em_delete_success') });
      loadEquipment();
    } catch {
      setMessage({ type: 'error', text: t('admin2.em_delete_error') });
    }
  };

  const resetForm = () => {
    setFormData({
      name: '',
      type: '',
      model: '',
      serial_number: '',
      branch_id: null,
      status: 'active',
      purchase_date: '',
      warranty_expiry: '',
      maintenance_date: '',
      cost: 0,
      description: ''
    });
  };

  const getStatusColor = (status) => {
    const statusOption = EQUIPMENT_STATUS_KEYS.find((s) => s.value === status);
    return statusOption ? statusOption.color : 'gray';
  };

  const getStatusLabel = (status) => {
    const statusOption = statusOptions.find((s) => s.value === status);
    return statusOption ? statusOption.label : status;
  };

  const getTypeLabel = (type) => {
    const typeOption = typeOptions.find((opt) => opt.value === type);
    return typeOption ? typeOption.label : type;
  };

  const getBranchName = (branchId) => {
    const branch = branches.find((b) => b.id === branchId);
    return branch ? branch.name : t('admin2.em_unknown_branch');
  };

  const filteredEquipment = equipment.filter((item) => {
    const matchesSearch = item.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    item.model?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    item.serial_number?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || item.status === statusFilter;
    const matchesType = typeFilter === 'all' || item.type === typeFilter;
    const matchesBranch = branchFilter === 'all' || item.branch_id === parseInt(branchFilter);
    return matchesSearch && matchesStatus && matchesType && matchesBranch;
  });
  const hasEquipmentFilters = searchTerm.trim() !== '' || statusFilter !== 'all' || typeFilter !== 'all' || branchFilter !== 'all';
  const equipmentEmptyTitle = hasEquipmentFilters ? t('admin2.em_empty_filtered_title') : t('admin2.em_empty_title');
  const equipmentEmptyDescription = hasEquipmentFilters ?
  t('admin2.em_empty_filtered_desc') :
  t('admin2.em_empty_desc');

  return (
    <div className="admin-d-flex-fd-column-gap-24-ov-hidden">
      {/* Заголовок и статистика */}
      <div className="admin-d-flex-jc-between-ai-center-fw-wrap-gap-16">
        <div>
          <h2 className="admin-fs-2xl-fw-bold-primary-m-0-0-8px-0">
            {t('admin2.em_page_title')}
          </h2>
          <p className="admin-secondary-fs-sm-m-0">
            {t('admin2.em_page_subtitle')}
          </p>
        </div>
        {stats &&
        <div className="admin-d-flex-gap-24-fw-wrap">
            <div className="text-center">
              <div className="admin-fs-2xl-fw-bold-blue-mb-4">
                {stats.total_equipment}
              </div>
              <div className="text-sm text-[var(--mac-text-secondary)]">
                {t('admin2.em_stat_total')}
              </div>
            </div>
            <div className="text-center">
              <div className="admin-fs-2xl-fw-bold-success-mb-4">
                {stats.active_equipment}
              </div>
              <div className="text-sm text-[var(--mac-text-secondary)]">
                {t('admin2.em_stat_active')}
              </div>
            </div>
          </div>
        }
      </div>

      {/* Сообщения */}
      {message.text &&
      <Alert
        type={message.type === 'success' ? 'success' : 'error'}
        title={message.type === 'success' ? t('admin2.em_alert_success') : t('admin2.em_alert_error')}
        message={message.text} />

      }

      {/* Фильтры и поиск */}
      <MacOSCard className="p-6">
        <div className="admin-d-flex-fd-column-gap-16-fw-wrap">
          <div className="admin-flex-1-pos-relative">
            <Input
              type="text"
              aria-label={t('admin2.em_search_aria')}
              placeholder={t('admin2.em_search_placeholder')}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="admin-pl-40" />
            
            <Search aria-hidden="true" className="admin-pos-absolute-left-12-top-50pct-tf-translateY-50-tertiary-w-16-h-16" />
          </div>
          <div className="admin-d-flex-gap-12-fw-wrap">
            <Select
              aria-label={t('admin2.em_filter_status_aria')}
              value={statusFilter}
              onChange={(v: unknown) => setStatusFilter(String(v))}
              options={[
                { value: 'all', label: t('admin2.em_filter_status_all') },
                ...statusOptions.map((option) => ({ value: option.value, label: option.label }))
              ]}
              size="large"
              className="admin-minw-150" />
            <Select
              aria-label={t('admin2.em_filter_type_aria')}
              value={typeFilter}
              onChange={(v: unknown) => setTypeFilter(String(v))}
              options={[
                { value: 'all', label: t('admin2.em_filter_type_all') },
                ...typeOptions.map((option) => ({ value: option.value, label: option.label }))
              ]}
              size="large"
              className="admin-minw-150" />
            <Select
              aria-label={t('admin2.em_filter_branch_aria')}
              value={branchFilter}
              onChange={(v: unknown) => setBranchFilter(String(v))}
              options={[
                { value: 'all', label: t('admin2.em_filter_branch_all') },
                ...branches.map((branch) => ({ value: String(branch.id), label: branch.name }))
              ]}
              size="large"
              className="admin-minw-150" />
            <Button
              onClick={() => setShowAddForm(true)}
              className="admin-d-flex-ai-center-gap-8-bgc-blue-bd-none-p-8px-16px">

              <Plus aria-hidden="true" className="w-4 h-4" />
              <span>{t('admin2.em_add_equipment_btn')}</span>
            </Button>
          </div>
        </div>
      </MacOSCard>

      {/* Форма добавления/редактирования */}
      {showAddForm &&
      <MacOSCard className="admin-p-24-ov-hidden">
          <div className="admin-d-flex-jc-between-ai-center-mb-16">
            <h3 className="admin-fs-lg-fw-semi-primary-m-0">
              {editingEquipment ? t('admin2.em_edit_title') : t('admin2.em_add_title')}
            </h3>
            <Button
            variant="outline"
            type="button"
            aria-label={editingEquipment ? t('admin2.em_close_edit_aria') : t('admin2.em_close_add_aria')}
            onClick={() => {
              setShowAddForm(false);
              setEditingEquipment(null);
              resetForm();
            }}
            className="p-2">
            
              <X aria-hidden="true" className="w-4 h-4" />
            </Button>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-16">
              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-4-10">
                  {t('admin2.em_label_name')}
                </label>
                <Input
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder={t('admin2.em_name_ph')} />

              </div>
              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-4-9">
                  {t('admin2.em_label_type')}
                </label>
                <Select
                aria-label={t('admin2.em_type_aria')}
                value={formData.type}
                onChange={(value: unknown) => setFormData({ ...formData, type: String(value) })}
                options={[
                  { value: '', label: t('admin2.em_select_type') },
                  ...typeOptions.map((option) => ({ value: option.value, label: option.label }))
                ]}
                size="large" />
              </div>
              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-4-8">
                  {t('admin2.em_label_model')}
                </label>
                <Input
                type="text"
                value={formData.model}
                onChange={(e) => setFormData({ ...formData, model: e.target.value })}
                placeholder={t('admin2.em_model_ph')} />

              </div>
              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-4-7">
                  {t('admin2.em_label_serial')}
                </label>
                <Input
                type="text"
                value={formData.serial_number}
                onChange={(e) => setFormData({ ...formData, serial_number: e.target.value })}
                placeholder={t('admin2.em_serial_ph')} />

              </div>
              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-4-6">
                  {t('admin2.em_label_branch')}
                </label>
                <Select
                aria-label={t('admin2.em_branch_aria')}
                value={formData.branch_id ? String(formData.branch_id) : ''}
                onChange={(value: unknown) => setFormData({ ...formData, branch_id: value ? Number(value) : null })}
                options={[
                  { value: '', label: t('admin2.em_select_branch') },
                  ...branches.map((branch) => ({ value: String(branch.id), label: branch.name }))
                ]}
                size="large" />
              </div>
              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-4-5">
                  {t('admin2.em_label_status')}
                </label>
                <Select
                aria-label={t('admin2.em_status_aria')}
                value={formData.status}
                onChange={(value: unknown) => setFormData({ ...formData, status: String(value) })}
                options={statusOptions.map((option) => ({ value: option.value, label: option.label }))}
                size="large" />
              </div>
              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-4-4">
                  {t('admin2.em_label_purchase_date')}
                </label>
                <Input
                type="date"
                value={formData.purchase_date}
                onChange={(e) => setFormData({ ...formData, purchase_date: e.target.value })} />

              </div>
              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-4-3">
                  {t('admin2.em_label_warranty')}
                </label>
                <Input
                type="date"
                value={formData.warranty_expiry}
                onChange={(e) => setFormData({ ...formData, warranty_expiry: e.target.value })} />

              </div>
              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-4-2">
                  {t('admin2.em_label_maintenance_date')}
                </label>
                <Input
                type="date"
                value={formData.maintenance_date}
                onChange={(e) => setFormData({ ...formData, maintenance_date: e.target.value })} />

              </div>
              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-4-1">
                  {t('admin2.em_label_cost')}
                </label>
                <Input
                type="number"
                value={formData.cost}
                onChange={(e) => setFormData({ ...formData, cost: parseFloat(e.target.value) })}
                placeholder={t('admin2.em_cost_ph')} />

              </div>
            </div>

            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-4">
                {t('admin2.em_label_description')}
              </label>
              <Textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder={t('admin2.em_description_ph')}
              rows={3} />

            </div>

            <div className="admin-d-flex-jc-end-gap-12">
              <Button
              type="button"
              variant="outline"
              onClick={() => {
                setShowAddForm(false);
                setEditingEquipment(null);
                resetForm();
              }}
              disabled={saving}>

                {t('admin2.em_cancel_btn')}
              </Button>
              <Button
              type="submit"
              disabled={saving}
              aria-label={editingEquipment ? 'Update equipment' : 'Add equipment'}
              className="admin-d-flex-ai-center-gap-8-bgc-blue-bd-none">
              
                {saving ?
              <>
                    <RefreshCw aria-hidden="true" className="admin-w-16-h-16-anim-spin-1s-linear-infin" />
                    {t('admin2.em_saving')}
                  </> :

              <>
                    <Save aria-hidden="true" className="w-4 h-4" />
                    {editingEquipment ? t('admin2.em_update_btn') : t('admin2.em_add_btn')}
                  </>
              }
              </Button>
            </div>
          </form>
        </MacOSCard>
      }

      {/* Список оборудования */}
      {loading ?
      <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-24-ov-hidden-1">
          {[1, 2, 3].map((i) =>
        <MacOSCard key={i} className="p-6">
              <Skeleton height="200px" />
            </MacOSCard>
        )}
        </div> :
      filteredEquipment.length === 0 ?
      <MacOSEmptyState
        icon={Wrench}
        title={equipmentEmptyTitle}
        description={equipmentEmptyDescription}
        action={
        <Button onClick={() => setShowAddForm(true)} variant="primary">
              <Plus aria-hidden="true" focusable="false" className="w-4 h-4 mr-2" />
              {t('admin2.em_add_equipment_btn')}
            </Button>
        } /> :


      <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-24-ov-hidden">
          {filteredEquipment.map((item) =>
        <MacOSCard key={item.id} className="p-6">
              <div className="admin-d-flex-jc-between-ai-start-mb-16">
                <div>
                  <h3 className="admin-fs-lg-fw-semi-primary-m-0-0-4px-0">
                    {item.name}
                  </h3>
                  <p className="admin-fs-sm-secondary-m-0">
                    {item.model} • {item.serial_number}
                  </p>
                </div>
                <Badge
              variant={getStatusColor(item.status)}
              text={getStatusLabel(item.status)} />
            
              </div>

              <div className="admin-d-flex-fd-column-gap-8-mb-16">
                <div className="admin-d-flex-ai-center-gap-8-fs-sm-secondary-3">
                  <Building2 aria-hidden="true" className="w-4 h-4" />
                  <span>{getBranchName(item.branch_id)}</span>
                </div>
                <div className="admin-d-flex-ai-center-gap-8-fs-sm-secondary-2">
                  <Wrench aria-hidden="true" className="w-4 h-4" />
                  <span>{getTypeLabel(item.type)}</span>
                </div>
                {item.cost > 0 &&
            <div className="admin-d-flex-ai-center-gap-8-fs-sm-secondary-1">
                    <DollarSign aria-hidden="true" className="w-4 h-4" />
                    <span>{item.cost.toLocaleString()} {t('admin2.em_currency')}</span>
                  </div>
            }
                {item.warranty_expiry &&
            <div className="admin-d-flex-ai-center-gap-8-fs-sm-secondary">
                    <Calendar aria-hidden="true" className="w-4 h-4" />
                    <span>{t('admin2.em_warranty_until', { date: new Date(item.warranty_expiry).toLocaleDateString() })}</span>
                  </div>
            }
              </div>

              {item.description &&
          <div className="mb-4">
                  <p className="admin-fs-sm-secondary-m-0-lh-1p4">
                    {item.description}
                  </p>
                </div>
          }

              <div className="admin-d-flex-jc-end-gap-8">
                <Button
              type="button"
              variant="outline"
              aria-label={t('admin2.em_edit_aria', { name: item.name })}
              onClick={() => handleEdit(item)}
              className="admin-p-6px-12px">
              
                  <Edit aria-hidden="true" className="w-4 h-4" />
                </Button>
                <Button
              type="button"
              variant="outline"
              aria-label={t('admin2.em_delete_aria', { name: item.name })}
              onClick={() => handleDelete(item.id)}
              className="admin-p-6px-12px-error-bd-c-error">
              
                  <Trash2 aria-hidden="true" className="w-4 h-4" />
                </Button>
              </div>
            </MacOSCard>
        )}
        </div>
      }
    </div>);

};

export default EquipmentManagement;
