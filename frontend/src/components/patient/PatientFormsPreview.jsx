import { useTranslation } from '../../i18n/useTranslation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Badge, Button, Checkbox, Icon, Input, Textarea,
} from '../ui/macos';
import { useConfirm } from '../common/ConfirmDialog';
import { api } from '../../api/client';
import logger from '../../utils/logger';
import {
  describePatientError,
} from './patientUtils';
import PanelEmptyState from './PanelEmptyState';

/**
 * L-H-4 fix: PatientFormsPreview выделен в отдельный файл.
 * L-H-1 fix: все строки на русском.
 * L-H-5 fix: skeleton-loading при загрузке форм.
 * L-H-8 fix: lucide-direct → macos <Icon>.
 * L-M-1 fix: autosave 30s debounce when dirty + storageEnabled.
 * L-M-9 fix: confirmation dialog для submit (irreversible action).
 * L-M-12 fix: aria-live для loading-state.
 *
 * Protected patient forms: preview → save draft / submit.
 */

const buildInitialFormAnswers = (form) => {
  const answers = {};
  const fields = Array.isArray(form?.fields) ? form.fields : [];
  const savedAnswers = form?.submission?.answers && typeof form.submission.answers === 'object'
    ? form.submission.answers
    : {};

  fields.forEach((field) => {
    const savedValue = savedAnswers[field.key];
    if (field.type === 'boolean') {
      answers[field.key] = typeof savedValue === 'boolean' ? savedValue : false;
      return;
    }
    answers[field.key] = typeof savedValue === 'string' ? savedValue : '';
  });

  return answers;
};

const buildInitialFormState = (form) => ({
  answers: buildInitialFormAnswers(form),
  status: 'idle',
  savedStatus: form?.submission?.status || '',
  error: '',
  message: '',
  submittedAt: form?.submission?.submitted_at || '',
  updatedAt: form?.submission?.updated_at || '',
});

function PatientFormsPreview({ status, preview = null, error = '', initData = '' }) {
  const { t } = useTranslation();
  const [formState, setFormState] = useState({});
  const [autoSaveTimestamps, setAutoSaveTimestamps] = useState({});
  const [autoSavingForms, setAutoSavingForms] = useState({});
  const autoSaveTimersRef = useRef({});
  const handleSaveRef = useRef(null);

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
    const nextState = {};
    forms.forEach((form) => {
      nextState[form.id] = buildInitialFormState(form);
    });
    setFormState(nextState);
  }, [forms]);

  // ─── handleSave (defined before early returns — hooks rules) ────────────
  const handleSave = useCallback(async (form, nextStatus) => {
    const currentForm = formState[form.id] || buildInitialFormState(form);

    // L-M-9 fix: confirmation dialog для submit (irreversible action).
    if (nextStatus === 'submitted') {
      const ok = await confirm({
        title: 'Отправка анкеты',
        message: 'После отправки изменения будут заблокированы.',
        description: 'Для редактирования отправленной анкеты потребуется обратиться в клинику. Действие нельзя отменить.',
        confirmLabel: 'Отправить',
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
      },
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
          message: submission.status === 'draft' ? 'Черновик сохранён.' : 'Анкета отправлена.',
          submittedAt: submission.submitted_at || '',
          updatedAt: submission.updated_at || '',
        },
      }));

      if (nextStatus === 'draft') {
        setAutoSaveTimestamps((current) => ({ ...current, [form.id]: new Date() }));
      }
    } catch (err) {
      const reason = err?.response?.data?.detail?.reason || 'patient_form_save_failed';
      setFormState((current) => ({
        ...current,
        [form.id]: {
          ...(current[form.id] || currentForm),
          status: 'error',
          error: describePatientError('forms', reason),
          message: '',
        },
      }));
    }
  }, [formState, initData, patientId, confirm]);

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

      if (timers[form.id]) clearTimeout(timers[form.id]);

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
      Object.values(timers).forEach((t) => clearTimeout(t));
    };
  }, [formState, forms, storageEnabled, initData]);

  // ─── Early returns (after all hooks) ────────────────────────────────────
  if (status === 'missing-init-data') {
    return (
      <PanelEmptyState
        icon="doc.text"
        title="Откройте из Telegram"
        description="Защищённые анкеты требуют Telegram Mini App identity перед показом данных пациента."
      />
    );
  }

  if (status === 'loading') {
    return (
      <PanelEmptyState
        icon="doc.text"
        title="Загрузка анкет…"
        description="Проверяем защищённый Telegram Mini App identity."
        variant="loading"
      />
    );
  }

  if (status === 'error') {
    return (
      <PanelEmptyState
        icon="exclamationmark.triangle"
        title="Анкеты недоступны"
        description={error || 'Не удалось загрузить защищённые анкеты пациента.'}
        variant="error"
      />
    );
  }

  if (forms.length === 0) {
    return (
      <PanelEmptyState
        icon="doc.text"
        title="Нет доступных анкет"
        description="Защищённые анкеты пациента ещё не настроены."
      />
    );
  }

  // ─── Render ─────────────────────────────────────────────────────────────
  const handleFieldChange = (formId, field, value) => {
    setFormState((current) => ({
      ...current,
      [formId]: {
        ...(current[formId] || {}),
        answers: {
          ...(current[formId]?.answers || {}),
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
        <div className="pp-forms-progress" aria-label="Прогресс заполнения анкет">
          <Icon name="doc.text" size={14} />
          <span>Анкет доступно: {forms.length}</span>
          <span className="pp-forms-progress-separator">·</span>
          <span>
            Заполнено: {forms.filter((f) => {
              const s = formState[f.id]?.savedStatus;
              return s === 'submitted' || s === 'draft';
            }).length}
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
                    {currentFormState.savedStatus === 'submitted' ? 'Отправлена' : 'Черновик сохранён'}
                  </Badge>
                )}
                <Badge variant={storageEnabled ? 'success' : 'warning'}>
                  {storageEnabled ? 'Защищённое хранилище включено' : 'Только чтение'}
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
                        description={storageEnabled ? 'Включено в защищённую отправку Mini App.' : 'Защищённый ввод не включён.'}
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
                        placeholder="Введите данные в защищённом Mini App."
                        onChange={(event) => handleFieldChange(form.id, field, event.target.value)}
                      />
                    ) : (
                      <Input
                        id={`patient-form-${form.id}-${field.key}`}
                        label={field.label}
                        value={typeof fieldValue === 'string' ? fieldValue : ''}
                        disabled={!storageEnabled}
                        maxLength={field.max_length || undefined}
                        placeholder="Введите данные в защищённом Mini App."
                        onChange={(event) => handleFieldChange(form.id, field, event.target.value)}
                      />
                    )}
                  </div>
                );
              })}
              <div className="pp-grid-span-2 pp-form-footer">
                {currentFormState.message && (
                  <div className="pp-message pp-message--success" role="status">
                    <Icon name="checkmark.circle" size={16} />
                    {currentFormState.message}
                  </div>
                )}
                {currentFormState.error && (
                  <div className="pp-message pp-message--error" role="alert">
                    <Icon name="exclamationmark.triangle" size={16} />
                    {currentFormState.error}
                  </div>
                )}
                {currentFormState.updatedAt && (
                  <div className="pp-form-timestamp">
                    Последнее сохранение: {currentFormState.updatedAt}
                  </div>
                )}
                {/* L-M-1 fix: autosave indicator */}
                {autoSavingForms[form.id] && (
                  <div className="pp-form-autosave-indicator" aria-live="polite">
                    <Icon name="arrow.clockwise" size={12} />
                    Автосохранение…
                  </div>
                )}
                {!autoSavingForms[form.id] && autoSaveTimestamps[form.id] && (
                  <div className="pp-form-autosave-timestamp">
                    <Icon name="checkmark.circle" size={12} />
                    Сохранено {autoSaveTimestamps[form.id].toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
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
                    <Icon name="square.and.arrow.down" size={16} />
                    Сохранить черновик
                  </Button>
                  <Button
                    variant="primary"
                    size="small"
                    disabled={!storageEnabled || !initData || isFormBusy}
                    loading={currentFormState.status === 'submitting'}
                    onClick={() => handleSave(form, 'submitted')}
                  >
                    <Icon name="paperplane" size={16} />
                    Отправить анкету
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

PatientFormsPreview.propTypes = {
  status: PropTypes.string.isRequired,
  preview: PropTypes.shape({
    forms: PropTypes.array,
    policy: PropTypes.shape({
      storage_enabled: PropTypes.bool,
    }),
    scope: PropTypes.shape({
      patient_id: PropTypes.number,
    }),
  }),
  error: PropTypes.string,
  initData: PropTypes.string,
};


export default PatientFormsPreview;
