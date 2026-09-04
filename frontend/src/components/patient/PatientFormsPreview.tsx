
import type { HttpApiError } from '../../types/errors';
import { extractDetailReason } from '../../utils/error-utils';
import { useTranslation } from '../../i18n/useTranslation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Badge, Button, Checkbox, Input, Textarea } from '../ui/macos';
import { useConfirm } from '../common/ConfirmDialog';
import { api } from '../../api/client';
import logger from '../../utils/logger';
import {
  describePatientError,
} from './patientUtils';
import PanelEmptyState from './PanelEmptyState';
import React from "react";
import { AlertTriangle, CheckCircle2, Download, FileText, RotateCw, Send } from 'lucide-react';

interface PatientFormField {
  key: string;
  type: string;
  label: string;
  max_length?: number;
}

interface PatientFormSubmission {
  answers?: Record<string, unknown>;
  status?: string;
  submitted_at?: string;
  updated_at?: string;
}

interface PatientForm {
  id: string | number;
  title: string;
  description?: string;
  fields?: PatientFormField[];
  submission?: PatientFormSubmission;
}

interface PatientFormsPreviewData {
  forms?: PatientForm[];
  policy?: { storage_enabled?: boolean };
  scope?: { patient_id?: number | null };
}

type FormStatus = 'idle' | 'saving-draft' | 'submitting' | 'saved' | 'error';

interface FormState {
  answers: Record<string, boolean | string>;
  status: FormStatus;
  savedStatus: string;
  error: string;
  message: string;
  submittedAt: string;
  updatedAt: string;
}

type HandleSaveFn = (form: PatientForm, nextStatus: 'draft' | 'submitted') => Promise<void>;

interface PatientFormsPreviewProps {
  status: string;
  preview?: PatientFormsPreviewData | null;
  error?: string;
  initData?: string;
}

/**
 * L-H-4 fix: PatientFormsPreview выделен в отдельный файл.
 * L-H-1 fix: все строки на русском.
 * L-H-5 fix: skeleton-loading при загрузке форм.
 * L-H-8 (история, ОТМЕНЕНО Track 3-2): macos-Icon обёртка → lucide refs (§3.3).
 * L-M-1 fix: autosave 30s debounce when dirty + storageEnabled.
 * L-M-9 fix: confirmation dialog для submit (irreversible action).
 * L-M-12 fix: aria-live для loading-state.
 *
 * Protected patient forms: preview → save draft / submit.
 */

const buildInitialFormAnswers = (form: PatientForm): Record<string, boolean | string> => {
  const answers: Record<string, boolean | string> = {};
  const fields = Array.isArray(form?.fields) ? form.fields : [];
  const savedAnswers = form?.submission?.answers && typeof form.submission.answers === 'object'
    ? form.submission.answers
    : {};

  fields.forEach((field) => {
    const savedValue = (savedAnswers as Record<string, unknown>)[field.key];
    if (field.type === 'boolean') {
      answers[field.key] = typeof savedValue === 'boolean' ? savedValue : false;
      return;
    }
    answers[field.key] = typeof savedValue === 'string' ? savedValue : '';
  });

  return answers;
};

const buildInitialFormState = (form: PatientForm): FormState => ({
  answers: buildInitialFormAnswers(form),
  status: 'idle',
  savedStatus: form?.submission?.status || '',
  error: '',
  message: '',
  submittedAt: form?.submission?.submitted_at || '',
  updatedAt: form?.submission?.updated_at || '',
});

function PatientFormsPreview({ status, preview = null, error = '', initData = '' }: PatientFormsPreviewProps) {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [formState, setFormState] = useState<Record<string, FormState>>({});
  const [autoSaveTimestamps, setAutoSaveTimestamps] = useState<Record<string, Date>>({});
  const [autoSavingForms, setAutoSavingForms] = useState<Record<string, boolean>>({});
  const autoSaveTimersRef = useRef<Record<string, ReturnType<typeof setTimeout> | null>>({});
  const handleSaveRef = useRef<HandleSaveFn | null>(null);

  // L-M-9 fix: useConfirm для submit-confirmation
  const [confirm, confirmDialog] = useConfirm();

  // L-M-6 fix: forms вычисляется через useMemo (было inline — вызывало
  // react-hooks/exhaustive-deps warning в autosave useEffect).
  const forms = useMemo(
    () => Array.isArray(preview?.forms) ? preview.forms : [],
    [preview]
  );
  const storageEnabled = preview?.policy?.storage_enabled === true;
  const patientId = preview?.scope?.patient_id || null;

  useEffect(() => {
    const nextState: Record<string, FormState> = {};
    forms.forEach((form) => {
      nextState[form.id] = buildInitialFormState(form);
    });
    setFormState(nextState);
  }, [forms]);

  // ─── handleSave (defined before early returns — hooks rules) ────────────
  const handleSave = useCallback(async (form: PatientForm, nextStatus: 'draft' | 'submitted') => {
    const currentForm = formState[form.id] || buildInitialFormState(form);

    // L-M-9 fix: confirmation dialog для submit (irreversible action).
    if (nextStatus === 'submitted') {
      const ok = await (confirm as unknown as (opts: Record<string, unknown>) => Promise<boolean>)({
        title: t('patient.pat_forms_submit_title'),
        message: t('patient.pat_forms_submit_message'),
        description: t('patient.pat_forms_submit_description'),
        confirmLabel: t('patient.pat_forms_submit_confirm'),
        cancelLabel: t('misc.cancel'),
        intent: 'primary',
      });
      if (!ok) return;
    }

    setFormState((current) => ({
      ...current,
      [form.id]: {
        ...(current[form.id] || currentForm),
        status: nextStatus === 'draft' ? 'saving-draft' : 'submitting',
        error: '',
        message: '',
      } as FormState,
    }));

    try {
      const response = await api.post('/telegram/mini-app/forms/submissions', {
        initData,
        patientId,
        formId: form.id,
        answers: currentForm.answers,
        status: nextStatus,
      });
      const submission = response.data?.submission || {};

      setFormState((current) => ({
        ...current,
        [form.id]: {
          ...(current[form.id] || currentForm),
          answers: {
            ...buildInitialFormAnswers(form),
            ...(submission.answers || currentForm.answers),
          },
          status: 'saved',
          savedStatus: submission.status || '',
          error: '',
          message: submission.status === 'draft' ? t('patient.pat_forms_draft_saved') : t('patient.pat_forms_submitted'),
          submittedAt: submission.submitted_at || '',
          updatedAt: submission.updated_at || '',
        } as FormState,
      }));

      if (nextStatus === 'draft') {
        setAutoSaveTimestamps((current) => ({ ...current, [form.id]: new Date() }));
      }
    } catch (err) {
      const reason = extractDetailReason(err) || 'patient_form_save_failed';
      setFormState((current) => ({
        ...current,
        [form.id]: {
          ...(current[form.id] || currentForm),
          status: 'error',
          error: describePatientError('forms', reason),
          message: '',
        } as FormState,
      }));
    }
  }, [formState, initData, patientId, confirm, t]);

  // L-M-1 fix: обновляем ref для autosave-timer.
  handleSaveRef.current = handleSave;

  // L-M-1 fix: autosave — 30s debounce. Все hooks ВЫЗВАНЫ до early returns.
  useEffect(() => {
    if (!storageEnabled || !initData || forms.length === 0) return;

    const timers = autoSaveTimersRef.current;
    forms.forEach((form) => {
      const currentFormState = formState[form.id];
      if (!currentFormState) return;
      if (currentFormState.savedStatus === 'submitted') return;
      if (currentFormState.status === 'saving-draft' || currentFormState.status === 'submitting') return;

      const existingTimer = timers[form.id];
      if (existingTimer) clearTimeout(existingTimer);

      timers[form.id] = setTimeout(async () => {
        if (handleSaveRef.current) {
          try {
            setAutoSavingForms((current) => ({ ...current, [form.id]: true }));
            await handleSaveRef.current(form, 'draft');
          } catch (e) {
            logger.warn('[PatientForms] autosave failed:', e);
          } finally {
            setAutoSavingForms((current) => ({ ...current, [form.id]: false }));
          }
        }
      }, 30000);
    });

    return () => {
      Object.values(timers).forEach((t) => {
        if (t) clearTimeout(t);
      });
    };
  }, [formState, forms, storageEnabled, initData]);

  // ─── Early returns (after all hooks) ────────────────────────────────────
  if (status === 'missing-init-data') {
    return (
      <PanelEmptyState
        icon={FileText}
        title={t('patient.pat_forms_missing_init_title')}
        description={t('patient.pat_forms_missing_init_desc')}
      />
    );
  }

  if (status === 'loading') {
    return (
      <PanelEmptyState
        icon={FileText}
        title={t('patient.pat_forms_loading_title')}
        description={t('patient.pat_forms_loading_desc')}
        variant="loading"
      />
    );
  }

  if (status === 'error') {
    return (
      <PanelEmptyState
        icon={AlertTriangle}
        title={t('patient.pat_forms_error_title')}
        description={error || t('patient.pat_forms_error_desc')}
        variant="error"
      />
    );
  }

  if (forms.length === 0) {
    return (
      <PanelEmptyState
        icon={FileText}
        title={t('patient.pat_forms_no_forms_title')}
        description={t('patient.pat_forms_no_forms_desc')}
      />
    );
  }

  // ─── Render ─────────────────────────────────────────────────────────────
  const handleFieldChange = (formId: string | number, field: PatientFormField, value: string | boolean) => {
    setFormState((current) => ({
      ...current,
      [formId]: {
        ...(current[formId] || buildInitialFormState({ id: formId } as PatientForm)),
        answers: {
          ...((current[formId] as FormState | undefined)?.answers || {}),
          [field.key]: field.type === 'boolean' ? Boolean(value) : value,
        },
        error: '',
        message: '',
      },
    }));
  };

  return (
    <div className="pp-forms-root">
      {/* L-L-7 fix: progress-indicator для multi-form.
          Показывает «Анкета N из M» если форм больше одной. */}
      {forms.length > 1 && (
        <div className="pp-forms-progress" aria-label={t('patient.pat_forms_progress_aria')}>
          <FileText size={14} aria-hidden="true" />
          <span>{t('patient.pat_forms_available', { count: forms.length })}</span>
          <span className="pp-forms-progress-separator">·</span>
          <span>
            {t('patient.pat_forms_filled', { count: forms.filter((f) => {
              const s = formState[f.id]?.savedStatus;
              return s === 'submitted' || s === 'draft';
            }).length })}
          </span>
        </div>
      )}
      {forms.map((form) => {
        const currentFormState = formState[form.id] || buildInitialFormState(form);
        const isFormBusy = currentFormState.status === 'saving-draft' || currentFormState.status === 'submitting';

        return (
          <div key={form.id} className="pp-card">
            <div className="pp-card-header">
              <div>
                <div className="pp-card-title">{form.title}</div>
                <p className="pp-card-subtitle">{form.description}</p>
              </div>
              <div className="pp-badges-row">
                {currentFormState.savedStatus && (
                  <Badge variant={currentFormState.savedStatus === 'submitted' ? 'success' : 'info'}>
                    {currentFormState.savedStatus === 'submitted' ? t('patient.pat_forms_badge_submitted') : t('patient.pat_forms_badge_draft')}
                  </Badge>
                )}
                <Badge variant={storageEnabled ? 'success' : 'warning'}>
                  {storageEnabled ? t('patient.pat_forms_storage_on') : t('patient.pat_forms_storage_off')}
                </Badge>
              </div>
            </div>
            <div className="pp-card-body pp-grid-2">
              {(form.fields || []).map((field) => {
                const fieldValue = currentFormState.answers?.[field.key];

                return (
                  <div key={field.key} className={field.type === 'textarea' ? 'pp-grid-span-2' : ''}>
                    {field.type === 'boolean' ? (
                      <Checkbox
                        id={`patient-form-${form.id}-${field.key}`}
                        checked={Boolean(fieldValue)}
                        disabled={!storageEnabled}
                        label={field.label}
                        description={storageEnabled ? t('patient.pat_forms_field_storage_on') : t('patient.pat_forms_field_storage_off')}
                        onChange={(checked) => handleFieldChange(form.id, field, checked)}
                      />
                    ) : field.type === 'textarea' ? (
                      <Textarea
                        id={`patient-form-${form.id}-${field.key}`}
                        label={field.label}
                        value={typeof fieldValue === 'string' ? fieldValue : ''}
                        disabled={!storageEnabled}
                        minRows={3}
                        maxRows={8}
                        maxLength={field.max_length || undefined}
                        placeholder={t('patient.pat_forms_input_placeholder')}
                        onChange={(event) => handleFieldChange(form.id, field, event.target.value)}
                      />
                    ) : (
                      <Input
                        id={`patient-form-${form.id}-${field.key}`}
                        label={field.label}
                        value={typeof fieldValue === 'string' ? fieldValue : ''}
                        disabled={!storageEnabled}
                        maxLength={field.max_length || undefined}
                        placeholder={t('patient.pat_forms_input_placeholder')}
                        onChange={(event) => handleFieldChange(form.id, field, event.target.value)}
                      />
                    )}
                  </div>
                );
              })}
              <div className="pp-grid-span-2 pp-form-footer">
                {currentFormState.message && (
                  <div className="pp-message pp-message--success" role="status">
                    <CheckCircle2 size={16} aria-hidden="true" />
                    {currentFormState.message}
                  </div>
                )}
                {currentFormState.error && (
                  <div className="pp-message pp-message--error" role="alert">
                    <AlertTriangle size={16} aria-hidden="true" />
                    {currentFormState.error}
                  </div>
                )}
                {currentFormState.updatedAt && (
                  <div className="pp-form-timestamp">
                    {t('patient.pat_forms_last_saved', { time: currentFormState.updatedAt })}
                  </div>
                )}
                {/* L-M-1 fix: autosave indicator */}
                {autoSavingForms[form.id] && (
                  <div className="pp-form-autosave-indicator" aria-live="polite">
                    <RotateCw size={12} aria-hidden="true" />
                    {t('patient.pat_forms_autosaving')}
                  </div>
                )}
                {!autoSavingForms[form.id] && autoSaveTimestamps[form.id] && (
                  <div className="pp-form-autosave-timestamp">
                    <CheckCircle2 size={12} aria-hidden="true" />
                    {t('patient.pat_forms_saved_at', { time: autoSaveTimestamps[form.id].toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }) })}
                  </div>
                )}
                <div className="pp-actions-row">
                  <Button
                    variant="outline"
                    size="small"
                    disabled={!storageEnabled || !initData || isFormBusy}
                    loading={currentFormState.status === 'saving-draft'}
                    onClick={() => handleSave(form, 'draft')}
                  >
                    <Download size={16} aria-hidden="true" />
                    {t('patient.pat_forms_save_draft')}
                  </Button>
                  <Button
                    variant="primary"
                    size="small"
                    disabled={!storageEnabled || !initData || isFormBusy}
                    loading={currentFormState.status === 'submitting'}
                    onClick={() => handleSave(form, 'submitted')}
                  >
                    <Send size={16} aria-hidden="true" />
                    {t('patient.pat_forms_submit_button')}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        );
      })}
      {/* L-M-9 fix: portal-mounted ConfirmDialog */}
      {confirmDialog}
    </div>
  );
}



export default PatientFormsPreview;
