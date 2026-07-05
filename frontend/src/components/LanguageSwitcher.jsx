/**
 * Language Switcher Component
 * Компактный переключатель языка для хедера
 */
import { useState, useRef, useEffect } from 'react';
import { useTranslation } from '../hooks/useTranslation';
import {
  Button, Icon,
} from './ui/macos';
import PropTypes from 'prop-types';

const LanguageSwitcher = ({ compact = false }) => {
    const { language, setLanguage, availableLanguages, t } = useTranslation();
    const [isOpen, setIsOpen] = useState(false);
    const menuRef = useRef(null);

    const currentLang = availableLanguages.find(l => l.code === language) || availableLanguages[0];

    // Закрытие меню при клике вне
    useEffect(() => {
        const handleClickOutside = (e) => {
            if (menuRef.current && !menuRef.current.contains(e.target)) {
                setIsOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const handleSelect = (code) => {
        setLanguage(code);
        setIsOpen(false);
    };

    return (
        <div ref={menuRef} style={{ position: 'relative', display: 'inline-block' }}>
            <Button
                variant="ghost"
                size="small"
                onClick={() => setIsOpen(!isOpen)}
                title={t('common.language')}
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--mac-spacing-2)',
                    padding: compact ? '4px 8px' : '6px 12px',
                }}
            >
                <span style={{ fontSize: 'var(--mac-font-size-lg)' }}>{currentLang.flag}</span>
                {!compact && <span>{currentLang.code.toUpperCase()}</span>}
                <Icon name="chevron.down" size="small" />
            </Button>

            {isOpen && (
                <div
                    style={{
                        position: 'absolute',
                        top: '100%',
                        right: 0,
                        marginTop: 'var(--mac-spacing-1)',
                        backgroundColor: 'var(--mac-bg-secondary)',
                        borderRadius: 'var(--mac-radius-md)',
                        boxShadow: 'var(--mac-shadow-lg)',
                        border: '1px solid var(--mac-border)',
                        overflow: 'hidden',
                        zIndex: 1000,
                        minWidth: '150px',
                    }}
                >
                    {availableLanguages.map((lang) => (
                        <button
                            key={lang.code}
                            onClick={() => handleSelect(lang.code)}
                            style={{
                                width: '100%',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '10px',
                                padding: '10px 14px',
                                border: 'none',
                                background: language === lang.code
                                    ? 'var(--mac-accent-blue)'
                                    : 'transparent',
                                color: language === lang.code
                                    ? 'white'
                                    : 'var(--mac-text-primary)',
                                cursor: 'pointer',
                                textAlign: 'left',
                                fontSize: 'var(--mac-font-size-base)',
                                transition: 'background 0.15s',
                            }}
                            onMouseEnter={(e) => {
                                if (language !== lang.code) {
                                    e.target.style.background = 'var(--mac-bg-tertiary)';
                                }
                            }}
                            onMouseLeave={(e) => {
                                if (language !== lang.code) {
                                    e.target.style.background = 'transparent';
                                }
                            }}
                        >
                            <span style={{ fontSize: 'var(--mac-font-size-xl)' }}>{lang.flag}</span>
                            <span>{lang.nativeName || lang.name}</span>
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
};


LanguageSwitcher.propTypes = {
  ...(LanguageSwitcher.propTypes || {}),
  compact: PropTypes.any,
};

export default LanguageSwitcher;
