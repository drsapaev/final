import React, { useState, useEffect } from 'react';
import { api } from '../../api/client';

export default function NotificationSystemStatus() {
    const [status, setStatus] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        loadStatus();
    }, []);

    async function loadStatus() {
        try {
            const data = await api.get('/notifications/notification-status');
            setStatus(data);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    }

    if (loading) return <div>Загрузка статуса...</div>;
    if (!status) return <div>Не удалось загрузить статус</div>;

    return (
        <div style={{ display: 'grid', gap: 16 }}>
            <StatusCard
                title="Email (SMTP)"
                configured={status.email?.configured}
                details={[
                    { label: 'Сервер', value: status.email?.server },
                    { label: 'Порт', value: status.email?.port },
                ]}
            />
            <StatusCard
                title="Telegram Bot"
                configured={status.telegram?.configured}
                details={[
                    { label: 'Bot Token', value: status.telegram?.bot_token ? '******' : 'Не задан' },
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

function StatusCard({ title, configured, details }) {
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
                    fontWeight: 600
                }}>
                    {configured ? 'Активен' : 'Не настроен'}
                </span>
            </div>
        </div>
    );
}
