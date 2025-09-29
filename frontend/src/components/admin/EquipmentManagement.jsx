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
import { Card, Button, Badge } from '../ui/native';

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
    model: '',
    serial_number: '',
    equipment_type: 'medical',
    branch_id: null,
    cabinet: '',
    status: 'active',
    purchase_date: '',
    warranty_expires: '',
    cost: '',
    supplier: '',
    notes: ''
  });

  const statusOptions = [
    { value: 'active', label: 'Активное', color: 'green' },
    { value: 'inactive', label: 'Неактивное', color: 'gray' },
    { value: 'maintenance', label: 'Обслуживание', color: 'yellow' },
    { value: 'broken', label: 'Сломано', color: 'red' },
    { value: 'replaced', label: 'Заменено', color: 'blue' }
  ];

  const typeOptions = [
    { value: 'medical', label: 'Медицинское', icon: '🏥' },
    { value: 'diagnostic', label: 'Диагностическое', icon: '🔬' },
    { value: 'surgical', label: 'Хирургическое', icon: '⚕️' },
    { value: 'laboratory', label: 'Лабораторное', icon: '🧪' },
    { value: 'office', label: 'Офисное', icon: '💻' },
    { value: 'it', label: 'IT оборудование', icon: '🖥️' }
  ];

  useEffect(() => {
    loadEquipment();
    loadBranches();
    loadStats();
  }, []);

  const loadEquipment = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (searchTerm) params.append('search', searchTerm);
      if (statusFilter !== 'all') params.append('status', statusFilter);
      if (typeFilter !== 'all') params.append('equipment_type', typeFilter);
      if (branchFilter !== 'all') params.append('branch_id', branchFilter);
      
      const response = await fetch(`/api/v1/clinic/equipment?${params}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        setEquipment(data);
      } else {
        throw new Error('Ошибка загрузки оборудования');
      }
    } catch (error) {
      setMessage({ type: 'error', text: error.message });
    } finally {
      setLoading(false);
    }
  };

  const loadBranches = async () => {
    try {
      const response = await fetch('/api/v1/clinic/branches', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        setBranches(data);
      }
    } catch (error) {
      console.error('Ошибка загрузки филиалов:', error);
    }
  };

  const loadStats = async () => {
    try {
      const response = await fetch('/api/v1/clinic/stats', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (error) {
      console.error('Ошибка загрузки статистики:', error);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    
    try {
      const url = editingEquipment 
        ? `/api/v1/clinic/equipment/${editingEquipment.id}`
        : '/api/v1/clinic/equipment';
      
      const method = editingEquipment ? 'PUT' : 'POST';
      
      const submitData = {
        ...formData,
        cost: formData.cost ? parseFloat(formData.cost) : null,
        purchase_date: formData.purchase_date || null,
        warranty_expires: formData.warranty_expires || null
      };
      
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(submitData)
      });
      
      if (response.ok) {
        setMessage({ type: 'success', text: editingEquipment ? 'Оборудование обновлено' : 'Оборудование создано' });
        setShowAddForm(false);
        setEditingEquipment(null);
        resetForm();
        loadEquipment();
        loadStats();
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Ошибка сохранения');
      }
    } catch (error) {
      setMessage({ type: 'error', text: error.message });
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (equipment) => {
    setEditingEquipment(equipment);
    setFormData({
      name: equipment.name,
      model: equipment.model || '',
      serial_number: equipment.serial_number || '',
      equipment_type: equipment.equipment_type,
      branch_id: equipment.branch_id,
      cabinet: equipment.cabinet || '',
      status: equipment.status,
      purchase_date: equipment.purchase_date || '',
      warranty_expires: equipment.warranty_expires || '',
      cost: equipment.cost || '',
      supplier: equipment.supplier || '',
      notes: equipment.notes || ''
    });
    setShowAddForm(true);
  };

  const handleDelete = async (equipmentId) => {
    if (!window.confirm('Вы уверены, что хотите удалить это оборудование?')) return;
    
    try {
      const response = await fetch(`/api/v1/clinic/equipment/${equipmentId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      
      if (response.ok) {
        setMessage({ type: 'success', text: 'Оборудование удалено' });
        loadEquipment();
        loadStats();
      } else {
        throw new Error('Ошибка удаления оборудования');
      }
    } catch (error) {
      setMessage({ type: 'error', text: error.message });
    }
  };

  const resetForm = () => {
    setFormData({
      name: '',
      model: '',
      serial_number: '',
      equipment_type: 'medical',
      branch_id: null,
      cabinet: '',
      status: 'active',
      purchase_date: '',
      warranty_expires: '',
      cost: '',
      supplier: '',
      notes: ''
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

  const getTypeIcon = (type) => {
    const typeOption = typeOptions.find(t => t.value === type);
    return typeOption ? typeOption.icon : '🔧';
  };

  const getTypeLabel = (type) => {
    const typeOption = typeOptions.find(t => t.value === type);
    return typeOption ? typeOption.label : type;
  };

  const getBranchName = (branchId) => {
    const branch = branches.find(b => b.id === branchId);
    return branch ? branch.name : 'Неизвестный филиал';
  };

  const isMaintenanceDue = (equipment) => {
    if (!equipment.next_maintenance) return false;
    const nextMaintenance = new Date(equipment.next_maintenance);
    const now = new Date();
    const daysUntilMaintenance = Math.ceil((nextMaintenance - now) / (1000 * 60 * 60 * 24));
    return daysUntilMaintenance <= 30 && daysUntilMaintenance >= 0;
  };

  const filteredEquipment = equipment.filter(item => {
    const matchesSearch = item.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         item.model?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         item.serial_number?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || item.status === statusFilter;
    const matchesType = typeFilter === 'all' || item.equipment_type === typeFilter;
    const matchesBranch = branchFilter === 'all' || item.branch_id === parseInt(branchFilter);
    return matchesSearch && matchesStatus && matchesType && matchesBranch;
  });

  return (
    <div className="space-y-6">
      {/* Заголовок и статистика */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Управление оборудованием</h2>
          <p className="text-gray-600">Учет и обслуживание оборудования клиники</p>
        </div>
        {stats && (
          <div className="flex space-x-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">{stats.total_equipment}</div>
              <div className="text-sm text-gray-600">Всего оборудования</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">{stats.active_equipment}</div>
              <div className="text-sm text-gray-600">Активного</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-yellow-600">{stats.equipment_in_maintenance}</div>
              <div className="text-sm text-gray-600">На обслуживании</div>
            </div>
          </div>
        )}
      </div>

      {/* Сообщения */}
      {message.text && (
        <div className={`p-4 rounded-lg flex items-center space-x-2 ${
          message.type === 'success' ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
        }`}>
          {message.type === 'success' ? <CheckCircle className="w-5 h-5" /> : <AlertTriangle className="w-5 h-5" />}
          <span>{message.text}</span>
        </div>
      )}

      {/* Фильтры и поиск */}
      <Card className="p-4">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
            <input
              type="text"
              placeholder="Поиск оборудования..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="all">Все статусы</option>
            {statusOptions.map(option => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="all">Все типы</option>
            {typeOptions.map(option => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
          <select
            value={branchFilter}
            onChange={(e) => setBranchFilter(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="all">Все филиалы</option>
            {branches.map(branch => (
              <option key={branch.id} value={branch.id}>{branch.name}</option>
            ))}
          </select>
        </div>
        <div className="mt-4 flex justify-end">
          <Button
            onClick={() => setShowAddForm(true)}
            className="flex items-center space-x-2"
          >
            <Plus className="w-4 h-4" />
            <span>Добавить оборудование</span>
          </Button>
        </div>
      </Card>

      {/* Форма добавления/редактирования */}
      {showAddForm && (
        <Card className="p-6">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-semibold">
              {editingEquipment ? 'Редактировать оборудование' : 'Добавить оборудование'}
            </h3>
            <Button
              variant="outline"
              onClick={() => {
                setShowAddForm(false);
                setEditingEquipment(null);
                resetForm();
              }}
            >
              <X className="w-4 h-4" />
            </Button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Название оборудования *
                </label>
                <input
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => setFormData({...formData, name: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Модель
                </label>
                <input
                  type="text"
                  value={formData.model}
                  onChange={(e) => setFormData({...formData, model: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Серийный номер
                </label>
                <input
                  type="text"
                  value={formData.serial_number}
                  onChange={(e) => setFormData({...formData, serial_number: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Тип оборудования *
                </label>
                <select
                  required
                  value={formData.equipment_type}
                  onChange={(e) => setFormData({...formData, equipment_type: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  {typeOptions.map(option => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Филиал *
                </label>
                <select
                  required
                  value={formData.branch_id || ''}
                  onChange={(e) => setFormData({...formData, branch_id: parseInt(e.target.value)})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="">Выберите филиал</option>
                  {branches.map(branch => (
                    <option key={branch.id} value={branch.id}>{branch.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Кабинет
                </label>
                <input
                  type="text"
                  value={formData.cabinet}
                  onChange={(e) => setFormData({...formData, cabinet: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Статус
                </label>
                <select
                  value={formData.status}
                  onChange={(e) => setFormData({...formData, status: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  {statusOptions.map(option => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Стоимость
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={formData.cost}
                  onChange={(e) => setFormData({...formData, cost: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Дата покупки
                </label>
                <input
                  type="date"
                  value={formData.purchase_date}
                  onChange={(e) => setFormData({...formData, purchase_date: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Гарантия до
                </label>
                <input
                  type="date"
                  value={formData.warranty_expires}
                  onChange={(e) => setFormData({...formData, warranty_expires: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Поставщик
                </label>
                <input
                  type="text"
                  value={formData.supplier}
                  onChange={(e) => setFormData({...formData, supplier: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Примечания
              </label>
              <textarea
                value={formData.notes}
                onChange={(e) => setFormData({...formData, notes: e.target.value})}
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            <div className="flex justify-end space-x-3">
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setShowAddForm(false);
                  setEditingEquipment(null);
                  resetForm();
                }}
              >
                Отмена
              </Button>
              <Button
                type="submit"
                disabled={saving}
                className="flex items-center space-x-2"
              >
                {saving ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <Save className="w-4 h-4" />
                )}
                <span>{saving ? 'Сохранение...' : 'Сохранить'}</span>
              </Button>
            </div>
          </form>
        </Card>
      )}

      {/* Список оборудования */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {loading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <Card key={i} className="p-6">
              <div className="animate-pulse">
                <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
                <div className="h-3 bg-gray-200 rounded w-1/2 mb-4"></div>
                <div className="h-3 bg-gray-200 rounded w-full mb-2"></div>
                <div className="h-3 bg-gray-200 rounded w-2/3"></div>
              </div>
            </Card>
          ))
        ) : filteredEquipment.length === 0 ? (
          <div className="col-span-full text-center py-12">
            <Wrench className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Оборудование не найдено</h3>
            <p className="text-gray-600">Добавьте первое оборудование или измените фильтры поиска</p>
          </div>
        ) : (
          filteredEquipment.map(item => (
            <Card key={item.id} className="p-6 hover:shadow-lg transition-shadow">
              <div className="flex justify-between items-start mb-4">
                <div className="flex items-center space-x-2">
                  <span className="text-2xl">{getTypeIcon(item.equipment_type)}</span>
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900">{item.name}</h3>
                    <p className="text-sm text-gray-600">{item.model}</p>
                  </div>
                </div>
                <Badge color={getStatusColor(item.status)}>
                  {getStatusLabel(item.status)}
                </Badge>
              </div>

              <div className="space-y-2 mb-4">
                <div className="flex items-center space-x-2 text-sm text-gray-600">
                  <Building2 className="w-4 h-4" />
                  <span>{getBranchName(item.branch_id)}</span>
                </div>
                {item.cabinet && (
                  <div className="flex items-center space-x-2 text-sm text-gray-600">
                    <MapPin className="w-4 h-4" />
                    <span>Кабинет {item.cabinet}</span>
                  </div>
                )}
                {item.serial_number && (
                  <div className="text-sm text-gray-600">
                    <span className="font-medium">Серийный номер:</span> {item.serial_number}
                  </div>
                )}
                {item.cost && (
                  <div className="flex items-center space-x-2 text-sm text-gray-600">
                    <DollarSign className="w-4 h-4" />
                    <span>{parseFloat(item.cost).toLocaleString()} сум</span>
                  </div>
                )}
                {item.supplier && (
                  <div className="text-sm text-gray-600">
                    <span className="font-medium">Поставщик:</span> {item.supplier}
                  </div>
                )}
                {isMaintenanceDue(item) && (
                  <div className="flex items-center space-x-2 text-sm text-yellow-600">
                    <AlertTriangle className="w-4 h-4" />
                    <span>Требуется обслуживание</span>
                  </div>
                )}
              </div>

              {item.notes && (
                <div className="mb-4">
                  <p className="text-sm text-gray-600">{item.notes}</p>
                </div>
              )}

              <div className="flex justify-end space-x-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleEdit(item)}
                >
                  <Edit className="w-4 h-4" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleDelete(item.id)}
                  className="text-red-600 hover:text-red-700"
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            </Card>
          ))
        )}
      </div>
    </div>
  );
};

export default EquipmentManagement;

