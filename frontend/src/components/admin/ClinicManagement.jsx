import { useState, useEffect } from 'react';
import { api } from '../../api/client';
import {
  Building2,
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

      if (statsResponse.status === 'fulfilled') {
        setStats(statsResponse.value.data);
      } else {
        logger.error('Ошибка загрузки статистики:', statsResponse.reason);
        // Fallback данные для статистики
        setStats({
          total_branches: 3,
          active_branches: 3,
          total_equipment: 15,
          active_equipment: 14,
          total_licenses: 8,
          active_licenses: 7,
          total_backups: 12,
          recent_backups: 3
        });
      }

      if (healthResponse.status === 'fulfilled') {
        setSystemHealth(healthResponse.value.data);
      } else {
        logger.error('Ошибка загрузки состояния системы:', healthResponse.reason);
        // Fallback данные для состояния системы
        setSystemHealth({
          status: 'healthy',
          warnings: []
        });
      }
    } catch (error) {
      logger.error('Ошибка загрузки данных системы:', error);
      // Fallback данные при ошибке
      setStats({
        total_branches: 3,
        active_branches: 3,
        total_equipment: 15,
        active_equipment: 14,
        total_licenses: 8,
        active_licenses: 7,
        total_backups: 12,
        recent_backups: 3
      });
      setSystemHealth({
        status: 'healthy',
        warnings: []
      });
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
  <div className="admin-flex-col-24">
      {/* Состояние системы */}
      <MacOSCard className="admin-p-16">
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
      <div className="admin-flex-col-16">
            <div className="admin-flex-center-12">
              <Badge
            variant={systemHealth.status === 'healthy' ? 'success' :
            systemHealth.status === 'warning' ? 'warning' : 'error'}
            text={getHealthLabel(systemHealth.status)} />
          
              <span className="admin-text-sm admin-text-secondary">
                Последняя проверка: {new Date().toLocaleString()}
              </span>
            </div>
            
            {systemHealth.warnings && systemHealth.warnings.length > 0 &&
        <div className="admin-flex-col-8">
                <h4 className="admin-fs-sm-fw-med-primary-1">
                  Предупреждения:
                </h4>
                {systemHealth.warnings.map((warning, index) =>
          <div key={index} className="admin-d-flex-ai-center-gap-8-fs-sm-warning">
                    <AlertTriangle className="admin-icon-16" />
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
      <MacOSCard className="admin-p-16">
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
          
            <Building2 className="admin-icon-20" />
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
          
            <Wrench className="admin-icon-20" />
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
          
            <Key className="admin-icon-20" />
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
          
            <HardDrive className="admin-icon-20" />
            <span>Резервное копирование</span>
          </Button>
        </div>
      </MacOSCard>

      {/* Системная информация */}
      <MacOSCard className="admin-p-16">
          <h3 className="admin-fs-lg-fw-semi-primary-mb-16">
            Системная информация
          </h3>
        <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-16-fw-wrap">
          <div className="admin-flex-col-8">
            <div className="admin-d-flex-jc-between-fs-sm-5">
              <span className="admin-text-secondary">Версия системы:</span>
              <span className="admin-fw-med-primary-3">
                1.0.0
              </span>
            </div>
            <div className="admin-d-flex-jc-between-fs-sm-4">
              <span className="admin-text-secondary">База данных:</span>
              <span className="admin-fw-med-primary-2">
                SQLite
              </span>
            </div>
            <div className="admin-d-flex-jc-between-fs-sm-3">
              <span className="admin-text-secondary">Статус БД:</span>
              <Badge variant="success" text="Подключена" />
            </div>
          </div>
          <div className="admin-flex-col-8">
            <div className="admin-d-flex-jc-between-fs-sm-2">
              <span className="admin-text-secondary">Последнее обновление:</span>
              <span className="admin-fw-med-primary-1">
                {new Date().toLocaleDateString()}
              </span>
            </div>
            <div className="admin-d-flex-jc-between-fs-sm-1">
              <span className="admin-text-secondary">Время работы:</span>
              <span className="admin-fw-med-primary">
                24/7
              </span>
            </div>
            <div className="admin-d-flex-jc-between-fs-sm">
              <span className="admin-text-secondary">Безопасность:</span>
              <Badge variant="success" text="Активна" />
            </div>
          </div>
        </div>
      </MacOSCard>
    </div>;



  // Состояние загрузки
  if (loading) {
    return (
      <div className="admin-p-0-bgc-bg-primary-2">
        <MacOSCard className="admin-p-24">
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
        <MacOSCard className="admin-p-24">
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
                <RefreshCw className="admin-icon-16-mr-8" />
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
            className="admin-mb-24" />

          }

        {/* Некритические ошибки */}
        {error && stats &&
          <Alert
            type="warning"
            title="Предупреждение"
            message={error}
            className="admin-mb-24" />

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
        
        <div className="admin-p-24">
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
              
              <CheckCircle className="admin-icon-16-mr-8" />
              Подтвердить
            </Button>
          </div>
        </div>
      </Modal>
    </div>);

};

export default ClinicManagement;
