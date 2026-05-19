import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Card, Button, Badge, Icon } from '../components/ui/macos';
import { useBreakpoint } from '../hooks/useEnhancedMediaQuery';
import { Calendar, Heart, FileText, ClipboardList } from 'lucide-react';
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

const PatientFormsPreview = ({ status, preview, error }) => {
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
  if (forms.length === 0) {
    return (
      <PanelEmptyState
        icon={ClipboardList}
        title="No forms available"
        description="No protected patient intake forms are configured yet."
      />
    );
  }

  return (
    <div className="space-y-4">
      {forms.map((form) => (
        <div key={form.id} className="border border-gray-200 rounded-lg overflow-hidden bg-white">
          <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
            <div className="font-medium text-gray-900">{form.title}</div>
            <p className="mt-1 text-sm text-gray-500">{form.description}</p>
          </div>
          <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
            {(form.fields || []).map((field) => (
              <label key={field.key} className={field.type === 'textarea' ? 'md:col-span-2' : ''}>
                <span className="block text-sm font-medium text-gray-700">{field.label}</span>
                {field.type === 'boolean' ? (
                  <div className="mt-2 flex items-center gap-2 text-sm text-gray-600">
                    <input type="checkbox" disabled className="h-4 w-4 rounded border-gray-300" />
                    <span>Not selected</span>
                  </div>
                ) : (
                  <textarea
                    disabled
                    rows={field.type === 'textarea' ? 3 : 1}
                    maxLength={field.max_length || undefined}
                    className="mt-2 w-full rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-500"
                    placeholder="Protected entry is disabled until secure storage is enabled."
                  />
                )}
              </label>
            ))}
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
  }),
  error: PropTypes.string,
};

PatientFormsPreview.defaultProps = {
  preview: null,
  error: '',
};

const PatientPanel = () => {
  useBreakpoint();
  const [query, setQuery] = useState('');
  const [searchParams] = useSearchParams();
  const activeSection = normalizeSection(searchParams.get('tab'));
  const [formsPreview, setFormsPreview] = useState(null);
  const [formsStatus, setFormsStatus] = useState('idle');
  const [formsError, setFormsError] = useState('');
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
      return undefined;
    }

    const initData = readTelegramMiniAppInitData();
    if (!initData) {
      setFormsStatus('missing-init-data');
      setFormsPreview(null);
      setFormsError('');
      return undefined;
    }

    let cancelled = false;
    setFormsStatus('loading');
    setFormsError('');
    setFormsPreview(null);

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
