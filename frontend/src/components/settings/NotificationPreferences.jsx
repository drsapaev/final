import React, { useState, useEffect } from 'react';
import { api, me } from '../../api/client';
import logger from '../../utils/logger';

export default function NotificationPreferences() {
    const [loading, setLoading] = useState(true);
    const [settings, setSettings] = useState(null);
    const [userId, setUserId] = useState(null);
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        loadSettings();
    }, []);

    async function loadSettings() {
        try {
            setLoading(true);
            const user = await me();
            setUserId(user.id);

            const data = await api.get(`/notifications/settings/${user.id}`);
            setSettings(data);
        } catch (err) {
            logger.error('Failed to load notification settings:', err);
        } finally {
            setLoading(false);
        }
    }

    async function handleToggle(key) {
        if (!settings || !userId) return;

        const newSettings = { ...settings, [key]: !settings[key] };
        setSettings(newSettings); // Optimistic update

        try {
            setSaving(true);
            await api.put(`/notifications/settings/${userId}`, newSettings);
        } catch (err) {
            logger.error('Failed to save settings:', err);
            // Revert on error
            setSettings(settings);
            alert('Ошибка при сохранении настроек');
        } finally {
            setSaving(false);
        }
    }

    async function handleTimeChange(key, value) {
        if (!settings || !userId) return;
        const newSettings = { ...settings, [key]: value };
        setSettings(newSettings);

        // Debounce or save on blur could be better, but for now simple save
        try {
            setSaving(true);
            await api.put(`/notifications/settings/${userId}`, newSettings);
        } catch (err) {
            logger.error('Failed to save settings:', err);
        } finally {
            setSaving(false);
        }
    }

    if (loading) return <div style={{ opacity: 0.6 }}>Загрузка настроек...</div>;
    if (!settings) return <div style={{ color: 'red' }}>Не удалось загрузить настройки</div>;

    return (
        <div style={{ display: 'grid', gap: 24 }}>

            {/* Email Notifications */}
            <div style={sectionStyle}>
                <h3 style={headerStyle}>Email Уведомления</h3>
                <div style={gridStyle}>
                    <Toggle
                        label="Напоминания о записи"
                        checked={settings.email_appointment_reminder}
                        onChange={() => handleToggle('email_appointment_reminder')}
                    />
                    <Toggle
                        label="Подтверждение записи"
                        checked={settings.email_appointment_confirmation}
                        onChange={() => handleToggle('email_appointment_confirmation')}
                    />
                    <Toggle
                        label="Отмена записи"
                        checked={settings.email_appointment_cancellation}
                        onChange={() => handleToggle('email_appointment_cancellation')}
                    />
                    <Toggle
                        label="Чек об оплате"
                        checked={settings.email_payment_receipt}
                        onChange={() => handleToggle('email_payment_receipt')}
                    />
                    <Toggle
                        label="Системные обновления"
                        checked={settings.email_system_updates}
                        onChange={() => handleToggle('email_system_updates')}
                    />
                    <Toggle
                        label="Оповещения безопасности"
                        checked={settings.email_security_alerts}
                        onChange={() => handleToggle('email_security_alerts')}
                    />
                </div>
            </div>

            {/* SMS Notifications */}
            <div style={sectionStyle}>
                <h3 style={headerStyle}>SMS Уведомления</h3>
                <div style={gridStyle}>
                    <Toggle
                        label="Напоминания о записи"
                        checked={settings.sms_appointment_reminder}
                        onChange={() => handleToggle('sms_appointment_reminder')}
                    />
                    <Toggle
                        label="Экстренные оповещения"
                        checked={settings.sms_emergency}
                        onChange={() => handleToggle('sms_emergency')}
                    />
                </div>
                <div style={{ fontSize: '12px', opacity: 0.7, marginTop: 8 }}>
                    * SMS уведомления могут тарифицироваться отдельно
                </div>
            </div>

            {/* Push Notifications */}
            <div style={sectionStyle}>
                <h3 style={headerStyle}>Push Уведомления (Мобильное приложение)</h3>
                <div style={gridStyle}>
                    <Toggle
                        label="Напоминания о записи"
                        checked={settings.push_appointment_reminder}
                        onChange={() => handleToggle('push_appointment_reminder')}
                    />
                    <Toggle
                        label="Обновления очереди"
                        checked={settings.push_appointment_confirmation}
                        onChange={() => handleToggle('push_appointment_confirmation')}
                    />
                    <Toggle
                        label="Чек об оплате"
                        checked={settings.push_payment_receipt}
                        onChange={() => handleToggle('push_payment_receipt')}
                    />
                </div>
            </div>

            {/* General Settings */}
            <div style={sectionStyle}>
                <h3 style={headerStyle}>Общие настройки</h3>
                <div style={{ display: 'grid', gap: 12, maxWidth: 400 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <label>Время напоминания (минут до приема)</label>
                        <input
                            type="number"
                            value={settings.reminder_time_before || 60}
                            onChange={(e) => handleTimeChange('reminder_time_before', parseInt(e.target.value))}
                            style={inputStyle}
                            min="15"
                            step="15"
                        />
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <label>Тихие часы (Начало)</label>
                        <input
                            type="time"
                            value={settings.quiet_hours_start || ''}
                            onChange={(e) => handleTimeChange('quiet_hours_start', e.target.value)}
                            style={inputStyle}
                        />
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <label>Тихие часы (Конец)</label>
                        <input
                            type="time"
                            value={settings.quiet_hours_end || ''}
                            onChange={(e) => handleTimeChange('quiet_hours_end', e.target.value)}
                            style={inputStyle}
                        />
                    </div>
                    <Toggle
                        label="Уведомления в выходные"
                        checked={settings.weekend_notifications}
                        onChange={() => handleToggle('weekend_notifications')}
                    />
                </div>
            </div>

            {saving && <div style={{ position: 'fixed', bottom: 20, right: 20, background: 'rgba(0,0,0,0.7)', color: 'white', padding: '8px 16px', borderRadius: 20 }}>Сохранение...</div>}
        </div>
    );
}

function Toggle({ label, checked, onChange }) {
    return (
        <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', userSelect: 'none' }}>
            <div style={{
                width: 36,
                height: 20,
                background: checked ? 'var(--accent-color, #007aff)' : 'var(--mac-disabled, #ccc)',
                borderRadius: 20,
                position: 'relative',
                transition: 'background 0.2s',
            }}>
                <div style={{
                    width: 16,
                    height: 16,
                    background: 'white',
                    borderRadius: '50%',
                    position: 'absolute',
                    top: 2,
                    left: checked ? 18 : 2,
                    transition: 'left 0.2s',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.2)'
                }} />
            </div>
            <span>{label}</span>
        </label>
    );
}

const sectionStyle = {
    background: 'var(--bg-secondary)',
    padding: 16,
    borderRadius: 12,
    border: '1px solid var(--border-color)',
};

const headerStyle = {
    margin: '0 0 16px 0',
    fontSize: '16px',
    fontWeight: 600,
    opacity: 0.9
};

const gridStyle = {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
    gap: 16
};

const inputStyle = {
    padding: '6px 10px',
    borderRadius: 8,
    border: '1px solid var(--border-color)',
    background: 'var(--bg-primary)',
    color: 'var(--text-primary)',
    width: 100
};
