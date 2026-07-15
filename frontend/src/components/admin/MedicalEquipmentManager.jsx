import { useState, useEffect, useCallback } from 'react';
import {
  MacOSCard,
  Button,
  Badge,
  Input,
  Select,
  SegmentedControl,
  Skeleton,
  MacOSEmptyState,
} from '../ui/macos';
import {
  Activity,
  Wifi,
  WifiOff,
  AlertTriangle,
  Settings,


  Wrench,
  BarChart3,
  Download,
  History,
  RefreshCw,
  Stethoscope,
  Heart,
  Thermometer,
  Scale,
  Zap } from
'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../api/client';
import logger from '../../utils/logger';
import { useTranslation } from '../../i18n/useTranslation';

const MedicalEquipmentManager = () => {
  const { t } = useTranslation();
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
      const response = await api.get('/medical-equipment/devices');
      setDevices(response.data.devices || []);
    } catch (error) {
      // P0 fix: removed mock-device fallback. Was showing fabricated "Тонометр
      // Omron M3" / "Термометр Braun" devices on API failure — admin could act
      // on non-existent equipment. Now shows empty list (existing MacOSEmptyState
      // renders "Нет устройств").
      logger.error('Ошибка загрузки устройств:', error);
      setDevices([]);
    } finally {
      setLoading(false);
    }
  };

  const loadOverview = async () => {
    try {
      const response = await api.get('/medical-equipment/statistics/overview');
      setOverview(response.data.overview);
    } catch (error) {
      // P0 fix: removed mock-overview fallback. Was showing fabricated stats
      // (2 devices, 15 measurements) on API failure. Now zeroes — render uses
      // overview.* directly so null would crash; zero-defaults are safe.
      logger.error('Ошибка загрузки обзора:', error);
      setOverview({
        total_devices: 0,
        online_devices: 0,
        offline_devices: 0,
        total_measurements: 0,
        device_types: {}
      });
    }
  };

  const loadMeasurements = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (filters.device_type) params.device_type = filters.device_type;

      const response = await api.get('/medical-equipment/measurements', { params });
      setMeasurements(response.data.measurements || []);
    } catch (error) {
      // P0 fix: removed mock-measurements fallback. Was showing fabricated
      // blood-pressure/thermometer readings on API failure.
      logger.error('Ошибка загрузки измерений:', error);
      setMeasurements([]);
    } finally {
      setLoading(false);
    }
  }, [filters.device_type]);

  useEffect(() => {
    if (activeTab === 'measurements') {
      loadMeasurements();
    }
  }, [activeTab, loadMeasurements]);

  const connectDevice = async (deviceId) => {
    try {
      const response = await api.post(`/medical-equipment/devices/${deviceId}/connect`);
      const data = response.data;
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
      const response = await api.post(`/medical-equipment/devices/${deviceId}/disconnect`);
      const data = response.data;
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

    try {void (
      await api.post('/medical-equipment/measurements', measurementForm));
      toast.success('Измерение выполнено');
      setMeasurementForm({ device_id: '', patient_id: '' });
      if (activeTab === 'measurements') {
        loadMeasurements();
      }
    } catch (error) {
      logger.error('Ошибка измерения:', error);
      if (error.response && error.response.data) {
        toast.error(error.response.data.detail || 'Ошибка измерения');
      } else {
        toast.error('Ошибка измерения');
      }
    }
  };

  const calibrateDevice = async (deviceId) => {
    try {
      const response = await api.post(`/medical-equipment/devices/${deviceId}/calibrate`);
      const data = response.data;
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
      const response = await api.post(`/medical-equipment/devices/${deviceId}/diagnostics`);
      const data = response.data;
      setSelectedDevice({ ...selectedDevice, diagnostics: data });
      toast.success('Диагностика завершена');
    } catch (error) {
      logger.error('Ошибка диагностики:', error);
      toast.error('Ошибка диагностики');
    }
  };

  const getStatusBadgeVariant = (status) => {
    switch (status) {
      case 'online':return 'success';
      case 'busy':return 'warning';
      case 'offline':return 'secondary';
      case 'error':return 'destructive';
      case 'maintenance':return 'warning';
      case 'calibrating':return 'info';
      default:return 'secondary';
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'online':return 'В сети';
      case 'busy':return 'Занято';
      case 'offline':return 'Не в сети';
      case 'error':return 'Ошибка';
      case 'maintenance':return 'Обслуживание';
      case 'calibrating':return 'Калибровка';
      default:return status;
    }
  };

  const getDeviceIcon = (deviceType) => {
    switch (deviceType) {
      case 'blood_pressure':return Heart;
      case 'pulse_oximeter':return Activity;
      case 'glucometer':return Zap;
      case 'thermometer':return Thermometer;
      case 'scale':return Scale;
      case 'ecg':return Stethoscope;
      default:return Activity;
    }
  };

  const getDeviceTypeName = (deviceType) => {
    switch (deviceType) {
      case 'blood_pressure':return 'Тонометр';
      case 'pulse_oximeter':return 'Пульсоксиметр';
      case 'glucometer':return 'Глюкометр';
      case 'thermometer':return 'Термометр';
      case 'scale':return 'Весы';
      case 'ecg':return 'ЭКГ';
      case 'ultrasound':return 'УЗИ';
      case 'xray':return 'Рентген';
      case 'analyzer':return 'Анализатор';
      case 'spirometer':return 'Спирометр';
      case 'height_meter':return 'Ростомер';
      default:return deviceType;
    }
  };

  const filteredDevices = devices.filter((device) => {
    if (filters.device_type && device.device_type !== filters.device_type) return false;
    if (filters.status && device.status !== filters.status) return false;
    if (filters.location && !device.location.toLowerCase().includes(filters.location.toLowerCase())) return false;
    return true;
  });
  const hasDeviceFilters = Boolean(filters.device_type || filters.status || filters.location.trim());
  const devicesEmptyTitle = hasDeviceFilters ? 'Устройства по фильтрам не найдены' : 'Устройства ещё не добавлены';
  const devicesEmptyDescription = hasDeviceFilters ?
  'Измените тип, статус или расположение, чтобы увидеть другие устройства.' :
  'Добавьте первое медицинское устройство, чтобы отслеживать его статус и измерения.';

  const renderOverviewTab = () =>
  <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h3 className="admin-section-h3-m0">
          Обзор оборудования
        </h3>
        <Button
        onClick={() => {loadDevices();loadOverview();}}
        disabled={loading}
        className="flex items-center justify-center gap-2">
        
          <RefreshCw size={16} />
          {loading ? 'Загрузка...' : 'Обновить'}
        </Button>
      </div>

      {overview ?
    <div className="admin-grid-auto-200-mb-24">
          <MacOSCard className="p-0">
            <div className="admin-stat-number-accent-mb-8">
              {overview.total_devices}
            </div>
            <div className="admin-text-sm-secondary">
              Всего устройств
            </div>
          </MacOSCard>
          <MacOSCard className="p-0">
            <div className="admin-stat-number-success-mb-8">
              {overview.online_devices}
            </div>
            <div className="admin-text-sm-secondary">
              В сети
            </div>
          </MacOSCard>
          <MacOSCard className="p-0">
            <div className="admin-stat-number-error-mb-8">
              {overview.offline_devices}
            </div>
            <div className="admin-text-sm-secondary">
              Не в сети
            </div>
          </MacOSCard>
          <MacOSCard className="p-0">
            <div className="admin-stat-number-purple-mb-8">
              {overview.total_measurements}
            </div>
            <div className="admin-text-sm-secondary">
              Всего измерений
            </div>
          </MacOSCard>
        </div> :

    <Skeleton type="card" count={4} />
    }

      <div className="admin-grid-auto-300-24">
        <MacOSCard className="p-0">
          <h4 className="admin-rule-header mb-4">
            Статистика по типам устройств
          </h4>
          {overview?.device_types ?
        Object.entries(overview.device_types).map(([type, stats]) =>
        <div key={type} className="admin-stat-row-border">
                <span className="admin-text-sm-primary">
                  {getDeviceTypeName(type)}
                </span>
                <div className="flex items-center justify-center gap-2">
                  <Badge variant="outline">{stats.total}</Badge>
                  <Badge variant="success">{stats.online}</Badge>
                </div>
              </div>
        ) :

        <Skeleton type="text" count={3} />
        }
        </MacOSCard>

        <MacOSCard className="p-0">
          <h4 className="admin-rule-header mb-4">
            Быстрые действия
          </h4>
          <div className="flex flex-col gap-3">
            <Button
            onClick={() => setActiveTab('devices')}
            variant="outline"
            className="admin-btn-justify-start">
            
              <Settings size={16} className="mr-2" />
              Управление устройствами
            </Button>
            <Button
            onClick={() => setActiveTab('measurements')}
            variant="outline"
            className="admin-btn-justify-start">
            
              <BarChart3 size={16} className="mr-2" />
              Просмотр измерений
            </Button>
            <Button
            onClick={() => setActiveTab('measurement')}
            variant="outline"
            className="admin-btn-justify-start">
            
              <Activity size={16} className="mr-2" />
              Выполнить измерение
            </Button>
          </div>
        </MacOSCard>
      </div>
    </div>;


  const renderDevicesTab = () =>
  <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h3 className="admin-section-h3-m0">Устройства</h3>
        <Button onClick={loadDevices} disabled={loading}>
          <RefreshCw size={16} className="mr-2" />
          {loading ? 'Загрузка...' : 'Обновить'}
        </Button>
      </div>

      {/* Фильтры */}
      <MacOSCard className="p-0">
        <div className="admin-grid-auto-200">
          <div>
            <label htmlFor="device-type-filter" className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2">Тип устройства</label>
            <Select
            id="device-type-filter"
            value={filters.device_type}
            onChange={(value) => setFilters({ ...filters, device_type: value })}
            options={[
            { value: '', label: 'Все типы' },
            { value: 'blood_pressure', label: 'Тонометр' },
            { value: 'pulse_oximeter', label: 'Пульсоксиметр' },
            { value: 'glucometer', label: 'Глюкометр' },
            { value: 'thermometer', label: 'Термометр' },
            { value: 'scale', label: 'Весы' },
            { value: 'ecg', label: 'ЭКГ' }]
            }
            size="large" />
          
          </div>
          <div>
            <label htmlFor="status-filter" className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2">{t('common.status')}</label>
            <Select
            id="status-filter"
            value={filters.status}
            onChange={(value) => setFilters({ ...filters, status: value })}
            options={[
            { value: '', label: 'Все статусы' },
            { value: 'online', label: 'В сети' },
            { value: 'offline', label: 'Не в сети' },
            { value: 'error', label: 'Ошибка' },
            { value: 'busy', label: 'Занято' }]
            }
            size="large" />
          
          </div>
          <div>
            <label htmlFor="location-filter" className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2">Местоположение</label>
            <Input
            id="location-filter"
            value={filters.location}
            onChange={(e) => setFilters({ ...filters, location: e.target.value })}
            placeholder="Поиск по местоположению" />
          
          </div>
        </div>
      </MacOSCard>

      {/* Список устройств */}
      <div className="admin-grid-auto-300">
        {filteredDevices.map((device) => {
        const DeviceIcon = getDeviceIcon(device.device_type);
        return (
          <MacOSCard key={device.id} className="p-4">
              <div className="admin-flex-between-flex-start-mb-12">
                <div className="flex items-center justify-center gap-2">
                  <DeviceIcon size={20} className="admin-icon-blue" />
                  <div>
                    <h4 className="admin-device-h4">{device.name}</h4>
                    <p className="admin-setting-desc">{getDeviceTypeName(device.device_type)}</p>
                  </div>
                </div>
                <Badge variant={getStatusBadgeVariant(device.status)}>
                  {getStatusText(device.status)}
                </Badge>
              </div>

              <div className="admin-flex-col-8-sm mb-4">
                <div><strong>Производитель:</strong> {device.manufacturer}</div>
                <div><strong>Модель:</strong> {device.model}</div>
                <div><strong>Местоположение:</strong> {device.location || 'Не указано'}</div>
                <div><strong>Серийный номер:</strong> {device.serial_number}</div>
              </div>

              <div className="admin-flex-wrap-8">
                {device.status === 'offline' ?
              <Button
                size="sm"
                onClick={() => connectDevice(device.id)}
                className="flex items-center justify-center">
                
                    <Wifi size={16} className="mr-1" />
                    Подключить
                  </Button> :

              <Button
                size="sm"
                variant="outline"
                onClick={() => disconnectDevice(device.id)}
                className="flex items-center justify-center">
                
                    <WifiOff size={16} className="mr-1" />
                    Отключить
                  </Button>
              }

                <Button
                size="sm"
                variant="outline"
                onClick={() => calibrateDevice(device.id)}
                disabled={device.status !== 'online'}>
                
                  <Wrench size={16} className="mr-1" />
                  Калибровка
                </Button>

                <Button
                size="sm"
                variant="outline"
                onClick={() => setSelectedDevice(device)}>
                
                  <Settings size={16} className="mr-1" />
                  Подробнее
                </Button>
              </div>
            </MacOSCard>);

      })}
      </div>

      {filteredDevices.length === 0 && !loading &&
    <MacOSEmptyState
      icon={Stethoscope}
      title={devicesEmptyTitle}
      description={devicesEmptyDescription} />

    }
    </div>;


  const renderMeasurementTab = () =>
  <div className="flex flex-col gap-6">
      <h3 className="admin-section-h3-m0">Выполнить измерение</h3>

      <MacOSCard className="p-6">
        <div className="admin-grid-auto-300-24">
          <div className="flex flex-col gap-4">
            <div>
              <label htmlFor="measurement-device" className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2">Устройство</label>
              <Select
              id="measurement-device"
              value={measurementForm.device_id}
              onChange={(value) => setMeasurementForm({ ...measurementForm, device_id: value })}
              options={[
              { value: '', label: 'Выберите устройство' },
              ...devices.
              filter((d) => d.status === 'online').
              map((device) => ({
                value: String(device.id),
                label: `${device.name} (${getDeviceTypeName(device.device_type)})`
              }))]
              }
              size="large" />
            
            </div>

            <div>
              <label htmlFor="measurement-patient" className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2">ID пациента (опционально)</label>
              <Input
              id="measurement-patient"
              value={measurementForm.patient_id}
              onChange={(e) => setMeasurementForm({ ...measurementForm, patient_id: e.target.value })}
              placeholder="Введите ID пациента" />
            
            </div>

            <Button
            onClick={takeMeasurement}
            disabled={!measurementForm.device_id}
            className="w-full">
            
              <Activity size={16} className="mr-2" />
              Выполнить измерение
            </Button>
          </div>

          <div className="flex flex-col gap-4">
            <h4 className="admin-device-h4-base-med">Доступные устройства</h4>
            <div className="flex flex-col gap-2">
              {devices.
            filter((d) => d.status === 'online').
            map((device) => {
              const DeviceIcon = getDeviceIcon(device.device_type);
              return (
                <div key={device.id} className="admin-measurement-device-row">
                      <div className="flex items-center justify-center gap-2">
                        <DeviceIcon size={16} className="admin-icon-blue" />
                        <span className="admin-text-sm-primary">{device.name}</span>
                      </div>
                      <Badge variant="success">Готов</Badge>
                    </div>);

            })}
            </div>

            {devices.filter((d) => d.status === 'online').length === 0 &&
          <MacOSEmptyState
            icon={WifiOff}
            title="Нет доступных устройств"
            description="Все устройства находятся в офлайн режиме" />

          }
          </div>
        </div>
      </MacOSCard>
    </div>;


  const renderMeasurementsTab = () => {
    return (
      <div className="flex flex-col gap-6">
        <div className="flex items-center justify-between">
          <h3 className="admin-section-h3-m0">История измерений</h3>
          <div className="admin-flex-gap-8">
            <Button onClick={loadMeasurements} disabled={loading}>
              <RefreshCw size={16} className="mr-2" />
              Обновить
            </Button>
            <Button variant="outline">
              <Download size={16} className="mr-2" />
              Экспорт
            </Button>
          </div>
        </div>

        {/* Фильтры для измерений */}
        <MacOSCard className="p-0">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="measurements-device-type" className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2">Тип устройства</label>
              <Select
                id="measurements-device-type"
                value={filters.device_type}
                onChange={(value) => setFilters({ ...filters, device_type: value })}
                options={[
                { value: '', label: 'Все типы' },
                { value: 'blood_pressure', label: 'Тонометр' },
                { value: 'pulse_oximeter', label: 'Пульсоксиметр' },
                { value: 'glucometer', label: 'Глюкометр' },
                { value: 'thermometer', label: 'Термометр' },
                { value: 'scale', label: 'Весы' }]
                }
                size="large" />
              
            </div>
            <div className="admin-flex admin-flex-start-end">
              <Button onClick={loadMeasurements}>
                Применить фильтры
              </Button>
            </div>
          </div>
        </MacOSCard>

        {/* Список измерений */}
        <div className="flex flex-col gap-4">
          {measurements.map((measurement, index) =>
          <MacOSCard key={index} className="p-4">
              <div className="admin-flex-between-flex-start">
                <div className="admin-flex-1">
                  <div className="admin-flex-center-8-mb-8">
                    <Badge variant="outline">{getDeviceTypeName(measurement.device_type)}</Badge>
                    <span className="admin-text-sm-secondary">
                      {new Date(measurement.timestamp).toLocaleString()}
                    </span>
                    {measurement.quality_score &&
                  <Badge variant={measurement.quality_score > 0.8 ? 'success' : 'warning'}>
                        Качество: {Math.round(measurement.quality_score * 100)}%
                      </Badge>
                  }
                  </div>

                  <div className="admin-grid-auto-200">
                    <div>
                      <strong>Устройство:</strong> {measurement.device_id}
                    </div>
                    {measurement.patient_id &&
                  <div>
                        <strong>Пациент:</strong> {measurement.patient_id}
                      </div>
                  }
                    <div>
                      <strong>Данные:</strong>
                      <div className="text-sm admin-mt-4">
                        {measurement.measurements && Object.entries(measurement.measurements).map(([key, value]) =>
                      <div key={key}>
                            {key}: {typeof value === 'number' ? value.toFixed(1) : value}
                          </div>
                      )}
                        {!measurement.measurements &&
                      <div className="admin-italic-secondary">
                            Данные недоступны
                          </div>
                      }
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </MacOSCard>
          )}
        </div>

        {measurements.length === 0 && !loading &&
        <div className="text-center py-8 text-gray-500">
            Измерения не найдены
          </div>
        }
      </div>);

  };

  return (
    <div className="admin-p-0-max-1400">
      <div className="admin-page-header-flex-16-mb-24">
        <Stethoscope size={24} color="var(--mac-accent)" />
        <div>
          <h2 className="admin-page-title">
            Медицинское оборудование
          </h2>
          <p className="admin-page-subtitle">
            Управление медицинскими устройствами и измерениями
          </p>
        </div>
      </div>

      <div className="admin-tabs-scroll">
        <SegmentedControl
          aria-label="Разделы медицинского оборудования"
          value={activeTab}
          onChange={setActiveTab}
          options={[
            {
              value: 'overview',
              label: (
                <span className="admin-inline-flex-center-8">
                  <BarChart3 size={14} aria-hidden="true" />
                  Обзор
                </span>
              )
            },
            {
              value: 'devices',
              label: (
                <span className="admin-inline-flex-center-8">
                  <Stethoscope size={14} aria-hidden="true" />
                  Устройства
                </span>
              )
            },
            {
              value: 'measurement',
              label: (
                <span className="admin-inline-flex-center-8">
                  <Activity size={14} aria-hidden="true" />
                  Измерение
                </span>
              )
            },
            {
              value: 'measurements',
              label: (
                <span className="admin-inline-flex-center-8">
                  <History size={14} aria-hidden="true" />
                  История
                </span>
              )
            }
          ]}
          size="large"
          className="admin-tabs-segmented" />
      </div>

      {activeTab === 'overview' && renderOverviewTab()}
      {activeTab === 'devices' && renderDevicesTab()}
      {activeTab === 'measurement' && renderMeasurementTab()}
      {activeTab === 'measurements' && renderMeasurementsTab()}

      {/* Модальное окно с подробностями устройства */}
      {selectedDevice &&
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

              <div className="flex flex-col gap-3">
                <div className="flex items-center justify-center">
                  <strong>Статус:</strong>
                  <Badge variant={getStatusBadgeVariant(selectedDevice.status)} className="admin-ml-8">
                    {getStatusText(selectedDevice.status)}
                  </Badge>
                </div>
                <div><strong>Местоположение:</strong> {selectedDevice.location || 'Не указано'}</div>
                <div><strong>Тип подключения:</strong> {selectedDevice.connection_type}</div>
                {selectedDevice.last_seen &&
              <div><strong>Последняя активность:</strong> {new Date(selectedDevice.last_seen).toLocaleString()}</div>
              }
                {selectedDevice.calibration_date &&
              <div><strong>Калибровка:</strong> {new Date(selectedDevice.calibration_date).toLocaleString()}</div>
              }
              </div>
            </div>

            {selectedDevice.diagnostics &&
          <div className="mb-6">
                <h4 className="font-medium mb-2">Результаты диагностики</h4>
                <div className="space-y-2">
                  {Object.entries(selectedDevice.diagnostics.tests).map(([test, result]) =>
              <div key={test} className="flex justify-between items-center p-2 bg-gray-50 rounded">
                      <span>{test}</span>
                      <Badge variant={result.passed ? 'success' : 'destructive'}>
                        {result.passed ? 'Пройден' : 'Ошибка'}
                      </Badge>
                    </div>
              )}
                </div>
              </div>
          }

            <div className="admin-flex-gap-8">
              <Button
              onClick={() => runDiagnostics(selectedDevice.id)}
              disabled={selectedDevice.status !== 'online'}>
              
                <AlertTriangle size={16} className="mr-2" />
                Диагностика
              </Button>
              <Button
              onClick={() => calibrateDevice(selectedDevice.id)}
              disabled={selectedDevice.status !== 'online'}
              variant="outline">
              
                <Wrench size={16} className="mr-2" />
                Калибровка
              </Button>
              <Button
              variant="outline"
              onClick={() => setSelectedDevice(null)}>
              
                Закрыть
              </Button>
            </div>
          </div>
        </div>
      }
    </div>);

};

export default MedicalEquipmentManager;
