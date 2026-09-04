/**
 * Language Switcher Component
 * Компактный переключатель языка для хедера
 *
 * PR-UI-03b: rewritten for accessibility (P1 + P2 from Codex review):
 * - Dropdown rendered via ReactDOM.createPortal to bypass ancestor overflow:hidden
 * - Full ARIA pattern: role=listbox, role=option, aria-haspopup, aria-expanded, aria-selected
 * - Keyboard navigation: ArrowUp/Down, Home/End, Enter, Escape
 * - Focus management: focus moves to listbox on open, returns to trigger on close
 */
import { useState, useRef, useEffect, useCallback, type KeyboardEvent } from 'react';
import ReactDOM from 'react-dom';
import { useTranslation } from '../i18n/useTranslation';
import { Button } from './ui/macos';
import { AVAILABLE_LANGUAGES } from '../i18n/useTranslation';
import { ChevronDown } from 'lucide-react';

const LanguageSwitcher = ({ compact = false }: { compact?: boolean }) => {
    const { language, setLanguage, t: rawT } = useTranslation();
    const t = rawT;
    const [isOpen, setIsOpen] = useState(false);
    const [activeIndex, setActiveIndex] = useState(0);
    const triggerRef = useRef<HTMLButtonElement>(null);
    const listboxRef = useRef<HTMLDivElement>(null);
    const optionRefs = useRef<(HTMLButtonElement | null)[]>([]);

    const currentLang = AVAILABLE_LANGUAGES.find(l => l.code === language) || AVAILABLE_LANGUAGES[0];
    const currentIndex = AVAILABLE_LANGUAGES.findIndex(l => l.code === language);
    const listboxId = 'language-switcher-listbox';

    // Close menu when clicking outside
    useEffect(() => {
        if (!isOpen) return;
        const handleClickOutside = (e: MouseEvent) => {
            const target = e.target as Node;
            if (triggerRef.current?.contains(target)) return;
            if (listboxRef.current?.contains(target)) return;
            setIsOpen(false);
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [isOpen]);

    // Focus management: when menu opens, focus the current language option
    useEffect(() => {
        if (isOpen) {
            const idx = Math.max(0, currentIndex);
            setActiveIndex(idx);
            // Defer focus to allow DOM to render the portal
            requestAnimationFrame(() => {
                optionRefs.current[idx]?.focus();
            });
        } else {
            // PR-UI-03b (Codex P2): focus restoration on close is handled
            // directly in the Escape handler (triggerRef.current?.focus()
            // before setIsOpen(false)). The useEffect approach does not work
            // because the portal unmounts before this effect runs, making
            // listboxRef.current null. For click-outside close, focus is
            // already on document.body (user clicked elsewhere), so we do
            // not force it back to the trigger.
        }
    }, [isOpen, currentIndex]);

    const handleSelect = useCallback((code: string) => {
        setLanguage(code);
        setIsOpen(false);
    }, [setLanguage]);

    const handleTriggerKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
        if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
            e.preventDefault();
            setIsOpen(true);
        }
    };

    const handleOptionKeyDown = (e: KeyboardEvent<HTMLButtonElement>, index: number) => {
        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                { const next = (index + 1) % AVAILABLE_LANGUAGES.length;
                setActiveIndex(next);
                optionRefs.current[next]?.focus(); }
                break;
            case 'ArrowUp':
                e.preventDefault();
                { const prev = (index - 1 + AVAILABLE_LANGUAGES.length) % AVAILABLE_LANGUAGES.length;
                setActiveIndex(prev);
                optionRefs.current[prev]?.focus(); }
                break;
            case 'Home':
                e.preventDefault();
                setActiveIndex(0);
                optionRefs.current[0]?.focus();
                break;
            case 'End':
                e.preventDefault();
                { const last = AVAILABLE_LANGUAGES.length - 1;
                setActiveIndex(last);
                optionRefs.current[last]?.focus(); }
                break;
            case 'Enter':
            case ' ':
                e.preventDefault();
                handleSelect(AVAILABLE_LANGUAGES[index].code);
                break;
            case 'Escape':
                e.preventDefault();
                // PR-UI-03b (Codex P2): focus trigger BEFORE closing.
                // When isOpen becomes false, the portal unmounts and listboxRef
                // becomes null, so the useEffect cannot restore focus.
                triggerRef.current?.focus();
                setIsOpen(false);
                break;
            case 'Tab':
                setIsOpen(false);
                break;
        }
    };

    // Calculate dropdown position for portal
    const [dropdownPos, setDropdownPos] = useState<{ left: number; top: number } | null>(null);
    useEffect(() => {
        if (isOpen && triggerRef.current) {
            const rect = triggerRef.current.getBoundingClientRect();
            setDropdownPos({
                left: rect.right - 150, // 150 = minWidth of dropdown
                top: rect.bottom + 4,
            });
        } else {
            setDropdownPos(null);
        }
    }, [isOpen]);

    const triggerLabel = t('common.language') || 'Language';

    return (
        <div style={{ position: 'relative', display: 'inline-block' }}>
            <Button
                ref={triggerRef}
                variant="ghost"
                size="small"
                onClick={() => setIsOpen(!isOpen)}
                onKeyDown={handleTriggerKeyDown}
                title={triggerLabel}
                aria-label={triggerLabel}
                aria-haspopup="listbox"
                aria-expanded={isOpen}
                aria-controls={isOpen ? listboxId : undefined}
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--mac-spacing-2)',
                    padding: compact ? '4px 8px' : '6px 12px',
                    flex: '0 0 auto',
                }}
            >
                <span style={{ fontSize: 'var(--mac-font-size-lg)' }} aria-hidden="true">{currentLang.flag}</span>
                {!compact && <span>{currentLang.code.toUpperCase()}</span>}
                <ChevronDown size={16} aria-hidden="true" />
            </Button>

            {isOpen && dropdownPos && ReactDOM.createPortal(
                <div
                    ref={listboxRef}
                    id={listboxId}
                    role="listbox"
                    aria-label={triggerLabel}
                    style={{
                        position: 'fixed',
                        left: `${dropdownPos.left}px`,
                        top: `${dropdownPos.top}px`,
                        backgroundColor: 'var(--mac-bg-secondary)',
                        borderRadius: 'var(--mac-radius-md)',
                        boxShadow: 'var(--mac-shadow-lg)',
                        border: '1px solid var(--mac-border)',
                        overflow: 'hidden',
                        zIndex: 2147483647,
                        minWidth: '150px',
                        padding: '4px',
                    }}
                >
                    {AVAILABLE_LANGUAGES.map((lang, index) => {
                        const isSelected = language === lang.code;
                        const isActive = index === activeIndex;
                        return (
                            <button
                                key={lang.code}
                                ref={(el) => { optionRefs.current[index] = el; }}
                                role="option"
                                aria-selected={isSelected}
                                onClick={() => handleSelect(lang.code)}
                                onKeyDown={(e) => handleOptionKeyDown(e, index)}
                                style={{
                                    width: '100%',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '10px',
                                    padding: '8px 12px',
                                    border: 'none',
                                    background: isSelected
                                        ? 'var(--mac-accent-blue)'
                                        : isActive
                                            ? 'var(--mac-bg-tertiary)'
                                            : 'transparent',
                                    color: isSelected
                                        ? 'white'
                                        : 'var(--mac-text-primary)',
                                    cursor: 'pointer',
                                    textAlign: 'left',
                                    fontSize: 'var(--mac-font-size-base)',
                                    borderRadius: 'var(--mac-radius-sm)',
                                    transition: 'background 0.15s',
                                }}
                            >
                                <span style={{ fontSize: 'var(--mac-font-size-xl)' }} aria-hidden="true">{lang.flag}</span>
                                <span>{lang.name}</span>
                                {isSelected && (
                                    <span style={{ marginLeft: 'auto', fontSize: '10px' }} aria-hidden="true">✓</span>
                                )}
                            </button>
                        );
                    })}
                </div>,
                document.body
            )}
        </div>
    );
};

export default LanguageSwitcher;
