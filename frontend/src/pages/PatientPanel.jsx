import { useEffect, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import { Card, Button, Badge, Icon } from '../components/ui/macos';
import { useBreakpoint } from '../hooks/useEnhancedMediaQuery';
import { Calendar, Bell } from 'lucide-react';
import RoleNotificationCenter from '../components/notifications/RoleNotificationCenter';
import { useNotificationCenter } from '../contexts/NotificationCenterContext';
import logger from '../utils/logger';

const Skeleton = ({ className = '' }) =>
  <div
    className={className}
    style={{
      background: 'linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%)',
      backgroundSize: '200% 100%',
      animation: 'shimmer 1.5s infinite',
      borderRadius: '8px',
      minHeight: '96px'
    }}
  />;

Skeleton.propTypes = {
  className: PropTypes.string
};

const PatientPanel = () => {
  void useBreakpoint();
  const [isLoading, setIsLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [appointments, setAppointments] = useState([]);

  const {
    loadNotifications,
    getNotificationsByRole,
    markAsRead,
    getUnreadCount
  } = useNotificationCenter();

  useEffect(() => {
    const load = async () => {
      setIsLoading(true);
      setAppointments([
        { id: 1, date: '2025-09-02', time: '09:30', doctor: 'Кардиолог', status: 'scheduled' },
        { id: 2, date: '2025-09-10', time: '10:00', doctor: 'Дерматолог', status: 'completed' }
      ]);

      try {
        await loadNotifications({ role: 'patient', limit: 50 });
      } catch (error) {
        logger.warn('[PatientPanel] Failed to load real notifications', error);
      } finally {
        setIsLoading(false);
      }
    };
    load();
  }, [loadNotifications]);

  const patientNotifications = useMemo(
    () => getNotificationsByRole('patient').filter((item) => !query || `${item.title} ${item.message}`.toLowerCase().includes(query.toLowerCase())),
    [getNotificationsByRole, query]
  );

  return (
    <div style={{
      padding: '0px',
      background: 'var(--mac-gradient-window)',
      minHeight: '100vh',
      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
      color: 'var(--mac-text-primary)'
    }}>

      <div style={{ maxWidth: '1200px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '24px' }}>

        <Card style={{
          backgroundColor: 'var(--mac-bg-primary)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-lg)',
          padding: '16px',
          boxShadow: 'var(--mac-shadow-sm)',
          backdropFilter: 'var(--mac-blur-light)',
          WebkitBackdropFilter: 'var(--mac-blur-light)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ position: 'relative', flex: 1 }}>
              <Icon
                name="magnifyingglass"
                size="small"
                style={{
                  position: 'absolute',
                  left: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: 'var(--mac-text-tertiary)'
                }}
              />

              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                style={{
                  width: '100%',
                  padding: '12px 12px 12px 40px',
                  border: '1px solid var(--mac-border)',
                  borderRadius: 'var(--mac-radius-md)',
                  backgroundColor: 'var(--mac-bg-secondary)',
                  color: 'var(--mac-text-primary)',
                  fontSize: 'var(--mac-font-size-base)',
                  fontFamily: 'inherit',
                  outline: 'none',
                  transition: 'border-color var(--mac-duration-normal) var(--mac-ease)'
                }}
                placeholder="Поиск по уведомлениям"
                onFocus={(e) => e.target.style.borderColor = 'var(--mac-accent-blue)'}
                onBlur={(e) => e.target.style.borderColor = 'var(--mac-border)'}
              />

            </div>
            <Button variant="primary">
              <Icon name="plus" size="small" />
              New Appointment
            </Button>
          </div>
        </Card>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card className="p-0 overflow-hidden">
            <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center gap-2">
              <Calendar className="w-4 h-4" />
              <h3 className="font-medium text-gray-900">Мои записи</h3>
            </div>
            <div className="p-4">
              {isLoading ? <Skeleton className="h-24" /> : (
                <div className="space-y-4">
                  {appointments.map((a) =>
                    <div key={a.id} className="p-4 border border-gray-200 rounded-lg flex items-center justify-between">
                      <div>
                        <div className="font-medium text-gray-900">{a.doctor}</div>
                        <div className="text-sm text-gray-500">{a.date} • {a.time}</div>
                      </div>
                      <Badge variant={a.status === 'scheduled' ? 'info' : 'success'}>
                        {a.status === 'scheduled' ? 'Запланировано' : 'Завершено'}
                      </Badge>
                    </div>
                  )}
                </div>
              )}
            </div>
          </Card>

          <Card className="p-0 overflow-hidden">
            <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center gap-2">
              <Bell className="w-4 h-4" />
              <h3 className="font-medium text-gray-900">Уведомления</h3>
              {getUnreadCount('patient') > 0 ? <Badge variant="error">{getUnreadCount('patient')}</Badge> : null}
            </div>
            <div className="p-4">
              {isLoading ? <Skeleton className="h-24" /> : (
                <div className="space-y-3">
                  {patientNotifications.length === 0 ? (
                    <div className="text-sm text-gray-500">Нет уведомлений.</div>
                  ) : patientNotifications.slice(0, 8).map((notification) => (
                    <button
                      type="button"
                      key={notification.id}
                      onClick={() => markAsRead(notification.id)}
                      className="w-full p-3 border border-gray-200 rounded-lg text-left"
                      style={{ background: notification.isRead ? 'var(--mac-bg-secondary)' : 'rgba(59,130,246,0.08)' }}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="font-medium text-gray-900">{notification.title}</div>
                        <Badge variant={notification.isRead ? 'success' : 'info'}>
                          {notification.isRead ? 'Read' : 'Unread'}
                        </Badge>
                      </div>
                      <div className="text-sm text-gray-600 mt-1">{notification.message}</div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>
      <RoleNotificationCenter role="patient" />
    </div>
  );
};

export default PatientPanel;
