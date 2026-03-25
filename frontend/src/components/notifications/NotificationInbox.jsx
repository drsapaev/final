import { useMemo } from 'react';
import PropTypes from 'prop-types';
import { Bell, CheckCheck, ExternalLink } from 'lucide-react';
import { Button, Card, Badge } from '../ui/macos';
import { useNotifications } from '../../hooks/useNotifications';

const ROLE_RULES = {
  doctor: {
    domains: ['queue', 'lab', 'system'],
    keywords: ['diagnostic', 'результат', 'critical', 'критич', 'system']
  },
  registrar: {
    domains: ['appointment', 'queue', 'payment', 'system'],
    keywords: ['запис', 'очеред', 'price', 'system', 'alert']
  },
  lab: {
    domains: ['lab', 'queue', 'system'],
    keywords: ['lab', 'анализ', 'critical', 'отчет', 'report']
  },
  patient: {
    domains: ['appointment', 'lab', 'payment', 'system'],
    keywords: ['напомин', 'перенос', 'анализ', 'оплат', 'payment']
  }
};

function formatTimestamp(isoDate) {
  try {
    return new Date(isoDate).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  } catch {
    return isoDate;
  }
}

export default function NotificationInbox({ role, title = 'Уведомления' }) {
  const { notifications, unreadCount, markAsRead, markAllAsRead } = useNotifications();

  const filteredNotifications = useMemo(() => {
    const normalizedRole = String(role || '').toLowerCase();
    const rules = ROLE_RULES[normalizedRole];
    if (!rules) {
      return notifications;
    }

    return notifications.filter((item) => {
      if (rules.domains.includes(item.domain)) {
        return true;
      }
      const searchable = `${item.title} ${item.message}`.toLowerCase();
      return rules.keywords.some((keyword) => searchable.includes(keyword));
    });
  }, [notifications, role]);

  return (
    <Card style={{ padding: '16px', marginBottom: '16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Bell size={18} />
          <strong>{title}</strong>
          <Badge variant={unreadCount > 0 ? 'warning' : 'info'}>{unreadCount}</Badge>
        </div>
        <Button variant="ghost" size="sm" onClick={markAllAsRead}>
          <CheckCheck size={14} /> Прочитать все
        </Button>
      </div>

      <div style={{ display: 'grid', gap: '8px', maxHeight: '280px', overflowY: 'auto' }}>
        {filteredNotifications.length === 0 && (
          <div style={{ opacity: 0.7, fontSize: '14px' }}>Пока нет релевантных уведомлений.</div>
        )}

        {filteredNotifications.map((item) => (
          <div
            key={item.id}
            style={{
              border: '1px solid var(--mac-border)',
              borderRadius: '10px',
              padding: '10px',
              background: item.is_read ? 'var(--mac-bg-secondary)' : 'color-mix(in oklab, var(--mac-accent) 8%, var(--mac-bg-primary))'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px' }}>
              <strong style={{ fontSize: '14px' }}>{item.title}</strong>
              <Badge variant={item.is_read ? 'success' : 'warning'}>{item.domain}</Badge>
            </div>
            <div style={{ fontSize: '13px', marginTop: '4px', whiteSpace: 'pre-wrap' }}>{item.message}</div>
            <div style={{ marginTop: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <small style={{ opacity: 0.7 }}>{formatTimestamp(item.created_at)}</small>
              <div style={{ display: 'flex', gap: '6px' }}>
                {!item.is_read && (
                  <Button variant="outline" size="sm" onClick={() => markAsRead(item.id)}>
                    Прочитано
                  </Button>
                )}
                {item.action_url && (
                  <Button variant="ghost" size="sm" onClick={() => window.location.assign(item.action_url)}>
                    <ExternalLink size={12} /> Открыть
                  </Button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

NotificationInbox.propTypes = {
  role: PropTypes.string,
  title: PropTypes.string
};
