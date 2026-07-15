import { useState, useEffect, useCallback } from 'react';
import {
  Building2,
  Plus,
  Search,
  Edit,
  Trash2,
  Save,
  X,
  RefreshCw,
  MapPin,
  Phone,
  Mail,
  Users } from
'lucide-react';
import {
  MacOSCard,
  Button,
  Badge,
  Input,
  Select,
  Checkbox,
  Skeleton,
  MacOSEmptyState,
  Alert,
} from '../ui/macos';
import { api } from '../../api/client';

import logger from '../../utils/logger';
import { useTranslation } from '../../i18n/useTranslation';

const emptyBranchStats = {
  total_branches: 0,
  active_branches: 0,
  inactive_branches: 0,
  maintenance_branches: 0
};

const deriveBranchStats = (branchList) => {
  const nextBranches = Array.isArray(branchList) ? branchList : [];
  return {
    total_branches: nextBranches.length,
    active_branches: nextBranches.filter((branch) => branch.status === 'active').length,
    inactive_branches: nextBranches.filter((branch) => branch.status === 'inactive').length,
    maintenance_branches: nextBranches.filter((branch) => branch.status === 'maintenance').length
  };
};

const BranchManagement = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [branches, setBranches] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingBranch, setEditingBranch] = useState(null);
  const [message, setMessage] = useState({ type: '', text: '' });
  const [stats, setStats] = useState(null);
  const [formErrors, setFormErrors] = useState({});

  // Форма филиала
  const [formData, setFormData] = useState({
    name: '',
    code: '',
    address: '',
    phone: '',
    email: '',
    status: 'active',
    capacity: 50,
    services_available: ['cardiology', 'dermatology', 'stomatology']
  });

  const statusOptions = [
  { value: 'active', label: 'Активный', color: 'success' },
  { value: 'inactive', label: 'Неактивный', color: 'error' },
  { value: 'maintenance', label: 'Обслуживание', color: 'warning' }];


  const specialtyOptions = [
  { value: 'cardiology', label: 'Кардиология' },
  { value: 'dermatology', label: 'Дерматология' },
  { value: 'stomatology', label: 'Стоматология' },
  { value: 'neurology', label: 'Неврология' },
  { value: 'orthopedics', label: 'Ортопедия' },
  { value: 'pediatrics', label: 'Педиатрия' },
  { value: 'gynecology', label: 'Гинекология' },
  { value: 'urology', label: 'Урология' }];


  const normalizeBranchPhone = (value) => {
    if (!value) {
      return '';
    }

    const digits = value.replace(/\D/g, '');
    if (!digits) {
      return '';
    }

    if (digits.length === 9) {
      return `+998${digits}`;
    }

    if (digits.length === 12 && digits.startsWith('998')) {
      return `+${digits}`;
    }

    if (digits.length === 11 && digits.startsWith('8')) {
      return `+998${digits.slice(1)}`;
    }

    return null;
  };

  const formatBranchPhone = (value) => {
    const normalized = normalizeBranchPhone(value);
    const canonical = normalized || value?.trim() || '';
    const digits = canonical.replace(/\D/g, '');

    if (digits.length !== 12 || !digits.startsWith('998')) {
      return canonical;
    }

    return `+${digits.slice(0, 3)} ${digits.slice(3, 5)} ${digits.slice(5, 8)} ${digits.slice(8, 10)} ${digits.slice(10, 12)}`;
  };

  const loadBranches = useCallback(async () => {
    try {
      setLoading(true);
      const response = await api.get('/clinic/branches');
      const nextBranches = Array.isArray(response.data)
        ? response.data
        : response.data?.branches || [];
      setBranches(nextBranches);
      setStats(deriveBranchStats(nextBranches));
    } catch (error) {
      logger.error('Ошибка загрузки филиалов:', error);
      setBranches([]);
      setStats(emptyBranchStats);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadBranches();
  }, [loadBranches]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      setSaving(true);
      setFormErrors({});

      const normalizedPhone = normalizeBranchPhone(formData.phone);
      if (formData.phone.trim() && normalizedPhone === null) {
        setFormErrors({ phone: 'Используйте формат +998 71 123 45 67' });
        setMessage({
          type: 'error',
          text: 'Телефон филиала должен быть в формате +998 71 123 45 67'
        });
        return;
      }

      const payload = {
        ...formData,
        phone: normalizedPhone || null
      };

      if (editingBranch) {
        await api.put(`/clinic/branches/${editingBranch.id}`, payload);
        setMessage({ type: 'success', text: 'Филиал обновлен' });
      } else {
        await api.post('/clinic/branches', payload);
        setMessage({ type: 'success', text: 'Филиал создан' });
      }

      setShowAddForm(false);
      setEditingBranch(null);
      resetForm();
      loadBranches();
    } catch {
      setMessage({ type: 'error', text: 'Ошибка сохранения филиала' });
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (branch) => {
    setFormData({
      ...branch,
      phone: formatBranchPhone(branch.phone || ''),
      services_available: branch.services_available || []
    });
    setEditingBranch(branch);
    setShowAddForm(true);
  };

  const handleDelete = async (branchId) => {
    try {
      await api.delete(`/clinic/branches/${branchId}`);
      setMessage({ type: 'success', text: 'Филиал удален' });
      loadBranches();
    } catch {
      setMessage({ type: 'error', text: 'Ошибка удаления филиала' });
    }
  };

  const resetForm = () => {
    setFormData({
      name: '',
      code: '',
      address: '',
      phone: '',
      email: '',
      status: 'active',
      capacity: 50,
      services_available: ['cardiology', 'dermatology', 'stomatology']
    });
    setFormErrors({});
  };

  const getStatusColor = (status) => {
    const statusOption = statusOptions.find((s) => s.value === status);
    return statusOption ? statusOption.color : 'gray';
  };

  const getStatusLabel = (status) => {
    const statusOption = statusOptions.find((s) => s.value === status);
    return statusOption ? statusOption.label : status;
  };

  const filteredBranches = branches.filter((branch) => {
    const matchesSearch = branch.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    branch.address?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    branch.code.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || branch.status === statusFilter;
    return matchesSearch && matchesStatus;
  });
  const hasBranchFilters = searchTerm.trim() !== '' || statusFilter !== 'all';
  const branchEmptyTitle = hasBranchFilters ? 'Филиалы по фильтрам не найдены' : 'Филиалы ещё не добавлены';
  const branchEmptyDescription = hasBranchFilters ?
  'Измените поисковый запрос или статус, чтобы увидеть другие филиалы.' :
  'Создайте первый филиал, чтобы начать управлять филиальной структурой клиники.';

  return (
    <div className="admin-d-flex-fd-column-gap-24-ov-hidden-1">
      {/* Заголовок и статистика */}
      <div className="admin-d-flex-jc-between-ai-center-fw-wrap-gap-16-1">
        <div>
          <h2 className="admin-fs-2xl-fw-bold-primary-m-0-0-8px-0-1">
            Управление филиалами
          </h2>
          <p className="admin-secondary-fs-sm-m-0-1">
            Создание и управление филиалами клиники
          </p>
        </div>
        {stats &&
        <div className="admin-d-flex-gap-24-fw-wrap-1">
            <div className="text-center">
              <div className="admin-fs-2xl-fw-bold-blue-mb-4-1">
                {stats.total_branches}
              </div>
              <div className="text-sm text-[var(--mac-text-secondary)]">
                Всего филиалов
              </div>
            </div>
            <div className="text-center">
              <div className="admin-fs-2xl-fw-bold-success-mb-4-1">
                {stats.active_branches}
              </div>
              <div className="text-sm text-[var(--mac-text-secondary)]">
                Активных
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
        <div className="admin-d-flex-fd-column-gap-16-fw-wrap-1">
          <div className="admin-flex-1-pos-relative">
            <Input
              type="text"
              aria-label="Поиск филиалов по названию, адресу или коду"
              placeholder="Поиск по названию, адресу или коду..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="admin-pl-40" />

            <Search aria-hidden="true" className="admin-pos-absolute-left-12-top-50pct-tf-translateY-50-tertiary-w-16-h-16-1" />
          </div>
          <div className="admin-d-flex-gap-12-fw-wrap-1">
            <Select
              aria-label="Фильтр филиалов по статусу"
              value={statusFilter}
              onChange={setStatusFilter}
              options={[
                { value: 'all', label: 'Все статусы' },
                ...statusOptions.map((option) => ({ value: option.value, label: option.label }))
              ]}
              size="large"
              className="admin-minw-150" />
            <Button
              onClick={() => setShowAddForm(true)}
              className="admin-d-flex-ai-center-gap-8-bgc-blue-bd-none-p-8px-16px-1">
              
              <Plus aria-hidden="true" className="w-4 h-4" />
              <span>Добавить филиал</span>
            </Button>
          </div>
        </div>
      </MacOSCard>

      {/* Форма добавления/редактирования */}
      {showAddForm &&
      <MacOSCard className="admin-p-24-ov-hidden-1">
          <div className="admin-d-flex-jc-between-ai-center-mb-16-1">
            <h3 className="admin-fs-lg-fw-semi-primary-m-0-1">
              {editingBranch ? 'Редактировать филиал' : 'Добавить филиал'}
            </h3>
            <Button
            variant="outline"
            type="button"
            aria-label={editingBranch ? 'Закрыть форму редактирования филиала' : 'Закрыть форму добавления филиала'}
            onClick={() => {
              setShowAddForm(false);
              setEditingBranch(null);
              resetForm();
            }}
            className="p-2">

              <X aria-hidden="true" className="w-4 h-4" />
            </Button>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-16-1">
              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-4-17">
                  Название филиала *
                </label>
                <Input
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="Введите название филиала" />
              
              </div>
              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-4-16">
                  Код филиала *
                </label>
                <Input
                type="text"
                required
                value={formData.code}
                onChange={(e) => setFormData({ ...formData, code: e.target.value })}
                placeholder="Введите код филиала" />
              
              </div>
              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-4-15">
                  Адрес
                </label>
                <Input
                type="text"
                value={formData.address}
                onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                placeholder="Введите адрес филиала" />
              
              </div>
              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-4-14">
                  Телефон
                </label>
                <Input
                type="tel"
                value={formData.phone}
                onChange={(e) => {
                  setFormData({ ...formData, phone: e.target.value });
                  if (formErrors.phone) {
                    setFormErrors((prev) => ({ ...prev, phone: null }));
                  }
                }}
                placeholder="+998 71 123 45 67"
                error={formErrors.phone} />
              <p className="admin-m-4px-0-0-0-fs-xs-secondary">
                Формат: +998 71 123 45 67
              </p>
              
              </div>
              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-4-13">
                  Email
                </label>
                <Input
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                placeholder="Введите email филиала" />
              
              </div>
              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-4-12">
                  Статус
                </label>
                <Select
                aria-label="Статус филиала"
                value={formData.status}
                onChange={(value) => setFormData({ ...formData, status: value })}
                options={statusOptions.map((option) => ({ value: option.value, label: option.label }))}
                size="large" />
              </div>
              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-4-11">
                  Вместимость
                </label>
                <Input
                type="number"
                value={formData.capacity}
                onChange={(e) => setFormData({ ...formData, capacity: parseInt(e.target.value) })}
                placeholder="Введите вместимость" />
              
              </div>
            </div>

            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                Доступные услуги
              </label>
              <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-8">
                {specialtyOptions.map((specialty) =>
              <label key={specialty.value} className="admin-d-flex-ai-center-gap-8-fs-sm-primary">
                    <Checkbox
                  checked={formData.services_available.includes(specialty.value)}
                  onChange={(checked) => {
                    if (checked) {
                      setFormData({
                        ...formData,
                        services_available: [...formData.services_available, specialty.value]
                      });
                    } else {
                      setFormData({
                        ...formData,
                        services_available: formData.services_available.filter((s) => s !== specialty.value)
                      });
                    }
                  }} />
                
                    <span>{specialty.label}</span>
                  </label>
              )}
              </div>
            </div>

            <div className="admin-d-flex-jc-end-gap-12-1">
              <Button
              type="button"
              variant="outline"
              onClick={() => {
                setShowAddForm(false);
                setEditingBranch(null);
                resetForm();
              }}
              disabled={saving}>
              
                Отмена
              </Button>
              <Button
              type="submit"
              disabled={saving}
              aria-label={editingBranch ? 'Update branch' : 'Create branch'}
              className="admin-d-flex-ai-center-gap-8-bgc-blue-bd-none-1">
              
                {saving ?
              <>
                    <RefreshCw aria-hidden="true" className="admin-w-16-h-16-anim-spin-1s-linear-infin-1" />
                    Сохранение...
                  </> :

              <>
                    <Save aria-hidden="true" className="w-4 h-4" />
                    {editingBranch ? 'Обновить' : 'Создать'}
                  </>
              }
              </Button>
            </div>
          </form>
        </MacOSCard>
      }

      {/* Список филиалов */}
      {loading ?
      <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-24-ov-hidden-3">
          {[1, 2, 3].map((i) =>
        <MacOSCard key={i} className="p-6">
              <Skeleton height="200px" />
            </MacOSCard>
        )}
        </div> :
      filteredBranches.length === 0 ?
      <MacOSEmptyState
        icon={Building2}
        title={branchEmptyTitle}
        description={branchEmptyDescription}
        action={
        <Button onClick={() => setShowAddForm(true)} variant="primary">
              <Plus aria-hidden="true" focusable="false" className="w-4 h-4 mr-2" />
              Добавить филиал
            </Button>
        } /> :


      <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-24-ov-hidden-2">
          {filteredBranches.map((branch) =>
        <MacOSCard key={branch.id} className="p-6">
              <div className="admin-d-flex-jc-between-ai-start-mb-16-1">
                <div>
                  <h3 className="admin-fs-lg-fw-semi-primary-m-0-0-4px-0-1">
                    {branch.name}
                  </h3>
                  <p className="admin-fs-sm-secondary-m-0-1">
                    {branch.code}
                  </p>
                </div>
                <Badge
              variant={getStatusColor(branch.status)}
              text={getStatusLabel(branch.status)} />
            
              </div>

              <div className="admin-d-flex-fd-column-gap-8-mb-16-1">
                {branch.address &&
            <div className="admin-d-flex-ai-center-gap-8-fs-sm-secondary-7">
                    <MapPin aria-hidden="true" className="w-4 h-4" />
                    <span>{branch.address}</span>
                  </div>
            }
                {branch.phone &&
            <div className="admin-d-flex-ai-center-gap-8-fs-sm-secondary-6">
                    <Phone aria-hidden="true" className="w-4 h-4" />
                    <span>{formatBranchPhone(branch.phone)}</span>
                  </div>
            }
                {branch.email &&
            <div className="admin-d-flex-ai-center-gap-8-fs-sm-secondary-5">
                    <Mail aria-hidden="true" className="w-4 h-4" />
                    <span>{branch.email}</span>
                  </div>
            }
                <div className="admin-d-flex-ai-center-gap-8-fs-sm-secondary-4">
                  <Users aria-hidden="true" className="w-4 h-4" />
                  <span>Вместимость: {branch.capacity}</span>
                </div>
              </div>

              {branch.services_available && branch.services_available.length > 0 &&
          <div className="mb-4">
                  <p className="admin-fs-sm-fw-med-primary-mb-8">
                    Услуги:
                  </p>
                  <div className="admin-d-flex-fw-wrap-gap-4">
                    {branch.services_available.map((service) => {
                const specialty = specialtyOptions.find((s) => s.value === service);
                return specialty ?
                <Badge
                  key={service}
                  variant="outline"
                  text={specialty.label}
                  className="admin-fs-xs" /> :

                null;
              })}
                  </div>
                </div>
          }

              <div className="admin-d-flex-jc-end-gap-8-1">
                <Button
              type="button"
              variant="outline"
              aria-label={`Редактировать филиал ${branch.name}`}
              onClick={() => handleEdit(branch)}
              className="admin-p-6px-12px-1">

                  <Edit aria-hidden="true" className="w-4 h-4" />
                </Button>
                <Button
              type="button"
              variant="outline"
              aria-label={`Удалить филиал ${branch.name}`}
              onClick={() => handleDelete(branch.id)}
              className="admin-p-6px-12px-error-bd-c-error-1">
              
                  <Trash2 aria-hidden="true" className="w-4 h-4" />
                </Button>
              </div>
            </MacOSCard>
        )}
        </div>
      }
    </div>);

};

export default BranchManagement;
