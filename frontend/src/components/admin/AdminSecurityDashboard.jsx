import { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';
import {
  Card, CardContent, CardHeader, CardTitle, Badge, Button, Icon, Alert, Input,
} from '../ui/macos';
import { api } from '../../api/client';
import { useTranslation } from '../../i18n/useTranslation';

/**
 * Admin Security Dashboard — M5.6 frontend integration.
 *
 * Shows: recent logins, downloads, exports, failed logins, suspicious IPs.
 * Also shows: compliance report, secrets rotation status, backup status.
 */
export default function AdminSecurityDashboard() {
  const { t } = useTranslation();
  const [dashboard, setDashboard] = useState(null);
  const [compliance, setCompliance] = useState(null);
  const [secrets, setSecrets] = useState(null);
  const [backup, setBackup] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('dashboard');

  const loadData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [dashRes, compRes, secRes, bakRes] = await Promise.allSettled([
        api.get('/admin/security/dashboard'),
        api.get('/admin/security/compliance/report'),
        api.get('/admin/security/secrets/status'),
        api.get('/admin/security/backup/status'),
      ]);
      if (dashRes.status === 'fulfilled') setDashboard(dashRes.value.data);
      if (compRes.status === 'fulfilled') setCompliance(compRes.value.data);
      if (secRes.status === 'fulfilled') setSecrets(secRes.value.data);
      if (bakRes.status === 'fulfilled') setBackup(bakRes.value.data);
    } catch (err) {
      setError('Не удалось загрузить данные безопасности');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const tabs = [
    { id: 'dashboard', label: 'Обзор', icon: 'chart.bar' },
    { id: 'compliance', label: 'Соответствие', icon: 'checkmark.shield' },
    { id: 'secrets', label: 'Секреты', icon: 'key' },
    { id: 'backup', label: 'Резервные копии', icon: 'cloud' },
  ];

  if (loading) {
    return (
      <Card variant="filled" padding="default">
        <CardContent>
          <Alert severity="info">Загрузка данных безопасности…</Alert>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card variant="filled" padding="default">
        <CardContent>
          <Alert severity="error">{error}</Alert>
          <Button variant="outline" onClick={loadData} style={{ marginTop: 12 }}>
            <Icon name="arrow.clockwise" size={16} />
            Повторить
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div style={{ display: 'grid', gap: 'var(--mac-spacing-4)' }}>
      {/* Tab bar */}
      <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            style={{
              padding: '8px 14px',
              border: '1px solid transparent',
              borderRadius: 'var(--mac-radius-md)',
              background: activeTab === tab.id ? 'var(--mac-bg-primary)' : 'transparent',
              color: activeTab === tab.id ? 'var(--mac-accent)' : 'var(--mac-text-secondary)',
              cursor: 'pointer',
              fontWeight: activeTab === tab.id ? 600 : 400,
            }}
          >
            <Icon name={tab.icon} size={14} />
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'dashboard' && dashboard && (
        <DashboardTab data={dashboard} />
      )}
      {activeTab === 'compliance' && compliance && (
        <ComplianceTab data={compliance} />
      )}
      {activeTab === 'secrets' && secrets && (
        <SecretsTab data={secrets} />
      )}
      {activeTab === 'backup' && backup && (
        <BackupTab data={backup} onVerify={loadData} />
      )}
    </div>
  );
}

function DashboardTab({ data }) {
  const { summary, recent_logins, failed_logins, suspicious_ips, recent_downloads, recent_exports } = data;
  return (
    <div style={{ display: 'grid', gap: 'var(--mac-spacing-4)' }}>
      {/* Summary cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
        <SummaryCard label="Всего событий" value={summary?.total_events || 0} />
        <SummaryCard label="Отказов доступа" value={summary?.total_denied || 0} variant="warning" />
        <SummaryCard label="Подозрительных IP" value={summary?.suspicious_ip_count || 0} variant="danger" />
      </div>

      {/* Failed logins */}
      {failed_logins && failed_logins.length > 0 && (
        <Card variant="filled" padding="none">
          <CardHeader style={{ background: 'var(--mac-bg-tertiary)', borderBottom: '1px solid var(--mac-border)', padding: '12px 16px' }}>
            <CardTitle style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Icon name="exclamationmark.triangle" size={18} />
              Неудачные входы ({failed_logins.length})
            </CardTitle>
          </CardHeader>
          <CardContent style={{ padding: '12px 16px' }}>
            {failed_logins.slice(0, 10).map((entry) => (
              <div key={entry.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--mac-border)' }}>
                <span>{entry.ip_address || 'N/A'} · {entry.actor_role || 'unknown'}</span>
                <span style={{ color: 'var(--mac-text-muted)', fontSize: '12px' }}>
                  {entry.timestamp ? new Date(entry.timestamp).toLocaleString('ru-RU') : ''}
                </span>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Suspicious IPs */}
      {suspicious_ips && suspicious_ips.length > 0 && (
        <Card variant="filled" padding="none">
          <CardHeader style={{ background: 'var(--mac-bg-tertiary)', borderBottom: '1px solid var(--mac-border)', padding: '12px 16px' }}>
            <CardTitle style={{ margin: 0 }}>Подозрительные IP-адреса</CardTitle>
          </CardHeader>
          <CardContent style={{ padding: '12px 16px' }}>
            {suspicious_ips.map((ip) => (
              <div key={ip.ip} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0' }}>
                <span>{ip.ip}</span>
                <Badge variant="danger">{ip.fail_count} отказов</Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Recent logins */}
      {recent_logins && recent_logins.length > 0 && (
        <Card variant="filled" padding="none">
          <CardHeader style={{ background: 'var(--mac-bg-tertiary)', borderBottom: '1px solid var(--mac-border)', padding: '12px 16px' }}>
            <CardTitle style={{ margin: 0 }}>Последние входы</CardTitle>
          </CardHeader>
          <CardContent style={{ padding: '12px 16px' }}>
            {recent_logins.slice(0, 10).map((entry) => (
              <div key={entry.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--mac-border)' }}>
                <span>{entry.actor_role || 'user'} · {entry.ip_address || 'N/A'}</span>
                <Badge variant={entry.outcome === 'success' ? 'success' : 'danger'}>
                  {entry.outcome}
                </Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function ComplianceTab({ data }) {
  return (
    <Card variant="filled" padding="default">
      <CardHeader>
        <CardTitle>Отчёт соответствия</CardTitle>
      </CardHeader>
      <CardContent>
        <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
          <Badge variant={data.summary?.failed === 0 ? 'success' : 'warning'}>
            {data.summary?.compliance_score || '0/0'}
          </Badge>
          <span style={{ color: 'var(--mac-text-secondary)' }}>
            {data.summary?.passed || 0} пройдено, {data.summary?.failed || 0} не пройдено
          </span>
        </div>
        {data.checks?.map((check) => (
          <div key={check.name} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0', borderBottom: '1px solid var(--mac-border)' }}>
            <Icon name={check.passed ? 'checkmark.circle.fill' : 'exclamationmark.triangle'} size={16} />
            <div>
              <div style={{ fontWeight: 500, color: 'var(--mac-text-primary)' }}>{check.label}</div>
              <div style={{ fontSize: '12px', color: 'var(--mac-text-muted)' }}>{check.details}</div>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function SecretsTab({ data }) {
  return (
    <Card variant="filled" padding="default">
      <CardHeader>
        <CardTitle>Статус секретов (ротация каждые {data.rotation_interval_days} дней)</CardTitle>
      </CardHeader>
      <CardContent>
        {Object.entries(data.secrets || {}).map(([name, status]) => (
          <div key={name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--mac-border)' }}>
            <div>
              <div style={{ fontWeight: 500 }}>{name}</div>
              <div style={{ fontSize: '12px', color: 'var(--mac-text-muted)' }}>
                {status.last_rotated ? `Ротация: ${new Date(status.last_rotated).toLocaleDateString('ru-RU')}` : 'Никогда не ротировался'}
                {status.days_since_rotation != null ? ` (${status.days_since_rotation} дн.)` : ''}
              </div>
            </div>
            <Badge variant={status.overdue ? 'danger' : 'success'}>
              {status.overdue ? 'Просрочен' : 'Актуален'}
            </Badge>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function BackupTab({ data, onVerify }) {
  const [verifying, setVerifying] = useState(false);
  const handleVerify = async () => {
    setVerifying(true);
    try {
      await api.post('/admin/security/backup/verify', { status: 'verified' });
      onVerify();
    } catch {
      // ignore
    } finally {
      setVerifying(false);
    }
  };

  return (
    <Card variant="filled" padding="default">
      <CardHeader>
        <CardTitle>Статус резервных копий</CardTitle>
      </CardHeader>
      <CardContent>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div>
            <div style={{ fontWeight: 500 }}>
              Последняя копия: {data.last_backup_at ? new Date(data.last_backup_at).toLocaleString('ru-RU') : 'никогда'}
            </div>
            <div style={{ fontSize: '12px', color: 'var(--mac-text-muted)' }}>
              {data.hours_since_last_backup != null ? `${data.hours_since_last_backup} ч. назад` : ''}
              {' · интервал: '}{data.expected_interval_hours} ч.
            </div>
          </div>
          <Badge variant={data.overdue ? 'danger' : 'success'}>
            {data.last_status === 'verified' ? 'Проверена' : data.last_status === 'failed' ? 'Ошибка' : 'Нет данных'}
          </Badge>
        </div>
        <Button variant="outline" onClick={handleVerify} loading={verifying}>
          <Icon name="checkmark.circle" size={16} />
          Отметить как проверенную
        </Button>
      </CardContent>
    </Card>
  );
}

function SummaryCard({ label, value, variant }) {
  const colors = {
    default: 'var(--mac-text-primary)',
    warning: 'var(--mac-warning, #f59e0b)',
    danger: 'var(--mac-danger, #ef4444)',
  };
  return (
    <div style={{
      padding: '12px 16px',
      borderRadius: 'var(--mac-radius-md)',
      border: '1px solid var(--mac-border)',
      background: 'var(--mac-bg-tertiary)',
    }}>
      <div style={{ fontSize: '12px', color: 'var(--mac-text-muted)' }}>{label}</div>
      <div style={{ fontSize: '24px', fontWeight: 600, color: colors[variant] || colors.default }}>
        {value}
      </div>
    </div>
  );
}

SummaryCard.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  variant: PropTypes.oneOf(['default', 'warning', 'danger']),
};
