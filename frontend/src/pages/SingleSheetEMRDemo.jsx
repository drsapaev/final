/**
 * SingleSheetEMR Demo Page
 * 
 * Демонстрация концепции "один лист = один визит"
 * 
 * v2.0: Debug Panel скрыт, открывается по Ctrl+Shift+D
 * v2.1: Добавлена поддержка переключения темы через ThemeContext
 */

import React, { useState, useEffect, useCallback } from 'react';
import { SingleSheetEMR } from '../components/emr';
import { useTheme } from '../contexts/ThemeContext';
import logger from '../utils/logger';

// Мок данные пациента
const mockPatient = {
    id: 1,
    first_name: 'Иван',
    last_name: 'Иванов',
    middle_name: 'Петрович',
    birth_date: '1980-05-15',
    sex: 'M',
    phone: '+7 (777) 123-45-67',
    allergies: ['Пенициллин', 'Йод'],
    diagnoses: ['Гипертоническая болезнь II ст.', 'СД 2 типа'],
    // История показателей для авто-заполнения
    vitals_history: {
        height: 172,
        weight: 85,
        date: '03.2025'
    }
};

// Мок данные визита
const mockVisit = {
    id: 1,
    patient_id: 1,
    doctor_id: 1,
    status: 'in_progress',
    started_at: new Date().toISOString(),
    is_signed: false
};

const SingleSheetEMRDemo = () => {
    const { isDark } = useTheme();
    const [savedData, setSavedData] = useState(null);
    const [telemetryData, setTelemetryData] = useState(null);
    const [showDebug, setShowDebug] = useState(false);

    // Hotkey: Ctrl+Shift+D для Debug Panel
    useEffect(() => {
        const handleKeyDown = (e) => {
            if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 'd') {
                e.preventDefault();
                setShowDebug(prev => !prev);
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, []);

    // Actions
    const handleSave = useCallback(async (emrData) => {
        logger.log('[EMR] Saving draft...', emrData);
        setSavedData(emrData);
        if (emrData.telemetry) {
            setTelemetryData(emrData.telemetry);
        }
        await new Promise(resolve => setTimeout(resolve, 300));
        logger.log('[EMR] Draft saved');
    }, []);

    const handleSign = useCallback(async (emrData) => {
        logger.log('[EMR] Signing...', emrData);
        setSavedData(emrData);
        if (emrData.telemetry) {
            setTelemetryData(emrData.telemetry);
        }
        await new Promise(resolve => setTimeout(resolve, 500));
        logger.log('[EMR] Signed');
    }, []);

    const handlePrint = useCallback((document) => {
        logger.log('[EMR] Printing document...', document);
        // TODO: replace alert with non-blocking toast + print preview modal
        // В production: generatePDF(document) с подписью и QR-кодом
        alert('Печать: В production здесь будет генерация PDF с подписью');
    }, []);

    const handleAISummary = useCallback((emrData) => {
        logger.log('[EMR] AI Summary requested', emrData);
        alert('AI Summary: В production здесь будет сводка из истории пациента');
    }, []);

    return (
        <div
            className={`emr-demo-container ${isDark ? 'dark-theme' : 'light-theme'}`}
            style={{
                display: 'flex',
                height: '100vh'
            }}>
            {/* EMR Panel - Основной интерфейс врача */}
            <div style={{
                flex: 1,
                height: '100%',
                overflow: 'hidden'
            }}>
                <SingleSheetEMR
                    context={{
                        patient: mockPatient,
                        visit: mockVisit,
                        role: 'doctor',
                        specialty: 'cardiology'
                    }}
                    actions={{
                        onSave: handleSave,
                        onSign: handleSign,
                        onPrint: handlePrint,
                        onAISummary: handleAISummary
                    }}
                    enableTelemetry={true}
                />
            </div>

            {/* Debug Panel - Скрыт по умолчанию, Ctrl+Shift+D */}
            {showDebug && (
                <div style={{
                    width: '350px',
                    padding: '16px',
                    overflow: 'auto',
                    background: 'var(--mac-background, #ffffff)',
                    borderLeft: '1px solid var(--mac-border, rgba(0,0,0,0.1))'
                }}>
                    <div style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        marginBottom: '16px'
                    }}>
                        <h3 style={{ margin: 0, fontSize: '14px', fontWeight: 600 }}>
                            🔧 Dev Panel
                        </h3>
                        <button
                            onClick={() => setShowDebug(false)}
                            style={{
                                padding: '4px 8px',
                                fontSize: '12px',
                                background: '#f5f5f7',
                                border: 'none',
                                borderRadius: '4px',
                                cursor: 'pointer'
                            }}
                        >
                            ✕ Закрыть
                        </button>
                    </div>

                    {/* UX Telemetry */}
                    {telemetryData && (
                        <div style={{ marginBottom: '24px' }}>
                            <h4 style={{ margin: '0 0 8px', fontSize: '12px', color: '#34c759' }}>
                                📊 UX TELEMETRY
                            </h4>
                            <div style={{
                                padding: '12px',
                                background: 'rgba(52, 199, 89, 0.1)',
                                borderRadius: '8px',
                                fontSize: '12px'
                            }}>
                                <div>⏱ Time to first input: <b>{telemetryData.timeToFirstInputMs || 'N/A'}ms</b></div>
                                <div>⏱ Total session: <b>{Math.round(telemetryData.totalSessionMs / 1000)}s</b></div>
                                <div>✏️ Fields touched: <b>{telemetryData.fieldsTouched}</b></div>
                                <div>🤖 AI suggestions: <b>{telemetryData.aiSuggestionsShown}</b></div>
                                <div>✅ AI accept rate: <b>{telemetryData.aiAcceptRate}%</b></div>
                            </div>
                        </div>
                    )}

                    <div style={{ marginBottom: '24px' }}>
                        <h4 style={{ margin: '0 0 8px', fontSize: '12px', color: '#86868b' }}>
                            SAVED DATA
                        </h4>
                        <pre style={{
                            margin: 0,
                            padding: '12px',
                            background: savedData ? '#e3f2e6' : '#f5f5f7',
                            borderRadius: '8px',
                            fontSize: '10px',
                            overflow: 'auto',
                            maxHeight: '300px'
                        }}>
                            {savedData ? JSON.stringify(savedData, null, 2) : 'Not saved yet'}
                        </pre>
                    </div>

                    <div style={{
                        padding: '12px',
                        background: 'rgba(0,122,255,0.1)',
                        borderRadius: '8px',
                        fontSize: '11px',
                        color: '#007aff'
                    }}>
                        <b>Hotkey:</b> Ctrl+Shift+D
                    </div>
                </div>
            )}
        </div>
    );
};

export default SingleSheetEMRDemo;
