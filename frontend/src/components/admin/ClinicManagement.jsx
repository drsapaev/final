import { useState, useEffect } from 'react';
import { api } from '../../api/client';
import {
  Building2,
  Layers,
  Wrench,
  Key,
  HardDrive,
  Settings,
  BarChart3,
  AlertTriangle,
  CheckCircle,
  RefreshCw,
  Activity } from



'lucide-react';
import {
  MacOSCard,
  Button,
  SegmentedControl,
  MacOSStatCard,
  Skeleton,
  MacOSEmptyState,
  Alert,
  Badge,
  Modal,
} from '../ui/macos';
import BranchManagement from './BranchManagement';
import EquipmentManagement from './EquipmentManagement';
import LicenseManagement from './LicenseManagement';
import BackupManagement from './BackupManagement';
import DepartmentManagement from './DepartmentManagement';
import ClinicSettings from './ClinicSettings';

import logger from '../../utils/logger';
const ClinicManagement = () => {
  const [activeTab, setActiveTab] = useState('overview');
  const [systemHealth, setSystemHealth] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState({ type: '', text: '' });
  const [error] = useState(null);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [pendingAction, setPendingAction] = useState(null);

  const tabs = [
  { id: 'overview', label: 'Обзор', icon: BarChart3 },
  { id: 'branches', label: 'Филиалы', icon: Building2 },
  { id: 'departments', label: 'Отделения', icon: Layers },
  { id: 'equipment', label: 'Оборудование', icon: Wrench },
  { id: 'licenses', label: 'Лицензии', icon: Key },
  { id: 'backups', label: 'Резервные копии', icon: HardDrive },
  { id: 'settings', label: 'Настройки', icon: Settings }];


  useEffect(() => {
    loadSystemData();
  }, []);

  const loadSystemData = async () => {
    try {
      setLoading(true);

      // Загружаем статистику и состояние системы параллельно
      // Эти эндпоинты помечены как некритичные в interceptor, чтобы не перенаправлять на login
      const [statsResponse, healthResponse] = await Promise.allSettled([
      api.get('/clinic/stats').catch((err) => Promise.reject(err)),
      api.get('/clinic/health').catch((err) => Promise.reject(err))]
      );

      // P0 fix: removed hardcoded fake-stats fallback. On API failure, set null
      // so the existing <MacOSEmptyState title="Статистика недоступна" /> renders
      // instead of fabricated numbers (admin was seeing "3 branches, 8 licenses,
      // 12 backups" even when the backend was down).
      if (statsResponse.status === 'fulfilled') {
        setStats(statsResponse.value.data);
      } else {
        logger.error('Ошибка загрузки статистики:', statsResponse.reason);
        setStats(null);
      }

      if (healthResponse.status === 'fulfilled') {
        setSystemHealth(healthResponse.value.data);
      } else {
        logger.error('Ошибка загрузки состояния системы:', healthResponse.reason);
        setSystemHealth(null);
      }
    } catch (error) {
      logger.error('Ошибка загрузки данных системы:', error);
      setStats(null);
      setSystemHealth(null);
      setMessage({ type: 'error', text: 'Ошибка загрузки данных системы' });
    } finally {
      setLoading(false);
    }
  };










  const getHealthLabel = (status) => {
    switch (status) {
      case 'healthy':return 'Здорово';
      case 'warning':return 'Предупреждение';
      case 'critical':return 'Критично';
      default:return 'Неизвестно';
    }
  };

  const handleConfirmAction = () => {
    if (pendingAction) {
      pendingAction();
      setPendingAction(null);
    }
    setShowConfirmModal(false);
  };






  const renderOverview = () =>
  <div className="flex flex-col gap-6">
      {/* Состояние системы */}
      <MacOSCard className="p-4">
          <div className="admin-d-flex-ai-center-jc-between-mb-16">
          <h3 className="admin-fs-lg-fw-semi-primary-m-0-2">
            Состояние системы
          </h3>
          <Button
          variant="outline"
          onClick={loadSystemData}
          disabled={loading}
          title="Refresh system status"
          aria-label="Refresh system status"
          className="admin-p-6px-12px-minw-auto">
          
            <RefreshCw className="admin-w-16-h-16-anim-dyn" style={{ '--admin-anim0': loading ? 'spin 1s linear infinite' : 'none' }} />
          </Button>
        </div>
        
        {systemHealth ?
      <div className="flex flex-col gap-4">
            <div className="admin-flex-center-12">
              <Badge
            variant={systemHealth.status === 'healthy' ? 'success' :
            systemHealth.status === 'warning' ? 'warning' : 'error'}
            text={getHealthLabel(systemHealth.status)} />
          
              <span className="text-sm text-[var(--mac-text-secondary)]">
                Последняя проверка: {new Date().toLocaleString()}
              </span>
            </div>
            
            {systemHealth.warnings && systemHealth.warnings.length > 0 &&
        <div className="flex flex-col gap-2">
                <h4 className="admin-fs-sm-fw-med-primary-1">
                  Предупреждения:
                </h4>
                {systemHealth.warnings.map((warning, index) =>
          <div key={index} className="admin-d-flex-ai-center-gap-8-fs-sm-warning">
                    <AlertTriangle className="w-4 h-4" />
                    <span>{warning}</span>
                  </div>
          )}
              </div>
        }
          </div> :

      <MacOSEmptyState
        icon={Activity}
        title="Загрузка состояния системы"
        description="Получение данных о состоянии системы..." />

      }
      </MacOSCard>

      {/* Статистика */}
      {stats ?
    <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-24">
          <MacOSStatCard
        title="Филиалы"
        value={stats.total_branches}
        subtitle={`${stats.active_branches} активных`}
        icon={Building2}
        iconColor="var(--mac-accent-blue)"
        trend="positive" />
      

          <MacOSStatCard
        title="Оборудование"
        value={stats.total_equipment}
        subtitle={`${stats.active_equipment} активного`}
        icon={Wrench}
        iconColor="var(--mac-success)"
        trend="positive" />
      

          <MacOSStatCard
        title="Лицензии"
        value={stats.total_licenses}
        subtitle={`${stats.active_licenses} активных`}
        icon={Key}
        iconColor="var(--mac-warning)"
        trend="positive" />
      

          <MacOSStatCard
        title="Резервные копии"
        value={stats.total_backups}
        subtitle={`${stats.recent_backups} за неделю`}
        icon={HardDrive}
        iconColor="var(--mac-error)"
        trend="neutral" />
      
        </div> :

    <MacOSEmptyState
      icon={BarChart3}
      title="Статистика недоступна"
      description="Не удалось загрузить статистику системы" />

    }

      {/* Быстрые действия */}
      <MacOSCard className="p-4">
          <h3 className="admin-fs-lg-fw-semi-primary-mb-16-1">
            Быстрые действия
          </h3>
        <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-16-fw-wrap-1">
          <Button
          onClick={() => setActiveTab('branches')}
          className="admin-d-flex-ai-center-gap-8-h-64-bgc-blue-bd-none-p-16-tr-all-0-2s-ease-tf-scale-1"
          onMouseEnter={(e) => {
            e.target.style.transform = 'scale(1.02)';
          }}
          onMouseLeave={(e) => {
            e.target.style.transform = 'scale(1)';
          }}>
          
            <Building2 className="w-5 h-5" />
            <span>Управление филиалами</span>
          </Button>
          
          <Button
          onClick={() => setActiveTab('equipment')}
          variant="outline"
          className="admin-d-flex-ai-center-gap-8-h-64-p-16-tr-all-0-2s-ease-tf-scale-1-2"
          onMouseEnter={(e) => {
            e.target.style.transform = 'scale(1.02)';
          }}
          onMouseLeave={(e) => {
            e.target.style.transform = 'scale(1)';
          }}>
          
            <Wrench className="w-5 h-5" />
            <span>Управление оборудованием</span>
          </Button>
          
          <Button
          onClick={() => setActiveTab('licenses')}
          variant="outline"
          className="admin-d-flex-ai-center-gap-8-h-64-p-16-tr-all-0-2s-ease-tf-scale-1-1"
          onMouseEnter={(e) => {
            e.target.style.transform = 'scale(1.02)';
          }}
          onMouseLeave={(e) => {
            e.target.style.transform = 'scale(1)';
          }}>
          
            <Key className="w-5 h-5" />
            <span>Управление лицензиями</span>
          </Button>
          
          <Button
          onClick={() => setActiveTab('backups')}
          variant="outline"
          className="admin-d-flex-ai-center-gap-8-h-64-p-16-tr-all-0-2s-ease-tf-scale-1"
          onMouseEnter={(e) => {
            e.target.style.transform = 'scale(1.02)';
          }}
          onMouseLeave={(e) => {
            e.target.style.transform = 'scale(1)';
          }}>
          
            <HardDrive className="w-5 h-5" />
            <span>Резервное копирование</span>
          </Button>
        </div>
      </MacOSCard>

      {/* Системная информация */}
      {/* UX Audit Admin #2.5: динамические данные из systemHealth вместо hardcoded. */}
      <MacOSCard className="p-4">
          <h3 className="admin-fs-lg-fw-semi-primary-mb-16">
            Системная информация
          </h3>
        <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-16-fw-wrap">
          <div className="flex flex-col gap-2">
            <div className="admin-d-flex-jc-between-fs-sm-5">
              <span className="text-[var(--mac-text-secondary)]">Статус системы:</span>
              <Badge variant={systemHealth?.overall_status === 'healthy' ? 'success' : 'error'}
                text={systemHealth?.overall_status === 'healthy' ? 'Работает' : 'Ошибка'} />
            </div>
            <div className="admin-d-flex-jc-between-fs-sm-3">
              <span className="text-[var(--mac-text-secondary)]">Статус БД:</span>
              <Badge variant={systemHealth?.db === 'healthy' ? 'success' : 'error'}
                text={systemHealth?.db === 'healthy' ? 'Подключена' : 'Недоступна'} />
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <div className="admin-d-flex-jc-between-fs-sm-2">
              <span className="text-[var(--mac-text-secondary)]">Последнее обновление:</span>
              <span className="admin-fw-med-primary-1">
                {new Date().toLocaleDateString()}
              </span>
            </div>
            <div className="admin-d-flex-jc-between-fs-sm">
              <span className="text-[var(--mac-text-secondary)]">Безопасность:</span>
              <Badge variant={systemHealth?.security === 'active' ? 'success' : 'warning'}
                text={systemHealth?.security === 'active' ? 'Активна' : 'Проверьте настройки'} />
            </div>
          </div>
        </div>
      </MacOSCard>
    </div>;



  // Состояние загрузки
  if (loading) {
    return (
      <div className="admin-p-0-bgc-bg-primary-2">
        <MacOSCard className="p-6">
          <div className="admin-d-flex-ai-center-gap-12-mb-24-1">
            <Building2 className="admin-w-32-h-32-blue" />
            <h2 className="admin-fs-2xl-fw-semi-primary-m-0-1">
              Управление клиникой
            </h2>
          </div>
          <Skeleton height="600px" />
        </MacOSCard>
      </div>);

  }

  // Критическая ошибка загрузки
  if (error && !stats) {
    return (
      <div className="admin-p-0-bgc-bg-primary-1">
        <MacOSCard className="p-6">
          <div className="admin-d-flex-ai-center-gap-12-mb-24">
            <Building2 className="admin-w-32-h-32-blue" />
            <h2 className="admin-fs-2xl-fw-semi-primary-m-0">
              Управление клиникой
            </h2>
          </div>
          <MacOSEmptyState
            icon={AlertTriangle}
            title="Не удалось загрузить данные"
            description="Проверьте подключение к серверу и попробуйте обновить страницу"
            action={
            <Button onClick={loadSystemData} variant="primary">
                <RefreshCw className="w-4 h-4 mr-2" />
                Попробовать снова
              </Button>
            } />
          
        </MacOSCard>
      </div>);

  }

  return (
    <div className="admin-p-0-bgc-bg-primary">
      <MacOSCard className="admin-p-0-ov-hidden">
        <div className="admin-p-16-ov-hidden">
          {/* Заголовок */}
          <div className="admin-d-flex-jc-between-ai-center-mb-24-pb-24-bd-b-1px-solid-var-mac-bo">
          <div>
            <h1 className="admin-fs-var-mac-font-size-3x-fw-bold-primary-m-0-0-8px-0">
              Управление клиникой
            </h1>
            <p className="admin-secondary-fs-sm-m-0-2">
              Централизованное управление всеми аспектами клиники
            </p>
          </div>
        </div>

        {/* Сообщения */}
        {message.text &&
          <Alert
            type={message.type === 'success' ? 'success' : 'error'}
            title={message.type === 'success' ? 'Успешно' : 'Ошибка'}
            message={message.text}
            className="mb-6" />

          }

        {/* Некритические ошибки */}
        {error && stats &&
          <Alert
            type="warning"
            title="Предупреждение"
            message={error}
            className="mb-6" />

          }

        {/* Навигация по вкладкам */}
        <div className="admin-maxw-100pct-ovx-auto-pb-6-mb-24-scrollba-thin">
          <SegmentedControl
            aria-label="Разделы управления клиникой"
            value={activeTab}
            onChange={setActiveTab}
            options={tabs.map((tab) => {
              const IconComponent = tab.icon;
              return {
                value: tab.id,
                label: (
                  <span className="admin-d-inline-flex-ai-center-gap-8">
                    {IconComponent && <IconComponent size={14} aria-hidden="true" />}
                    {tab.label}
                  </span>
                )
              };
            })}
            size="large"
            className="admin-minw-max-content-bg-var-mac-gradient-sid-bd-1px-solid-var-mac-ma-radius-14-bsh-var-mac-main-shell-s" />
        </div>

        {/* Содержимое вкладок */}
        {activeTab === 'overview' && renderOverview()}
        {activeTab === 'branches' && <BranchManagement />}
        {activeTab === 'departments' && <DepartmentManagement />}
        {activeTab === 'equipment' && <EquipmentManagement />}
        {activeTab === 'licenses' && <LicenseManagement />}
        {activeTab === 'backups' && <BackupManagement />}
        {activeTab === 'settings' && <ClinicSettings />}
        </div>
      </MacOSCard>

      {/* Модальное окно подтверждения */}
      <Modal
        isOpen={showConfirmModal}
        onClose={() => setShowConfirmModal(false)}
        title="Подтверждение действия"
        size="sm"
        className="admin-z-9999">
        
        <div className="p-6">
          <p className="admin-fs-base-primary-mb-24-lh-1p5">
            Вы уверены, что хотите выполнить это действие? 
            Это может повлиять на работу системы.
          </p>
          
          <div className="admin-d-flex-jc-end-gap-12-2">
            <Button
              variant="outline"
              onClick={() => setShowConfirmModal(false)}>
              
              Отмена
            </Button>
            <Button
              onClick={handleConfirmAction}
              className="admin-bgc-blue-bd-none">
              
              <CheckCircle className="w-4 h-4 mr-2" />
              Подтвердить
            </Button>
          </div>
        </div>
      </Modal>
    </div>);

};

export default ClinicManagement;
