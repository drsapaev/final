import React, { useState, useEffect } from 'react';
import { 
  MacOSCard, 
  MacOSButton, 
  MacOSBadge, 
  MacOSInput, 
  MacOSSelect, 
  MacOSLoadingSkeleton,
  MacOSEmptyState,
  MacOSAlert
} from '../ui/macos';
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

import logger from '../../utils/logger';
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

  useEffect(() => {
    if (activeTab === 'measurements') {
      loadMeasurements();
    }
  }, [activeTab]);

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
        logger.error('Ошибка загрузки устройств:', response.status);
        // Fallback данные для демонстрации
        setDevices([
          {
            id: 1,
            name: 'Тонометр Omron M3',
            device_type: 'blood_pressure',
            manufacturer: 'Omron',
            model: 'M3',
            serial_number: 'OMR001',
            status: 'online',
            location: 'Кабинет 1'
          },
          {
            id: 2,
            name: 'Термометр Braun',
            device_type: 'thermometer',
            manufacturer: 'Braun',
            model: 'ThermoScan 7',
            serial_number: 'BRN002',
            status: 'offline',
            location: 'Кабинет 2'
          }
        ]);
      }
    } catch (error) {
      logger.error('Ошибка загрузки устройств:', error);
      // Fallback данные при ошибке сети
      setDevices([
        {
          id: 1,
          name: 'Тонометр Omron M3',
          device_type: 'blood_pressure',
          manufacturer: 'Omron',
          model: 'M3',
          serial_number: 'OMR001',
          status: 'online',
          location: 'Кабинет 1'
        },
        {
          id: 2,
          name: 'Термометр Braun',
          device_type: 'thermometer',
          manufacturer: 'Braun',
          model: 'ThermoScan 7',
          serial_number: 'BRN002',
          status: 'offline',
          location: 'Кабинет 2'
        }
      ]);
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
      } else {
        logger.error('Ошибка загрузки обзора:', response.status);
        // Fallback данные для обзора
        setOverview({
          total_devices: 2,
          online_devices: 1,
          offline_devices: 1,
          total_measurements: 15,
          device_types: {
            blood_pressure: 1,
            thermometer: 1
          }
        });
      }
    } catch (error) {
      logger.error('Ошибка загрузки обзора:', error);
      // Fallback данные при ошибке сети
      setOverview({
        total_devices: 2,
        online_devices: 1,
        offline_devices: 1,
        total_measurements: 15,
        device_types: {
          blood_pressure: 1,
          thermometer: 1
        }
      });
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
        logger.error('Ошибка загрузки измерений:', response.status);
        // Fallback данные для измерений
        setMeasurements([
          {
            id: 1,
            device_type: 'blood_pressure',
            patient_id: 'P001',
            systolic: 120,
            diastolic: 80,
            pulse: 72,
            timestamp: new Date().toISOString(),
            device_name: 'Тонометр Omron M3'
          },
          {
            id: 2,
            device_type: 'thermometer',
            patient_id: 'P002',
            temperature: 36.6,
            timestamp: new Date(Date.now() - 3600000).toISOString(),
            device_name: 'Термометр Braun'
          }
        ]);
      }
    } catch (error) {
      logger.error('Ошибка загрузки измерений:', error);
      // Fallback данные при ошибке сети
      setMeasurements([
        {
          id: 1,
          device_type: 'blood_pressure',
          patient_id: 'P001',
          systolic: 120,
          diastolic: 80,
          pulse: 72,
          timestamp: new Date().toISOString(),
          device_name: 'Тонометр Omron M3'
        },
        {
          id: 2,
          device_type: 'thermometer',
          patient_id: 'P002',
          temperature: 36.6,
          timestamp: new Date(Date.now() - 3600000).toISOString(),
          device_name: 'Термометр Braun'
        }
      ]);
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
      logger.error('Ошибка подключения устройства:', error);
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
      logger.error('Ошибка отключения устройства:', error);
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
      logger.error('Ошибка измерения:', error);
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
      logger.error('Ошибка калибровки:', error);
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
      logger.error('Ошибка диагностики:', error);
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center' 
      }}>
        <h3 style={{ 
          margin: 0,
          color: 'var(--mac-text-primary)',
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-semibold)'
        }}>
          Обзор оборудования
        </h3>
        <MacOSButton 
          onClick={() => { loadDevices(); loadOverview(); }} 
          disabled={loading}
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '8px' 
          }}
        >
          <RefreshCw size={16} />
          {loading ? 'Загрузка...' : 'Обновить'}
        </MacOSButton>
      </div>

      {overview ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '24px' }}>
          <MacOSCard style={{ padding: 0 }}>
            <div style={{ 
              fontSize: 'var(--mac-font-size-2xl)',
              fontWeight: 'var(--mac-font-weight-bold)',
              color: 'var(--mac-accent)',
              marginBottom: '8px'
            }}>
              {overview.total_devices}
            </div>
            <div style={{ 
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)'
            }}>
              Всего устройств
            </div>
          </MacOSCard>
          <MacOSCard style={{ padding: 0 }}>
            <div style={{ 
              fontSize: 'var(--mac-font-size-2xl)',
              fontWeight: 'var(--mac-font-weight-bold)',
              color: 'var(--mac-success)',
              marginBottom: '8px'
            }}>
              {overview.online_devices}
            </div>
            <div style={{ 
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)'
            }}>
              В сети
            </div>
          </MacOSCard>
          <MacOSCard style={{ padding: 0 }}>
            <div style={{ 
              fontSize: 'var(--mac-font-size-2xl)',
              fontWeight: 'var(--mac-font-weight-bold)',
              color: 'var(--mac-error)',
              marginBottom: '8px'
            }}>
              {overview.offline_devices}
            </div>
            <div style={{ 
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)'
            }}>
              Не в сети
            </div>
          </MacOSCard>
          <MacOSCard style={{ padding: 0 }}>
            <div style={{ 
              fontSize: 'var(--mac-font-size-2xl)',
              fontWeight: 'var(--mac-font-weight-bold)',
              color: 'var(--mac-purple)',
              marginBottom: '8px'
            }}>
              {overview.total_measurements}
            </div>
            <div style={{ 
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)'
            }}>
              Всего измерений
            </div>
          </MacOSCard>
        </div>
      ) : (
        <MacOSLoadingSkeleton type="card" count={4} />
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '24px' }}>
        <MacOSCard style={{ padding: 0 }}>
          <h4 style={{ 
            margin: '0 0 16px 0',
            color: 'var(--mac-text-primary)',
            fontSize: 'var(--mac-font-size-md)',
            fontWeight: 'var(--mac-font-weight-semibold)'
          }}>
            Статистика по типам устройств
          </h4>
          {overview?.device_types ? (
            Object.entries(overview.device_types).map(([type, stats]) => (
              <div key={type} style={{ 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'center',
                padding: '8px 0',
                borderBottom: '1px solid var(--mac-border)'
              }}>
                <span style={{ 
                  color: 'var(--mac-text-primary)',
                  fontSize: 'var(--mac-font-size-sm)'
                }}>
                  {getDeviceTypeName(type)}
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <MacOSBadge variant="outline">{stats.total}</MacOSBadge>
                  <MacOSBadge variant="success">{stats.online}</MacOSBadge>
                </div>
              </div>
            ))
          ) : (
            <MacOSLoadingSkeleton type="text" count={3} />
          )}
        </MacOSCard>

        <MacOSCard style={{ padding: 0 }}>
          <h4 style={{ 
            margin: '0 0 16px 0',
            color: 'var(--mac-text-primary)',
            fontSize: 'var(--mac-font-size-md)',
            fontWeight: 'var(--mac-font-weight-semibold)'
          }}>
            Быстрые действия
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <MacOSButton 
              onClick={() => setActiveTab('devices')} 
              variant="outline"
              style={{ justifyContent: 'flex-start' }}
            >
              <Settings size={16} style={{ marginRight: '8px' }} />
              Управление устройствами
            </MacOSButton>
            <MacOSButton 
              onClick={() => setActiveTab('measurements')} 
              variant="outline"
              style={{ justifyContent: 'flex-start' }}
            >
              <BarChart3 size={16} style={{ marginRight: '8px' }} />
              Просмотр измерений
            </MacOSButton>
            <MacOSButton 
              onClick={() => setActiveTab('measurement')} 
              variant="outline"
              style={{ justifyContent: 'flex-start' }}
            >
              <Activity size={16} style={{ marginRight: '8px' }} />
              Выполнить измерение
            </MacOSButton>
          </div>
        </MacOSCard>
      </div>
    </div>
  );

  const renderDevicesTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ 
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-semibold)',
          color: 'var(--mac-text-primary)',
          margin: 0
        }}>Устройства</h3>
        <MacOSButton onClick={loadDevices} disabled={loading}>
          <RefreshCw size={16} style={{ marginRight: '8px' }} />
          {loading ? 'Загрузка...' : 'Обновить'}
        </MacOSButton>
      </div>

      {/* Фильтры */}
      <MacOSCard style={{ padding: 0 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
          <div>
            <label htmlFor="device-type-filter" style={{ 
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              marginBottom: '8px'
            }}>Тип устройства</label>
            <MacOSSelect
              id="device-type-filter"
              value={filters.device_type}
              onChange={(e) => setFilters({ ...filters, device_type: e.target.value })}
              options={[
                { value: '', label: 'Все типы' },
                { value: 'blood_pressure', label: 'Тонометр' },
                { value: 'pulse_oximeter', label: 'Пульсоксиметр' },
                { value: 'glucometer', label: 'Глюкометр' },
                { value: 'thermometer', label: 'Термометр' },
                { value: 'scale', label: 'Весы' },
                { value: 'ecg', label: 'ЭКГ' }
              ]}
            />
          </div>
          <div>
            <label htmlFor="status-filter" style={{ 
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              marginBottom: '8px'
            }}>Статус</label>
            <MacOSSelect
              id="status-filter"
              value={filters.status}
              onChange={(e) => setFilters({ ...filters, status: e.target.value })}
              options={[
                { value: '', label: 'Все статусы' },
                { value: 'online', label: 'В сети' },
                { value: 'offline', label: 'Не в сети' },
                { value: 'error', label: 'Ошибка' },
                { value: 'busy', label: 'Занято' }
              ]}
            />
          </div>
          <div>
            <label htmlFor="location-filter" style={{ 
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              marginBottom: '8px'
            }}>Местоположение</label>
            <MacOSInput
              id="location-filter"
              value={filters.location}
              onChange={(e) => setFilters({ ...filters, location: e.target.value })}
              placeholder="Поиск по местоположению"
            />
          </div>
        </div>
      </MacOSCard>

      {/* Список устройств */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px' }}>
        {filteredDevices.map((device) => {
          const DeviceIcon = getDeviceIcon(device.device_type);
          return (
            <MacOSCard key={device.id} style={{ padding: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <DeviceIcon size={20} style={{ color: 'var(--mac-blue)' }} />
                  <div>
                    <h4 style={{ 
                      fontSize: 'var(--mac-font-size-base)',
                      fontWeight: 'var(--mac-font-weight-semibold)',
                      color: 'var(--mac-text-primary)',
                      margin: 0
                    }}>{device.name}</h4>
                    <p style={{ 
                      fontSize: 'var(--mac-font-size-sm)',
                      color: 'var(--mac-text-secondary)',
                      margin: 0
                    }}>{getDeviceTypeName(device.device_type)}</p>
                  </div>
                </div>
                <MacOSBadge variant={getStatusBadgeVariant(device.status)}>
                  {getStatusText(device.status)}
                </MacOSBadge>
              </div>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: 'var(--mac-font-size-sm)', marginBottom: '16px' }}>
                <div><strong>Производитель:</strong> {device.manufacturer}</div>
                <div><strong>Модель:</strong> {device.model}</div>
                <div><strong>Местоположение:</strong> {device.location || 'Не указано'}</div>
                <div><strong>Серийный номер:</strong> {device.serial_number}</div>
              </div>

              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                {device.status === 'offline' ? (
                  <MacOSButton
                    size="sm"
                    onClick={() => connectDevice(device.id)}
                    style={{ display: 'flex', alignItems: 'center' }}
                  >
                    <Wifi size={16} style={{ marginRight: '4px' }} />
                    Подключить
                  </MacOSButton>
                ) : (
                  <MacOSButton
                    size="sm"
                    variant="outline"
                    onClick={() => disconnectDevice(device.id)}
                    style={{ display: 'flex', alignItems: 'center' }}
                  >
                    <WifiOff size={16} style={{ marginRight: '4px' }} />
                    Отключить
                  </MacOSButton>
                )}
                
                <MacOSButton
                  size="sm"
                  variant="outline"
                  onClick={() => calibrateDevice(device.id)}
                  disabled={device.status !== 'online'}
                >
                  <Wrench size={16} style={{ marginRight: '4px' }} />
                  Калибровка
                </MacOSButton>
                
                <MacOSButton
                  size="sm"
                  variant="outline"
                  onClick={() => setSelectedDevice(device)}
                >
                  <Settings size={16} style={{ marginRight: '4px' }} />
                  Подробнее
                </MacOSButton>
              </div>
            </MacOSCard>
          );
        })}
      </div>

      {filteredDevices.length === 0 && !loading && (
        <MacOSEmptyState
          icon={Stethoscope}
          title="Устройства не найдены"
          description="Попробуйте изменить фильтры или добавить новое устройство"
        />
      )}
    </div>
  );

  const renderMeasurementTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <h3 style={{ 
        fontSize: 'var(--mac-font-size-lg)',
        fontWeight: 'var(--mac-font-weight-semibold)',
        color: 'var(--mac-text-primary)',
        margin: 0
      }}>Выполнить измерение</h3>
      
      <MacOSCard style={{ padding: '24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '24px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <label htmlFor="measurement-device" style={{ 
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '8px'
              }}>Устройство</label>
              <MacOSSelect
                id="measurement-device"
                value={measurementForm.device_id}
                onChange={(e) => setMeasurementForm({ ...measurementForm, device_id: e.target.value })}
                options={[
                  { value: '', label: 'Выберите устройство' },
                  ...devices
                    .filter(d => d.status === 'online')
                    .map(device => ({
                      value: device.id,
                      label: `${device.name} (${getDeviceTypeName(device.device_type)})`
                    }))
                ]}
              />
            </div>

            <div>
              <label htmlFor="measurement-patient" style={{ 
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '8px'
              }}>ID пациента (опционально)</label>
              <MacOSInput
                id="measurement-patient"
                value={measurementForm.patient_id}
                onChange={(e) => setMeasurementForm({ ...measurementForm, patient_id: e.target.value })}
                placeholder="Введите ID пациента"
              />
            </div>

            <MacOSButton 
              onClick={takeMeasurement}
              disabled={!measurementForm.device_id}
              style={{ width: '100%' }}
            >
              <Activity size={16} style={{ marginRight: '8px' }} />
              Выполнить измерение
            </MacOSButton>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <h4 style={{ 
              fontSize: 'var(--mac-font-size-base)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              margin: 0
            }}>Доступные устройства</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {devices
                .filter(d => d.status === 'online')
                .map(device => {
                  const DeviceIcon = getDeviceIcon(device.device_type);
                  return (
                    <div key={device.id} style={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      justifyContent: 'space-between', 
                      padding: '8px', 
                      border: '1px solid var(--mac-border)', 
                      borderRadius: 'var(--mac-border-radius)',
                      backgroundColor: 'var(--mac-background-secondary)'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <DeviceIcon size={16} style={{ color: 'var(--mac-blue)' }} />
                        <span style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-primary)' }}>{device.name}</span>
                      </div>
                      <MacOSBadge variant="success">Готов</MacOSBadge>
                    </div>
                  );
                })}
            </div>
            
            {devices.filter(d => d.status === 'online').length === 0 && (
              <MacOSEmptyState
                icon={WifiOff}
                title="Нет доступных устройств"
                description="Все устройства находятся в офлайн режиме"
              />
            )}
          </div>
        </div>
      </MacOSCard>
    </div>
  );

  const renderMeasurementsTab = () => {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ 
            fontSize: 'var(--mac-font-size-lg)',
            fontWeight: 'var(--mac-font-weight-semibold)',
            color: 'var(--mac-text-primary)',
            margin: 0
          }}>История измерений</h3>
          <div style={{ display: 'flex', gap: '8px' }}>
            <MacOSButton onClick={loadMeasurements} disabled={loading}>
              <RefreshCw size={16} style={{ marginRight: '8px' }} />
              Обновить
            </MacOSButton>
            <MacOSButton variant="outline">
              <Download size={16} style={{ marginRight: '8px' }} />
              Экспорт
            </MacOSButton>
          </div>
        </div>

        {/* Фильтры для измерений */}
        <MacOSCard style={{ padding: 0 }}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="measurements-device-type" style={{ 
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '8px'
              }}>Тип устройства</label>
              <MacOSSelect
                id="measurements-device-type"
                value={filters.device_type}
                onChange={(e) => setFilters({ ...filters, device_type: e.target.value })}
                options={[
                  { value: '', label: 'Все типы' },
                  { value: 'blood_pressure', label: 'Тонометр' },
                  { value: 'pulse_oximeter', label: 'Пульсоксиметр' },
                  { value: 'glucometer', label: 'Глюкометр' },
                  { value: 'thermometer', label: 'Термометр' },
                  { value: 'scale', label: 'Весы' }
                ]}
              />
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-end' }}>
              <MacOSButton onClick={loadMeasurements}>
                Применить фильтры
              </MacOSButton>
            </div>
          </div>
        </MacOSCard>

        {/* Список измерений */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {measurements.map((measurement, index) => (
            <MacOSCard key={index} style={{ padding: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                    <MacOSBadge variant="outline">{getDeviceTypeName(measurement.device_type)}</MacOSBadge>
                    <span style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>
                      {new Date(measurement.timestamp).toLocaleString()}
                    </span>
                    {measurement.quality_score && (
                      <MacOSBadge variant={measurement.quality_score > 0.8 ? 'success' : 'warning'}>
                        Качество: {Math.round(measurement.quality_score * 100)}%
                      </MacOSBadge>
                    )}
                  </div>
                  
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
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
                      <div style={{ fontSize: 'var(--mac-font-size-sm)', marginTop: '4px' }}>
                        {measurement.measurements && Object.entries(measurement.measurements).map(([key, value]) => (
                          <div key={key}>
                            {key}: {typeof value === 'number' ? value.toFixed(1) : value}
                          </div>
                        ))}
                        {!measurement.measurements && (
                          <div style={{ color: 'var(--mac-text-secondary)', fontStyle: 'italic' }}>
                            Данные недоступны
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </MacOSCard>
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
    <div style={{ padding: 0, maxWidth: '1400px', margin: '0 auto' }}>
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: '16px',
        marginBottom: '24px'
      }}>
        <Stethoscope size={24} color="var(--mac-accent)" />
        <div>
          <h2 style={{ 
            margin: 0, 
            color: 'var(--mac-text-primary)',
            fontSize: 'var(--mac-font-size-xl)',
            fontWeight: 'var(--mac-font-weight-bold)'
          }}>
            Медицинское оборудование
          </h2>
          <p style={{ 
            margin: '4px 0 0 0',
            color: 'var(--mac-text-secondary)',
            fontSize: 'var(--mac-font-size-sm)'
          }}>
            Управление медицинскими устройствами и измерениями
          </p>
        </div>
      </div>

      <div style={{ marginBottom: '24px' }}>
        <div style={{ 
          display: 'flex', 
          borderBottom: '1px solid var(--mac-border)'
        }}>
          <button
            onClick={() => setActiveTab('overview')}
            style={{
              padding: '16px 24px',
              border: 'none',
              background: 'none',
              cursor: 'pointer',
              borderBottom: activeTab === 'overview' ? '2px solid var(--mac-accent)' : '2px solid transparent',
              color: activeTab === 'overview' ? 'var(--mac-accent)' : 'var(--mac-text-secondary)',
              fontWeight: activeTab === 'overview' ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-normal)',
              fontSize: 'var(--mac-font-size-sm)',
              transition: 'all var(--mac-duration-normal) var(--mac-ease)'
            }}
          >
            Обзор
          </button>
          <button
            onClick={() => setActiveTab('devices')}
            style={{
              padding: '16px 24px',
              border: 'none',
              background: 'none',
              cursor: 'pointer',
              borderBottom: activeTab === 'devices' ? '2px solid var(--mac-accent)' : '2px solid transparent',
              color: activeTab === 'devices' ? 'var(--mac-accent)' : 'var(--mac-text-secondary)',
              fontWeight: activeTab === 'devices' ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-normal)',
              fontSize: 'var(--mac-font-size-sm)',
              transition: 'all var(--mac-duration-normal) var(--mac-ease)'
            }}
          >
            Устройства
          </button>
          <button
            onClick={() => setActiveTab('measurement')}
            style={{
              padding: '16px 24px',
              border: 'none',
              background: 'none',
              cursor: 'pointer',
              borderBottom: activeTab === 'measurement' ? '2px solid var(--mac-accent)' : '2px solid transparent',
              color: activeTab === 'measurement' ? 'var(--mac-accent)' : 'var(--mac-text-secondary)',
              fontWeight: activeTab === 'measurement' ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-normal)',
              fontSize: 'var(--mac-font-size-sm)',
              transition: 'all var(--mac-duration-normal) var(--mac-ease)'
            }}
          >
            Измерение
          </button>
          <button
            onClick={() => setActiveTab('measurements')}
            style={{
              padding: '16px 24px',
              border: 'none',
              background: 'none',
              cursor: 'pointer',
              borderBottom: activeTab === 'measurements' ? '2px solid var(--mac-accent)' : '2px solid transparent',
              color: activeTab === 'measurements' ? 'var(--mac-accent)' : 'var(--mac-text-secondary)',
              fontWeight: activeTab === 'measurements' ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-normal)',
              fontSize: 'var(--mac-font-size-sm)',
              transition: 'all var(--mac-duration-normal) var(--mac-ease)'
            }}
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
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  <strong>Статус:</strong> 
                  <MacOSBadge variant={getStatusBadgeVariant(selectedDevice.status)} style={{ marginLeft: '8px' }}>
                    {getStatusText(selectedDevice.status)}
                  </MacOSBadge>
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

            <div style={{ display: 'flex', gap: '8px' }}>
              <MacOSButton
                onClick={() => runDiagnostics(selectedDevice.id)}
                disabled={selectedDevice.status !== 'online'}
              >
                <AlertTriangle size={16} style={{ marginRight: '8px' }} />
                Диагностика
              </MacOSButton>
              <MacOSButton
                onClick={() => calibrateDevice(selectedDevice.id)}
                disabled={selectedDevice.status !== 'online'}
                variant="outline"
              >
                <Wrench size={16} style={{ marginRight: '8px' }} />
                Калибровка
              </MacOSButton>
              <MacOSButton
                variant="outline"
                onClick={() => setSelectedDevice(null)}
              >
                Закрыть
              </MacOSButton>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MedicalEquipmentManager;

