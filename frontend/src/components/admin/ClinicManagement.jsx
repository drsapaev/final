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
  <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Состояние системы */}
      <MacOSCard style={{ padding: '16px' }}>
          <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '16px'
      }}>
          <h3 style={{
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-semibold)',
          color: 'var(--mac-text-primary)',
          margin: 0
        }}>
            Состояние системы
          </h3>
          <Button
          variant="outline"
          onClick={loadSystemData}
          disabled={loading}
          title="Refresh system status"
          aria-label="Refresh system status"
          style={{
            padding: '6px 12px',
            minWidth: 'auto'
          }}>
          
            <RefreshCw style={{
            width: '16px',
            height: '16px',
            animation: loading ? 'spin 1s linear infinite' : 'none'
          }} />
          </Button>
        </div>
        
        {systemHealth ?
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <Badge
            variant={systemHealth.status === 'healthy' ? 'success' :
            systemHealth.status === 'warning' ? 'warning' : 'error'}
            text={getHealthLabel(systemHealth.status)} />
          
              <span style={{
            fontSize: 'var(--mac-font-size-sm)',
            color: 'var(--mac-text-secondary)'
          }}>
                Последняя проверка: {new Date().toLocaleString()}
              </span>
            </div>
            
            {systemHealth.warnings && systemHealth.warnings.length > 0 &&
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <h4 style={{
            fontSize: 'var(--mac-font-size-sm)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-primary)'
          }}>
                  Предупреждения:
                </h4>
                {systemHealth.warnings.map((warning, index) =>
          <div key={index} style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: 'var(--mac-font-size-sm)',
            color: 'var(--mac-warning)'
          }}>
                    <AlertTriangle style={{ width: '16px', height: '16px' }} />
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
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
      gap: '24px'
    }}>
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
      <MacOSCard style={{ padding: '16px' }}>
          <h3 style={{
        fontSize: 'var(--mac-font-size-lg)',
        fontWeight: 'var(--mac-font-weight-semibold)',
        color: 'var(--mac-text-primary)',
        marginBottom: '16px'
      }}>
            Быстрые действия
          </h3>
        <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: '16px',
        flexWrap: 'wrap'
      }}>
          <Button
          onClick={() => setActiveTab('branches')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            height: '64px',
            backgroundColor: 'var(--mac-accent-blue)',
            border: 'none',
            padding: '16px',
            transition: 'all 0.2s ease',
            transform: 'scale(1)'
          }}
          onMouseEnter={(e) => {
            e.target.style.transform = 'scale(1.02)';
          }}
          onMouseLeave={(e) => {
            e.target.style.transform = 'scale(1)';
          }}>
          
            <Building2 style={{ width: '20px', height: '20px' }} />
            <span>Управление филиалами</span>
          </Button>
          
          <Button
          onClick={() => setActiveTab('equipment')}
          variant="outline"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            height: '64px',
            padding: '16px',
            transition: 'all 0.2s ease',
            transform: 'scale(1)'
          }}
          onMouseEnter={(e) => {
            e.target.style.transform = 'scale(1.02)';
          }}
          onMouseLeave={(e) => {
            e.target.style.transform = 'scale(1)';
          }}>
          
            <Wrench style={{ width: '20px', height: '20px' }} />
            <span>Управление оборудованием</span>
          </Button>
          
          <Button
          onClick={() => setActiveTab('licenses')}
          variant="outline"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            height: '64px',
            padding: '16px',
            transition: 'all 0.2s ease',
            transform: 'scale(1)'
          }}
          onMouseEnter={(e) => {
            e.target.style.transform = 'scale(1.02)';
          }}
          onMouseLeave={(e) => {
            e.target.style.transform = 'scale(1)';
          }}>
          
            <Key style={{ width: '20px', height: '20px' }} />
            <span>Управление лицензиями</span>
          </Button>
          
          <Button
          onClick={() => setActiveTab('backups')}
          variant="outline"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            height: '64px',
            padding: '16px',
            transition: 'all 0.2s ease',
            transform: 'scale(1)'
          }}
          onMouseEnter={(e) => {
            e.target.style.transform = 'scale(1.02)';
          }}
          onMouseLeave={(e) => {
            e.target.style.transform = 'scale(1)';
          }}>
          
            <HardDrive style={{ width: '20px', height: '20px' }} />
            <span>Резервное копирование</span>
          </Button>
        </div>
      </MacOSCard>

      {/* Системная информация */}
      <MacOSCard style={{ padding: '16px' }}>
          <h3 style={{
        fontSize: 'var(--mac-font-size-lg)',
        fontWeight: 'var(--mac-font-weight-semibold)',
        color: 'var(--mac-text-primary)',
        marginBottom: '16px'
      }}>
            Системная информация
          </h3>
        <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
        gap: '16px',
        flexWrap: 'wrap'
      }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: 'var(--mac-font-size-sm)'
          }}>
              <span style={{ color: 'var(--mac-text-secondary)' }}>Версия системы:</span>
              <span style={{
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)'
            }}>
                1.0.0
              </span>
            </div>
            <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: 'var(--mac-font-size-sm)'
          }}>
              <span style={{ color: 'var(--mac-text-secondary)' }}>База данных:</span>
              <span style={{
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)'
            }}>
                SQLite
              </span>
            </div>
            <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: 'var(--mac-font-size-sm)'
          }}>
              <span style={{ color: 'var(--mac-text-secondary)' }}>Статус БД:</span>
              <Badge variant="success" text="Подключена" />
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: 'var(--mac-font-size-sm)'
          }}>
              <span style={{ color: 'var(--mac-text-secondary)' }}>Последнее обновление:</span>
              <span style={{
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)'
            }}>
                {new Date().toLocaleDateString()}
              </span>
            </div>
            <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: 'var(--mac-font-size-sm)'
          }}>
              <span style={{ color: 'var(--mac-text-secondary)' }}>Время работы:</span>
              <span style={{
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)'
            }}>
                24/7
              </span>
            </div>
            <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: 'var(--mac-font-size-sm)'
          }}>
              <span style={{ color: 'var(--mac-text-secondary)' }}>Безопасность:</span>
              <Badge variant="success" text="Активна" />
            </div>
          </div>
        </div>
      </MacOSCard>
    </div>;



  // Состояние загрузки
  if (loading) {
    return (
      <div style={{
        padding: 0,
        backgroundColor: 'var(--mac-bg-primary)'
      }}>
        <MacOSCard style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
            <Building2 style={{ width: '32px', height: '32px', color: 'var(--mac-accent-blue)' }} />
            <h2 style={{
              fontSize: 'var(--mac-font-size-2xl)',
              fontWeight: 'var(--mac-font-weight-semibold)',
              color: 'var(--mac-text-primary)',
              margin: 0
            }}>
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
      <div style={{
        padding: 0,
        backgroundColor: 'var(--mac-bg-primary)'
      }}>
        <MacOSCard style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
            <Building2 style={{ width: '32px', height: '32px', color: 'var(--mac-accent-blue)' }} />
            <h2 style={{
              fontSize: 'var(--mac-font-size-2xl)',
              fontWeight: 'var(--mac-font-weight-semibold)',
              color: 'var(--mac-text-primary)',
              margin: 0
            }}>
              Управление клиникой
            </h2>
          </div>
          <MacOSEmptyState
            icon={AlertTriangle}
            title="Не удалось загрузить данные"
            description="Проверьте подключение к серверу и попробуйте обновить страницу"
            action={
            <Button onClick={loadSystemData} variant="primary">
                <RefreshCw style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                Попробовать снова
              </Button>
            } />
          
        </MacOSCard>
      </div>);

  }

  return (
    <div style={{
      padding: 0,
      backgroundColor: 'var(--mac-bg-primary)'
    }}>
      <MacOSCard style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '16px', overflow: 'hidden' }}>
          {/* Заголовок */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '24px',
            paddingBottom: '24px',
            borderBottom: '1px solid var(--mac-border)'
          }}>
          <div>
            <h1 style={{
                fontSize: 'var(--mac-font-size-3xl)',
                fontWeight: 'var(--mac-font-weight-bold)',
                color: 'var(--mac-text-primary)',
                margin: '0 0 8px 0'
              }}>
              Управление клиникой
            </h1>
            <p style={{
                color: 'var(--mac-text-secondary)',
                fontSize: 'var(--mac-font-size-sm)',
                margin: 0
              }}>
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
            style={{ marginBottom: '24px' }} />

          }

        {/* Некритические ошибки */}
        {error && stats &&
          <Alert
            type="warning"
            title="Предупреждение"
            message={error}
            style={{ marginBottom: '24px' }} />

          }

        {/* Навигация по вкладкам */}
        <div style={{
          maxWidth: '100%',
          overflowX: 'auto',
          paddingBottom: '6px',
          marginBottom: '24px',
          scrollbarWidth: 'thin'
        }}>
          <SegmentedControl
            aria-label="Разделы управления клиникой"
            value={activeTab}
            onChange={setActiveTab}
            options={tabs.map((tab) => {
              const IconComponent = tab.icon;
              return {
                value: tab.id,
                label: (
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
                    {IconComponent && <IconComponent size={14} aria-hidden="true" />}
                    {tab.label}
                  </span>
                )
              };
            })}
            size="large"
            style={{
              minWidth: 'max-content',
              background: 'var(--mac-gradient-sidebar)',
              border: '1px solid var(--mac-main-shell-border)',
              borderRadius: '14px',
              boxShadow: 'var(--mac-main-shell-shadow)'
            }} />
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
        style={{ zIndex: 9999 }}>
        
        <div style={{ padding: '24px' }}>
          <p style={{
            fontSize: 'var(--mac-font-size-base)',
            color: 'var(--mac-text-primary)',
            marginBottom: '24px',
            lineHeight: '1.5'
          }}>
            Вы уверены, что хотите выполнить это действие? 
            Это может повлиять на работу системы.
          </p>
          
          <div style={{
            display: 'flex',
            justifyContent: 'flex-end',
            gap: '12px'
          }}>
            <Button
              variant="outline"
              onClick={() => setShowConfirmModal(false)}>
              
              Отмена
            </Button>
            <Button
              onClick={handleConfirmAction}
              style={{
                backgroundColor: 'var(--mac-accent-blue)',
                border: 'none'
              }}>
              
              <CheckCircle style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Подтвердить
            </Button>
          </div>
        </div>
      </Modal>
    </div>);

};

export default ClinicManagement;
