import React, { useState, useEffect } from 'react';
import { me } from '../api/client';
import HeaderNew from '../components/layout/HeaderNew.jsx';
import NotificationPreferences from '../components/settings/NotificationPreferences.jsx';
import TwoFactorManager from '../components/security/TwoFactorManager';
import logger from '../utils/logger';

export default function UserProfile() {
    const [user, setUser] = useState(null);
    const [activeTab, setActiveTab] = useState('notifications');

    useEffect(() => {
        loadUser();
    }, []);

    async function loadUser() {
        try {
            const data = await me();
            setUser(data);
        } catch (err) {
            logger.error('Failed to load user profile:', err);
        }
    }

    if (!user) return <div style={{ padding: 20 }}>Загрузка профиля...</div>;

    return (
        <div style={{
            maxWidth: 1000,
            margin: '0 auto',
            padding: '20px 0',
            width: '100%'
        }}>
            {/* Profile Header */}
            <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 20,
                marginBottom: 32,
                padding: '0 20px'
            }}>
                <div style={{
                    width: 80,
                    height: 80,
                    borderRadius: '50%',
                    background: 'var(--accent-color)',
                    color: 'white',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 32,
                    fontWeight: 'bold'
                }}>
                    {user.username?.[0]?.toUpperCase() || 'U'}
                </div>
                <div>
                    <h1 style={{ margin: '0 0 4px 0', fontSize: 24 }}>{user.full_name || user.username}</h1>
                    <div style={{ opacity: 0.7 }}>{user.role} • {user.email}</div>
                </div>
            </div>

            {/* Tabs */}
            <div style={{
                display: 'flex',
                gap: 4,
                padding: '0 20px',
                marginBottom: 24,
                borderBottom: '1px solid var(--border-color)'
            }}>
                <TabButton
                    active={activeTab === 'info'}
                    onClick={() => setActiveTab('info')}
                    label="Личные данные"
                />
                <TabButton
                    active={activeTab === 'notifications'}
                    onClick={() => setActiveTab('notifications')}
                    label="Уведомления"
                />
                <TabButton
                    active={activeTab === 'security'}
                    onClick={() => setActiveTab('security')}
                    label="Безопасность"
                />
            </div>

            {/* Content */}
            <div style={{ padding: '0 20px' }}>
                {activeTab === 'info' && (
                    <div style={cardStyle}>
                        <h3>Личная информация</h3>
                        <div style={{ opacity: 0.6 }}>
                            Редактирование профиля будет доступно в следующих обновлениях.
                        </div>
                    </div>
                )}

                {activeTab === 'notifications' && (
                    <NotificationPreferences />
                )}

                {activeTab === 'security' && (
                    <div style={{ display: 'grid', gap: 20 }}>
                        <div style={cardStyle}>
                            <h3>Двухфакторная аутентификация</h3>
                            <TwoFactorManager />
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

function TabButton({ active, onClick, label }) {
    return (
        <button
            onClick={onClick}
            style={{
                padding: '12px 16px',
                background: 'none',
                border: 'none',
                borderBottom: active ? '2px solid var(--accent-color)' : '2px solid transparent',
                color: active ? 'var(--text-primary)' : 'var(--text-secondary)',
                fontWeight: active ? 600 : 400,
                cursor: 'pointer',
                transition: 'all 0.2s'
            }}
        >
            {label}
        </button>
    );
}

const cardStyle = {
    background: 'var(--bg-secondary)',
    padding: 20,
    borderRadius: 12,
    border: '1px solid var(--border-color)',
};
