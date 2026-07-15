import { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Badge, Button, Checkbox, Icon, Input, Textarea,
} from '../ui/macos';
import { api } from '../../api/client';
import {
  describePatientError,
} from './patientUtils';
import PanelEmptyState from './PanelEmptyState';

/**
 * L-H-4 fix: PatientFormsPreview выделен в отдельный файл (~180 строк).
 *
 * L-H-1 fix: все строки на русском.
 * L-H-2 fix: Tailwind classes → CSS-классы .pp-*
 * L-H-5 fix: skeleton-loading при загрузке форм.
 * L-H-8 fix: lucide-direct → macos <Icon>.
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

function PatientFormsPreview({ status, preview, error, initData }) {
  const [formState, setFormState] = useState({});

  useEffect(() => {
    const forms = Array.isArray(preview?.forms) ? preview.forms : [];
    const nextState = {};

    forms.forEach((form) => {
      nextState[form.id] = buildInitialFormState(form);
    });

    setFormState(nextState);
  }, [preview]);

  // L-H-5 fix: skeleton-loading
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

  const forms = Array.isArray(preview?.forms) ? preview.forms : [];
  const storageEnabled = preview?.policy?.storage_enabled === true;
  const patientId = preview?.scope?.patient_id || null;

  if (forms.length === 0) {
    return (
      <PanelEmptyState
        icon="doc.text"
        title="Нет доступных анкет"
        description="Защищённые анкеты пациента ещё не настроены."
      />
    );
  }

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

  const handleSave = async (form, nextStatus) => {
    const currentForm = formState[form.id] || buildInitialFormState(form);

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
  };

  return (
    <div className="pp-forms-root">
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

PatientFormsPreview.defaultProps = {
  preview: null,
  error: '',
  initData: '',
};

export default PatientFormsPreview;
