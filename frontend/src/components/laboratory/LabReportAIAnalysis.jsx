import { useEffect, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle,
  Icon, Typography,
} from '../ui/macos';
import { AIButton, AIAssistant } from '../ai';

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
function normalizeSexForAI(sex) {
  if (!sex) return null;
  const s = String(sex).trim().toUpperCase();
  if (s === 'M' || s === 'MALE') return 'male';
  if (s === 'F' || s === 'FEMALE') return 'female';
  return 'other';
}

function collectResultsFromInstance(instance) {
  if (!instance?.sections) return [];
  return instance.sections.flatMap((section) =>
    (section.fields || []).map((field) => ({
      name: field.label || field.field_key,
      value: field.value_text ?? (field.value_numeric != null ? String(field.value_numeric) : ''),
      unit: field.unit || '',
      reference: field.reference_text || '',
      flag: field.resolved_flag,
    }))
  );
}

function hasAnyFilledResult(results) {
  return results.some((r) => r.value !== '' && r.value != null);
}

export default function LabReportAIAnalysis({ activeInstance, notify }) {
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
  const hasResults = hasAnyFilledResult(results);

  const [aiBlockedReason, setAiBlockedReason] = useState('');

  useEffect(() => {
    if (!activeInstance) {
      setAiBlockedReason('');
      return;
    }
    if (!hasResults) {
      setAiBlockedReason('AI-анализ недоступен: нет заполненных показателей в отчёте.');
      return;
    }
    if (resolvedPatientAge == null) {
      setAiBlockedReason(
        'AI-анализ недоступен: в snapshot пациента не указан возраст. ' +
        'Проверьте, что у пациента заполнена дата рождения.'
      );
      return;
    }
    if (!resolvedPatientGender) {
      setAiBlockedReason(
        'AI-анализ недоступен: в snapshot пациента не указан пол. ' +
        'Референсные интервалы зависят от пола — интерпретация невозможна.'
      );
      return;
    }
    setAiBlockedReason('');
  }, [activeInstance, hasResults, resolvedPatientAge, resolvedPatientGender]);

  const handleOpenAIAnalysis = () => {
    if (!activeInstance) return;
    if (!hasResults) {
      notify('error', 'Сначала заполните хотя бы один показатель в отчёте.');
      return;
    }
    if (resolvedPatientAge == null || !resolvedPatientGender) {
      notify('error', aiBlockedReason || 'AI-анализ недоступен: проверьте данные пациента');
      return;
    }
    setShowAIAnalysis(true);
  };

  if (!activeInstance) return null;

  return (
    <>
      <AIButton
        text="AI Интерпретация"
        size="small"
        onClick={handleOpenAIAnalysis}
        disabled={!hasResults || Boolean(aiBlockedReason)}
        tooltip={
          aiBlockedReason
          || (hasResults
              ? 'AI интерпретация результатов с учётом возраста и пола пациента'
              : 'Заполните показатели в отчёте для активации AI')
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
                AI Интерпретация результатов отчёта #{activeInstance.id}
              </Typography>
              <Button
                type="button"
                size="small"
                title="Закрыть AI-анализ"
                aria-label="Закрыть AI-анализ"
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
                <strong>Пациент:</strong>{' '}
                {patientSnapshot.full_name || `#${patientSnapshot.patient_id || '?'}`}
                {' · '}
                <strong>Возраст:</strong>{' '}
                {resolvedPatientAge != null ? `${resolvedPatientAge} лет` : 'неизвестен'}
                {' · '}
                <strong>Пол:</strong>{' '}
                {resolvedPatientGender
                  ? ({ male: 'мужской', female: 'женский', other: 'другой' }[resolvedPatientGender] || resolvedPatientGender)
                  : 'не указан'}
                {' · '}
                <strong>Показателей:</strong> {results.length}
              </Typography>
              {(resolvedPatientAge == null || !resolvedPatientGender) && (
                <Typography variant="caption" color="error" component="div" sx={{ mt: 0.5 }}>
                  AI-интерпретация невозможна без возраста и пола пациента.
                </Typography>
              )}
            </Alert>

            <AIAssistant
              analysisType="lab"
              data={{
                results: results.map((r) => ({
                  name: r.name,
                  value: r.value,
                  unit: r.unit,
                  reference: r.reference,
                  flag: r.flag,
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
              Закрыть
            </Button>
          </DialogActions>
        </Dialog>
      )}
    </>
  );
}

LabReportAIAnalysis.propTypes = {
  activeInstance: PropTypes.object,
  notify: PropTypes.func.isRequired,
};
