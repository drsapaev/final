/**
 * EMRSmartFieldV2 - Text field with AI-powered suggestions
 * 
 * REPLACES old Ghost/MVP/Word modes with SAFE alternative:
 * - NO inline ghost text
 * - NO auto-insertion
 * - Suggestions shown NEXT TO the field (popover)
 * - Click to apply (through setField → reducer)
 * 
 * IDE-like behavior:
 * - Shows AI button when field has content
 * - Click AI button → show suggestion popover
 * - Keyboard: Tab to accept first suggestion
 * 
 * ⚠️ EXPERIMENTAL: Advanced Ghost Mode (Opt-in)
 * - Enables inline ghost text for rapid entry
 * - "AI draft – not yet committed" visual marker
 * - Explicit commit required (Tab/Enter)
 */

import { useState, useCallback, useMemo, useRef, useEffect } from 'react';
import { SmartAssistButton } from '../ai/SmartAssistButton';
import { AISuggestionPopover } from '../ai/AISuggestionPopover';
import './EMRSmartFieldV2.css';
import { Input } from '../../ui/macos';
import { useTranslation } from '@/i18n/useTranslation';

// === Domain types ===
export interface EMRSmartFieldV2Suggestion {
  id?: string | number;
  content?: string;
  text?: string;
  source?: string;
  confidence?: number;
  [key: string]: unknown;
}

export interface EMRSmartFieldV2Props {
  /** Current text value (controlled). */
  value?: string;
  /** Called whenever the user edits the field. Optional second arg for metadata. */
  onChange?: (value: string, options?: Record<string, unknown>) => void;
  /** Placeholder text. */
  placeholder?: string;
  /** When true, render a textarea instead of a single-line input. */
  multiline?: boolean;
  /** Rows for the textarea (ignored when multiline=false). */
  rows?: number;
  /** Read-only flag. */
  disabled?: boolean;
  /** Field id (used for scroll navigation and aria). */
  id?: string;
  /** Field name — passed to AI request handler to disambiguate which field. */
  fieldName?: string;
  /** AI suggestions to show in the popover. */
  suggestions?: EMRSmartFieldV2Suggestion[] | unknown[];
  /** Loading flag for AI requests. */
  aiLoading?: boolean;
  /** Apply a suggestion to the field. */
  onApplySuggestion?: (suggestion: unknown) => void;
  /** Dismiss a suggestion. */
  onDismissSuggestion?: (suggestion: unknown) => void;
  /** Request AI suggestions for the field. Receives field name or text. */
  onRequestAI?: (textOrFieldName: string) => void;
  /** Whether to show the AI assist button. */
  showAIButton?: boolean;
  /** Opt-in experimental inline ghost-text mode. */
  experimentalGhostMode?: boolean;
  /** Telemetry callback. */
  onTelemetry?: (payload: Record<string, unknown>) => void;
  /** Optional label (observed in DiagnosisSection caller). */
  label?: string;
  /** Optional required flag (observed in DiagnosisSection caller). */
  required?: boolean;
  /** Optional AI-disabled tooltip (observed in ExaminationSection caller). */
  aiDisabledTooltip?: string;
  [key: string]: unknown;
}

/**
 * EMRSmartFieldV2 Component
 *
 * @param {Object} props
 * @param {string} props.value - Current value
 * @param {Function} props.onChange - Change handler (value, metadata?)
 * @param {string} props.placeholder - Placeholder text
 * @param {boolean} props.multiline - Textarea or input
 * @param {number} props.rows - Rows for textarea
 * @param {boolean} props.disabled - Read-only
 * @param {string} props.id - Field ID (for scroll navigation)
 * @param {string} props.fieldName - Field name for AI
 * @param {Array} props.suggestions - AI suggestions for this field
 * @param {boolean} props.aiLoading - AI is loading
 * @param {Function} props.onApplySuggestion - Apply suggestion callback
 * @param {Function} props.onDismissSuggestion - Dismiss suggestion callback
 * @param {Function} props.onRequestAI - Request AI suggestions
 * @param {boolean} props.showAIButton - Show AI button
 * @param {boolean} props.experimentalGhostMode - Enable experimental ghost mode
 * @param {Function} props.onTelemetry - Telemetry callback (type, payload)
 */
export function EMRSmartFieldV2({
    value = '',
    onChange,
    placeholder = 'Начните ввод...',
    multiline = true,
    rows = 3,
    disabled = false,
    id,
    fieldName,
    suggestions = [],
    aiLoading = false,
    onApplySuggestion,
    onDismissSuggestion,
    onRequestAI,
    showAIButton = true,
    experimentalGhostMode = false,
    onTelemetry,
    // EMRSMART-FE-001 (audit 3886 round 27): label/required were declared
    // but never destructured — the editable field had no accessible name.
    label,
    required,
}: EMRSmartFieldV2Props) {
    const [isFocused, setIsFocused] = useState(false);
    const [showPopover, setShowPopover] = useState(false);
    const [ghostText, setGhostText] = useState('');
    // EMRAI-FE-003 (audit 3886 round 27): locally rejected suggestions and
    // the batch the user explicitly closed must not reappear on the next
    // render while the field stays focused.
    const [dismissedKeys, setDismissedKeys] = useState<string[]>([]);
    const closedAgainstRef = useRef<unknown[] | null>(null);
    const fieldRef = useRef<HTMLTextAreaElement | HTMLInputElement | null>(null);
    const containerRef = useRef<HTMLDivElement | null>(null);

    // Visible suggestions = current batch minus locally rejected ones
    const visibleSuggestions = useMemo(() => {
        const keyOf = (s: EMRSmartFieldV2Suggestion) =>
            (s.id !== undefined ? `id:${String(s.id)}` : `content:${String(s.content ?? s.text ?? '')}`);
        const list = suggestions as EMRSmartFieldV2Suggestion[];
        return list.filter(s => !dismissedKeys.includes(keyOf(s)));
    }, [suggestions, dismissedKeys]);

    // Has pending suggestions
    const hasSuggestions = visibleSuggestions.length > 0;

    // A brand-new batch resets per-batch dismissal state
    useEffect(() => {
        setDismissedKeys([]);
    }, [suggestions]);

    // Handle value change
    const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
        onChange?.(e.target.value);
    }, [onChange]);

    // Handle focus
    const handleFocus = useCallback(() => {
        setIsFocused(true);
    }, []);

    // Handle blur
    const handleBlur = useCallback(() => {
        setIsFocused(false);
        // Delay closing popover to allow click
        setTimeout(() => {
            if (!containerRef.current?.contains(document.activeElement)) {
                setShowPopover(false);
            }
        }, 200);
    }, []);

    // Handle AI button click
    const handleAIButtonClick = useCallback(() => {
        if (hasSuggestions) {
            setShowPopover(!showPopover);
        } else if (onRequestAI) {
            onRequestAI(fieldName as string);
        }
    }, [hasSuggestions, showPopover, onRequestAI, fieldName]);

    // Handle apply suggestion
    const handleApply = useCallback((suggestion: EMRSmartFieldV2Suggestion) => {
        // Merge strategy: append or replace based on current value
        let newValue: string;
        const content = String(suggestion.content ?? '');
        if (value.trim()) {
            if (experimentalGhostMode && content.startsWith(value)) {
                // If suggestion extends current value (completion), replace it
                newValue = content;
                onTelemetry?.({ type: 'ghost.accepted', payload: { suggestionId: suggestion.id, source: suggestion.source } });
            } else {
                // Append with newline
                newValue = `${value.trim()}\n${content}`;
            }
        } else {
            newValue = content;
        }

        onChange?.(newValue, {
            source: 'ai',
            suggestionId: suggestion.id,
            confidence: suggestion.confidence,
        });

        onApplySuggestion?.(suggestion);
        if (!experimentalGhostMode) {
            onTelemetry?.({ type: 'ai_popover.accepted', payload: { suggestionId: suggestion.id, source: suggestion.source } });
        }
        // EMRAI-FE-003: the applied batch is finished — do not auto-reopen it
        closedAgainstRef.current = suggestions;
        setShowPopover(false);
    }, [value, onChange, onApplySuggestion, experimentalGhostMode, onTelemetry, suggestions]);

    // Handle dismiss
    const handleDismiss = useCallback((suggestion: EMRSmartFieldV2Suggestion) => {
        const key = suggestion.id !== undefined
            ? `id:${String(suggestion.id)}`
            : `content:${String(suggestion.content ?? suggestion.text ?? '')}`;
        onTelemetry?.({ type: 'ai.dismissed', payload: { suggestionId: suggestion.id } });
        onDismissSuggestion?.(suggestion);
        // EMRAI-FE-003: remove the rejected suggestion locally so it
        // disappears immediately and cannot re-render while focused.
        setDismissedKeys(prev => [...prev, key]);
        const remaining = visibleSuggestions.filter(s => {
            const k = s.id !== undefined ? `id:${String(s.id)}` : `content:${String(s.content ?? s.text ?? '')}`;
            return k !== key;
        }).length;
        if (remaining === 0) {
            closedAgainstRef.current = suggestions;
            setShowPopover(false);
        }
    }, [onDismissSuggestion, onTelemetry, visibleSuggestions, suggestions]);

    // EMRAI-FE-003: explicit user close (header ×, Esc, click outside) —
    // remember WHICH batch was closed so the auto-open effect does not
    // resurrect the same suggestions on the next render. A fresh batch or
    // an explicit AI-button click still reopens.
    const handlePopoverClose = useCallback(() => {
        closedAgainstRef.current = suggestions;
        setShowPopover(false);
    }, [suggestions]);

    // Show popover when suggestions arrive and field is focused
    useEffect(() => {
        if (hasSuggestions && isFocused) {
            if (!showPopover && !experimentalGhostMode) {
                // Auto-show popover when new suggestions arrive (standard mode).
                // EMRAI-FE-003: never resurrect the batch the user explicitly
                // closed or finished applying.
                if (closedAgainstRef.current !== suggestions) {
                    setShowPopover(true);
                }
            }

            // Ghost Text Logic
            const firstSuggestion = visibleSuggestions[0] as EMRSmartFieldV2Suggestion | undefined;
            if (experimentalGhostMode && firstSuggestion?.content && value) {
                const topSuggestion = String(firstSuggestion.content);
                if (topSuggestion.startsWith(value) && topSuggestion.length > value.length) {
                    setGhostText(topSuggestion.substring(value.length));
                } else {
                    setGhostText('');
                }
            } else {
                setGhostText('');
            }
        } else {
            setGhostText('');
        }
    }, [hasSuggestions, isFocused, showPopover, experimentalGhostMode, suggestions, visibleSuggestions, value]);

    // Keyboard: Tab to accept first suggestion
    useEffect(() => {
        if (!showPopover || visibleSuggestions.length === 0) return;

        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Tab' && !e.shiftKey && document.activeElement === fieldRef.current) {
                e.preventDefault();
                const first = visibleSuggestions[0] as EMRSmartFieldV2Suggestion;
                handleApply(first);
            }
        };

        document.addEventListener('keydown', handleKeyDown);
        return () => document.removeEventListener('keydown', handleKeyDown);
    }, [showPopover, visibleSuggestions, handleApply]);

    const InputComponent = multiline ? 'textarea' : 'input';

    return (
        <div
            ref={containerRef}
            className={`emr-smart-field-v2 ${isFocused ? 'emr-smart-field-v2--focused' : ''} ${disabled ? 'emr-smart-field-v2--disabled' : ''}`}
        >
            {/* Field */}
            <div className="emr-smart-field-v2__input-wrapper">
                <InputComponent
                    ref={fieldRef as unknown as never}
                    id={id}
                    className="emr-smart-field-v2__input"
                    value={value}
                    onChange={handleChange}
                    onFocus={handleFocus}
                    onBlur={handleBlur}
                    placeholder={placeholder}
                    disabled={disabled}
                    rows={multiline ? rows : undefined}
                    aria-label={label || undefined}
                    aria-required={required ? true : undefined}
                />

                {/* Ghost Text Overlay */}
                {experimentalGhostMode && ghostText && isFocused && (
                    <div className="emr-smart-field-v2__ghost-overlay">
                        <span className="emr-smart-field-v2__ghost-invisible">{value}</span>
                        <span className="emr-smart-field-v2__ghost-text">{ghostText}</span>
                        <span className="emr-smart-field-v2__ghost-marker">AI draft – not yet committed</span>
                    </div>
                )}

                {/* AI Button */}
                {showAIButton && !disabled && (
                    <div className="emr-smart-field-v2__ai-btn">
                        <SmartAssistButton
                            onClick={handleAIButtonClick}
                            isLoading={aiLoading}
                            hasSuggestions={hasSuggestions}
                            disabled={disabled}
                            size="small"
                        />
                    </div>
                )}
            </div>

            {/* Suggestion Popover */}
            {showPopover && (
                <AISuggestionPopover
                    suggestions={visibleSuggestions as unknown as never[]}
                    onApply={handleApply}
                    onDismiss={handleDismiss}
                    disabled={disabled}
                    isOpen={showPopover}
                    onClose={handlePopoverClose}
                    position="bottom"
                    anchorRef={containerRef}
                />
            )}

            {/* Hint when focused with suggestions */}
            {hasSuggestions && isFocused && !showPopover && (
                <div className="emr-smart-field-v2__hint">
                    ✨ Есть AI подсказки — нажмите 🧠
                </div>
            )}
        </div>
    );
}



export default EMRSmartFieldV2;
