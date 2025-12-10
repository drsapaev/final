import React, { useState, useEffect } from 'react';
import { 
  Wrench, 
  Plus, 
  Search, 
  Filter, 
  Edit, 
  Trash2, 
  Save, 
  X,
  RefreshCw,
  Calendar,
  DollarSign,
  AlertTriangle,
  CheckCircle,
  Clock,
  MapPin,
  Building2
} from 'lucide-react';
import { 
  MacOSCard, 
  MacOSButton, 
  MacOSBadge,
  MacOSInput,
  MacOSSelect,
  MacOSTextarea,
  MacOSCheckbox,
  MacOSLoadingSkeleton,
  MacOSEmptyState,
  MacOSAlert,
  MacOSModal
} from '../ui/macos';
import { api } from '../../api/client';

import logger from '../../utils/logger';
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
    { value: 'retired', label: 'Списано', color: 'gray' }
  ];

  const typeOptions = [
    { value: 'medical', label: 'Медицинское оборудование' },
    { value: 'diagnostic', label: 'Диагностическое' },
    { value: 'surgical', label: 'Хирургическое' },
    { value: 'laboratory', label: 'Лабораторное' },
    { value: 'imaging', label: 'Визуализация' },
    { value: 'monitoring', label: 'Мониторинг' },
    { value: 'other', label: 'Прочее' }
  ];

  useEffect(() => {
    loadEquipment();
    loadBranches();
    loadStats();
  }, []);

  const loadEquipment = async () => {
    try {
      setLoading(true);
      const response = await api.get('/equipment');
      setEquipment(response.data.equipment || []);
    } catch (error) {
      logger.error('Ошибка загрузки оборудования:', error);
      // Fallback данные
      setEquipment([
        {
          id: 1,
          name: 'ЭКГ аппарат',
          type: 'diagnostic',
          model: 'ECG-2000',
          serial_number: 'ECG001',
          branch_id: 1,
          status: 'active',
          purchase_date: '2023-01-15',
          warranty_expiry: '2025-01-15',
          maintenance_date: '2024-01-15',
          cost: 150000,
          description: 'Портативный ЭКГ аппарат'
        },
        {
          id: 2,
          name: 'УЗИ сканер',
          type: 'imaging',
          model: 'US-3000',
          serial_number: 'US001',
          branch_id: 1,
          status: 'active',
          purchase_date: '2023-03-20',
          warranty_expiry: '2025-03-20',
          maintenance_date: '2024-03-20',
          cost: 500000,
          description: 'Ультразвуковой сканер'
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const loadBranches = async () => {
    try {
      const response = await api.get('/branches');
      setBranches(response.data.branches || []);
    } catch (error) {
      logger.error('Ошибка загрузки филиалов:', error);
      setBranches([
        { id: 1, name: 'Центральный филиал', code: 'CEN001' },
        { id: 2, name: 'Филиал Чиланзар', code: 'CHI002' }
      ]);
    }
  };

  const loadStats = async () => {
    try {
      const response = await api.get('/equipment/stats');
      setStats(response.data);
    } catch (error) {
      logger.error('Ошибка загрузки статистики:', error);
      setStats({
        total_equipment: 2,
        active_equipment: 2,
        maintenance_equipment: 0,
        broken_equipment: 0
      });
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      setSaving(true);
      
      if (editingEquipment) {
        await api.put(`/equipment/${editingEquipment.id}`, formData);
        setMessage({ type: 'success', text: 'Оборудование обновлено' });
      } else {
        await api.post('/equipment', formData);
        setMessage({ type: 'success', text: 'Оборудование добавлено' });
      }
      
      setShowAddForm(false);
      setEditingEquipment(null);
      resetForm();
      loadEquipment();
      loadStats();
    } catch (error) {
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
      await api.delete(`/equipment/${equipmentId}`);
      setMessage({ type: 'success', text: 'Оборудование удалено' });
      loadEquipment();
      loadStats();
    } catch (error) {
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
    const statusOption = statusOptions.find(s => s.value === status);
    return statusOption ? statusOption.color : 'gray';
  };

  const getStatusLabel = (status) => {
    const statusOption = statusOptions.find(s => s.value === status);
    return statusOption ? statusOption.label : status;
  };

  const getTypeLabel = (type) => {
    const typeOption = typeOptions.find(t => t.value === type);
    return typeOption ? typeOption.label : type;
  };

  const getBranchName = (branchId) => {
    const branch = branches.find(b => b.id === branchId);
    return branch ? branch.name : 'Неизвестно';
  };

  const filteredEquipment = equipment.filter(item => {
    const matchesSearch = item.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         item.model?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         item.serial_number?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || item.status === statusFilter;
    const matchesType = typeFilter === 'all' || item.type === typeFilter;
    const matchesBranch = branchFilter === 'all' || item.branch_id === parseInt(branchFilter);
    return matchesSearch && matchesStatus && matchesType && matchesBranch;
  });

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
        {stats && (
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
        )}
      </div>

      {/* Сообщения */}
      {message.text && (
        <MacOSAlert
          type={message.type === 'success' ? 'success' : 'error'}
          title={message.type === 'success' ? 'Успешно' : 'Ошибка'}
          message={message.text}
        />
      )}

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
              placeholder="Поиск по названию, модели или серийному номеру..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{ paddingLeft: '40px' }}
            />
            <Search style={{ 
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
            <MacOSSelect
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{ minWidth: '150px' }}
            >
              <option value="all">Все статусы</option>
              {statusOptions.map(option => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </MacOSSelect>
            <MacOSSelect
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              style={{ minWidth: '150px' }}
            >
              <option value="all">Все типы</option>
              {typeOptions.map(option => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </MacOSSelect>
            <MacOSSelect
              value={branchFilter}
              onChange={(e) => setBranchFilter(e.target.value)}
              style={{ minWidth: '150px' }}
            >
              <option value="all">Все филиалы</option>
              {branches.map(branch => (
                <option key={branch.id} value={branch.id}>{branch.name}</option>
              ))}
            </MacOSSelect>
            <MacOSButton
              onClick={() => setShowAddForm(true)}
              style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '8px',
                backgroundColor: 'var(--mac-accent-blue)',
                border: 'none',
                padding: '8px 16px'
              }}
            >
              <Plus style={{ width: '16px', height: '16px' }} />
              <span>Добавить оборудование</span>
            </MacOSButton>
          </div>
        </div>
      </MacOSCard>

      {/* Форма добавления/редактирования */}
      {showAddForm && (
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
              onClick={() => {
                setShowAddForm(false);
                setEditingEquipment(null);
                resetForm();
              }}
              style={{ padding: '8px' }}
            >
              <X style={{ width: '16px', height: '16px' }} />
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
                  placeholder="Введите название оборудования"
                />
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
                <MacOSSelect
                  required
                  value={formData.type}
                  onChange={(e) => setFormData({ ...formData, type: e.target.value })}
                >
                  <option value="">Выберите тип</option>
                  {typeOptions.map(option => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </MacOSSelect>
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
                  placeholder="Введите модель"
                />
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
                  placeholder="Введите серийный номер"
                />
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
                <MacOSSelect
                  required
                  value={formData.branch_id || ''}
                  onChange={(e) => setFormData({ ...formData, branch_id: parseInt(e.target.value) })}
                >
                  <option value="">Выберите филиал</option>
                  {branches.map(branch => (
                    <option key={branch.id} value={branch.id}>{branch.name}</option>
                  ))}
                </MacOSSelect>
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
                <MacOSSelect
                  value={formData.status}
                  onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                >
                  {statusOptions.map(option => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </MacOSSelect>
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
                  onChange={(e) => setFormData({ ...formData, purchase_date: e.target.value })}
                />
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
                  onChange={(e) => setFormData({ ...formData, warranty_expiry: e.target.value })}
                />
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
                  onChange={(e) => setFormData({ ...formData, maintenance_date: e.target.value })}
                />
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
                  placeholder="Введите стоимость"
                />
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
                rows={3}
              />
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
                disabled={saving}
              >
                Отмена
              </MacOSButton>
              <MacOSButton
                type="submit"
                disabled={saving}
                style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '8px',
                  backgroundColor: 'var(--mac-accent-blue)',
                  border: 'none'
                }}
              >
                {saving ? (
                  <>
                    <RefreshCw style={{ 
                      width: '16px', 
                      height: '16px',
                      animation: 'spin 1s linear infinite'
                    }} />
                    Сохранение...
                  </>
                ) : (
                  <>
                    <Save style={{ width: '16px', height: '16px' }} />
                    {editingEquipment ? 'Обновить' : 'Добавить'}
                  </>
                )}
              </MacOSButton>
            </div>
          </form>
        </MacOSCard>
      )}

      {/* Список оборудования */}
      {loading ? (
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', 
          gap: '24px',
          overflow: 'hidden'
        }}>
          {[1, 2, 3].map(i => (
            <MacOSCard key={i} style={{ padding: '24px' }}>
              <MacOSLoadingSkeleton height="200px" />
            </MacOSCard>
          ))}
        </div>
      ) : filteredEquipment.length === 0 ? (
        <MacOSEmptyState
          icon={Wrench}
          title="Оборудование не найдено"
          description="Добавьте первое оборудование или измените фильтры поиска"
          action={
            <MacOSButton onClick={() => setShowAddForm(true)} variant="primary">
              <Plus style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Добавить оборудование
            </MacOSButton>
          }
        />
      ) : (
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', 
          gap: '24px',
          overflow: 'hidden'
        }}>
          {filteredEquipment.map(item => (
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
                  text={getStatusLabel(item.status)}
                />
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '16px' }}>
                <div style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '8px',
                  fontSize: 'var(--mac-font-size-sm)', 
                  color: 'var(--mac-text-secondary)' 
                }}>
                  <Building2 style={{ width: '16px', height: '16px' }} />
                  <span>{getBranchName(item.branch_id)}</span>
                </div>
                <div style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '8px',
                  fontSize: 'var(--mac-font-size-sm)', 
                  color: 'var(--mac-text-secondary)' 
                }}>
                  <Wrench style={{ width: '16px', height: '16px' }} />
                  <span>{getTypeLabel(item.type)}</span>
                </div>
                {item.cost > 0 && (
                  <div style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: '8px',
                    fontSize: 'var(--mac-font-size-sm)', 
                    color: 'var(--mac-text-secondary)' 
                  }}>
                    <DollarSign style={{ width: '16px', height: '16px' }} />
                    <span>{item.cost.toLocaleString()} сум</span>
                  </div>
                )}
                {item.warranty_expiry && (
                  <div style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: '8px',
                    fontSize: 'var(--mac-font-size-sm)', 
                    color: 'var(--mac-text-secondary)' 
                  }}>
                    <Calendar style={{ width: '16px', height: '16px' }} />
                    <span>Гарантия до: {new Date(item.warranty_expiry).toLocaleDateString()}</span>
                  </div>
                )}
              </div>

              {item.description && (
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
              )}

              <div style={{ 
                display: 'flex', 
                justifyContent: 'flex-end', 
                gap: '8px' 
              }}>
                <MacOSButton
                  variant="outline"
                  onClick={() => handleEdit(item)}
                  style={{ padding: '6px 12px' }}
                >
                  <Edit style={{ width: '16px', height: '16px' }} />
                </MacOSButton>
                <MacOSButton
                  variant="outline"
                  onClick={() => handleDelete(item.id)}
                  style={{ 
                    padding: '6px 12px',
                    color: 'var(--mac-error)',
                    borderColor: 'var(--mac-error)'
                  }}
                >
                  <Trash2 style={{ width: '16px', height: '16px' }} />
                </MacOSButton>
              </div>
            </MacOSCard>
          ))}
        </div>
      )}
    </div>
  );
};

export default EquipmentManagement;