/**
 * EMRContainerV2 - Modular EMR container using v2 sections
 * 
 * Phase 4 Result:
 * - Uses modular sections instead of inline JSX
 * - SingleSheetEMR stays working until migration complete
 * - All Phase 1-3 features work (autosave, guards, history, conflict)
 * 
 * Phase 6 Additions:
 * - Keyboard shortcuts (Ctrl+S, Ctrl+Z, Ctrl+Y)
 * - Sticky header
 */

import React, { useState, useCallback } from 'react';
import PropTypes from 'prop-types';
import { useEMR } from '../../hooks/useEMR';
import { useEMRAutosave } from '../../hooks/useEMRAutosave';
import { useBeforeUnload } from '../../hooks/useNavigationGuard';
import { useEMRKeyboard } from '../../hooks/useEMRKeyboard';
import EMRStatusIndicator from './EMRStatusIndicator';
import EMRHistoryPanel from './EMRHistoryPanel';
import EMRDiffViewer from './EMRDiffViewer';
import EMRConflictDialog from './EMRConflictDialog';
import EMRHelpDialog from './EMRHelpDialog';
import { useAppData } from '../../contexts/AppDataContext';
import { mcpAPI } from '../../api/mcpClient';
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

import './EMRContainerV2.css';

/**
 * EMRContainerV2 Component
 * 
 * @param {Object} props
 * @param {number} props.visitId - Visit ID
 * @param {number} props.patientId - Patient ID
 * @param {string} props.patientName - Patient name (for sticky header)
 * @param {React.ComponentType} props.ICD10Component - Optional ICD10 autocomplete
 */
export function EMRContainerV2({ visitId, patientId, ICD10Component }) {
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
    } = useEMR(visitId);

    // Get current user (doctor) for history/AI suggestions
    const { currentUser } = useAppData();
    const doctorId = currentUser?.id;

    // Autosave setup
    const { lastAutosave, config: autosaveConfig } = useEMRAutosave({
        isDirty,
        isSaving,
        isSigned,
        status,
        saveEMR,
        debounceMs: 3000,
        maxWaitMs: 30000,
        enabled: !isSigned,
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

    // AI Suggestions state
    const [aiSuggestions, setAiSuggestions] = useState({});
    const [aiLoading, setAiLoading] = useState({});

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

    // Handle Telemetry
    const handleTelemetry = useCallback((event) => {
        // Log minimal counters
        // ghost.enabled, ghost.accepted, ghost.dismissed, history.accepted
        if (event && event.type) {
            if (process.env.NODE_ENV === 'development') {
                // eslint-disable-next-line no-console
                console.log('[EMR Telemetry]', event);
            }
            // In production: send to analytics backend
        }
    }, []);

    // Handle AI Request - calls MCP API for suggestions
    const handleRequestAI = useCallback(async (fieldName) => {
        // eslint-disable-next-line no-console
        console.log('[EMR AI Request]', {
            fieldName,
            specialty: data.specialty || 'general',
            complaintsLength: data.complaints?.length || 0,
            complaintsPreview: data.complaints?.substring(0, 50) || '(empty)'
        });
        handleTelemetry({ type: 'ai.requested', payload: { fieldName } });

        // Set loading state for this field
        setAiLoading(prev => ({ ...prev, [fieldName]: true }));

        try {
            let result;
            const specialty = data.specialty || 'general';

            switch (fieldName) {
                case 'diagnosis':
                    // Use ICD-10 suggestions
                    result = await mcpAPI.suggestICD10({
                        symptoms: data.complaints ? [data.complaints] : [],
                        diagnosis: data.diagnosis || '',
                        specialty,
                        maxSuggestions: 5
                    });
                    // eslint-disable-next-line no-console
                    console.log('[EMR AI] ICD10 result:', result);

                    // Log debug_meta in dev mode for transparency
                    if (process.env.NODE_ENV === 'development' && result?.debug_meta) {
                        // eslint-disable-next-line no-console
                        console.log('[AI Debug]', result.debug_meta);
                    }

                    // Handle wrapped response: {status, data: {suggestions: [...]}}
                    const icd10Data = result?.data || result;

                    // Backend now returns structured JSON: {suggestions: [{code, label, confidence}]}
                    const suggestions = icd10Data?.suggestions || [];

                    if (suggestions.length > 0) {
                        setAiSuggestions(prev => ({
                            ...prev,
                            [fieldName]: suggestions.map(s => ({
                                id: s.code || s.id,
                                content: `${s.code} - ${s.label || s.name || s.description}`,
                                source: 'ai',
                                confidence: s.confidence || 0.8,
                                meta: { code: s.code, label: s.label }
                            }))
                        }));
                    } else {
                        // eslint-disable-next-line no-console
                        console.log('[EMR AI] No ICD-10 suggestions returned');
                    }
                    break;

                case 'examination':
                case 'treatment':
                    // Use complaint analysis for general suggestions
                    if (data.complaints) {
                        result = await mcpAPI.analyzeComplaint({
                            complaint: data.complaints,
                            patientAge: data.patient_age,
                            patientGender: data.patient_gender
                        });
                        // eslint-disable-next-line no-console
                        console.log('[EMR AI] Complaint analysis result:', result);

                        // Log debug_meta in dev mode for transparency
                        if (process.env.NODE_ENV === 'development' && result?.debug_meta) {
                            // eslint-disable-next-line no-console
                            console.log('[AI Debug]', result.debug_meta);
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
                            }
                        }
                    } else {
                        // ⚠️ ВАЖНО: Никогда не молчать!
                        // Показать пользователю, почему AI не работает
                        setAiSuggestions(prev => ({
                            ...prev,
                            [fieldName]: [{
                                id: 'info-no-complaints',
                                content: '💡 Для AI-подсказок сначала заполните поле «Жалобы»',
                                source: 'info',
                                confidence: 0,
                                isInfo: true  // Marking as info, not a real suggestion
                            }]
                        }));
                        // eslint-disable-next-line no-console
                        console.log('[EMR AI] No complaints to analyze - showing info message');
                    }
                    break;

                default:
                    // eslint-disable-next-line no-console
                    console.log('[EMR AI] No AI handler for field:', fieldName);
            }
        } catch (err) {
            // eslint-disable-next-line no-console
            console.error('[EMR AI Error]', err);
            handleTelemetry({ type: 'ai.error', payload: { fieldName, error: err.message } });
        } finally {
            setAiLoading(prev => ({ ...prev, [fieldName]: false }));
        }
    }, [data.specialty, data.complaints, data.diagnosis, data.patient_age, data.patient_gender, handleTelemetry]);

    // Toggle Ghost Mode with validation
    const toggleGhostMode = () => {
        if (isSigned || isAmended) {
            alert('Ghost Mode недоступен в подписанной карте.');
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
        if (!window.confirm('Подписать ЭМК? После подписания редактирование возможно только через поправку.')) {
            return;
        }
        await signEMR();
    }, [signEMR]);

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

    const handleAmend = async () => {
        if (amendReason.trim().length >= 10) {
            await amendEMR(amendReason);
            setShowAmendForm(false);
            setAmendReason('');
        }
    };

    // Conflict handlers
    const handleCompareConflict = () => {
        setSelectedVersion(conflict?.serverVersion);
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
                        <h2>ЭМК v2</h2>
                        {patientId && <span className="emr-v2-patient-id">Пациент #{patientId}</span>}
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

                        <button
                            className="emr-v2-btn emr-v2-btn--icon"
                            onClick={() => setShowHelp(true)}
                            title="Справка и безопасность"
                        >
                            ❓
                        </button>

                        <button
                            className={`emr-v2-btn ${experimentalGhostMode ? 'emr-v2-btn--active' : ''}`}
                            onClick={toggleGhostMode}
                            disabled={isSigned || isAmended}
                            title={isSigned ? 'Недоступно в подписанной карте' : 'Расширенный режим ввода (экспериментальный)'}
                        >
                            👻
                        </button>
                        <button
                            className="emr-v2-btn emr-v2-btn--icon"
                            onClick={() => setShowHistory(!showHistory)}
                            title="История изменений"
                        >
                            📜
                        </button>
                    </div>
                </header>

                {/* Toolbar */}
                <div className="emr-v2-toolbar">
                    <button onClick={undo} disabled={!canUndo} title="Отменить (Ctrl+Z)">
                        ↩️ Отменить
                    </button>
                    <button onClick={redo} disabled={!canRedo} title="Повторить (Ctrl+Y)">
                        ↪️ Повторить
                    </button>
                    <button onClick={loadEMR} title="Обновить">
                        🔄 Обновить
                    </button>
                </div>

                {/* Sections */}
                <div className="emr-v2-sections">
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
                        onRequestAI={handleRequestAI}
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
                        onRequestAI={handleRequestAI}
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
                        onRequestAI={handleRequestAI}
                        suggestions={aiSuggestions.treatment || []}
                        aiLoading={aiLoading.treatment || false}
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
                    />

                    <NotesSection
                        value={data.notes}
                        onChange={handleFieldChange('notes')}
                        disabled={isSigned}
                    />
                </div>

                {/* Actions */}
                <div className="emr-v2-actions">
                    {!isSigned ? (
                        <>
                            <button
                                className="emr-v2-btn emr-v2-btn--primary"
                                onClick={() => saveEMR()}
                                disabled={isSaving || !isDirty}
                            >
                                {isSaving ? '💾 Сохранение...' : '💾 Сохранить'}
                            </button>
                            <button
                                className="emr-v2-btn emr-v2-btn--success"
                                onClick={handleSign}
                                disabled={isSaving || isDirty}
                                title={isDirty ? 'Сначала сохраните' : 'Подписать'}
                            >
                                ✅ Подписать
                            </button>
                        </>
                    ) : (
                        <>
                            <div className="emr-v2-signed-badge">
                                ✅ Подписана {isAmended && '(с поправками)'}
                            </div>

                            {!showAmendForm ? (
                                <button
                                    className="emr-v2-btn emr-v2-btn--warning"
                                    onClick={() => setShowAmendForm(true)}
                                >
                                    📝 Внести поправку
                                </button>
                            ) : (
                                <div className="emr-v2-amend-form">
                                    <textarea
                                        value={amendReason}
                                        onChange={(e) => setAmendReason(e.target.value)}
                                        placeholder="Причина поправки (мин. 10 символов)..."
                                    />
                                    <div className="emr-v2-amend-actions">
                                        <button
                                            className="emr-v2-btn emr-v2-btn--primary"
                                            onClick={handleAmend}
                                            disabled={amendReason.trim().length < 10}
                                        >
                                            Сохранить
                                        </button>
                                        <button
                                            className="emr-v2-btn"
                                            onClick={() => setShowAmendForm(false)}
                                        >
                                            Отмена
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
        </div>
    );
}

EMRContainerV2.propTypes = {
    visitId: PropTypes.number.isRequired,
    patientId: PropTypes.number,
    ICD10Component: PropTypes.elementType,
};

EMRContainerV2.defaultProps = {
    patientId: null,
    ICD10Component: null,
};

export default EMRContainerV2;
