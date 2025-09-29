import React, { useState, useEffect } from 'react';
import { Card, Button, Badge, Input, Select, Label, Skeleton } from '../ui/native';
import { 
  Activity, 
  Wifi, 
  WifiOff, 
  AlertTriangle, 
  Settings, 
  Play, 
  Square, 
  Wrench, 
  BarChart3,
  Download,
  RefreshCw,
  Stethoscope,
  Heart,
  Thermometer,
  Scale,
  Zap
} from 'lucide-react';
import { toast } from 'react-toastify';

const MedicalEquipmentManager = () => {
  const [activeTab, setActiveTab] = useState('devices');
  const [devices, setDevices] = useState([]);
  const [measurements, setMeasurements] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [overview, setOverview] = useState(null);

  // Состояние для измерения
  const [measurementForm, setMeasurementForm] = useState({
    device_id: '',
    patient_id: ''
  });

  // Состояние для фильтров
  const [filters, setFilters] = useState({
    device_type: '',
    status: '',
    location: ''
  });

  useEffect(() => {
    loadDevices();
    loadOverview();
  }, []);

  const loadDevices = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${import.meta.env.VITE_API_URL}/medical-equipment/devices`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setDevices(data.devices || []);
      } else {
        toast.error('Ошибка загрузки устройств');
      }
    } catch (error) {
      console.error('Ошибка загрузки устройств:', error);
      toast.error('Ошибка загрузки устройств');
    } finally {
      setLoading(false);
    }
  };

  const loadOverview = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${import.meta.env.VITE_API_URL}/medical-equipment/statistics/overview`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setOverview(data.overview);
      }
    } catch (error) {
      console.error('Ошибка загрузки обзора:', error);
    }
  };

  const loadMeasurements = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('access_token');
      const params = new URLSearchParams();
      if (filters.device_type) params.append('device_type', filters.device_type);
      
      const response = await fetch(`${import.meta.env.VITE_API_URL}/medical-equipment/measurements?${params}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setMeasurements(data.measurements || []);
      } else {
        toast.error('Ошибка загрузки измерений');
      }
    } catch (error) {
      console.error('Ошибка загрузки измерений:', error);
      toast.error('Ошибка загрузки измерений');
    } finally {
      setLoading(false);
    }
  };

  const connectDevice = async (deviceId) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${import.meta.env.VITE_API_URL}/medical-equipment/devices/${deviceId}/connect`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      const data = await response.json();
      if (data.success) {
        toast.success('Устройство подключено');
        loadDevices();
      } else {
        toast.error(data.message || 'Ошибка подключения');
      }
    } catch (error) {
      console.error('Ошибка подключения устройства:', error);
      toast.error('Ошибка подключения устройства');
    }
  };

  const disconnectDevice = async (deviceId) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${import.meta.env.VITE_API_URL}/medical-equipment/devices/${deviceId}/disconnect`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      const data = await response.json();
      if (data.success) {
        toast.success('Устройство отключено');
        loadDevices();
      } else {
        toast.error(data.message || 'Ошибка отключения');
      }
    } catch (error) {
      console.error('Ошибка отключения устройства:', error);
      toast.error('Ошибка отключения устройства');
    }
  };

  const takeMeasurement = async () => {
    if (!measurementForm.device_id) {
      toast.error('Выберите устройство');
      return;
    }

    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${import.meta.env.VITE_API_URL}/medical-equipment/measurements`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(measurementForm)
      });

      if (response.ok) {
        const data = await response.json();
        toast.success('Измерение выполнено');
        setMeasurementForm({ device_id: '', patient_id: '' });
        if (activeTab === 'measurements') {
          loadMeasurements();
        }
      } else {
        const errorData = await response.json();
        toast.error(errorData.detail || 'Ошибка измерения');
      }
    } catch (error) {
      console.error('Ошибка измерения:', error);
      toast.error('Ошибка измерения');
    }
  };

  const calibrateDevice = async (deviceId) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${import.meta.env.VITE_API_URL}/medical-equipment/devices/${deviceId}/calibrate`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      const data = await response.json();
      if (data.success) {
        toast.success('Калибровка завершена');
        loadDevices();
      } else {
        toast.error(data.message || 'Ошибка калибровки');
      }
    } catch (error) {
      console.error('Ошибка калибровки:', error);
      toast.error('Ошибка калибровки');
    }
  };

  const runDiagnostics = async (deviceId) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${import.meta.env.VITE_API_URL}/medical-equipment/devices/${deviceId}/diagnostics`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setSelectedDevice({ ...selectedDevice, diagnostics: data });
        toast.success('Диагностика завершена');
      } else {
        toast.error('Ошибка диагностики');
      }
    } catch (error) {
      console.error('Ошибка диагностики:', error);
      toast.error('Ошибка диагностики');
    }
  };

  const getStatusBadgeVariant = (status) => {
    switch (status) {
      case 'online': return 'success';
      case 'busy': return 'warning';
      case 'offline': return 'secondary';
      case 'error': return 'destructive';
      case 'maintenance': return 'warning';
      case 'calibrating': return 'info';
      default: return 'secondary';
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'online': return 'В сети';
      case 'busy': return 'Занято';
      case 'offline': return 'Не в сети';
      case 'error': return 'Ошибка';
      case 'maintenance': return 'Обслуживание';
      case 'calibrating': return 'Калибровка';
      default: return status;
    }
  };

  const getDeviceIcon = (deviceType) => {
    switch (deviceType) {
      case 'blood_pressure': return Heart;
      case 'pulse_oximeter': return Activity;
      case 'glucometer': return Zap;
      case 'thermometer': return Thermometer;
      case 'scale': return Scale;
      case 'ecg': return Stethoscope;
      default: return Activity;
    }
  };

  const getDeviceTypeName = (deviceType) => {
    switch (deviceType) {
      case 'blood_pressure': return 'Тонометр';
      case 'pulse_oximeter': return 'Пульсоксиметр';
      case 'glucometer': return 'Глюкометр';
      case 'thermometer': return 'Термометр';
      case 'scale': return 'Весы';
      case 'ecg': return 'ЭКГ';
      case 'ultrasound': return 'УЗИ';
      case 'xray': return 'Рентген';
      case 'analyzer': return 'Анализатор';
      case 'spirometer': return 'Спирометр';
      case 'height_meter': return 'Ростомер';
      default: return deviceType;
    }
  };

  const filteredDevices = devices.filter(device => {
    if (filters.device_type && device.device_type !== filters.device_type) return false;
    if (filters.status && device.status !== filters.status) return false;
    if (filters.location && !device.location.toLowerCase().includes(filters.location.toLowerCase())) return false;
    return true;
  });

  const renderOverviewTab = () => (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold">Обзор оборудования</h3>
        <Button onClick={() => { loadDevices(); loadOverview(); }} disabled={loading}>
          <RefreshCw className="w-4 h-4 mr-2" />
          {loading ? 'Загрузка...' : 'Обновить'}
        </Button>
      </div>

      {overview && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <Card className="p-4">
            <div className="text-2xl font-bold text-blue-600">{overview.total_devices}</div>
            <div className="text-sm text-gray-600">Всего устройств</div>
          </Card>
          <Card className="p-4">
            <div className="text-2xl font-bold text-green-600">{overview.online_devices}</div>
            <div className="text-sm text-gray-600">В сети</div>
          </Card>
          <Card className="p-4">
            <div className="text-2xl font-bold text-red-600">{overview.offline_devices}</div>
            <div className="text-sm text-gray-600">Не в сети</div>
          </Card>
          <Card className="p-4">
            <div className="text-2xl font-bold text-purple-600">{overview.total_measurements}</div>
            <div className="text-sm text-gray-600">Всего измерений</div>
          </Card>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card className="p-6">
          <h4 className="font-semibold mb-4">Статистика по типам устройств</h4>
          {overview?.device_types && Object.entries(overview.device_types).map(([type, stats]) => (
            <div key={type} className="flex justify-between items-center py-2">
              <span>{getDeviceTypeName(type)}</span>
              <div className="flex items-center space-x-2">
                <Badge variant="outline">{stats.total}</Badge>
                <Badge variant="success">{stats.online}</Badge>
              </div>
            </div>
          ))}
        </Card>

        <Card className="p-6">
          <h4 className="font-semibold mb-4">Быстрые действия</h4>
          <div className="space-y-3">
            <Button 
              onClick={() => setActiveTab('devices')} 
              className="w-full justify-start"
              variant="outline"
            >
              <Settings className="w-4 h-4 mr-2" />
              Управление устройствами
            </Button>
            <Button 
              onClick={() => setActiveTab('measurements')} 
              className="w-full justify-start"
              variant="outline"
            >
              <BarChart3 className="w-4 h-4 mr-2" />
              Просмотр измерений
            </Button>
            <Button 
              onClick={() => setActiveTab('measurement')} 
              className="w-full justify-start"
              variant="outline"
            >
              <Activity className="w-4 h-4 mr-2" />
              Выполнить измерение
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );

  const renderDevicesTab = () => (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold">Устройства</h3>
        <Button onClick={loadDevices} disabled={loading}>
          <RefreshCw className="w-4 h-4 mr-2" />
          {loading ? 'Загрузка...' : 'Обновить'}
        </Button>
      </div>

      {/* Фильтры */}
      <Card className="p-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <Label htmlFor="device-type-filter">Тип устройства</Label>
            <Select
              id="device-type-filter"
              value={filters.device_type}
              onChange={(e) => setFilters({...filters, device_type: e.target.value})}
            >
              <option value="">Все типы</option>
              <option value="blood_pressure">Тонометр</option>
              <option value="pulse_oximeter">Пульсоксиметр</option>
              <option value="glucometer">Глюкометр</option>
              <option value="thermometer">Термометр</option>
              <option value="scale">Весы</option>
              <option value="ecg">ЭКГ</option>
            </Select>
          </div>
          <div>
            <Label htmlFor="status-filter">Статус</Label>
            <Select
              id="status-filter"
              value={filters.status}
              onChange={(e) => setFilters({...filters, status: e.target.value})}
            >
              <option value="">Все статусы</option>
              <option value="online">В сети</option>
              <option value="offline">Не в сети</option>
              <option value="error">Ошибка</option>
              <option value="busy">Занято</option>
            </Select>
          </div>
          <div>
            <Label htmlFor="location-filter">Местоположение</Label>
            <Input
              id="location-filter"
              value={filters.location}
              onChange={(e) => setFilters({...filters, location: e.target.value})}
              placeholder="Поиск по местоположению"
            />
          </div>
        </div>
      </Card>

      {/* Список устройств */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredDevices.map((device) => {
          const DeviceIcon = getDeviceIcon(device.device_type);
          return (
            <Card key={device.id} className="p-4">
              <div className="flex justify-between items-start mb-3">
                <div className="flex items-center space-x-2">
                  <DeviceIcon className="w-5 h-5 text-blue-600" />
                  <div>
                    <h4 className="font-semibold">{device.name}</h4>
                    <p className="text-sm text-gray-600">{getDeviceTypeName(device.device_type)}</p>
                  </div>
                </div>
                <Badge variant={getStatusBadgeVariant(device.status)}>
                  {getStatusText(device.status)}
                </Badge>
              </div>
              
              <div className="space-y-2 text-sm mb-4">
                <div><strong>Производитель:</strong> {device.manufacturer}</div>
                <div><strong>Модель:</strong> {device.model}</div>
                <div><strong>Местоположение:</strong> {device.location || 'Не указано'}</div>
                <div><strong>Серийный номер:</strong> {device.serial_number}</div>
              </div>

              <div className="flex flex-wrap gap-2">
                {device.status === 'offline' ? (
                  <Button
                    size="sm"
                    onClick={() => connectDevice(device.id)}
                    className="flex items-center"
                  >
                    <Wifi className="w-4 h-4 mr-1" />
                    Подключить
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => disconnectDevice(device.id)}
                    className="flex items-center"
                  >
                    <WifiOff className="w-4 h-4 mr-1" />
                    Отключить
                  </Button>
                )}
                
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => calibrateDevice(device.id)}
                  disabled={device.status !== 'online'}
                >
                  <Wrench className="w-4 h-4 mr-1" />
                  Калибровка
                </Button>
                
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setSelectedDevice(device)}
                >
                  <Settings className="w-4 h-4 mr-1" />
                  Подробнее
                </Button>
              </div>
            </Card>
          );
        })}
      </div>

      {filteredDevices.length === 0 && !loading && (
        <div className="text-center py-8 text-gray-500">
          Устройства не найдены
        </div>
      )}
    </div>
  );

  const renderMeasurementTab = () => (
    <div className="space-y-6">
      <h3 className="text-lg font-semibold">Выполнить измерение</h3>
      
      <Card className="p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-4">
            <div>
              <Label htmlFor="measurement-device">Устройство</Label>
              <Select
                id="measurement-device"
                value={measurementForm.device_id}
                onChange={(e) => setMeasurementForm({...measurementForm, device_id: e.target.value})}
              >
                <option value="">Выберите устройство</option>
                {devices
                  .filter(d => d.status === 'online')
                  .map(device => (
                    <option key={device.id} value={device.id}>
                      {device.name} ({getDeviceTypeName(device.device_type)})
                    </option>
                  ))}
              </Select>
            </div>

            <div>
              <Label htmlFor="measurement-patient">ID пациента (опционально)</Label>
              <Input
                id="measurement-patient"
                value={measurementForm.patient_id}
                onChange={(e) => setMeasurementForm({...measurementForm, patient_id: e.target.value})}
                placeholder="Введите ID пациента"
              />
            </div>

            <Button 
              onClick={takeMeasurement}
              disabled={!measurementForm.device_id}
              className="w-full"
            >
              <Activity className="w-4 h-4 mr-2" />
              Выполнить измерение
            </Button>
          </div>

          <div className="space-y-4">
            <h4 className="font-medium">Доступные устройства</h4>
            <div className="space-y-2">
              {devices
                .filter(d => d.status === 'online')
                .map(device => {
                  const DeviceIcon = getDeviceIcon(device.device_type);
                  return (
                    <div key={device.id} className="flex items-center justify-between p-2 border rounded">
                      <div className="flex items-center space-x-2">
                        <DeviceIcon className="w-4 h-4 text-blue-600" />
                        <span className="text-sm">{device.name}</span>
                      </div>
                      <Badge variant="success">Готов</Badge>
                    </div>
                  );
                })}
            </div>
            
            {devices.filter(d => d.status === 'online').length === 0 && (
              <div className="text-center py-4 text-gray-500">
                Нет доступных устройств
              </div>
            )}
          </div>
        </div>
      </Card>
    </div>
  );

  const renderMeasurementsTab = () => {
    useEffect(() => {
      if (activeTab === 'measurements') {
        loadMeasurements();
      }
    }, [activeTab]);

    return (
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <h3 className="text-lg font-semibold">История измерений</h3>
          <div className="flex space-x-2">
            <Button onClick={loadMeasurements} disabled={loading}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Обновить
            </Button>
            <Button variant="outline">
              <Download className="w-4 h-4 mr-2" />
              Экспорт
            </Button>
          </div>
        </div>

        {/* Фильтры для измерений */}
        <Card className="p-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label htmlFor="measurements-device-type">Тип устройства</Label>
              <Select
                id="measurements-device-type"
                value={filters.device_type}
                onChange={(e) => setFilters({...filters, device_type: e.target.value})}
              >
                <option value="">Все типы</option>
                <option value="blood_pressure">Тонометр</option>
                <option value="pulse_oximeter">Пульсоксиметр</option>
                <option value="glucometer">Глюкометр</option>
                <option value="thermometer">Термометр</option>
                <option value="scale">Весы</option>
              </Select>
            </div>
            <div className="flex items-end">
              <Button onClick={loadMeasurements}>
                Применить фильтры
              </Button>
            </div>
          </div>
        </Card>

        {/* Список измерений */}
        <div className="space-y-4">
          {measurements.map((measurement, index) => (
            <Card key={index} className="p-4">
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <div className="flex items-center space-x-2 mb-2">
                    <Badge variant="outline">{getDeviceTypeName(measurement.device_type)}</Badge>
                    <span className="text-sm text-gray-600">
                      {new Date(measurement.timestamp).toLocaleString()}
                    </span>
                    {measurement.quality_score && (
                      <Badge variant={measurement.quality_score > 0.8 ? 'success' : 'warning'}>
                        Качество: {Math.round(measurement.quality_score * 100)}%
                      </Badge>
                    )}
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <strong>Устройство:</strong> {measurement.device_id}
                    </div>
                    {measurement.patient_id && (
                      <div>
                        <strong>Пациент:</strong> {measurement.patient_id}
                      </div>
                    )}
                    <div>
                      <strong>Данные:</strong>
                      <div className="text-sm mt-1">
                        {Object.entries(measurement.measurements).map(([key, value]) => (
                          <div key={key}>
                            {key}: {typeof value === 'number' ? value.toFixed(1) : value}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </Card>
          ))}
        </div>

        {measurements.length === 0 && !loading && (
          <div className="text-center py-8 text-gray-500">
            Измерения не найдены
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="p-6">
      <div className="mb-6">
        <h2 className="text-2xl font-bold mb-2">Медицинское оборудование</h2>
        <p className="text-gray-600">Управление медицинскими устройствами и измерениями</p>
      </div>

      <div className="mb-6">
        <div className="flex space-x-1 bg-gray-100 p-1 rounded-lg">
          <button
            onClick={() => setActiveTab('overview')}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === 'overview'
                ? 'bg-white text-blue-600 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            Обзор
          </button>
          <button
            onClick={() => setActiveTab('devices')}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === 'devices'
                ? 'bg-white text-blue-600 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            Устройства
          </button>
          <button
            onClick={() => setActiveTab('measurement')}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === 'measurement'
                ? 'bg-white text-blue-600 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            Измерение
          </button>
          <button
            onClick={() => setActiveTab('measurements')}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === 'measurements'
                ? 'bg-white text-blue-600 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            История
          </button>
        </div>
      </div>

      {activeTab === 'overview' && renderOverviewTab()}
      {activeTab === 'devices' && renderDevicesTab()}
      {activeTab === 'measurement' && renderMeasurementTab()}
      {activeTab === 'measurements' && renderMeasurementsTab()}

      {/* Модальное окно с подробностями устройства */}
      {selectedDevice && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto">
            <h3 className="text-lg font-semibold mb-4">Подробности устройства</h3>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
              <div className="space-y-3">
                <div><strong>Название:</strong> {selectedDevice.name}</div>
                <div><strong>Тип:</strong> {getDeviceTypeName(selectedDevice.device_type)}</div>
                <div><strong>Производитель:</strong> {selectedDevice.manufacturer}</div>
                <div><strong>Модель:</strong> {selectedDevice.model}</div>
                <div><strong>Серийный номер:</strong> {selectedDevice.serial_number}</div>
                <div><strong>Версия ПО:</strong> {selectedDevice.firmware_version}</div>
              </div>
              
              <div className="space-y-3">
                <div><strong>Статус:</strong> 
                  <Badge variant={getStatusBadgeVariant(selectedDevice.status)} className="ml-2">
                    {getStatusText(selectedDevice.status)}
                  </Badge>
                </div>
                <div><strong>Местоположение:</strong> {selectedDevice.location || 'Не указано'}</div>
                <div><strong>Тип подключения:</strong> {selectedDevice.connection_type}</div>
                {selectedDevice.last_seen && (
                  <div><strong>Последняя активность:</strong> {new Date(selectedDevice.last_seen).toLocaleString()}</div>
                )}
                {selectedDevice.calibration_date && (
                  <div><strong>Калибровка:</strong> {new Date(selectedDevice.calibration_date).toLocaleString()}</div>
                )}
              </div>
            </div>

            {selectedDevice.diagnostics && (
              <div className="mb-6">
                <h4 className="font-medium mb-2">Результаты диагностики</h4>
                <div className="space-y-2">
                  {Object.entries(selectedDevice.diagnostics.tests).map(([test, result]) => (
                    <div key={test} className="flex justify-between items-center p-2 bg-gray-50 rounded">
                      <span>{test}</span>
                      <Badge variant={result.passed ? 'success' : 'destructive'}>
                        {result.passed ? 'Пройден' : 'Ошибка'}
                      </Badge>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="flex gap-2">
              <Button
                onClick={() => runDiagnostics(selectedDevice.id)}
                disabled={selectedDevice.status !== 'online'}
              >
                <AlertTriangle className="w-4 h-4 mr-2" />
                Диагностика
              </Button>
              <Button
                onClick={() => calibrateDevice(selectedDevice.id)}
                disabled={selectedDevice.status !== 'online'}
                variant="outline"
              >
                <Wrench className="w-4 h-4 mr-2" />
                Калибровка
              </Button>
              <Button
                variant="outline"
                onClick={() => setSelectedDevice(null)}
              >
                Закрыть
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MedicalEquipmentManager;

