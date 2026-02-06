/**
 * EMRContainer - Phase 1: Basic functional container
 * 
 * No styling beauty - just working fields + Save button.
 * Tests the full v2 flow: load → edit → save with conflict handling.
 */

import React, { useState } from 'react';
import { useEMR } from '../../hooks/useEMR';
import './EMRContainer.css';

/**
 * EMRContainer Component
 * 
 * @param {Object} props
 * @param {number} props.visitId - Visit ID
 * @param {number} props.patientId - Patient ID (for display)
 */
export function EMRContainer({ visitId, patientId }) {
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
        canUndo,
        canRedo,
        version,
        loadEMR,
        saveEMR,
        signEMR,
        amendEMR,
        setField,
        undo,
        redo,
        reloadFromServer,
    } = useEMR(visitId);

    const [amendReason, setAmendReason] = useState('');
    const [showAmendInput, setShowAmendInput] = useState(false);

    // =========================================================================
    // HANDLERS
    // =========================================================================

    const handleFieldChange = (field) => (e) => {
        setField(field, e.target.value);
    };

    const handleSave = async () => {
        try {
            await saveEMR();
        } catch (err) {
            console.error('Save failed:', err);
        }
    };

    const handleSign = async () => {
        if (!window.confirm('Подписать ЭМК? После подписания редактирование возможно только через поправку.')) {
            return;
        }
        try {
            await signEMR();
        } catch (err) {
            console.error('Sign failed:', err);
        }
    };

    const handleAmend = async () => {
        if (amendReason.trim().length < 10) {
            alert('Причина должна быть не менее 10 символов');
            return;
        }
        try {
            await amendEMR(amendReason);
            setShowAmendInput(false);
            setAmendReason('');
        } catch (err) {
            console.error('Amend failed:', err);
        }
    };

    // =========================================================================
    // STATUS INDICATOR
    // =========================================================================

    const getStatusText = () => {
        if (status === 'loading') return '⏳ Загрузка...';
        if (status === 'saving') return '💾 Сохранение...';
        if (status === 'conflict') return '⚠️ Конфликт версий';
        if (status === 'error') return `❌ ${error}`;
        if (isSigned) return '✅ Подписана';
        if (isAmended) return '📝 С поправками';
        if (isDirty) return '● Есть изменения';
        if (lastSaved) return `Сохранено: ${new Date(lastSaved).toLocaleTimeString()}`;
        return 'Новая запись';
    };

    const getStatusClass = () => {
        if (status === 'conflict') return 'emr-status--conflict';
        if (status === 'error') return 'emr-status--error';
        if (isSaving) return 'emr-status--saving';
        if (isSigned) return 'emr-status--signed';
        if (isDirty) return 'emr-status--dirty';
        return 'emr-status--idle';
    };

    // =========================================================================
    // RENDER
    // =========================================================================

    return (
        <div className="emr-container">
            {/* Header */}
            <div className="emr-header">
                <h2>ЭМК v2 {patientId && `(Пациент #${patientId})`}</h2>
                <div className={`emr-status ${getStatusClass()}`}>
                    {getStatusText()}
                    {version > 0 && <span className="emr-version">v{version}</span>}
                </div>
            </div>

            {/* Conflict Alert */}
            {conflict && (
                <div className="emr-conflict-alert">
                    <strong>⚠️ Конфликт версий</strong>
                    <p>
                        Кто-то изменил ЭМК. Ваша версия: {conflict.yourVersion},
                        текущая: {conflict.serverVersion}
                    </p>
                    <div className="emr-conflict-actions">
                        <button onClick={reloadFromServer}>
                            🔄 Загрузить новую версию
                        </button>
                        <button onClick={() => saveEMR({ force: true })}>
                            💪 Перезаписать (мои изменения)
                        </button>
                    </div>
                </div>
            )}

            {/* Undo/Redo Toolbar */}
            <div className="emr-toolbar">
                <button onClick={undo} disabled={!canUndo} title="Отменить (Ctrl+Z)">
                    ↩️ Отменить
                </button>
                <button onClick={redo} disabled={!canRedo} title="Повторить (Ctrl+Y)">
                    ↪️ Повторить
                </button>
                <button onClick={loadEMR} title="Перезагрузить">
                    🔄 Обновить
                </button>
            </div>

            {/* Form Fields */}
            <div className="emr-form">
                {/* Жалобы */}
                <div className="emr-field">
                    <label htmlFor="complaints">Жалобы</label>
                    <textarea
                        id="complaints"
                        value={data.complaints || ''}
                        onChange={handleFieldChange('complaints')}
                        disabled={isSigned}
                        rows={3}
                        placeholder="Опишите жалобы пациента..."
                    />
                </div>

                {/* Анамнез */}
                <div className="emr-field">
                    <label htmlFor="anamnesis">Анамнез</label>
                    <textarea
                        id="anamnesis"
                        value={data.anamnesis || ''}
                        onChange={handleFieldChange('anamnesis')}
                        disabled={isSigned}
                        rows={3}
                        placeholder="История болезни..."
                    />
                </div>

                {/* Осмотр */}
                <div className="emr-field">
                    <label htmlFor="examination">Осмотр</label>
                    <textarea
                        id="examination"
                        value={data.examination || ''}
                        onChange={handleFieldChange('examination')}
                        disabled={isSigned}
                        rows={3}
                        placeholder="Результаты осмотра..."
                    />
                </div>

                {/* Диагноз */}
                <div className="emr-field">
                    <label htmlFor="diagnosis">Диагноз</label>
                    <input
                        type="text"
                        id="diagnosis"
                        value={data.diagnosis || ''}
                        onChange={handleFieldChange('diagnosis')}
                        disabled={isSigned}
                        placeholder="Основной диагноз..."
                    />
                </div>

                {/* МКБ-10 */}
                <div className="emr-field">
                    <label htmlFor="icd10_code">Код МКБ-10</label>
                    <input
                        type="text"
                        id="icd10_code"
                        value={data.icd10_code || ''}
                        onChange={handleFieldChange('icd10_code')}
                        disabled={isSigned}
                        placeholder="например, J06.9"
                    />
                </div>

                {/* Лечение */}
                <div className="emr-field">
                    <label htmlFor="treatment">Лечение / Назначения</label>
                    <textarea
                        id="treatment"
                        value={data.treatment || ''}
                        onChange={handleFieldChange('treatment')}
                        disabled={isSigned}
                        rows={3}
                        placeholder="План лечения..."
                    />
                </div>

                {/* Рекомендации */}
                <div className="emr-field">
                    <label htmlFor="recommendations">Рекомендации</label>
                    <textarea
                        id="recommendations"
                        value={data.recommendations || ''}
                        onChange={handleFieldChange('recommendations')}
                        disabled={isSigned}
                        rows={2}
                        placeholder="Рекомендации пациенту..."
                    />
                </div>
            </div>

            {/* Actions */}
            <div className="emr-actions">
                {!isSigned ? (
                    <>
                        <button
                            className="emr-btn emr-btn--primary"
                            onClick={handleSave}
                            disabled={isSaving || !isDirty}
                        >
                            {isSaving ? '💾 Сохранение...' : '💾 Сохранить'}
                        </button>
                        <button
                            className="emr-btn emr-btn--success"
                            onClick={handleSign}
                            disabled={isSaving || isDirty}
                            title={isDirty ? 'Сначала сохраните изменения' : 'Подписать ЭМК'}
                        >
                            ✅ Подписать
                        </button>
                    </>
                ) : (
                    <>
                        <div className="emr-signed-badge">
                            ✅ ЭМК подписана {isAmended && '(с поправками)'}
                        </div>

                        {!showAmendInput ? (
                            <button
                                className="emr-btn emr-btn--warning"
                                onClick={() => setShowAmendInput(true)}
                            >
                                📝 Внести поправку
                            </button>
                        ) : (
                            <div className="emr-amend-form">
                                <textarea
                                    value={amendReason}
                                    onChange={(e) => setAmendReason(e.target.value)}
                                    placeholder="Причина поправки (минимум 10 символов)..."
                                    rows={2}
                                />
                                <div className="emr-amend-actions">
                                    <button
                                        className="emr-btn emr-btn--primary"
                                        onClick={handleAmend}
                                        disabled={amendReason.trim().length < 10 || isSaving}
                                    >
                                        💾 Сохранить поправку
                                    </button>
                                    <button
                                        className="emr-btn"
                                        onClick={() => setShowAmendInput(false)}
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
    );
}

export default EMRContainer;
