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
import { useTranslation } from '../../i18n/adapter';

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
    <div className="admin-d-flex-fd-column-gap-24-ov-hidden">
      {/* Заголовок и статистика */}
      <div className="admin-d-flex-jc-between-ai-center-fw-wrap-gap-16">
        <div>
          <h2 className="admin-fs-2xl-fw-bold-primary-m-0-0-8px-0">
            Управление оборудованием
          </h2>
          <p className="admin-secondary-fs-sm-m-0">
            Учет и управление медицинским оборудованием
          </p>
        </div>
        {stats &&
        <div className="admin-d-flex-gap-24-fw-wrap">
            <div className="text-center">
              <div className="admin-fs-2xl-fw-bold-blue-mb-4">
                {stats.total_equipment}
              </div>
              <div className="text-sm text-[var(--mac-text-secondary)]">
                Всего единиц
              </div>
            </div>
            <div className="text-center">
              <div className="admin-fs-2xl-fw-bold-success-mb-4">
                {stats.active_equipment}
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
        <div className="admin-d-flex-fd-column-gap-16-fw-wrap">
          <div className="admin-flex-1-pos-relative">
            <Input
              type="text"
              aria-label="Поиск оборудования по названию, модели или серийному номеру"
              placeholder="Поиск по названию, модели или серийному номеру..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="admin-pl-40" />
            
            <Search aria-hidden="true" className="admin-pos-absolute-left-12-top-50pct-tf-translateY-50-tertiary-w-16-h-16" />
          </div>
          <div className="admin-d-flex-gap-12-fw-wrap">
            <Select
              aria-label="Фильтр оборудования по статусу"
              value={statusFilter}
              onChange={setStatusFilter}
              options={[
                { value: 'all', label: 'Все статусы' },
                ...statusOptions.map((option) => ({ value: option.value, label: option.label }))
              ]}
              size="large"
              className="admin-minw-150" />
            <Select
              aria-label="Фильтр оборудования по типу"
              value={typeFilter}
              onChange={setTypeFilter}
              options={[
                { value: 'all', label: 'Все типы' },
                ...typeOptions.map((option) => ({ value: option.value, label: option.label }))
              ]}
              size="large"
              className="admin-minw-150" />
            <Select
              aria-label="Фильтр оборудования по филиалу"
              value={branchFilter}
              onChange={setBranchFilter}
              options={[
                { value: 'all', label: 'Все филиалы' },
                ...branches.map((branch) => ({ value: String(branch.id), label: branch.name }))
              ]}
              size="large"
              className="admin-minw-150" />
            <Button
              onClick={() => setShowAddForm(true)}
              className="admin-d-flex-ai-center-gap-8-bgc-blue-bd-none-p-8px-16px">
              
              <Plus aria-hidden="true" className="w-4 h-4" />
              <span>Добавить оборудование</span>
            </Button>
          </div>
        </div>
      </MacOSCard>

      {/* Форма добавления/редактирования */}
      {showAddForm &&
      <MacOSCard className="admin-p-24-ov-hidden">
          <div className="admin-d-flex-jc-between-ai-center-mb-16">
            <h3 className="admin-fs-lg-fw-semi-primary-m-0">
              {editingEquipment ? 'Редактировать оборудование' : 'Добавить оборудование'}
            </h3>
            <Button
            variant="outline"
            type="button"
            aria-label={editingEquipment ? 'Закрыть форму редактирования оборудования' : 'Закрыть форму добавления оборудования'}
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
                  Название *
                </label>
                <Input
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="Введите название оборудования" />
              
              </div>
              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-4-9">
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
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-4-8">
                  Модель
                </label>
                <Input
                type="text"
                value={formData.model}
                onChange={(e) => setFormData({ ...formData, model: e.target.value })}
                placeholder="Введите модель" />
              
              </div>
              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-4-7">
                  Серийный номер
                </label>
                <Input
                type="text"
                value={formData.serial_number}
                onChange={(e) => setFormData({ ...formData, serial_number: e.target.value })}
                placeholder="Введите серийный номер" />
              
              </div>
              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-4-6">
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
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-4-5">
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
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-4-4">
                  Дата покупки
                </label>
                <Input
                type="date"
                value={formData.purchase_date}
                onChange={(e) => setFormData({ ...formData, purchase_date: e.target.value })} />
              
              </div>
              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-4-3">
                  Окончание гарантии
                </label>
                <Input
                type="date"
                value={formData.warranty_expiry}
                onChange={(e) => setFormData({ ...formData, warranty_expiry: e.target.value })} />
              
              </div>
              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-4-2">
                  Последнее обслуживание
                </label>
                <Input
                type="date"
                value={formData.maintenance_date}
                onChange={(e) => setFormData({ ...formData, maintenance_date: e.target.value })} />
              
              </div>
              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-4-1">
                  Стоимость (сум)
                </label>
                <Input
                type="number"
                value={formData.cost}
                onChange={(e) => setFormData({ ...formData, cost: parseFloat(e.target.value) })}
                placeholder="Введите стоимость" />
              
              </div>
            </div>

            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-4">
                Описание
              </label>
              <Textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="Введите описание оборудования"
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
              
                Отмена
              </Button>
              <Button
              type="submit"
              disabled={saving}
              aria-label={editingEquipment ? 'Update equipment' : 'Add equipment'}
              className="admin-d-flex-ai-center-gap-8-bgc-blue-bd-none">
              
                {saving ?
              <>
                    <RefreshCw aria-hidden="true" className="admin-w-16-h-16-anim-spin-1s-linear-infin" />
                    Сохранение...
                  </> :

              <>
                    <Save aria-hidden="true" className="w-4 h-4" />
                    {editingEquipment ? 'Обновить' : 'Добавить'}
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
              Добавить оборудование
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
                    <span>{item.cost.toLocaleString()} сум</span>
                  </div>
            }
                {item.warranty_expiry &&
            <div className="admin-d-flex-ai-center-gap-8-fs-sm-secondary">
                    <Calendar aria-hidden="true" className="w-4 h-4" />
                    <span>Гарантия до: {new Date(item.warranty_expiry).toLocaleDateString()}</span>
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
              aria-label={`Редактировать оборудование ${item.name}`}
              onClick={() => handleEdit(item)}
              className="admin-p-6px-12px">
              
                  <Edit aria-hidden="true" className="w-4 h-4" />
                </Button>
                <Button
              type="button"
              variant="outline"
              aria-label={`Удалить оборудование ${item.name}`}
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
