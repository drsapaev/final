import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Card, Button, Badge, Icon, Input, Textarea, Checkbox } from '../components/ui/macos';
import { useBreakpoint } from '../hooks/useEnhancedMediaQuery';
import { Calendar, Heart, FileText, ClipboardList, Save, Send } from 'lucide-react';
import PropTypes from 'prop-types';
import { api } from '../api/client';

const PanelEmptyState = ({ icon: EmptyIcon, title, description }) => (
  <div className="p-6 border border-dashed border-gray-300 rounded-lg text-center bg-white/60">
    <EmptyIcon className="w-8 h-8 mx-auto mb-3 text-gray-400" aria-hidden="true" />
    <div className="font-medium text-gray-900">{title}</div>
    <p className="mt-1 text-sm text-gray-500">{description}</p>
  </div>
);

PanelEmptyState.propTypes = {
  icon: PropTypes.elementType.isRequired,
  title: PropTypes.string.isRequired,
  description: PropTypes.string.isRequired,
};

const patientSections = {
  forms: {
    icon: ClipboardList,
    title: 'Patient Forms',
    description: 'This part is prepared for protected forms flow and will be completed in the Mini App runtime.',
  },
  documents: {
    icon: FileText,
    title: 'Documents',
    description: 'Protected documents flow is not yet fully implemented. Use clinic contact to request copies.',
  },
  doctors: {
    icon: ClipboardList,
    title: 'Doctors',
    description: 'Protected doctor selection and booking continuation are under Mini App rollout.',
  },
  cabinet: {
    icon: FileText,
    title: 'Cabinet',
    description: 'Protected personal cabinet is currently in progress and will open from Mini App entry.',
  },
};

const normalizeSection = (value) => {
  if (!value) {
    return 'home';
  }
  return patientSections[String(value).toLowerCase()] ? String(value).toLowerCase() : 'home';
};

const readTelegramMiniAppInitData = () => {
  if (typeof window === 'undefined') {
    return '';
  }
  const initData = window.Telegram?.WebApp?.initData;
  return typeof initData === 'string' ? initData.trim() : '';
};

const buildInitialPatientFormAnswers = (form) => {
  const answers = {};
  const fields = Array.isArray(form?.fields) ? form.fields : [];

  fields.forEach((field) => {
    answers[field.key] = field.type === 'boolean' ? false : '';
  });

  return answers;
};

const patientFormErrorMessages = {
  patient_form_answer_unknown_field: 'The form changed. Reload the Mini App and try again.',
  patient_form_answer_type_invalid: 'One answer has an invalid value. Check the form and try again.',
  patient_form_answer_too_long: 'One answer is too long. Shorten it and try again.',
  patient_form_answer_required: 'A required answer is missing.',
  patient_scope_mismatch: 'This form does not belong to the linked patient.',
};

const describePatientFormError = (reason) => (
  patientFormErrorMessages[reason] || 'The form could not be saved. Try again from Telegram.'
);

const PatientFormsPreview = ({ status, preview, error, initData }) => {
  const [formState, setFormState] = useState({});

  useEffect(() => {
    const forms = Array.isArray(preview?.forms) ? preview.forms : [];
    const nextState = {};

    forms.forEach((form) => {
      nextState[form.id] = {
        answers: buildInitialPatientFormAnswers(form),
        status: 'idle',
        error: '',
        message: '',
        submittedAt: '',
        updatedAt: '',
      };
    });

    setFormState(nextState);
  }, [preview]);

  if (status === 'missing-init-data') {
    return (
      <PanelEmptyState
        icon={ClipboardList}
        title="Open from Telegram"
        description="Protected forms require Telegram Mini App identity before patient data can be shown."
      />
    );
  }

  if (status === 'loading') {
    return (
      <PanelEmptyState
        icon={ClipboardList}
        title="Loading forms"
        description="Checking protected Telegram Mini App identity."
      />
    );
  }

  if (status === 'error') {
    return (
      <PanelEmptyState
        icon={ClipboardList}
        title="Forms unavailable"
        description={error || 'Protected patient forms could not be loaded.'}
      />
    );
  }

  const forms = Array.isArray(preview?.forms) ? preview.forms : [];
  const storageEnabled = preview?.policy?.storage_enabled === true;
  const patientId = preview?.scope?.patient_id || null;
  if (forms.length === 0) {
    return (
      <PanelEmptyState
        icon={ClipboardList}
        title="No forms available"
        description="No protected patient intake forms are configured yet."
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
    const currentForm = formState[form.id] || {
      answers: buildInitialPatientFormAnswers(form),
    };

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
            ...buildInitialPatientFormAnswers(form),
            ...(submission.answers || currentForm.answers),
          },
          status: 'saved',
          error: '',
          message: submission.status === 'draft' ? 'Draft saved.' : 'Form submitted.',
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
          error: describePatientFormError(reason),
          message: '',
        },
      }));
    }
  };

  return (
    <div className="space-y-4">
      {forms.map((form) => (
        <div key={form.id} className="border border-gray-200 rounded-lg overflow-hidden bg-white">
          <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <div className="font-medium text-gray-900">{form.title}</div>
              <p className="mt-1 text-sm text-gray-500">{form.description}</p>
            </div>
            <Badge variant={storageEnabled ? 'success' : 'warning'}>
              {storageEnabled ? 'Secure storage on' : 'Read only'}
            </Badge>
          </div>
          <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
            {(form.fields || []).map((field) => {
              const current = formState[form.id] || { answers: buildInitialPatientFormAnswers(form) };
              const fieldValue = current.answers?.[field.key];

              return (
                <div key={field.key} className={field.type === 'textarea' ? 'md:col-span-2' : ''}>
                {field.type === 'boolean' ? (
                  <Checkbox
                    id={`patient-form-${form.id}-${field.key}`}
                    checked={Boolean(fieldValue)}
                    disabled={!storageEnabled}
                    label={field.label}
                    description={storageEnabled ? 'Included in protected Mini App submission.' : 'Protected entry is not enabled.'}
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
                    placeholder="Enter details inside the protected Mini App."
                    onChange={(event) => handleFieldChange(form.id, field, event.target.value)}
                  />
                ) : (
                  <Input
                    id={`patient-form-${form.id}-${field.key}`}
                    label={field.label}
                    value={typeof fieldValue === 'string' ? fieldValue : ''}
                    disabled={!storageEnabled}
                    maxLength={field.max_length || undefined}
                    placeholder="Enter details inside the protected Mini App."
                    onChange={(event) => handleFieldChange(form.id, field, event.target.value)}
                  />
                )}
                </div>
              );
            })}
            <div className="md:col-span-2 flex flex-col gap-3 border-t border-gray-100 pt-4">
              {formState[form.id]?.message && (
                <div className="text-sm text-green-700" role="status">
                  {formState[form.id].message}
                </div>
              )}
              {formState[form.id]?.error && (
                <div className="text-sm text-red-700" role="alert">
                  {formState[form.id].error}
                </div>
              )}
              {formState[form.id]?.updatedAt && (
                <div className="text-xs text-gray-500">
                  Last saved: {formState[form.id].updatedAt}
                </div>
              )}
              <div className="flex flex-col sm:flex-row gap-2 sm:justify-end">
                <Button
                  variant="secondary"
                  size="small"
                  disabled={!storageEnabled || !initData || formState[form.id]?.status === 'saving-draft' || formState[form.id]?.status === 'submitting'}
                  loading={formState[form.id]?.status === 'saving-draft'}
                  onClick={() => handleSave(form, 'draft')}
                >
                  <Save className="w-4 h-4" aria-hidden="true" />
                  Save draft
                </Button>
                <Button
                  variant="primary"
                  size="small"
                  disabled={!storageEnabled || !initData || formState[form.id]?.status === 'saving-draft' || formState[form.id]?.status === 'submitting'}
                  loading={formState[form.id]?.status === 'submitting'}
                  onClick={() => handleSave(form, 'submitted')}
                >
                  <Send className="w-4 h-4" aria-hidden="true" />
                  Submit form
                </Button>
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

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

const PatientPanel = () => {
  useBreakpoint();
  const [query, setQuery] = useState('');
  const [searchParams] = useSearchParams();
  const activeSection = normalizeSection(searchParams.get('tab'));
  const [formsPreview, setFormsPreview] = useState(null);
  const [formsStatus, setFormsStatus] = useState('idle');
  const [formsError, setFormsError] = useState('');
  const [formsInitData, setFormsInitData] = useState('');
  const appointments = [];
  const results = [];
  const hasPatientData = appointments.length > 0 || results.length > 0;

  const sectionConfig = patientSections[activeSection];
  const isSectionMode = Boolean(sectionConfig);
  const sectionTitle = sectionConfig?.title || 'Patient Home';

  useEffect(() => {
    if (activeSection !== 'forms') {
      setFormsStatus('idle');
      setFormsPreview(null);
      setFormsError('');
      setFormsInitData('');
      return undefined;
    }

    const initData = readTelegramMiniAppInitData();
    if (!initData) {
      setFormsStatus('missing-init-data');
      setFormsPreview(null);
      setFormsError('');
      setFormsInitData('');
      return undefined;
    }

    let cancelled = false;
    setFormsStatus('loading');
    setFormsError('');
    setFormsPreview(null);
    setFormsInitData(initData);

    api.post('/telegram/mini-app/forms/preview', { initData })
      .then((response) => {
        if (cancelled) {
          return;
        }
        setFormsPreview(response.data);
        setFormsStatus('ready');
      })
      .catch((err) => {
        if (cancelled) {
          return;
        }
        const reason = err?.response?.data?.detail?.reason || 'forms_preview_failed';
        setFormsError(reason);
        setFormsStatus('error');
      });

    return () => {
      cancelled = true;
    };
  }, [activeSection]);

  return (
    <div
      style={{
        padding: '0px',
        background: 'var(--mac-gradient-window)',
        minHeight: '100vh',
        fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
        color: 'var(--mac-text-primary)',
      }}
    >
      <div style={{ maxWidth: '1200px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <Card
          style={{
            backgroundColor: 'var(--mac-bg-primary)',
            border: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-lg)',
            padding: '16px',
            boxShadow: 'var(--mac-shadow-sm)',
            backdropFilter: 'var(--mac-blur-light)',
            WebkitBackdropFilter: 'var(--mac-blur-light)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ position: 'relative', flex: 1 }}>
              <Icon
                name="magnifyingglass"
                size="small"
                style={{
                  position: 'absolute',
                  left: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: 'var(--mac-text-tertiary)',
                }}
              />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                disabled={!hasPatientData}
                style={{
                  width: '100%',
                  padding: '12px 12px 12px 40px',
                  border: '1px solid var(--mac-border)',
                  borderRadius: 'var(--mac-radius-md)',
                  backgroundColor: 'var(--mac-bg-secondary)',
                  color: 'var(--mac-text-primary)',
                  fontSize: 'var(--mac-font-size-base)',
                  fontFamily: 'inherit',
                  outline: 'none',
                  transition: 'border-color var(--mac-duration-normal) var(--mac-ease)',
                  opacity: hasPatientData ? 1 : 0.65,
                }}
                placeholder={
                  hasPatientData
                    ? 'Search patient records or use quick actions from links'
                    : 'Patient records are not loaded yet'
                }
                onFocus={(e) => {
                  e.target.style.borderColor = 'var(--mac-accent-blue)';
                }}
                onBlur={(e) => {
                  e.target.style.borderColor = 'var(--mac-border)';
                }}
              />
            </div>
            <Button variant="secondary" disabled title="Quick action is disabled until data is available">
              <Icon name="plus" size="small" />
              Add Quick Action
            </Button>
          </div>
        </Card>

        {isSectionMode ? (
          <Card className="p-0 overflow-hidden" data-testid={`patient-section-${activeSection}`}>
            <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center gap-2">
              <sectionConfig.icon className="w-4 h-4" />
              <h3 className="font-medium text-gray-900">{sectionTitle}</h3>
            </div>
            <div className="p-4">
              {activeSection === 'forms' ? (
                <PatientFormsPreview
                  status={formsStatus}
                  preview={formsPreview}
                  error={formsError}
                  initData={formsInitData}
                />
              ) : (
                <PanelEmptyState
                  icon={sectionConfig.icon}
                  title={sectionConfig.title}
                  description={sectionConfig.description}
                />
              )}
            </div>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card className="p-0 overflow-hidden">
              <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center gap-2">
                <Calendar className="w-4 h-4" />
                <h3 className="font-medium text-gray-900">Upcoming Visits</h3>
              </div>
              <div className="p-4">
                {appointments.length > 0 ? (
                  <div className="space-y-4">
                    {appointments.map((a) => (
                      <div key={a.id} className="p-4 border border-gray-200 rounded-lg flex items-center justify-between">
                        <div>
                          <div className="font-medium text-gray-900">{a.doctor}</div>
                          <div className="text-sm text-gray-500">{a.date} · {a.time}</div>
                        </div>
                        <Badge variant={a.status === 'scheduled' ? 'info' : 'success'}>
                          {a.status === 'scheduled' ? 'Scheduled' : 'Completed'}
                        </Badge>
                      </div>
                    ))}
                  </div>
                ) : (
                  <PanelEmptyState
                    icon={Calendar}
                    title="No visits yet"
                    description="Add a visit after linking with clinic booking or registration team."
                  />
                )}
              </div>
            </Card>

            <Card className="p-0 overflow-hidden">
              <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center gap-2">
                <Heart className="w-4 h-4" />
                <h3 className="font-medium text-gray-900">Lab Results</h3>
              </div>
              <div className="p-4">
                {results.length > 0 ? (
                  <div className="space-y-4">
                    {results.map((r) => (
                      <div
                        key={r.id}
                        className="p-4 border border-gray-200 rounded-lg flex items-center justify-between"
                      >
                        <div>
                          <div className="font-medium text-gray-900">{r.title}</div>
                          <div className="text-sm text-gray-500">{r.date}</div>
                        </div>
                        <Button variant="outline" size="sm">
                          <FileText className="w-4 h-4 mr-2" />
                          Open
                        </Button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <PanelEmptyState
                    icon={FileText}
                    title="No results yet"
                    description="Use the protected report link once results are ready."
                  />
                )}
              </div>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
};

export default PatientPanel;
