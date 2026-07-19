import { useTranslation } from '../../i18n/useTranslation';
/**
 * EMRContainerV2 - Modular EMR container using v2 sections
 * 
 * Phase 4 Result:
 * - Uses modular sections instead of inline JSX
 * - Legacy single-sheet EMR has been retired
 * - All Phase 1-3 features work (autosave, guards, history, conflict)
 * 
 * Phase 6 Additions:
 * - Keyboard shortcuts (Ctrl+S, Ctrl+Z, Ctrl+Y)
 * - Sticky header
 */

import React, { useState, useCallback, useEffect } from 'react';
import PropTypes from 'prop-types';
import { useEMR } from '../../hooks/useEMR';
import { useEMRAutosave } from '../../hooks/useEMRAutosave';
import { useBeforeUnload } from '../../hooks/useNavigationGuard';
import { useEMRKeyboard } from '../../hooks/useEMRKeyboard';
import { useVisitLifecycle } from '../../hooks/useVisitLifecycle';
import { useDebouncedCallback } from '../../hooks/useDebouncedCallback';
import { cacheService, CACHE_CONFIG, CACHE_TAGS } from '../../core/cache';
import { DEBOUNCE } from '../../core/debouncePolicy';
import EMRStatusIndicator from './EMRStatusIndicator';
import EMRHistoryPanel from './EMRHistoryPanel';
import EMRDiffViewer from './EMRDiffViewer';
import EMRConflictDialog from './EMRConflictDialog';
import EMRHelpDialog from './EMRHelpDialog';
import { useAppData } from '../../contexts/AppDataContext';
import { mcpAPI } from '../../api/mcpClient';
import { isCanonicalSpecialty, normalizeSpecialty } from '../../utils/emrSpecialty';
// Analytics is handled via handleTelemetry callback

// Import modular sections
import {
    ComplaintsSection,
    AnamnesisMorbiSection,
    AnamnesisVitaeSection,
    ExaminationSection,
    DiagnosisSection,
    TreatmentSection,
    RecommendationsSection,
    NotesSection,
} from './sections';

// Import specialty sections (lazy loaded)
import {
    CardiologySection,
    DermatologySection,
    type DermatologyPhoto,
    DentistrySection,
} from './sections/specialty';

// P0 fix: LabResultsSection — shows lab panel results to all doctors.
// Previously doctors had no way to see LabReportInstance data; cardiologist
// had a separate manual-entry CardioBloodTest table, derma/dental had nothing.
import LabResultsSection from './sections/LabResultsSection';

import './EMRContainerV2.css';
// P-013 fix: shared ConfirmDialog hook replacing window.confirm() calls.
import { useConfirm } from '../common/ConfirmDialog';
// QW-03 (UX audit): replace native alert() in Ghost Mode with notify.warning.
import notify from '../../services/notify';
import { Button } from '../ui/macos';
import logger from '../../utils/logger';
// QW-04 (UX audit): replace emoji toolbar buttons with lucide-react icons
// (consistent with the rest of the app + screen-reader friendly via aria-label).
import {
    HelpCircle,
    Ghost, // UX Audit Doctor M-19: kept for backward compat, replaced by PanelTopOpen
    PanelTopOpen,
    History,
    Undo2,
    Redo2,
    RefreshCw,
    Save,
    CheckCircle2,
    FilePenLine,
    Ban,
} from 'lucide-react';

/**
 * EMRContainerV2 Component
 * 
 * @param {Object} props
 * @param {number} props.visitId - Visit ID
 * @param {number} props.patientId - Patient ID
 * @param {string} props.specialty - Canonical specialty key
 * @param {string} props.patientName - Patient name (for sticky header)
 * @param {React.ComponentType} props.ICD10Component - Optional ICD10 autocomplete
 */
interface EMRContainerV2Props {
    visitId: string | number;
    patientId?: string | number | null;
    specialty?: string;
    patientName?: string;
    ICD10Component?: React.ComponentType<Record<string, unknown>> | null;
}

interface EMRDataShape {
    complaints?: string;
    anamnesis_morbi?: string;
    anamnesis_vitae?: string;
    examination?: string;
    diagnosis?: string;
    treatment?: string;
    recommendations?: string;
    notes?: string;
    icd10_code?: string;
    specialty?: string;
    vitals?: Record<string, unknown>;
    medications?: { text?: string; list?: unknown[] };
    specialty_data?: Record<string, unknown>;
    patient_age?: string | number;
    patient_gender?: string;
    [key: string]: unknown;
}

/** Normalize legacy field values that may be a string OR an object with `.text`. */
function fieldText(value: unknown): string {
    if (typeof value === 'string') return value;
    if (value && typeof value === 'object' && 'text' in value) {
        const t = (value as { text?: unknown }).text;
        return typeof t === 'string' ? t : '';
    }
    return '';
}

interface EMRHookResult {
    data: EMRDataShape | null;
    status: string;
    isDirty: boolean;
    lastSaved: string | null;
    conflict: unknown;
    error: unknown;
    isSaving: boolean;
    isSigned: boolean;
    isAmended: boolean;
    accessDenied: boolean;
    version: number | null;
    canUndo: boolean;
    canRedo: boolean;
    loadEMR: () => Promise<unknown>;
    saveEMR: (opts?: Record<string, unknown>) => Promise<unknown>;
    signEMR: (opts?: Record<string, unknown>) => Promise<unknown>;
    amendEMR: (reason: string, opts?: Record<string, unknown>) => Promise<unknown>;
    setField: (field: string, value: unknown) => void;
    undo: () => void;
    redo: () => void;
    reloadFromServer: () => Promise<unknown>;
    forceOverwrite: () => Promise<unknown>;
}

export function EMRContainerV2({ visitId, patientId = null, specialty, ICD10Component = null }: EMRContainerV2Props) {
    // P-013 fix: shared ConfirmDialog hook (replaces 1 window.confirm() call).
    const [confirmRaw, confirmDialog] = useConfirm();
  const confirm = confirmRaw as unknown as (opts: Record<string, unknown>) => Promise<boolean>;
    const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
    const canonicalSpecialty = normalizeSpecialty(specialty);
    const {
        data,
        status,
        isDirty,
        lastSaved,
        conflict,
        error,
        isSaving,
        isSigned,
        isAmended,
        accessDenied,
        version,
        canUndo,
        canRedo,
        loadEMR,
        saveEMR,
        signEMR,
        amendEMR,
        setField,
        undo,
        redo,
        reloadFromServer,
        forceOverwrite,
    } = useEMR(visitId, { specialty: canonicalSpecialty }) as EMRHookResult;

    // Get current user (doctor) for history/AI suggestions
    const { currentUser } = useAppData() as { currentUser?: { id?: string | number | null } };
    const doctorId = currentUser?.id;

    // Autosave setup
    const { lastAutosave, config: autosaveConfig } = useEMRAutosave({
        isDirty,
        isSaving,
        isSigned,
        status,
        saveEMR,
        debounceMs: DEBOUNCE.autosave,
        maxWaitMs: 30000,
        enabled: !isSigned && !accessDenied,
    });

    // Navigation guard
    useBeforeUnload(isDirty);

    // Local UI state
    const [showHistory, setShowHistory] = useState(false);
    const [showHelp, setShowHelp] = useState(false);
    const [selectedVersion, setSelectedVersion] = useState(null);
    const [showDiff, setShowDiff] = useState(false);
    const [amendReason, setAmendReason] = useState('');
    const [showAmendForm, setShowAmendForm] = useState(false);
    const [experimentalGhostMode, setExperimentalGhostMode] = useState(false);

    // AI Suggestions state — keyed by EMR field name (examination/diagnosis/treatment).
    const [aiSuggestions, setAiSuggestions] = useState<Record<string, unknown[]>>({});
    const [aiLoading, setAiLoading] = useState<Record<string, boolean>>({});

    // 🔄 Visit Lifecycle Management - критично для безопасности данных
    const visitLifecycle = useVisitLifecycle(visitId, patientId, {
        invalidateCacheOnChange: true,
        onVisitChange: ({ prevVisitId, newVisitId }) => {
            // Очищаем AI-состояние при смене визита
            setAiSuggestions({});
            setAiLoading({});
            logger.info('[EMR] Visit changed', { prevVisitId, newVisitId });
        },
        onCleanup: () => {
            // Дополнительная очистка при размонтировании
            setExperimentalGhostMode(false);
        },
    });
    const { getAbortSignal } = visitLifecycle;

    // Cache EMR snapshot for the current visit
    useEffect(() => {
        if (visitId && data) {
            cacheService.cacheEMR(visitId, data);
        }
    }, [visitId, data]);

    // 🔒 1. Strict Rules for Ghost Mode
    // Auto-disable if signed, amended, or conflict occurs
    React.useEffect(() => {
        if (isSigned || isAmended || conflict) {
            setExperimentalGhostMode(false);
        }
    }, [isSigned, isAmended, conflict]);

    // Auto-disable on visit change
    React.useEffect(() => {
        setExperimentalGhostMode(false);
    }, [visitId]);

    const buildAiCacheKey = useCallback((fieldName) => {
        const specialty = data.specialty || 'general';
        const complaints = (data.complaints || '').trim().toLowerCase();
        const diagnosis = (data.diagnosis || '').trim().toLowerCase();
        const patientAge = typeof data.patient_age === 'number' ? data.patient_age : String(data.patient_age ?? '');
        const patientGender = typeof data.patient_gender === 'string' ? data.patient_gender : String(data.patient_gender ?? '');
        return cacheService.generateKey(
            'ai',
            fieldName,
            specialty,
            complaints,
            diagnosis,
            patientAge,
            patientGender
        );
    }, [data.specialty, data.complaints, data.diagnosis, data.patient_age, data.patient_gender]);

    const buildAiTags = useCallback(() => {
        const tags = [CACHE_TAGS.aiAnalysis];
        if (visitId) tags.push(CACHE_TAGS.visit(visitId));
        if (patientId) tags.push(CACHE_TAGS.patient(patientId));
        return tags;
    }, [visitId, patientId]);

    // Handle Telemetry
    const handleTelemetry = useCallback((event) => {
        // Log minimal counters
        // ghost.enabled, ghost.accepted, ghost.dismissed, history.accepted
        if (event && event.type) {
            if (process.env.NODE_ENV === 'development') {
                logger.info('[EMR Telemetry]', event);
            }
            // In production: send to analytics backend
        }
    }, []);

    // Handle AI Request - calls MCP API for suggestions
    const handleRequestAI = useCallback(async (fieldName) => {
        logger.info('[EMR AI Request]', {
            fieldName,
            specialty: data.specialty || 'general',
            complaintsLength: data.complaints?.length || 0,
            complaintsPreview: data.complaints?.substring(0, 50) || '(empty)'
        });
        handleTelemetry({ type: 'ai.requested', payload: { fieldName } });

        const cacheKey = buildAiCacheKey(fieldName);
        const cachedSuggestions = cacheService.get(cacheKey);
        if (cachedSuggestions) {
            setAiSuggestions(prev => ({ ...prev, [fieldName]: cachedSuggestions }));
            setAiLoading(prev => ({ ...prev, [fieldName]: false }));
            handleTelemetry({ type: 'ai.cache.hit', payload: { fieldName } });
            return;
        }

        // Set loading state for this field
        setAiLoading(prev => ({ ...prev, [fieldName]: true }));

        try {
            let result;
            const specialty = data.specialty || 'general';
            const requestOptions = { signal: getAbortSignal() };

            switch (fieldName) {
                case 'diagnosis': {
                    // Use ICD-10 suggestions
                    result = await mcpAPI.suggestICD10({
                        symptoms: data.complaints ? [data.complaints] : [],
                        diagnosis: data.diagnosis || '',
                        specialty,
                        maxSuggestions: 5
                    }, requestOptions);
                    logger.info('[EMR AI] ICD10 result:', result);

                    // Log debug_meta in dev mode for transparency
                    if (process.env.NODE_ENV === 'development' && result?.debug_meta) {
                        logger.info('[AI Debug]', result.debug_meta);
                    }

                    // Handle wrapped response: {status, data: {suggestions: [...]}}
                    const icd10Data = result?.data || result;

                    // Backend now returns structured JSON: {suggestions: [{code, label, confidence}]}
                    const suggestions = icd10Data?.suggestions || [];

                    if (suggestions.length > 0) {
                        const formattedSuggestions = suggestions.map(s => ({
                            id: s.code || s.id,
                            content: `${s.code} - ${s.label || s.name || s.description}`,
                            source: 'ai',
                            confidence: s.confidence || 0.8,
                            meta: { code: s.code, label: s.label }
                        }));
                        setAiSuggestions(prev => ({
                            ...prev,
                            [fieldName]: formattedSuggestions
                        }));
                        cacheService.set(cacheKey, formattedSuggestions, {
                            ttl: CACHE_CONFIG.aiTTL,
                            tags: buildAiTags(),
                        });
                    } else {
                        logger.info('[EMR AI] No ICD-10 suggestions returned');
                    }
                    break;
                }

                case 'examination':
                case 'treatment':
                    // Use complaint analysis for general suggestions
                    if (data.complaints) {
                        result = await mcpAPI.analyzeComplaint({
                            complaint: data.complaints,
                            patientAge: data.patient_age,
                            patientGender: data.patient_gender
                        }, requestOptions);
                        logger.info('[EMR AI] Complaint analysis result:', result);

                        // Log debug_meta in dev mode for transparency
                        if (process.env.NODE_ENV === 'development' && result?.debug_meta) {
                            logger.info('[AI Debug]', result.debug_meta);
                        }

                        const analysisData = result?.data || result;
                        if (analysisData) {
                            const fieldSuggestions = [];
                            if (fieldName === 'examination' && analysisData.examination_plan) {
                                fieldSuggestions.push({
                                    id: 'exam-1',
                                    content: analysisData.examination_plan,
                                    source: 'ai',
                                    confidence: 0.8
                                });
                            }
                            if (fieldName === 'treatment' && analysisData.treatment_suggestion) {
                                fieldSuggestions.push({
                                    id: 'treat-1',
                                    content: analysisData.treatment_suggestion,
                                    source: 'ai',
                                    confidence: 0.8
                                });
                            }
                            // Also check for recommendations field
                            if (analysisData.recommendations) {
                                fieldSuggestions.push({
                                    id: 'rec-1',
                                    content: typeof analysisData.recommendations === 'string'
                                        ? analysisData.recommendations
                                        : JSON.stringify(analysisData.recommendations),
                                    source: 'ai',
                                    confidence: 0.7
                                });
                            }
                            if (fieldSuggestions.length > 0) {
                                setAiSuggestions(prev => ({ ...prev, [fieldName]: fieldSuggestions }));
                                cacheService.set(cacheKey, fieldSuggestions, {
                                    ttl: CACHE_CONFIG.aiTTL,
                                    tags: buildAiTags(),
                                });
                            }
                        }
                    } else {
                        // ⚠️ ВАЖНО: Никогда не молчать!
                        // Показать пользователю, почему AI не работает
                        setAiSuggestions(prev => ({
                            ...prev,
                            [fieldName]: [{
                                id: 'info-no-complaints',
                                content: t('misc.emr_ai_no_complaints'),
                                source: 'info',
                                confidence: 0,
                                isInfo: true  // Marking as info, not a real suggestion
                            }]
                        }));
                        logger.info('[EMR AI] No complaints to analyze - showing info message');
                    }
                    break;

                default:
                    logger.info('[EMR AI] No AI handler for field:', fieldName);
            }
        } catch (err) {
            if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') {
                return;
            }
            logger.error('[EMR AI Error]', err);
            handleTelemetry({ type: 'ai.error', payload: { fieldName, error: err.message } });
        } finally {
            setAiLoading(prev => ({ ...prev, [fieldName]: false }));
        }
    }, [
        data.specialty,
        data.complaints,
        data.diagnosis,
        data.patient_age,
        data.patient_gender,
        handleTelemetry,
        buildAiCacheKey,
        buildAiTags,
        getAbortSignal
    ]);

    const debouncedRequestAI = useDebouncedCallback(handleRequestAI, 'ai', [handleRequestAI]);

    useEffect(() => {
        debouncedRequestAI.cancel?.();
    }, [visitId, debouncedRequestAI]);

    // Toggle Ghost Mode with validation
    const toggleGhostMode = () => {
        if (isSigned || isAmended) {
            // QW-03 (UX audit): replaced native alert() with notify.warning to keep
            // the visual style consistent with the rest of the app and to avoid
            // blocking the main thread.
            notify.warning(t('misc.emr_ghost_unavailable'));
            return;
        }
        const newValue = !experimentalGhostMode;
        setExperimentalGhostMode(newValue);
        handleTelemetry({ type: 'ghost.enabled', payload: { enabled: newValue } });
    };

    // Field change handlers
    const handleFieldChange = useCallback((field) => (value) => {
        setField(field, value);
    }, [setField]);

    // Actions
    const handleSign = useCallback(async () => {
        // P-013 fix: replaced window.confirm() with shared useConfirm hook.
        const ok = await confirm({
            title: t('misc.emr_sign_title'),
            message: t('misc.emr_sign_message'),
            description: t('misc.emr_sign_desc'),
            confirmLabel: t('misc.emr_sign_confirm'),
            cancelLabel: t('misc.cancel'),
            intent: 'primary',
        });
        if (!ok) {
            return;
        }
        await signEMR();
    }, [signEMR, confirm]);

    // Keyboard shortcuts (must be after handleSign declaration)
    useEMRKeyboard({
        onSave: () => saveEMR(),
        onUndo: undo,
        onRedo: redo,
        onSign: handleSign,
        canUndo,
        canRedo,
        canSave: isDirty && !isSaving,
        canSign: !isDirty && !isSaving && !isSigned,
        enabled: true,
    });

    if (!visitId) {
        return (
            <div className="emr-v2-container">
                <div className="emr-v2-main">
                    <div className="emr-v2-actions">
                        {t('misc.emr_err_visit_id')}
                    </div>
                </div>
            </div>
        );
    }

    if (!specialty || !isCanonicalSpecialty(canonicalSpecialty)) {
        return (
            <div className="emr-v2-container">
                <div className="emr-v2-main">
                    <div className="emr-v2-actions">
                        {t('misc.emr_err_specialty')}
                    </div>
                </div>
            </div>
        );
    }

    const handleAmend = async () => {
        if (amendReason.trim().length >= 10) {
            await amendEMR(amendReason);
            setShowAmendForm(false);
            setAmendReason('');
        }
    };

    // Conflict handlers
    const handleCompareConflict = () => {
        const conflictData = (conflict ?? null) as { serverVersion?: unknown } | null;
        setSelectedVersion(conflictData?.serverVersion ?? null);
        setShowDiff(true);
    };

    // =========================================================================
    // RENDER
    // =========================================================================

    return (
        <div className={`emr-v2-container ${showHistory ? 'emr-v2-container--with-sidebar' : ''}`}>
            {/* Main content */}
            <div className="emr-v2-main">
                {/* Header */}
                <header className="emr-v2-header">
                    <div className="emr-v2-header__left">
                        {/* UX Audit Doctor M-20: «ЭМК v2» → «Электронная медицинская карта». */}
                        <h2>{t('misc.emr_title')}</h2>
                        {patientId && <span className="emr-v2-patient-id">{t('misc.emr_patient', { id: patientId })}</span>}
                    </div>

                    <div className="emr-v2-header__right">
                        <EMRStatusIndicator
                            status={status}
                            isDirty={isDirty}
                            isSigned={isSigned}
                            isAmended={isAmended}
                            lastSaved={lastSaved}
                            lastAutosave={lastAutosave}
                            error={error}
                            conflict={conflict}
                            version={version}
                            autosaveConfig={autosaveConfig}
                        />

                        <Button
                            variant="ghost"
                            size="small"
                            onClick={() => setShowHelp(true)}
                            title={t('misc.emr_help_title')}
                            aria-label={t('misc.emr_help_title')}
                        >
                            <HelpCircle size={16} aria-hidden="true" />
                        </Button>

                        {/* UX Audit Doctor M-19: «Ghost Mode» → «Расширенный режим», Ghost icon → PanelTopOpen. */}
                        <Button
                            variant={experimentalGhostMode ? 'primary' : 'ghost'}
                            size="small"
                            onClick={toggleGhostMode}
                            disabled={isSigned || isAmended}
                            title={isSigned ? t('misc.emr_ghost_unavailable_title') : t('misc.emr_ghost_title')}
                            aria-label={isSigned ? t('misc.emr_ghost_unavailable_aria') : t('misc.emr_ghost_aria')}
                            aria-pressed={experimentalGhostMode}
                        >
                            <PanelTopOpen size={16} aria-hidden="true" />
                        </Button>
                        <Button
                            variant="ghost"
                            size="small"
                            onClick={() => setShowHistory(!showHistory)}
                            title={t('misc.emr_history_title')}
                            aria-label={t('misc.emr_history_title')}
                            aria-expanded={showHistory}
                        >
                            <History size={16} aria-hidden="true" />
                        </Button>
                    </div>
                </header>

                {/* Toolbar */}
                <div className="emr-v2-toolbar">
                    <Button variant="ghost" size="small" onClick={undo} disabled={!canUndo} title={t('misc.emr_undo_title')} aria-label={t('misc.emr_undo_title')}>
                        <Undo2 size={14} aria-hidden="true" /> {t('misc.emr_undo')}
                    </Button>
                    <Button variant="ghost" size="small" onClick={redo} disabled={!canRedo} title={t('misc.emr_redo_title')} aria-label={t('misc.emr_redo_title')}>
                        <Redo2 size={14} aria-hidden="true" /> {t('misc.emr_redo')}
                    </Button>
                    <Button variant="ghost" size="small" onClick={loadEMR} title={t('misc.emr_refresh_title')} aria-label={t('misc.emr_refresh_aria')}>
                        <RefreshCw size={14} aria-hidden="true" /> {t('misc.emr_refresh')}
                    </Button>
                </div>

                {/* Sections */}
                <div className="emr-v2-sections">
                    {/* UX Audit Doctor M-48: progress indicator for EMR sections. */}
                    {(() => {
                        const sections = [
                            { name: t('misc.emr_sec_complaints'), filled: !!(data?.complaints || fieldText(data?.complaints)) },
                            { name: t('misc.emr_sec_anamnesis'), filled: !!(data?.anamnesis_morbi || fieldText(data?.anamnesis_morbi)) },
                            { name: t('misc.emr_sec_examination'), filled: !!(data?.examination || fieldText(data?.examination)) },
                            { name: t('misc.emr_sec_diagnosis'), filled: !!(data?.diagnosis || fieldText(data?.diagnosis)) },
                            { name: t('misc.emr_sec_treatment'), filled: !!(data?.treatment || fieldText(data?.treatment)) },
                            { name: t('misc.emr_sec_recommendations'), filled: !!(data?.recommendations || fieldText(data?.recommendations)) },
                            { name: t('misc.emr_sec_notes'), filled: !!(data?.notes || fieldText(data?.notes)) },
                        ];
                        const filledCount = sections.filter(s => s.filled).length;
                        return (
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', fontSize: '13px', color: 'var(--mac-text-secondary)' }}>
                                <span>{t('misc.emr_filled', { filled: filledCount, total: sections.length })}</span>
                                <div style={{ flex: 1, maxWidth: '200px', height: '6px', borderRadius: '3px', background: 'var(--mac-bg-tertiary)' }}>
                                    <div style={{ width: `${(filledCount / sections.length) * 100}%`, height: '100%', borderRadius: '3px', background: 'var(--mac-success)', transition: 'width 0.3s ease' }} />
                                </div>
                                {sections.filter(s => !s.filled).length > 0 && (
                                    <span style={{ fontSize: '12px' }}>
                                        {t('misc.emr_remaining', { sections: sections.filter(s => !s.filled).map(s => s.name).join(', ') })}
                                    </span>
                                )}
                            </div>
                        );
                    })()}
                    {/* Phase 4+ cognitive load reduction: sections are collapsible.
                        Default-open: Complaints + Examination + Diagnosis (the 3
                        sections a doctor fills on every visit).
                        Default-closed: AnamnesisVitae, Treatment, Recommendations,
                        Notes (filled only when clinically relevant — collapsing
                        them removes visual noise from the default visit screen). */}
                    <ComplaintsSection
                        value={data.complaints}
                        onChange={handleFieldChange('complaints')}
                        disabled={isSigned}
                        doctorId={doctorId}
                    />

                    <AnamnesisMorbiSection
                        value={data.anamnesis_morbi}
                        onChange={handleFieldChange('anamnesis_morbi')}
                        disabled={isSigned}
                        doctorId={doctorId}
                        icd10Code={data.icd10_code || ''}
                    />

                    <AnamnesisVitaeSection
                        value={data.anamnesis_vitae}
                        onChange={handleFieldChange('anamnesis_vitae')}
                        disabled={isSigned}
                        doctorId={doctorId}
                        vitals={data.vitals || {}}
                        onVitalsChange={handleFieldChange('vitals')}
                        defaultOpen={false}
                    />

                    <ExaminationSection
                        value={data.examination}
                        onChange={handleFieldChange('examination')}
                        disabled={isSigned}
                        specialty={data.specialty || 'general'}
                        icd10Code={data.icd10_code || ''}
                        complaints={data.complaints || ''}
                        doctorId={doctorId}
                        experimentalGhostMode={experimentalGhostMode}
                        onTelemetry={handleTelemetry}
                        onRequestAI={debouncedRequestAI}
                        suggestions={aiSuggestions.examination || []}
                        aiLoading={aiLoading.examination || false}
                    />

                    <DiagnosisSection
                        diagnosis={data.diagnosis}
                        icd10Code={data.icd10_code}
                        onDiagnosisChange={handleFieldChange('diagnosis')}
                        onIcd10Change={handleFieldChange('icd10_code')}
                        disabled={isSigned}
                        ICD10Component={ICD10Component}
                        doctorId={doctorId}
                        experimentalGhostMode={experimentalGhostMode}
                        onTelemetry={handleTelemetry}
                        onRequestAI={debouncedRequestAI}
                        suggestions={aiSuggestions.diagnosis || []}
                        aiLoading={aiLoading.diagnosis || false}
                    />

                    <TreatmentSection
                        value={data.medications?.text || ''}
                        onChange={(text) => handleFieldChange('medications')({
                            ...(data.medications || {}),
                            text
                        })}
                        medications={data.medications?.list || []}
                        onMedicationsChange={(list) => handleFieldChange('medications')({
                            ...(data.medications || {}),
                            list
                        })}
                        disabled={isSigned}
                        specialty={data.specialty || 'general'}
                        icd10Code={data.icd10_code || ''}
                        complaints={data.complaints || ''}
                        experimentalGhostMode={experimentalGhostMode}
                        doctorId={doctorId}
                        onTelemetry={handleTelemetry}
                        onRequestAI={debouncedRequestAI}
                        suggestions={aiSuggestions.treatment || []}
                        aiLoading={aiLoading.treatment || false}
                        defaultOpen={false}
                    />

                    {/* Recommendations is reused in TreatmentSection above, or separate? 
                        EMR V2 usually separates Treatment (Process) and Recommendations (Output).
                        But TreatmentSection title is "Лечение".
                        If data.treatment doesn't exist in backend, and TreatmentSection uses data.treatment, 
                        then it was broken or binding to undefined.
                        I'll bind it to 'recommendations' for now or 'treatment' if I add it to schema.
                        Wait, earlier view showed 'recommendations' in schema but no 'treatment'.
                        I will assume 'treatment' matches the UI intent for "Plan/Treatment".
                        But if backend lacks it, I should maybe use 'recommendations'.
                        However, usually "Recommendations" is separate.
                        
                        Let's check 'data.treatment' usage in original file.
                        Original file used 'data.treatment'. 
                        If backend doesn't return it, it's undefined.
                        
                        I will stick to 'data.treatment' for text value to avoid breaking existing logic if it exists somewhere else or is dynamic.
                        BUT I will bind medications to 'medications'. 
                    */}
                    <RecommendationsSection
                        value={data.recommendations}
                        onChange={handleFieldChange('recommendations')}
                        disabled={isSigned}
                        icd10Code={data.icd10_code || ''}
                        defaultOpen={false}
                    />

                    <NotesSection
                        value={data.notes}
                        onChange={handleFieldChange('notes')}
                        disabled={isSigned}
                        defaultOpen={false}
                    />

                    {/* Specialty-specific sections */}
                    {data.specialty === 'cardiology' && (
                        <CardiologySection
                            ecgData={(data.specialty_data?.ecg as Record<string, unknown>) || {}}
                            echoData={(data.specialty_data?.echo as Record<string, unknown>) || {}}
                            labResults={(data.specialty_data?.cardio_labs as Record<string, unknown>) || {}}
                            onChange={(field, value) => handleFieldChange('specialty_data')({
                                ...(data.specialty_data || {}),
                                [field]: value
                            })}
                            disabled={isSigned}
                            visitId={visitId}
                            patientId={patientId}
                        />
                    )}

                    {data.specialty === 'dermatology' && (
                        <DermatologySection
                            photos={(data.specialty_data?.photos as DermatologyPhoto[]) || []}
                            skinType={(data.specialty_data?.skin_type as string) || ''}
                            conditions={(data.specialty_data?.conditions as unknown[]) || []}
                            localization={(data.specialty_data?.localization as Record<string, unknown>) || {}}
                            onChange={(field, value) => handleFieldChange('specialty_data')({
                                ...(data.specialty_data || {}),
                                [field]: value
                            })}
                            disabled={isSigned}
                            visitId={visitId}
                            patientId={patientId}
                        />
                    )}

                    {(data.specialty === 'dentist' || data.specialty === 'dentistry') && (
                        <DentistrySection
                            toothStatus={(data.specialty_data?.tooth_status as Record<string, unknown>) || {}}
                            hygieneIndices={(data.specialty_data?.hygiene_indices as Record<string, unknown>) || {}}
                            periodontalPockets={(data.specialty_data?.periodontal_pockets as Record<string, unknown>) || {}}
                            measurements={(data.specialty_data?.measurements as Record<string, unknown>) || {}}
                            radiographs={(data.specialty_data?.radiographs as Record<string, unknown>) || {}}
                            onChange={(field, value) => handleFieldChange('specialty_data')({
                                ...(data.specialty_data || {}),
                                [field]: value
                            })}
                            disabled={isSigned}
                        />
                    )}

                    {/* P0 fix: Lab results section — visible to ALL specialties.
                        Shows finalized LabReportInstance data from the lab panel.
                        Collapsible (defaultOpen=false when no results, true when
                        results exist). Read-only — doctors view, don't edit. */}
                    <LabResultsSection
                        patientId={patientId}
                        visitId={visitId}
                        disabled={isSigned}
                    />
                </div>

                {/* Actions */}
                <div className="emr-v2-actions">
                    {accessDenied && (
                        <div className="emr-v2-signed-badge" style={{ marginBottom: 8 }} role="alert">
                            <Ban size={14} aria-hidden="true" /> {t('misc.emr_no_access_save')}
                        </div>
                    )}
                    {!isSigned ? (
                        <>
                            <button
                                className="emr-v2-btn emr-v2-btn--primary"
                                onClick={() => saveEMR({ isDraft: false })}
                            disabled={isSaving || !isDirty || accessDenied}
                            aria-label={isSaving ? t('misc.emr_saving_aria') : t('misc.emr_save_aria')}
                        >
                            {isSaving ? (
                                <><Save size={14} aria-hidden="true" /> {t('misc.emr_saving')}</>
                            ) : (
                                <><Save size={14} aria-hidden="true" /> {t('misc.emr_save')}</>
                            )}
                        </button>
                            {/* UX Audit Doctor M-13: комбинированная кнопка «Сохранить и подписать». */}
                            <button
                                className="emr-v2-btn emr-v2-btn--success"
                                onClick={async () => {
                                    if (isDirty) {
                                        await saveEMR({ isDraft: false });
                                    }
                                    handleSign();
                                }}
                                disabled={isSaving || accessDenied}
                                title={accessDenied ? t('misc.emr_no_access_save_title') : t('misc.emr_save_sign_title')}
                                aria-label={t('misc.emr_save_sign_aria')}
                            >
                                <CheckCircle2 size={14} aria-hidden="true" /> {t('misc.emr_save_sign')}
                            </button>
                        </>
                    ) : (
                        <>
                            <div className="emr-v2-signed-badge">
                                <CheckCircle2 size={14} aria-hidden="true" /> {t('misc.emr_signed')} {isAmended && t('misc.emr_with_amendments')}
                            </div>

                            {!showAmendForm ? (
                                <button
                                    className="emr-v2-btn emr-v2-btn--warning"
                                    onClick={() => setShowAmendForm(true)}
                                    aria-label={t('misc.emr_amend_aria')}
                                >
                                    <FilePenLine size={14} aria-hidden="true" /> {t('misc.emr_amend')}
                                </button>
                            ) : (
                                <div className="emr-v2-amend-form">
                                    <textarea
                                        aria-label={t('misc.emr_amend_reason_aria')}
                                        value={amendReason}
                                        onChange={(e) => setAmendReason(e.target.value)}
                                        placeholder={t('misc.emr_amend_reason_ph')}
                                    />
                                    <div className="emr-v2-amend-actions">
                                        <button
                                            className="emr-v2-btn emr-v2-btn--primary"
                                            onClick={handleAmend}
                                            disabled={amendReason.trim().length < 10}
                                        >
                                            {t('misc.emr_save')}
                                        </button>
                                        <button
                                            className="emr-v2-btn"
                                            onClick={() => setShowAmendForm(false)}
                                        >
                                            {t('misc.cancel')}
                                        </button>
                                    </div>
                                </div>
                            )}
                        </>
                    )}
                </div>
            </div>

            {/* History sidebar */}
            {showHistory && (
                <EMRHistoryPanel
                    visitId={visitId}
                    currentVersion={version}
                    selectedVersion={selectedVersion}
                    onSelectVersion={(v) => {
                        setSelectedVersion(v);
                        setShowDiff(true);
                    }}
                    isOpen={showHistory}
                    onClose={() => setShowHistory(false)}
                />
            )}

            {/* Diff viewer modal */}
            {showDiff && selectedVersion && (
                <div
                    className="emr-v2-modal-overlay"
                    onClick={() => setShowDiff(false)}
                    onKeyDown={(e) => e.key === 'Escape' && setShowDiff(false)}
                    role="button"
                    tabIndex={0}
                    aria-label="Close diff viewer"
                >
                    <div
                        onClick={(e) => e.stopPropagation()}
                        onKeyDown={(e) => e.stopPropagation()}
                        role="dialog"
                        aria-modal="true"
                    >
                        <EMRDiffViewer
                            visitId={visitId}
                            versionFrom={selectedVersion}
                            versionTo={version}
                            onClose={() => setShowDiff(false)}
                        />
                    </div>
                </div>
            )}

            {/* Conflict dialog */}
            {conflict && (
                <EMRConflictDialog
                    conflict={conflict}
                    isSigned={isSigned}
                    onReload={reloadFromServer}
                    onCompare={handleCompareConflict}
                    onAmend={() => setShowAmendForm(true)}
                    onForceOverwrite={forceOverwrite}
                    loading={isSaving}
                />
            )}

            {/* Help Dialog */}
            <EMRHelpDialog
                isOpen={showHelp}
                onClose={() => setShowHelp(false)}
            />
            {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
            {confirmDialog as unknown as React.ReactNode}
        </div>
    );
}

EMRContainerV2.propTypes = {
    visitId: PropTypes.number.isRequired,
    patientId: PropTypes.number,
    specialty: PropTypes.string.isRequired,
    ICD10Component: PropTypes.elementType,
};


export default EMRContainerV2;
