
import { useState, useEffect } from 'react';
import { api } from '../../api/client';
import logger from '../../utils/logger';
import { useTranslation } from '../../i18n/useTranslation';

interface NotificationChannelStatus {
  configured?: boolean;
  server?: string;
  port?: number | string;
  bot_token?: string;
  chat_id?: string;
  api_url?: string;
}

interface NotificationStatus {
  email?: NotificationChannelStatus;
  telegram?: NotificationChannelStatus;
  sms?: NotificationChannelStatus;
}

interface StatusCardDetail {
  label: string;
  value?: string | number | boolean;
}

interface StatusCardProps {
  title: string;
  configured?: boolean;
  details: StatusCardDetail[];
}

export default function NotificationSystemStatus() {
  const { t: rawT } = useTranslation(); const t = rawT;
    const [status, setStatus] = useState<NotificationStatus | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        loadStatus();
    }, []);

    async function loadStatus() {
        try {
            const response = await api.get('/notifications/notification-status');
            setStatus(response.data ?? response);
        } catch (err) {
            logger.error('Failed to load notification system status', err);
        } finally {
            setLoading(false);
        }
    }

    if (loading) return <div aria-busy="true">{t('misc.nss_zagruzka_statusa')}</div>;
    if (!status) return <div>{t('misc.nss_ne_udalos_zagruzit_status')}</div>;

    return (
        <div style={{ display: 'grid', gap: 16 }}>
            <StatusCard
                title="Email (SMTP)"
                configured={status.email?.configured}
                details={[
                    { label: t('misc.nss_server'), value: status.email?.server },
                    { label: t('misc.nss_port'), value: status.email?.port },
                ]}
            />
            <StatusCard
                title="Telegram Bot"
                configured={status.telegram?.configured}
                details={[
                    { label: 'Bot Token', value: status.telegram?.bot_token ? '******' : t('misc.nss_ne_zadan') },
                    { label: 'Chat ID', value: status.telegram?.chat_id },
                ]}
            />
            <StatusCard
                title="SMS Provider"
                configured={status.sms?.configured}
                details={[
                    { label: 'API URL', value: status.sms?.api_url },
                ]}
            />
        </div>
    );
}

function StatusCard({ title, configured, details }: StatusCardProps) {
    const { t: rawT } = useTranslation(); const t = rawT;
    return (
        <div style={{
            border: '1px solid var(--border-color)',
            borderRadius: 12,
            padding: 16,
            background: 'var(--bg-primary)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
        }}>
            <div>
                <h3 style={{ margin: '0 0 8px 0', fontSize: 16 }}>{title}</h3>
                <div style={{ fontSize: 13, opacity: 0.8 }}>
                    {details.map((d, i) => (
                        <div key={i}>{d.label}: {d.value || '—'}</div>
                    ))}
                </div>
            </div>
            <div>
                <span style={{
                    padding: '4px 12px',
                    borderRadius: 20,
                    background: configured ? 'var(--success-bg, #d1fae5)' : 'var(--danger-bg, #fee2e2)',
                    color: configured ? 'var(--success-text, #065f46)' : 'var(--danger-text, #991b1b)',
                    fontSize: 12,
                    fontWeight: 'var(--mac-font-weight-semibold)'
                }}>
                    {configured ? t('misc.nss_aktiven') : t('misc.nss_ne_nastroen')}
                </span>
            </div>
        </div>
    );
}

