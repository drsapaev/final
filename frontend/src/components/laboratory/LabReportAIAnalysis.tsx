
import { useEffect, useMemo, useState } from 'react';
import {
  Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle,
  Icon, Typography,
} from '../ui/macos';
import { AIButton, AIAssistant } from '../ai';
// STRAT#22: t() для i18n — AI analysis strings мигрированы.
import { useTranslation } from '../../i18n/useTranslation';
import React from "react";

/**
 * P-01 fix: AI-анализ лабораторного бланка перенесён из LabResultsManager
 * в LabReportWorkbench как отдельный подкомпонент.
 *
 * Преимущества новой реализации:
 *   - Использует patient_snapshot из activeInstance (age_years, sex уже
 *     вычислены на backend) — не нужен отдельный запрос GET /patients/{id}
 *   - Берёт результаты из sections бланка, а не из плоской модели
 *   - Сохраняет P-02 fix: блокировка AI при отсутствии возраста/пола
 *   - Показывает явный Alert с реальными данными пациента
 *
 * AI-кнопка показывается только если:
 *   - есть активный бланк (activeInstance)
 *   - есть заполненные поля (не только пустые values)
 */
function normalizeSexForAI(sex: unknown): 'male' | 'female' | 'other' | null {
  if (!sex) return null;
  const s = String(sex).trim().toUpperCase();
  if (s === 'M' || s === 'MALE') return 'male';
  if (s === 'F' || s === 'FEMALE') return 'female';
  return 'other';
}

interface LabField {
  label?: string;
  field_key?: string;
  value_text?: string | null;
  value_numeric?: number | null;
  unit?: string;
  reference_text?: string;
  resolved_flag?: string;
}

interface LabSection {
  fields?: LabField[];
}

interface LabInstance {
  id?: string | number;
  sections?: LabSection[];
  patient_snapshot?: Record<string, unknown>;
}

function collectResultsFromInstance(instance: LabInstance | null | undefined) {
  if (!instance?.sections) return [];
  return instance.sections.flatMap((section) =>
    (section.fields || []).map((field) => ({
      name: field.label || field.field_key || '',
      value: field.value_text ?? (field.value_numeric != null ? String(field.value_numeric) : ''),
      unit: field.unit || '',
      reference: field.reference_text || '',
      flag: field.resolved_flag,
    }))
  );
}

function hasAnyFilledResult(results: Array<{ value: string | null | undefined }>) {
  return results.some((r) => r.value !== '' && r.value != null);
}

interface LabReportAIAnalysisProps {
  activeInstance?: LabInstance | null;
  notify: (severity: string, message: string) => void;
}

export default function LabReportAIAnalysis({ activeInstance, notify }: LabReportAIAnalysisProps) {
  const { t: rawT } = useTranslation(); const t = rawT;
  void t;
  const [showAIAnalysis, setShowAIAnalysis] = useState(false);

  // Извлекаем возраст и пол из patient_snapshot (backend уже вычислил age_years).
  // P-02 fix сохранён: AI блокируется при отсутствии возраста/пола.
  const patientSnapshot = activeInstance?.patient_snapshot || {};
  const resolvedPatientAge = patientSnapshot.age_years ?? null;
  const resolvedPatientGender = normalizeSexForAI(patientSnapshot.sex);

  const results = useMemo(
    () => collectResultsFromInstance(activeInstance),
    [activeInstance]
  );
  const hasResults = hasAnyFilledResult(results as Array<{ value: string | null | undefined }>);

  const [aiBlockedReason, setAiBlockedReason] = useState('');

  useEffect(() => {
    if (!activeInstance) {
      setAiBlockedReason('');
      return;
    }
    if (!hasResults) {
      setAiBlockedReason(t('ai.blocked_no_results'));
      return;
    }
    if (resolvedPatientAge == null) {
      setAiBlockedReason(
        t('ai.blocked_no_age')
      );
      return;
    }
    if (!resolvedPatientGender) {
      setAiBlockedReason(
        t('ai.blocked_no_gender')
      );
      return;
    }
    setAiBlockedReason('');
  }, [activeInstance, hasResults, resolvedPatientAge, resolvedPatientGender]);

  const handleOpenAIAnalysis = () => {
    if (!activeInstance) return;
    if (!hasResults) {
      notify('error', t('ai.fill_fields_first'));
      return;
    }
    if (resolvedPatientAge == null || !resolvedPatientGender) {
      notify('error', aiBlockedReason || t('ai.blocked_generic'));
      return;
    }
    setShowAIAnalysis(true);
  };

  if (!activeInstance) return null;

  return (
    <>
      <AIButton
        text={t('ai.button_label')}
        size="small"
        onClick={handleOpenAIAnalysis}
        disabled={!hasResults || Boolean(aiBlockedReason)}
        tooltip={
          aiBlockedReason
          || (hasResults
              ? t('ai.button_tooltip')
              : t('ai.button_disabled'))
        }
      />

      {showAIAnalysis && (
        <Dialog
          open={showAIAnalysis}
          onClose={() => setShowAIAnalysis(false)}
          maxWidth="md"
          fullWidth
        >
          <DialogTitle>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Typography variant="h6">
                {t('ai.dialog_title')} #{activeInstance.id}
              </Typography>
              <Button
                type="button"
                size="small"
                title={t('ai.dialog_close_aria')}
                aria-label={t('ai.dialog_close_aria')}
                onClick={() => setShowAIAnalysis(false)}
              >
                {/* L-M-8 fix: emoji ✕ заменён на lucide-icon X для консистентности
                    с остальными UI-кнопками (cashier/registrar/admin/doctor panels). */}
                <Icon name="xmark" size={14} />
              </Button>
            </Box>
          </DialogTitle>

          <DialogContent>
            {/* P-02 fix: явное отображение данных пациента, на основе которых
                строится AI-интерпретация. Данные берутся из patient_snapshot
                (backend уже вычислил age_years), без отдельного запроса. */}
            <Alert severity="info" sx={{ mb: 2 }}>
              <Typography variant="caption" component="div">
                <strong>{t('ai.patient_label')}:</strong>{' '}
                {String(patientSnapshot.full_name || `#${patientSnapshot.patient_id || '?'}`)}
                {' · '}
                <strong>{t('ai.age_label')}:</strong>{' '}
                {resolvedPatientAge != null ? `${resolvedPatientAge} ${t('ai.age_years')}` : t('ai.age_unknown')}
                {' · '}
                <strong>{t('ai.gender_label')}:</strong>{' '}
                {resolvedPatientGender
                  ? ({ male: t('ai.gender_male'), female: t('ai.gender_female'), other: t('ai.gender_other') }[resolvedPatientGender] || resolvedPatientGender)
                  : t('ai.gender_not_set')}
                {' · '}
                <strong>{t('ai.fields_count')}:</strong> {results.length}
              </Typography>
              {(resolvedPatientAge == null || !resolvedPatientGender) && (
                <Typography variant="caption" color="error" component="div" sx={{ mt: 0.5 }}>
                  {t('ai.missing_age_gender')}
                </Typography>
              )}
            </Alert>

            <AIAssistant
              analysisType="lab"
              data={{
                results: results.map((r) => ({
                  name: (r as { name: string }).name,
                  value: (r as { value: string }).value,
                  unit: (r as { unit: string }).unit,
                  reference: (r as { reference: string }).reference,
                  flag: (r as { flag?: string }).flag,
                })),
                patient_age: resolvedPatientAge,
                patient_gender: resolvedPatientGender,
              }}
              onResult={() => {
                /* результат сохраняется внутри AIAssistant */
              }}
            />
          </DialogContent>

          <DialogActions>
            <Button onClick={() => setShowAIAnalysis(false)}>
              {t('ai.dialog_close')}
            </Button>
          </DialogActions>
        </Dialog>
      )}
    </>
  );
}

