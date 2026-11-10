
/**
 * DentistrySection - Специализированная секция для стоматологии
 * 
 * Интегрирует:
 * - Интерактивную зубную карту (TeethChart)
 * - Индексы гигиены (OHIS, PLI, CPI, Bleeding)
 * - Пародонтальные карманы
 * - Измерения прикуса
 * - Рентгенограммы
 */

import { useState, useCallback } from 'react';
import EMRSection from '../EMRSection';
import React from 'react';
import EMRTextField from '../EMRTextField';
import TeethChart from '@/components/dental/TeethChart';
import './DentistrySection.css';
import { Input, Checkbox } from '@/components/ui/macos';
import { useTranslation } from '@/i18n/useTranslation';

/**
 * DentistrySection Component
 * 
 * @param {Object} props
 * @param {Object} props.toothStatus - Статусы зубов из specialty_data
 * @param {Object} props.hygieneIndices - Индексы гигиены
 * @param {Object} props.periodontalPockets - Пародонтальные карманы
 * @param {Object} props.measurements - Измерения прикуса
 * @param {Object} props.radiographs - Рентгенограммы
 * @param {Function} props.onChange - Handler для изменения specialty_data
 * @param {boolean} props.disabled - Read-only mode
 */
interface DentistrySectionProps {
  toothStatus?: Record<string, unknown>;
  hygieneIndex?: Record<string, unknown>;
  hygieneIndices?: Record<string, unknown>;
  periodontalPockets?: Record<string, unknown>;
  measurements?: Record<string, unknown>;
  radiographs?: Record<string, unknown>;
  onChange?: ((field: string, value: unknown) => void) | undefined;
  disabled?: boolean;
  /**
   * Visit identity (DENTCHART-FE-001, audit 3886): the tooth chart is
   * remounted when the patient/visit identity changes, so no local chart
   * state (selection, palette choice) can survive a patient switch.
   */
  visitId?: string | number | null;
  /** Patient identity (DENTCHART-FE-001, audit 3886). */
  patientId?: string | number | null;
}


/**
 * DENTDATA-FE-001 (audit 3886): records saved by the previous version can
 * hold legacy event-shaped objects ({ target: { value } }) instead of the
 * scalar the doctor actually typed. Normalize such values at the read
 * boundary so the controlled inputs recover instead of rendering
 * "[object Object]".
 */
const scalarText = (value: unknown): string => {
  if (typeof value === 'string') return value;
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  if (value && typeof value === 'object') {
    const legacy = (value as { target?: { value?: unknown } }).target?.value;
    if (typeof legacy === 'string') return legacy;
    if (typeof legacy === 'number' && Number.isFinite(legacy)) return String(legacy);
  }
  return '';
};

export function DentistrySection({
    toothStatus: toothStatusRaw = {},
    hygieneIndices: hygieneIndicesRaw = {},
    periodontalPockets: periodontalPocketsRaw = {},
    measurements: measurementsRaw = {},
    radiographs: radiographsRaw = {},
    onChange,
    disabled = false,
    visitId,
    patientId,
}: DentistrySectionProps) {
  const { t: rawT } = useTranslation(); const t = rawT;
    const hygieneIndices = hygieneIndicesRaw as Record<string, any>;
  const toothStatus = toothStatusRaw as Record<string, any>;
  const periodontalPockets = periodontalPocketsRaw as Record<string, any>;
  const measurements = measurementsRaw as Record<string, any>;
  const radiographs = radiographsRaw as Record<string, any>;
  const [activeTab, setActiveTab] = useState('chart'); // 'chart' | 'hygiene' | 'periodontal' | 'occlusion' | 'radiographs'

    // Handlers
    const handleToothChange = useCallback((toothNumber: string | number, toothData: unknown) => {
        onChange?.('tooth_status', {
            ...toothStatus,
            [toothNumber]: toothData
        });
    }, [toothStatus, onChange]);

    // DENTCHART-FE-003 (audit 3886): Clear All must clear the CANONICAL
    // specialty_data.tooth_status, not only the chart's local copy.
    const handleClearToothStatus = useCallback(() => {
        onChange?.('tooth_status', {});
    }, [onChange]);

    const handleHygieneIndexChange = useCallback((field: string, value: unknown) => {
        onChange?.('hygiene_indices', {
            ...hygieneIndices,
            [field]: value
        });
    }, [hygieneIndices, onChange]);

    const handleMeasurementChange = useCallback((field: string, value: unknown) => {
        onChange?.('measurements', {
            ...measurements,
            [field]: value
        });
    }, [measurements, onChange]);

    const handleRadiographChange = useCallback((field: string, value: unknown) => {
        onChange?.('radiographs', {
            ...radiographs,
            [field]: value
        });
    }, [radiographs, onChange]);

    return (
        <EMRSection
            title={t('misc.ds_stomatologicheskie_dannye')}
            icon="smile"
            disabled={disabled}
            defaultOpen={true}
        >
            {/* Tabs */}
            <div className="dentistry-tabs">
                <button
                    className={`dentistry-tab ${activeTab === 'chart' ? 'active' : ''}`}
                    onClick={() => setActiveTab('chart')}
                    disabled={disabled}
                >
                    Зубная карта
                </button>
                <button
                    className={`dentistry-tab ${activeTab === 'hygiene' ? 'active' : ''}`}
                    onClick={() => setActiveTab('hygiene')}
                    disabled={disabled}
                >
                    Гигиена
                </button>
                <button
                    className={`dentistry-tab ${activeTab === 'periodontal' ? 'active' : ''}`}
                    onClick={() => setActiveTab('periodontal')}
                    disabled={disabled}
                >
                    Пародонт
                </button>
                <button
                    className={`dentistry-tab ${activeTab === 'occlusion' ? 'active' : ''}`}
                    onClick={() => setActiveTab('occlusion')}
                    disabled={disabled}
                >
                    Прикус
                </button>
                <button
                    className={`dentistry-tab ${activeTab === 'radiographs' ? 'active' : ''}`}
                    onClick={() => setActiveTab('radiographs')}
                    disabled={disabled}
                >
                    Рентген
                </button>
            </div>

            {/* Tooth Chart Tab */}
            {activeTab === 'chart' && (
                <div className="dentistry-tab-content">
                    {/* DENTCHART-FE-001 (audit 3886): key the chart by the
                        patient/visit identity so a same-mounted switch to
                        another patient remounts the chart with fresh local
                        state instead of reusing the previous patient's
                        selection/palette remnants. */}
                    <TeethChart
                        key={`dentchart-${String(patientId ?? 'no-patient')}-${String(visitId ?? 'no-visit')}`}
                        initialData={toothStatus}
                        onToothClick={handleToothChange}
                        onClearAll={handleClearToothStatus}
                        readOnly={disabled}
                    />
                </div>
            )}

            {/* Hygiene Indices Tab */}
            {activeTab === 'hygiene' && (
                <div className="dentistry-tab-content">
                    <div className="dentistry-indices-grid">
                        <EMRTextField
                            label="OHIS (Oral Hygiene Index Simplified)"
                            value={scalarText(hygieneIndices?.ohis)}
                            onValueChange={(value) => handleHygieneIndexChange('ohis', value)}
                            disabled={disabled}
                            type="number"
                            placeholder="0.0 - 6.0"
                        />
                        <EMRTextField
                            label="PLI (Plaque Index)"
                            value={scalarText(hygieneIndices?.pli)}
                            onValueChange={(value) => handleHygieneIndexChange('pli', value)}
                            disabled={disabled}
                            type="number"
                            placeholder="0.0 - 3.0"
                        />
                        <EMRTextField
                            label="CPI (Community Periodontal Index)"
                            value={scalarText(hygieneIndices?.cpi)}
                            onValueChange={(value) => handleHygieneIndexChange('cpi', value)}
                            disabled={disabled}
                            type="number"
                            placeholder="0 - 4"
                        />
                        <EMRTextField
                            label="Bleeding Index (%)"
                            value={scalarText(hygieneIndices?.bleeding)}
                            onValueChange={(value) => handleHygieneIndexChange('bleeding', value)}
                            disabled={disabled}
                            type="number"
                            placeholder="0 - 100"
                        />
                    </div>
                </div>
            )}

            {/* Periodontal Pockets Tab */}
            {activeTab === 'periodontal' && (
                <div className="dentistry-tab-content">
                    <div className="dentistry-periodontal-info">
                        <p>{t('misc.ds_parodontalnye_karmany_izmery')}</p>
                        <p className="dentistry-note">
                            Глубина: 0-3мм — норма, 4-5мм — умеренный, 6+мм — тяжелый
                        </p>
                    </div>

                    {/* Upper Jaw */}
                    <div className="periodontal-jaw-section">
                        <h5 className="periodontal-jaw-title">{t('misc.ds_verhnyaya_chelyust')}</h5>
                        <div className="periodontal-teeth-grid upper">
                            {[18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28].map(toothNum => {
                                const depth = periodontalPockets?.[toothNum];
                                const measured = typeof depth === 'number' && Number.isFinite(depth);
                                const severityClass = measured
                                    ? (depth >= 6 ? 'severe' : depth >= 4 ? 'moderate' : 'normal')
                                    : 'normal';
                                return (
                                    <div key={toothNum} className={`periodontal-tooth ${severityClass}`}>
                                        <span className="tooth-number">{toothNum}</span>
                                        <Input
                                            type="number"
                                            aria-label={`Periodontal pocket depth for tooth ${toothNum}`}
                                            min="0"
                                            max="15"
                                            value={measured ? depth : ''}
                                            onChange={(e) => {
                                                // DENTPOCKET-FE-001 (audit 3886): read the
                                                // input's value, not the event object. The old
                                                // parseFloat(eventObject) || 0 collapsed EVERY
                                                // entered depth (4/6/7.5 mm, including severe
                                                // 6+ mm pockets) into a fabricated 0 mm
                                                // "normal" measurement.
                                                const raw = e.target.value;
                                                const parsed = Number.parseFloat(raw);
                                                if (raw.trim() === '' || !Number.isFinite(parsed)) {
                                                    // Explicitly unmeasured — never a silent 0 mm.
                                                    if (!(toothNum in periodontalPockets)) return;
                                                    const next = { ...periodontalPockets };
                                                    delete next[toothNum];
                                                    onChange?.('periodontal_pockets', next);
                                                    return;
                                                }
                                                if (parsed < 0 || parsed > 15) {
                                                    // Out of the declared 0–15 mm range: refuse
                                                    // the change; the next committed change snaps
                                                    // the field back to the last valid value
                                                    // instead of silently rewriting it.
                                                    return;
                                                }
                                                onChange?.('periodontal_pockets', {
                                                    ...periodontalPockets,
                                                    [toothNum]: parsed
                                                });
                                            }}
                                            disabled={disabled}
                                            className="pocket-depth-input"
                                        />
                                        <span className="depth-unit">мм</span>
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    {/* Lower Jaw */}
                    <div className="periodontal-jaw-section">
                        <h5 className="periodontal-jaw-title">{t('misc.ds_nizhnyaya_chelyust')}</h5>
                        <div className="periodontal-teeth-grid lower">
                            {[48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38].map(toothNum => {
                                const depth = periodontalPockets?.[toothNum];
                                const measured = typeof depth === 'number' && Number.isFinite(depth);
                                const severityClass = measured
                                    ? (depth >= 6 ? 'severe' : depth >= 4 ? 'moderate' : 'normal')
                                    : 'normal';
                                return (
                                    <div key={toothNum} className={`periodontal-tooth ${severityClass}`}>
                                        <span className="tooth-number">{toothNum}</span>
                                        <Input
                                            type="number"
                                            aria-label={`Periodontal pocket depth for tooth ${toothNum}`}
                                            min="0"
                                            max="15"
                                            value={measured ? depth : ''}
                                            onChange={(e) => {
                                                // DENTPOCKET-FE-001 (audit 3886): read the
                                                // input's value, not the event object. The old
                                                // parseFloat(eventObject) || 0 collapsed EVERY
                                                // entered depth (4/6/7.5 mm, including severe
                                                // 6+ mm pockets) into a fabricated 0 mm
                                                // "normal" measurement.
                                                const raw = e.target.value;
                                                const parsed = Number.parseFloat(raw);
                                                if (raw.trim() === '' || !Number.isFinite(parsed)) {
                                                    // Explicitly unmeasured — never a silent 0 mm.
                                                    if (!(toothNum in periodontalPockets)) return;
                                                    const next = { ...periodontalPockets };
                                                    delete next[toothNum];
                                                    onChange?.('periodontal_pockets', next);
                                                    return;
                                                }
                                                if (parsed < 0 || parsed > 15) {
                                                    // Out of the declared 0–15 mm range: refuse
                                                    // the change; the next committed change snaps
                                                    // the field back to the last valid value
                                                    // instead of silently rewriting it.
                                                    return;
                                                }
                                                onChange?.('periodontal_pockets', {
                                                    ...periodontalPockets,
                                                    [toothNum]: parsed
                                                });
                                            }}
                                            disabled={disabled}
                                            className="pocket-depth-input"
                                        />
                                        <span className="depth-unit">мм</span>
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    {/* Summary Stats */}
                    <div className="periodontal-summary">
                        {(() => {
                            const pockets = Object.values((periodontalPockets || {}) as Record<string, number>).filter(v => v > 0);
                            if (pockets.length === 0) return null;

                            const avg = (pockets.reduce((a, b) => a + b, 0) / pockets.length).toFixed(1);
                            const max = Math.max(...pockets);
                            const severe = pockets.filter(p => p >= 6).length;
                            const moderate = pockets.filter(p => p >= 4 && p < 6).length;

                            return (
                                <div className="periodontal-stats">
                                    <div className="stat-item">
                                        <span className="stat-value">{avg}</span>
                                        <span className="stat-label">{t('misc.ds_srednyaya_glubina_mm')}</span>
                                    </div>
                                    <div className="stat-item">
                                        <span className="stat-value">{max}</span>
                                        <span className="stat-label">{t('misc.ds_maks_glubina_mm')}</span>
                                    </div>
                                    <div className="stat-item severe">
                                        <span className="stat-value">{severe}</span>
                                        <span className="stat-label">{t('misc.ds_tyazhyolyh_6mm')}</span>
                                    </div>
                                    <div className="stat-item moderate">
                                        <span className="stat-value">{moderate}</span>
                                        <span className="stat-label">{t('misc.ds_umerennyh_4_5mm')}</span>
                                    </div>
                                </div>
                            );
                        })()}
                    </div>
                </div>
            )}

            {/* Occlusion Measurements Tab */}
            {activeTab === 'occlusion' && (
                <div className="dentistry-tab-content">
                    <div className="dentistry-measurements-grid">
                        <EMRTextField
                            label={t('misc.ds_overjet_mm')}
                            value={scalarText(measurements?.overjet)}
                            onValueChange={(value) => handleMeasurementChange('overjet', value)}
                            disabled={disabled}
                            type="number"
                            placeholder={t('misc.ds_gorizontalnoe_perekrytie')}
                        />
                        <EMRTextField
                            label={t('misc.ds_overbite_mm')}
                            value={scalarText(measurements?.overbite)}
                            onValueChange={(value) => handleMeasurementChange('overbite', value)}
                            disabled={disabled}
                            type="number"
                            placeholder={t('misc.ds_vertikalnoe_perekrytie')}
                        />
                        <EMRTextField
                            label={t('misc.ds_midline_deviation_mm')}
                            value={scalarText(measurements?.midline)}
                            onValueChange={(value) => handleMeasurementChange('midline', value)}
                            disabled={disabled}
                            type="number"
                            placeholder={t('misc.ds_otklonenie_sredinnoy_linii')}
                        />
                        <div className="dentistry-checkbox-group">
                            <label className="dentistry-checkbox">
                                <Checkbox aria-label="Crossbite measurement" checked={measurements?.crossbite || false} onChange={(e) => handleMeasurementChange('crossbite', e)}
                                    disabled={disabled}
                                />
                                <span>{t('misc.ds_perekrestnyy_prikus')}</span>
                            </label>
                            <label className="dentistry-checkbox">
                                <Checkbox aria-label="Open bite measurement" checked={measurements?.openBite || false} onChange={(e) => handleMeasurementChange('openBite', e)}
                                    disabled={disabled}
                                />
                                <span>{t('misc.ds_otkrytyy_prikus')}</span>
                            </label>
                        </div>
                    </div>
                </div>
            )}

            {/* Radiographs Tab */}
            {activeTab === 'radiographs' && (
                <div className="dentistry-tab-content">
                    <div className="dentistry-radiographs-grid">
                        <EMRTextField
                            label={t('misc.ds_panoramnyy_snimok')}
                            value={scalarText(radiographs?.panoramic)}
                            onValueChange={(value) => handleRadiographChange('panoramic', value)}
                            disabled={disabled}
                            placeholder={t('misc.ds_url_ili_put_k_faylu')}
                        />
                        <EMRTextField
                            label={t('misc.ds_klkt')}
                            value={scalarText(radiographs?.cbct)}
                            onValueChange={(value) => handleRadiographChange('cbct', value)}
                            disabled={disabled}
                            placeholder={t('misc.ds_url_ili_put_k_faylu')}
                        />
                        <div className="dentistry-radiographs-note">
                            <p>{t('misc.ds_pritselnye_i_prikusnye_snimk')}</p>
                        </div>
                    </div>
                </div>
            )}
        </EMRSection>
    );
}

export default DentistrySection;

