/**
 * IconSelector Component
 * Компонент для выбора иконки из набора lucide-react иконок
 */

import React, { useState } from 'react';
import {
    Heart,
    Activity,
    UserCheck,
    Smile,
    FlaskConical,
    Syringe,
    Calendar,
    Clock,
    AlertCircle,
    TrendingUp,
    Package,
    Stethoscope,
    TestTube,
    Scissors,
    FolderTree
} from 'lucide-react';

// Маппинг иконок (должен совпадать с ModernTabs.jsx)
export const iconMap = {
    Heart,
    Activity,
    UserCheck,
    Smile,
    FlaskConical,
    Syringe,
    Calendar,
    Clock,
    AlertCircle,
    TrendingUp,
    Package,
    Stethoscope,
    TestTube,
    Scissors,
    FolderTree
};

// Метаданные иконок для отображения
export const iconMetadata = [
    { name: 'Heart', label: 'Сердце', icon: Heart },
    { name: 'Activity', label: 'Активность', icon: Activity },
    { name: 'UserCheck', label: 'Пользователь', icon: UserCheck },
    { name: 'Smile', label: 'Улыбка', icon: Smile },
    { name: 'FlaskConical', label: 'Колба', icon: FlaskConical },
    { name: 'Syringe', label: 'Шприц', icon: Syringe },
    { name: 'Calendar', label: 'Календарь', icon: Calendar },
    { name: 'Clock', label: 'Часы', icon: Clock },
    { name: 'AlertCircle', label: 'Предупреждение', icon: AlertCircle },
    { name: 'TrendingUp', label: 'Тренд', icon: TrendingUp },
    { name: 'Package', label: 'Пакет', icon: Package },
    { name: 'Stethoscope', label: 'Стетоскоп', icon: Stethoscope },
    { name: 'TestTube', label: 'Пробирка', icon: TestTube },
    { name: 'Scissors', label: 'Ножницы', icon: Scissors },
    { name: 'FolderTree', label: 'Папка', icon: FolderTree }
];

const IconSelector = ({ value, onChange, label = 'Выберите иконку' }) => {
    const [isOpen, setIsOpen] = useState(false);
    const selectedIcon = iconMetadata.find(icon => icon.name === value);

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <label style={{
                fontSize: '14px',
                fontWeight: '500',
                color: 'var(--mac-text-primary)'
            }}>
                {label}
            </label>
            <div style={{ position: 'relative' }}>
                <button
                    type="button"
                    onClick={() => setIsOpen(!isOpen)}
                    style={{
                        width: '100%',
                        padding: '10px 12px',
                        border: '1px solid var(--mac-border)',
                        borderRadius: 'var(--mac-radius-md)',
                        background: 'var(--mac-bg-primary)',
                        color: 'var(--mac-text-primary)',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        gap: '8px'
                    }}
                >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        {selectedIcon ? (
                            <>
                                <selectedIcon.icon size={20} />
                                <span>{selectedIcon.label}</span>
                            </>
                        ) : (
                            <span style={{ color: 'var(--mac-text-secondary)' }}>Не выбрано</span>
                        )}
                    </div>
                    <span style={{ color: 'var(--mac-text-secondary)' }}>
                        {isOpen ? '▲' : '▼'}
                    </span>
                </button>

                {isOpen && (
                    <>
                        <div
                            style={{
                                position: 'fixed',
                                top: 0,
                                left: 0,
                                right: 0,
                                bottom: 0,
                                zIndex: 1000
                            }}
                            onClick={() => setIsOpen(false)}
                        />
                        <div style={{
                            position: 'absolute',
                            top: '100%',
                            left: 0,
                            right: 0,
                            zIndex: 1001,
                            marginTop: '4px',
                            background: 'var(--mac-bg-primary)',
                            border: '1px solid var(--mac-border)',
                            borderRadius: 'var(--mac-radius-md)',
                            boxShadow: 'var(--mac-shadow-lg)',
                            padding: '12px',
                            maxHeight: '300px',
                            overflowY: 'auto'
                        }}>
                            <div style={{
                                display: 'grid',
                                gridTemplateColumns: 'repeat(3, 1fr)',
                                gap: '8px'
                            }}>
                                {iconMetadata.map((iconMeta) => {
                                    const IconComponent = iconMeta.icon;
                                    const isSelected = value === iconMeta.name;
                                    return (
                                        <button
                                            key={iconMeta.name}
                                            type="button"
                                            onClick={() => {
                                                onChange(iconMeta.name);
                                                setIsOpen(false);
                                            }}
                                            style={{
                                                padding: '12px',
                                                border: isSelected
                                                    ? '2px solid var(--mac-primary)'
                                                    : '1px solid var(--mac-border)',
                                                borderRadius: 'var(--mac-radius-md)',
                                                background: isSelected
                                                    ? 'var(--mac-bg-secondary)'
                                                    : 'var(--mac-bg-primary)',
                                                cursor: 'pointer',
                                                display: 'flex',
                                                flexDirection: 'column',
                                                alignItems: 'center',
                                                gap: '6px',
                                                transition: 'all 0.2s'
                                            }}
                                            onMouseEnter={(e) => {
                                                if (!isSelected) {
                                                    e.currentTarget.style.background = 'var(--mac-bg-secondary)';
                                                    e.currentTarget.style.borderColor = 'var(--mac-primary)';
                                                }
                                            }}
                                            onMouseLeave={(e) => {
                                                if (!isSelected) {
                                                    e.currentTarget.style.background = 'var(--mac-bg-primary)';
                                                    e.currentTarget.style.borderColor = 'var(--mac-border)';
                                                }
                                            }}
                                        >
                                            <IconComponent size={24} />
                                            <span style={{
                                                fontSize: '11px',
                                                color: 'var(--mac-text-secondary)',
                                                textAlign: 'center'
                                            }}>
                                                {iconMeta.label}
                                            </span>
                                        </button>
                                    );
                                })}
                            </div>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
};

export default IconSelector;

