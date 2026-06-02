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
  MacOSButton,
  MacOSBadge,
  MacOSInput,
  Select,
  MacOSTextarea,

  MacOSLoadingSkeleton,
  MacOSEmptyState,
  MacOSAlert } from

'../ui/macos';
import { api } from '../../api/client';

import logger from '../../utils/logger';

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

const EquipmentManagement = () => {
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
  });

  const statusOptions = [
  { value: 'active', label: 'Активное', color: 'success' },
  { value: 'maintenance', label: 'Обслуживание', color: 'warning' },
  { value: 'broken', label: 'Сломано', color: 'error' },
  { value: 'retired', label: 'Списано', color: 'gray' }];


  const typeOptions = [
  { value: 'medical', label: 'Медицинское оборудование' },
  { value: 'diagnostic', label: 'Диагностическое' },
  { value: 'surgical', label: 'Хирургическое' },
  { value: 'laboratory', label: 'Лабораторное' },
  { value: 'imaging', label: 'Визуализация' },
  { value: 'monitoring', label: 'Мониторинг' },
  { value: 'other', label: 'Прочее' }];


  const loadEquipment = useCallback(async () => {
    try {
      setLoading(true);
      const response = await api.get('/clinic/equipment');
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
      const response = await api.get('/clinic/branches');
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
      setMessage({ type: 'error', text: 'Заполните обязательные поля' });
      return;
    }

    try {
      setSaving(true);

      if (editingEquipment) {
        await api.put(`/clinic/equipment/${editingEquipment.id}`, formData);
        setMessage({ type: 'success', text: 'Оборудование обновлено' });
      } else {
        await api.post('/clinic/equipment', formData);
        setMessage({ type: 'success', text: 'Оборудование добавлено' });
      }

      setShowAddForm(false);
      setEditingEquipment(null);
      resetForm();
      loadEquipment();
    } catch {
      setMessage({ type: 'error', text: 'Ошибка сохранения оборудования' });
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
      setMessage({ type: 'success', text: 'Оборудование удалено' });
      loadEquipment();
    } catch {
      setMessage({ type: 'error', text: 'Ошибка удаления оборудования' });
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

  const getBranchName = (branchId) => {
    const branch = branches.find((b) => b.id === branchId);
    return branch ? branch.name : 'Неизвестно';
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
  const equipmentEmptyTitle = hasEquipmentFilters ? 'Оборудование по фильтрам не найдено' : 'Оборудование ещё не добавлено';
  const equipmentEmptyDescription = hasEquipmentFilters ?
  'Измените поиск, статус, тип или филиал, чтобы увидеть другое оборудование.' :
  'Добавьте первую единицу оборудования, чтобы вести учет техники по филиалам.';

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
            Управление оборудованием
          </h2>
          <p style={{
            color: 'var(--mac-text-secondary)',
            fontSize: 'var(--mac-font-size-sm)',
            margin: 0
          }}>
            Учет и управление медицинским оборудованием
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
                {stats.total_equipment}
              </div>
              <div style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)'
            }}>
                Всего единиц
              </div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{
              fontSize: 'var(--mac-font-size-2xl)',
              fontWeight: 'var(--mac-font-weight-bold)',
              color: 'var(--mac-success)',
              marginBottom: '4px'
            }}>
                {stats.active_equipment}
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
              aria-label="Поиск оборудования по названию, модели или серийному номеру"
              placeholder="Поиск по названию, модели или серийному номеру..."
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
              aria-label="Фильтр оборудования по статусу"
              value={statusFilter}
              onChange={setStatusFilter}
              options={[
                { value: 'all', label: 'Все статусы' },
                ...statusOptions.map((option) => ({ value: option.value, label: option.label }))
              ]}
              size="large"
              style={{ minWidth: '150px' }} />
            <Select
              aria-label="Фильтр оборудования по типу"
              value={typeFilter}
              onChange={setTypeFilter}
              options={[
                { value: 'all', label: 'Все типы' },
                ...typeOptions.map((option) => ({ value: option.value, label: option.label }))
              ]}
              size="large"
              style={{ minWidth: '150px' }} />
            <Select
              aria-label="Фильтр оборудования по филиалу"
              value={branchFilter}
              onChange={setBranchFilter}
              options={[
                { value: 'all', label: 'Все филиалы' },
                ...branches.map((branch) => ({ value: String(branch.id), label: branch.name }))
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
              <span>Добавить оборудование</span>
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
              {editingEquipment ? 'Редактировать оборудование' : 'Добавить оборудование'}
            </h3>
            <MacOSButton
            variant="outline"
            type="button"
            aria-label={editingEquipment ? 'Закрыть форму редактирования оборудования' : 'Закрыть форму добавления оборудования'}
            onClick={() => {
              setShowAddForm(false);
              setEditingEquipment(null);
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
                  Название *
                </label>
                <MacOSInput
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="Введите название оборудования" />
              
              </div>
              <div>
                <label style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '4px'
              }}>
                  Тип *
                </label>
                <Select
                aria-label="Тип оборудования"
                value={formData.type}
                onChange={(value) => setFormData({ ...formData, type: value })}
                options={[
                  { value: '', label: 'Выберите тип' },
                  ...typeOptions.map((option) => ({ value: option.value, label: option.label }))
                ]}
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
                  Модель
                </label>
                <MacOSInput
                type="text"
                value={formData.model}
                onChange={(e) => setFormData({ ...formData, model: e.target.value })}
                placeholder="Введите модель" />
              
              </div>
              <div>
                <label style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '4px'
              }}>
                  Серийный номер
                </label>
                <MacOSInput
                type="text"
                value={formData.serial_number}
                onChange={(e) => setFormData({ ...formData, serial_number: e.target.value })}
                placeholder="Введите серийный номер" />
              
              </div>
              <div>
                <label style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '4px'
              }}>
                  Филиал *
                </label>
                <Select
                aria-label="Филиал оборудования"
                value={formData.branch_id ? String(formData.branch_id) : ''}
                onChange={(value) => setFormData({ ...formData, branch_id: value ? Number(value) : null })}
                options={[
                  { value: '', label: 'Выберите филиал' },
                  ...branches.map((branch) => ({ value: String(branch.id), label: branch.name }))
                ]}
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
                  Статус
                </label>
                <Select
                aria-label="Статус оборудования"
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
                  Дата покупки
                </label>
                <MacOSInput
                type="date"
                value={formData.purchase_date}
                onChange={(e) => setFormData({ ...formData, purchase_date: e.target.value })} />
              
              </div>
              <div>
                <label style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '4px'
              }}>
                  Окончание гарантии
                </label>
                <MacOSInput
                type="date"
                value={formData.warranty_expiry}
                onChange={(e) => setFormData({ ...formData, warranty_expiry: e.target.value })} />
              
              </div>
              <div>
                <label style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '4px'
              }}>
                  Последнее обслуживание
                </label>
                <MacOSInput
                type="date"
                value={formData.maintenance_date}
                onChange={(e) => setFormData({ ...formData, maintenance_date: e.target.value })} />
              
              </div>
              <div>
                <label style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '4px'
              }}>
                  Стоимость (сум)
                </label>
                <MacOSInput
                type="number"
                value={formData.cost}
                onChange={(e) => setFormData({ ...formData, cost: parseFloat(e.target.value) })}
                placeholder="Введите стоимость" />
              
              </div>
            </div>

            <div>
              <label style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              marginBottom: '4px'
            }}>
                Описание
              </label>
              <MacOSTextarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="Введите описание оборудования"
              rows={3} />
            
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
                setEditingEquipment(null);
                resetForm();
              }}
              disabled={saving}>
              
                Отмена
              </MacOSButton>
              <MacOSButton
              type="submit"
              disabled={saving}
              aria-label={editingEquipment ? 'Update equipment' : 'Add equipment'}
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
                    {editingEquipment ? 'Обновить' : 'Добавить'}
                  </>
              }
              </MacOSButton>
            </div>
          </form>
        </MacOSCard>
      }

      {/* Список оборудования */}
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
      filteredEquipment.length === 0 ?
      <MacOSEmptyState
        icon={Wrench}
        title={equipmentEmptyTitle}
        description={equipmentEmptyDescription}
        action={
        <MacOSButton onClick={() => setShowAddForm(true)} variant="primary">
              <Plus aria-hidden="true" focusable="false" style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Добавить оборудование
            </MacOSButton>
        } /> :


      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
        gap: '24px',
        overflow: 'hidden'
      }}>
          {filteredEquipment.map((item) =>
        <MacOSCard key={item.id} style={{ padding: '24px' }}>
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
                    {item.name}
                  </h3>
                  <p style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-secondary)',
                margin: 0
              }}>
                    {item.model} • {item.serial_number}
                  </p>
                </div>
                <MacOSBadge
              variant={getStatusColor(item.status)}
              text={getStatusLabel(item.status)} />
            
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '16px' }}>
                <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)'
            }}>
                  <Building2 aria-hidden="true" style={{ width: '16px', height: '16px' }} />
                  <span>{getBranchName(item.branch_id)}</span>
                </div>
                <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)'
            }}>
                  <Wrench aria-hidden="true" style={{ width: '16px', height: '16px' }} />
                  <span>{getTypeLabel(item.type)}</span>
                </div>
                {item.cost > 0 &&
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)'
            }}>
                    <DollarSign aria-hidden="true" style={{ width: '16px', height: '16px' }} />
                    <span>{item.cost.toLocaleString()} сум</span>
                  </div>
            }
                {item.warranty_expiry &&
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)'
            }}>
                    <Calendar aria-hidden="true" style={{ width: '16px', height: '16px' }} />
                    <span>Гарантия до: {new Date(item.warranty_expiry).toLocaleDateString()}</span>
                  </div>
            }
              </div>

              {item.description &&
          <div style={{ marginBottom: '16px' }}>
                  <p style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)',
              margin: 0,
              lineHeight: '1.4'
            }}>
                    {item.description}
                  </p>
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
              aria-label={`Редактировать оборудование ${item.name}`}
              onClick={() => handleEdit(item)}
              style={{ padding: '6px 12px' }}>
              
                  <Edit aria-hidden="true" style={{ width: '16px', height: '16px' }} />
                </MacOSButton>
                <MacOSButton
              type="button"
              variant="outline"
              aria-label={`Удалить оборудование ${item.name}`}
              onClick={() => handleDelete(item.id)}
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

export default EquipmentManagement;
