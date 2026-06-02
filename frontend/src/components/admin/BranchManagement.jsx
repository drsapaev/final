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
  MacOSButton,
  MacOSBadge,
  MacOSInput,
  Select,
  MacOSCheckbox,
  MacOSLoadingSkeleton,
  MacOSEmptyState,
  MacOSAlert } from
'../ui/macos';
import { api } from '../../api/client';

import logger from '../../utils/logger';

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
            Управление филиалами
          </h2>
          <p style={{
            color: 'var(--mac-text-secondary)',
            fontSize: 'var(--mac-font-size-sm)',
            margin: 0
          }}>
            Создание и управление филиалами клиники
          </p>
        </div>
        {stats &&
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
                {stats.total_branches}
              </div>
              <div style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)'
            }}>
                Всего филиалов
              </div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{
              fontSize: 'var(--mac-font-size-2xl)',
              fontWeight: 'var(--mac-font-weight-bold)',
              color: 'var(--mac-success)',
              marginBottom: '4px'
            }}>
                {stats.active_branches}
              </div>
              <div style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)'
            }}>
                Активных
              </div>
            </div>
          </div>
        }
      </div>

      {/* Сообщения */}
      {message.text &&
      <MacOSAlert
        type={message.type === 'success' ? 'success' : 'error'}
        title={message.type === 'success' ? 'Успешно' : 'Ошибка'}
        message={message.text} />

      }

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
              aria-label="Поиск филиалов по названию, адресу или коду"
              placeholder="Поиск по названию, адресу или коду..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{ paddingLeft: '40px' }} />

            <Search aria-hidden="true" style={{
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
            <Select
              aria-label="Фильтр филиалов по статусу"
              value={statusFilter}
              onChange={setStatusFilter}
              options={[
                { value: 'all', label: 'Все статусы' },
                ...statusOptions.map((option) => ({ value: option.value, label: option.label }))
              ]}
              size="large"
              style={{ minWidth: '150px' }} />
            <MacOSButton
              onClick={() => setShowAddForm(true)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                backgroundColor: 'var(--mac-accent-blue)',
                border: 'none',
                padding: '8px 16px'
              }}>
              
              <Plus aria-hidden="true" style={{ width: '16px', height: '16px' }} />
              <span>Добавить филиал</span>
            </MacOSButton>
          </div>
        </div>
      </MacOSCard>

      {/* Форма добавления/редактирования */}
      {showAddForm &&
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
              {editingBranch ? 'Редактировать филиал' : 'Добавить филиал'}
            </h3>
            <MacOSButton
            variant="outline"
            type="button"
            aria-label={editingBranch ? 'Закрыть форму редактирования филиала' : 'Закрыть форму добавления филиала'}
            onClick={() => {
              setShowAddForm(false);
              setEditingBranch(null);
              resetForm();
            }}
            style={{ padding: '8px' }}>

              <X aria-hidden="true" style={{ width: '16px', height: '16px' }} />
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
                  Название филиала *
                </label>
                <MacOSInput
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="Введите название филиала" />
              
              </div>
              <div>
                <label style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '4px'
              }}>
                  Код филиала *
                </label>
                <MacOSInput
                type="text"
                required
                value={formData.code}
                onChange={(e) => setFormData({ ...formData, code: e.target.value })}
                placeholder="Введите код филиала" />
              
              </div>
              <div>
                <label style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '4px'
              }}>
                  Адрес
                </label>
                <MacOSInput
                type="text"
                value={formData.address}
                onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                placeholder="Введите адрес филиала" />
              
              </div>
              <div>
                <label style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '4px'
              }}>
                  Телефон
                </label>
                <MacOSInput
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
              <p style={{
                margin: '4px 0 0 0',
                fontSize: 'var(--mac-font-size-xs)',
                color: 'var(--mac-text-secondary)'
              }}>
                Формат: +998 71 123 45 67
              </p>
              
              </div>
              <div>
                <label style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '4px'
              }}>
                  Email
                </label>
                <MacOSInput
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                placeholder="Введите email филиала" />
              
              </div>
              <div>
                <label style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '4px'
              }}>
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
                <label style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '4px'
              }}>
                  Вместимость
                </label>
                <MacOSInput
                type="number"
                value={formData.capacity}
                onChange={(e) => setFormData({ ...formData, capacity: parseInt(e.target.value) })}
                placeholder="Введите вместимость" />
              
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
                Доступные услуги
              </label>
              <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
              gap: '8px'
            }}>
                {specialtyOptions.map((specialty) =>
              <label key={specialty.value} style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-primary)'
              }}>
                    <MacOSCheckbox
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
                setEditingBranch(null);
                resetForm();
              }}
              disabled={saving}>
              
                Отмена
              </MacOSButton>
              <MacOSButton
              type="submit"
              disabled={saving}
              aria-label={editingBranch ? 'Update branch' : 'Create branch'}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                backgroundColor: 'var(--mac-accent-blue)',
                border: 'none'
              }}>
              
                {saving ?
              <>
                    <RefreshCw aria-hidden="true" style={{
                  width: '16px',
                  height: '16px',
                  animation: 'spin 1s linear infinite'
                }} />
                    Сохранение...
                  </> :

              <>
                    <Save aria-hidden="true" style={{ width: '16px', height: '16px' }} />
                    {editingBranch ? 'Обновить' : 'Создать'}
                  </>
              }
              </MacOSButton>
            </div>
          </form>
        </MacOSCard>
      }

      {/* Список филиалов */}
      {loading ?
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
        gap: '24px',
        overflow: 'hidden'
      }}>
          {[1, 2, 3].map((i) =>
        <MacOSCard key={i} style={{ padding: '24px' }}>
              <MacOSLoadingSkeleton height="200px" />
            </MacOSCard>
        )}
        </div> :
      filteredBranches.length === 0 ?
      <MacOSEmptyState
        icon={Building2}
        title={branchEmptyTitle}
        description={branchEmptyDescription}
        action={
        <MacOSButton onClick={() => setShowAddForm(true)} variant="primary">
              <Plus aria-hidden="true" focusable="false" style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Добавить филиал
            </MacOSButton>
        } /> :


      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
        gap: '24px',
        overflow: 'hidden'
      }}>
          {filteredBranches.map((branch) =>
        <MacOSCard key={branch.id} style={{ padding: '24px' }}>
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
                    {branch.name}
                  </h3>
                  <p style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-secondary)',
                margin: 0
              }}>
                    {branch.code}
                  </p>
                </div>
                <MacOSBadge
              variant={getStatusColor(branch.status)}
              text={getStatusLabel(branch.status)} />
            
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '16px' }}>
                {branch.address &&
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)'
            }}>
                    <MapPin aria-hidden="true" style={{ width: '16px', height: '16px' }} />
                    <span>{branch.address}</span>
                  </div>
            }
                {branch.phone &&
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)'
            }}>
                    <Phone aria-hidden="true" style={{ width: '16px', height: '16px' }} />
                    <span>{formatBranchPhone(branch.phone)}</span>
                  </div>
            }
                {branch.email &&
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)'
            }}>
                    <Mail aria-hidden="true" style={{ width: '16px', height: '16px' }} />
                    <span>{branch.email}</span>
                  </div>
            }
                <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)'
            }}>
                  <Users aria-hidden="true" style={{ width: '16px', height: '16px' }} />
                  <span>Вместимость: {branch.capacity}</span>
                </div>
              </div>

              {branch.services_available && branch.services_available.length > 0 &&
          <div style={{ marginBottom: '16px' }}>
                  <p style={{
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              marginBottom: '8px'
            }}>
                    Услуги:
                  </p>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                    {branch.services_available.map((service) => {
                const specialty = specialtyOptions.find((s) => s.value === service);
                return specialty ?
                <MacOSBadge
                  key={service}
                  variant="outline"
                  text={specialty.label}
                  style={{ fontSize: 'var(--mac-font-size-xs)' }} /> :

                null;
              })}
                  </div>
                </div>
          }

              <div style={{
            display: 'flex',
            justifyContent: 'flex-end',
            gap: '8px'
          }}>
                <MacOSButton
              type="button"
              variant="outline"
              aria-label={`Редактировать филиал ${branch.name}`}
              onClick={() => handleEdit(branch)}
              style={{ padding: '6px 12px' }}>

                  <Edit aria-hidden="true" style={{ width: '16px', height: '16px' }} />
                </MacOSButton>
                <MacOSButton
              type="button"
              variant="outline"
              aria-label={`Удалить филиал ${branch.name}`}
              onClick={() => handleDelete(branch.id)}
              style={{
                padding: '6px 12px',
                color: 'var(--mac-error)',
                borderColor: 'var(--mac-error)'
              }}>
              
                  <Trash2 aria-hidden="true" style={{ width: '16px', height: '16px' }} />
                </MacOSButton>
              </div>
            </MacOSCard>
        )}
        </div>
      }
    </div>);

};

export default BranchManagement;
