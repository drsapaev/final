/**
 * Language Switcher Component
 * Компактный переключатель языка для хедера
 */
import { useState, useRef, useEffect } from 'react';
import { useTranslation } from '../hooks/useTranslation';
import { Button, Icon } from './ui/macos';
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

    const [hoveredLang, setHoveredLang] = useState(null);

    // Escape key handling
    useEffect(() => {
        const handleKeyDown = (e) => {
            if (e.key === 'Escape' && isOpen) {
                setIsOpen(false);
            }
        };
        document.addEventListener('keydown', handleKeyDown);
        return () => document.removeEventListener('keydown', handleKeyDown);
    }, [isOpen]);

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
                aria-haspopup="menu"
                aria-expanded={isOpen}
                aria-label={t('common.language')}
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: compact ? '4px 8px' : '6px 12px',
                }}
            >
                <span style={{ fontSize: '16px' }} aria-hidden="true">{currentLang.flag}</span>
                {!compact && <span>{currentLang.code.toUpperCase()}</span>}
                <Icon name="chevron.down" size="small" />
            </Button>

            {isOpen && (
                <div
                    role="menu"
                    style={{
                        position: 'absolute',
                        top: '100%',
                        right: 0,
                        marginTop: '4px',
                        backgroundColor: 'var(--mac-bg-secondary)',
                        borderRadius: 'var(--mac-radius-md)',
                        boxShadow: 'var(--mac-shadow-lg)',
                        border: '1px solid var(--mac-border)',
                        overflow: 'hidden',
                        zIndex: 1000,
                        minWidth: '150px',
                    }}
                >
                    {availableLanguages.map((lang) => {
                        const isHovered = hoveredLang === lang.code;
                        const isSelected = language === lang.code;
                        return (
                            <button
                                key={lang.code}
                                role="menuitem"
                                onClick={() => handleSelect(lang.code)}
                                style={{
                                    width: '100%',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '10px',
                                    padding: '10px 14px',
                                    border: 'none',
                                    background: isSelected
                                        ? 'var(--mac-accent-blue)'
                                        : isHovered
                                            ? 'var(--mac-bg-tertiary)'
                                            : 'transparent',
                                    color: isSelected
                                        ? 'white'
                                        : 'var(--mac-text-primary)',
                                    cursor: 'pointer',
                                    textAlign: 'left',
                                    fontSize: '14px',
                                    transition: 'background 0.15s',
                                }}
                                onMouseEnter={() => setHoveredLang(lang.code)}
                                onMouseLeave={() => setHoveredLang(null)}
                                onFocus={() => setHoveredLang(lang.code)}
                                onBlur={() => setHoveredLang(null)}
                            >
                                <span style={{ fontSize: '18px' }} aria-hidden="true">{lang.flag}</span>
                                <span>{lang.nativeName || lang.name}</span>
                            </button>
                        );
                    })}
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
