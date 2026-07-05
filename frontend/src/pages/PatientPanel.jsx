import { useEffect, useState } from 'react';
import { useLocation, useSearchParams } from 'react-router-dom';
import {
  Card, Button, Badge, Icon, Input, Textarea, Checkbox,
} from '../components/ui/macos';
import { useBreakpoint } from '../hooks/useEnhancedMediaQuery';
import { Calendar, Heart, FileText, ClipboardList, Save, Send } from 'lucide-react';
import PropTypes from 'prop-types';
import logger from '../utils/logger';
import { api } from '../api/client';
import './patient.css';

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
  booking: {
    icon: Calendar,
    title: 'Book a visit',
    description: 'Protected appointment booking opens from Telegram Mini App identity.',
  },
  payments: {
    icon: FileText,
    title: 'Payments and debt',
    description: 'Protected payment totals open from Telegram Mini App identity.',
  },
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

const toLocalDateInputValue = (value) => {
  const localDate = new Date(value.getTime() - (value.getTimezoneOffset() * 60_000));
  return localDate.toISOString().slice(0, 10);
};

const getDefaultAppointmentDate = () => {
  const nextDate = new Date();
  nextDate.setDate(nextDate.getDate() + 1);
  return toLocalDateInputValue(nextDate);
};

const splitBookingServices = (value) => (
  String(value || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
);

const bookingErrorMessages = {
  appointment_date_in_past: 'Choose today or a future date.',
  appointment_date_invalid: 'Choose a valid appointment date.',
  appointment_time_invalid: 'Use a valid time value.',
  appointment_time_slot_occupied: 'This doctor time is already occupied. Choose another time or leave time empty.',
  auth_date_expired: 'Open the Mini App from Telegram again.',
  hash_mismatch: 'Open the Mini App from Telegram again.',
  patient_scope_mismatch: 'This booking request does not belong to the linked patient.',
  patient_scope_required: 'Link Telegram to a patient before booking.',
  telegram_link_required: 'Link Telegram to a patient before booking.',
  bot_token_required: 'Telegram Mini App is not configured yet.',
};

const describeBookingError = (reason) => (
  bookingErrorMessages[reason] || 'The booking request could not be processed.'
);

const cabinetErrorMessages = {
  auth_date_expired: 'Open the Mini App from Telegram again.',
  hash_mismatch: 'Open the Mini App from Telegram again.',
  patient_scope_mismatch: 'This cabinet does not belong to the linked patient.',
  patient_scope_required: 'Link Telegram to a patient before opening the cabinet.',
  telegram_link_required: 'Link Telegram to a patient before opening the cabinet.',
  bot_token_required: 'Telegram Mini App is not configured yet.',
};

const describeCabinetError = (reason) => (
  cabinetErrorMessages[reason] || 'The patient cabinet could not be loaded.'
);

const buildBookingPayload = (initData, bookingForm) => ({
  initData,
  appointmentDate: bookingForm.appointmentDate,
  appointmentTime: bookingForm.appointmentTime || null,
  department: bookingForm.department.trim() || null,
  notes: bookingForm.notes.trim() || null,
  services: splitBookingServices(bookingForm.servicesText),
});

const PatientBookingPanel = () => {
  const [bookingForm, setBookingForm] = useState(() => ({
    appointmentDate: getDefaultAppointmentDate(),
    appointmentTime: '',
    department: '',
    servicesText: '',
    notes: '',
  }));
  const [bookingStatus, setBookingStatus] = useState('idle');
  const [bookingPreview, setBookingPreview] = useState(null);
  const [createdBooking, setCreatedBooking] = useState(null);
  const [bookingError, setBookingError] = useState('');
  const initData = readTelegramMiniAppInitData();
  const isBusy = bookingStatus === 'previewing' || bookingStatus === 'creating';
  const appointment = bookingPreview?.appointment || createdBooking?.preview?.appointment || null;

  if (!initData) {
    return (
      <PanelEmptyState
        icon={Calendar}
        title="Open from Telegram"
        description="Protected booking requires Telegram Mini App identity before a visit can be created."
      />
    );
  }

  const handleChange = (field, value) => {
    setBookingForm((current) => ({
      ...current,
      [field]: value,
    }));
    setBookingError('');
  };

  const previewBooking = async () => {
    setBookingStatus('previewing');
    setBookingError('');
    setCreatedBooking(null);

    try {
      const response = await api.post('/telegram/mini-app/appointments/preview', buildBookingPayload(initData, bookingForm));
      setBookingPreview(response.data);
      setBookingStatus('preview-ready');
    } catch (err) {
      const reason = err?.response?.data?.detail?.reason || 'booking_preview_failed';
      setBookingError(describeBookingError(reason));
      setBookingStatus('error');
    }
  };

  const createBooking = async () => {
    setBookingStatus('creating');
    setBookingError('');

    try {
      const response = await api.post('/telegram/mini-app/appointments', buildBookingPayload(initData, bookingForm));
      setCreatedBooking(response.data);
      setBookingPreview(response.data?.preview || null);
      setBookingStatus('created');
    } catch (err) {
      const reason = err?.response?.data?.detail?.reason || 'booking_create_failed';
      setBookingError(describeBookingError(reason));
      setBookingStatus('error');
    }
  };

  return (
    <div className="space-y-4">
      <div className="border border-gray-200 rounded-lg overflow-hidden bg-white">
        <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="font-medium text-gray-900">Appointment request</div>
            <p className="mt-1 text-sm text-gray-500">Create a protected booking request linked to your Telegram patient profile.</p>
          </div>
          <Badge variant={createdBooking ? 'success' : 'info'}>
            {createdBooking ? 'Created' : 'Mini App protected'}
          </Badge>
        </div>
        <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input
            type="date"
            label="Date"
            value={bookingForm.appointmentDate}
            disabled={isBusy}
            required
            onChange={(event) => handleChange('appointmentDate', event.target.value)}
          />
          <Input
            type="time"
            label="Preferred time"
            value={bookingForm.appointmentTime}
            disabled={isBusy}
            onChange={(event) => handleChange('appointmentTime', event.target.value)}
          />
          <Input
            label="Department"
            value={bookingForm.department}
            disabled={isBusy}
            maxLength={64}
            placeholder="For example: Cardiology"
            onChange={(event) => handleChange('department', event.target.value)}
          />
          <Input
            label="Services"
            value={bookingForm.servicesText}
            disabled={isBusy}
            placeholder="Consultation, analysis"
            onChange={(event) => handleChange('servicesText', event.target.value)}
          />
          <div className="md:col-span-2">
            <Textarea
              label="Comment"
              value={bookingForm.notes}
              disabled={isBusy}
              minRows={3}
              maxRows={6}
              maxLength={1000}
              placeholder="Optional note for registration"
              onChange={(event) => handleChange('notes', event.target.value)}
            />
          </div>

          {appointment && (
            <div className="md:col-span-2 rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm text-gray-700">
              <div className="font-medium text-gray-900">Booking summary</div>
              <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-2">
                <div>Date: {appointment.appointment_date}</div>
                <div>Time: {appointment.appointment_time || 'Registrar will confirm'}</div>
                <div>Department: {appointment.department || 'Not specified'}</div>
                <div>Payment: {appointment.payment_type} / {appointment.payment_currency}</div>
              </div>
              {Array.isArray(appointment.services) && appointment.services.length > 0 && (
                <div className="mt-2">Services: {appointment.services.join(', ')}</div>
              )}
            </div>
          )}

          {createdBooking && (
            <div className="md:col-span-2 text-sm text-green-700" role="status">
              Visit request #{createdBooking.appointment_id} created.
            </div>
          )}
          {bookingError && (
            <div className="md:col-span-2 text-sm text-red-700" role="alert">
              {bookingError}
            </div>
          )}

          <div className="md:col-span-2 flex flex-col sm:flex-row gap-2 sm:justify-end border-t border-gray-100 pt-4">
            <Button
              variant="secondary"
              size="small"
              disabled={isBusy || !bookingForm.appointmentDate}
              loading={bookingStatus === 'previewing'}
              onClick={previewBooking}
            >
              <FileText className="w-4 h-4" aria-hidden="true" />
              Review request
            </Button>
            <Button
              variant="primary"
              size="small"
              disabled={isBusy || !bookingForm.appointmentDate}
              loading={bookingStatus === 'creating'}
              onClick={createBooking}
            >
              <Calendar className="w-4 h-4" aria-hidden="true" />
              Book visit
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

const PatientCabinetSummary = ({ mode = 'cabinet' }) => {
  const [cabinetStatus, setCabinetStatus] = useState('idle');
  const [cabinetSummary, setCabinetSummary] = useState(null);
  const [cabinetError, setCabinetError] = useState('');
  const [cabinetInitData, setCabinetInitData] = useState('');
  const [reportDownloads, setReportDownloads] = useState({});

  useEffect(() => {
    const initData = readTelegramMiniAppInitData();
    if (!initData) {
      setCabinetStatus('missing-init-data');
      setCabinetSummary(null);
      setCabinetError('');
      setCabinetInitData('');
      return undefined;
    }

    let cancelled = false;
    setCabinetStatus('loading');
    setCabinetSummary(null);
    setCabinetError('');
    setCabinetInitData(initData);

    api.post('/telegram/mini-app/cabinet/summary', { initData })
      .then((response) => {
        if (cancelled) {
          return;
        }
        setCabinetSummary(response.data);
        setCabinetStatus('ready');
      })
      .catch((err) => {
        if (cancelled) {
          return;
        }
        const reason = err?.response?.data?.detail?.reason || 'cabinet_summary_failed';
        setCabinetError(describeCabinetError(reason));
        setCabinetStatus('error');
      });

    return () => {
      cancelled = true;
    };
  }, []);

  if (cabinetStatus === 'missing-init-data') {
    return (
      <PanelEmptyState
        icon={FileText}
        title="Open from Telegram"
        description="Protected cabinet requires Telegram Mini App identity before patient data can be shown."
      />
    );
  }

  if (cabinetStatus === 'loading') {
    return (
      <PanelEmptyState
        icon={FileText}
        title="Loading cabinet"
        description="Checking protected Telegram Mini App identity."
      />
    );
  }

  if (cabinetStatus === 'error') {
    return (
      <PanelEmptyState
        icon={FileText}
        title="Cabinet unavailable"
        description={cabinetError || 'Protected patient cabinet could not be loaded.'}
      />
    );
  }

  const isPaymentsMode = mode === 'payments';
  const isReportsMode = mode === 'reports';
  const payments = cabinetSummary?.payments || {};
  const appointments = Array.isArray(cabinetSummary?.appointments) ? cabinetSummary.appointments : [];
  const visits = Array.isArray(cabinetSummary?.visits) ? cabinetSummary.visits : [];
  const queue = Array.isArray(cabinetSummary?.queue) ? cabinetSummary.queue : [];
  const reports = Array.isArray(cabinetSummary?.reports) ? cabinetSummary.reports : [];

  const downloadReport = async (report) => {
    setReportDownloads((current) => ({
      ...current,
      [report.id]: 'loading',
    }));

    try {
      const response = await api.post(
        '/telegram/mini-app/reports/download',
        {
          initData: cabinetInitData,
          reportId: report.id,
        },
        { responseType: 'blob' },
      );
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = objectUrl;
      link.download = `kosmed-report-${report.id}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objectUrl);
      setReportDownloads((current) => ({
        ...current,
        [report.id]: 'ready',
      }));
    } catch {
      setReportDownloads((current) => ({
        ...current,
        [report.id]: 'error',
      }));
    }
  };

  return (
    <div className="space-y-4">
      <div className="border border-gray-200 rounded-lg overflow-hidden bg-white">
        <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="font-medium text-gray-900">
              {isPaymentsMode
                ? 'Payments and debt'
                : isReportsMode
                  ? 'Reports and documents'
                  : (cabinetSummary?.patient?.name || 'Linked patient')}
            </div>
            <p className="mt-1 text-sm text-gray-500">
              {isPaymentsMode
                ? `Protected payment totals for ${cabinetSummary?.patient?.name || 'linked patient'}.`
                : isReportsMode
                  ? `Ready report files for ${cabinetSummary?.patient?.name || 'linked patient'}.`
                  : 'Protected cabinet summary from the linked Telegram patient profile.'}
            </p>
          </div>
          <Badge variant="success">Mini App protected</Badge>
        </div>

        <div className="p-4 space-y-4">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
              <div className="text-xs text-gray-500">Billed</div>
              <div className="mt-1 font-medium text-gray-900">{payments.billed || '0'} UZS</div>
            </div>
            <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
              <div className="text-xs text-gray-500">Paid</div>
              <div className="mt-1 font-medium text-gray-900">{payments.paid || '0'} UZS</div>
            </div>
            <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
              <div className="text-xs text-gray-500">Pending</div>
              <div className="mt-1 font-medium text-gray-900">{payments.pending || '0'} UZS</div>
            </div>
            <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
              <div className="text-xs text-gray-500">Debt</div>
              <div className="mt-1 font-medium text-gray-900">{payments.debt || '0'} UZS</div>
            </div>
          </div>

          {isPaymentsMode && (
            <div className="rounded-lg border border-gray-200 bg-white p-3 text-sm text-gray-700">
              <div className="font-medium text-gray-900">Linked activity</div>
              <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-2">
                <div>Linked visits: {payments.linked_visit_count ?? 0}</div>
                <div>Active queue entries: {payments.active_queue_count ?? 0}</div>
              </div>
              <div className="mt-2 text-gray-500">
                Online payment and refund actions stay disabled in Telegram; clinic staff completes payment operations in the clinic app.
              </div>
            </div>
          )}

          {isReportsMode && (
            <div className="rounded-lg border border-gray-200 bg-white p-3">
              <div className="font-medium text-gray-900">Ready reports</div>
              <div className="mt-3 space-y-3">
                {reports.length > 0 ? reports.map((report) => (
                  <div key={report.id} className="flex flex-col gap-3 rounded-lg border border-gray-100 p-3 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <div className="text-sm font-medium text-gray-900">{report.name || 'Lab report'}</div>
                      <div className="mt-1 text-sm text-gray-500">{report.ready_at || 'Ready date pending'}</div>
                      {reportDownloads[report.id] === 'error' && (
                        <div className="mt-1 text-sm text-red-700" role="alert">
                          Report could not be opened. Try again from Telegram.
                        </div>
                      )}
                    </div>
                    <Button
                      variant="secondary"
                      size="small"
                      loading={reportDownloads[report.id] === 'loading'}
                      disabled={reportDownloads[report.id] === 'loading'}
                      onClick={() => downloadReport(report)}
                    >
                      <FileText className="w-4 h-4" aria-hidden="true" />
                      Open PDF
                    </Button>
                  </div>
                )) : (
                  <div className="text-sm text-gray-500">No ready reports yet.</div>
                )}
              </div>
            </div>
          )}

          {!isPaymentsMode && !isReportsMode && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="rounded-lg border border-gray-200 bg-white p-3">
              <div className="font-medium text-gray-900">Appointments</div>
              <div className="mt-3 space-y-2">
                {appointments.length > 0 ? appointments.map((appointment) => (
                  <div key={appointment.id} className="flex items-center justify-between gap-3 text-sm">
                    <div>
                      <div className="text-gray-900">{appointment.date || 'Date pending'}</div>
                      <div className="text-gray-500">{appointment.time || 'Time pending'} · {appointment.department || 'Department pending'}</div>
                    </div>
                    <Badge variant={appointment.status ? 'info' : 'secondary'}>
                      {appointment.status || 'status unavailable'}
                    </Badge>
                  </div>
                )) : (
                  <div className="text-sm text-gray-500">No appointment requests yet.</div>
                )}
              </div>
            </div>

            <div className="rounded-lg border border-gray-200 bg-white p-3">
              <div className="font-medium text-gray-900">Visits</div>
              <div className="mt-3 space-y-2">
                {visits.length > 0 ? visits.map((visit) => (
                  <div key={visit.id} className="flex items-center justify-between gap-3 text-sm">
                    <div className="text-gray-900">Visit #{visit.id}</div>
                    <div className="text-gray-500">{visit.date || 'Date pending'} · {visit.status || 'status unavailable'}</div>
                  </div>
                )) : (
                  <div className="text-sm text-gray-500">No recent visits yet.</div>
                )}
              </div>
            </div>

            <div className="rounded-lg border border-gray-200 bg-white p-3">
              <div className="font-medium text-gray-900">Today queue</div>
              <div className="mt-3 space-y-2">
                {queue.length > 0 ? queue.map((entry) => (
                  <div key={`${entry.number}-${entry.status}`} className="flex items-center justify-between gap-3 text-sm">
                    <div className="text-gray-900">#{entry.number}</div>
                    <div className="text-gray-500">{entry.status}{entry.cabinet ? ` · ${entry.cabinet}` : ''}</div>
                  </div>
                )) : (
                  <div className="text-sm text-gray-500">No active queue entry today.</div>
                )}
              </div>
            </div>

            <div className="rounded-lg border border-gray-200 bg-white p-3">
              <div className="font-medium text-gray-900">Ready reports</div>
              <div className="mt-3 space-y-2">
                {reports.length > 0 ? reports.map((report) => (
                  <div key={report.id} className="flex items-center justify-between gap-3 text-sm">
                    <div>
                      <div className="text-gray-900">{report.name || 'Lab report'}</div>
                      <div className="text-gray-500">{report.ready_at || 'Ready date pending'}</div>
                    </div>
                    <Badge variant={report.status ? 'success' : 'secondary'}>
                      {report.status || 'status unavailable'}
                    </Badge>
                  </div>
                )) : (
                  <div className="text-sm text-gray-500">No ready reports yet.</div>
                )}
              </div>
            </div>
          </div>
          )}
        </div>
      </div>
    </div>
  );
};

PatientCabinetSummary.propTypes = {
  mode: PropTypes.oneOf(['cabinet', 'payments', 'reports']),
};

const buildInitialPatientFormAnswers = (form) => {
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

const buildInitialPatientFormState = (form) => ({
  answers: buildInitialPatientFormAnswers(form),
  status: 'idle',
  savedStatus: form?.submission?.status || '',
  error: '',
  message: '',
  submittedAt: form?.submission?.submitted_at || '',
  updatedAt: form?.submission?.updated_at || '',
});

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
      nextState[form.id] = buildInitialPatientFormState(form);
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
    const currentForm = formState[form.id] || buildInitialPatientFormState(form);

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
          savedStatus: submission.status || '',
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
      {forms.map((form) => {
        const currentFormState = formState[form.id] || buildInitialPatientFormState(form);
        const isFormBusy = currentFormState.status === 'saving-draft' || currentFormState.status === 'submitting';

        return (
        <div key={form.id} className="border border-gray-200 rounded-lg overflow-hidden bg-white">
          <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <div className="font-medium text-gray-900">{form.title}</div>
              <p className="mt-1 text-sm text-gray-500">{form.description}</p>
            </div>
            <div className="flex flex-wrap gap-2 sm:justify-end">
              {currentFormState.savedStatus && (
                <Badge variant={currentFormState.savedStatus === 'submitted' ? 'success' : 'info'}>
                  {currentFormState.savedStatus === 'submitted' ? 'Submitted' : 'Draft saved'}
                </Badge>
              )}
              <Badge variant={storageEnabled ? 'success' : 'warning'}>
                {storageEnabled ? 'Secure storage on' : 'Read only'}
              </Badge>
            </div>
          </div>
          <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
            {(form.fields || []).map((field) => {
              const fieldValue = currentFormState.answers?.[field.key];

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
              {currentFormState.message && (
                <div className="text-sm text-green-700" role="status">
                  {currentFormState.message}
                </div>
              )}
              {currentFormState.error && (
                <div className="text-sm text-red-700" role="alert">
                  {currentFormState.error}
                </div>
              )}
              {currentFormState.updatedAt && (
                <div className="text-xs text-gray-500">
                  Last saved: {currentFormState.updatedAt}
                </div>
              )}
              <div className="flex flex-col sm:flex-row gap-2 sm:justify-end">
                <Button
                  variant="secondary"
                  size="small"
                  disabled={!storageEnabled || !initData || isFormBusy}
                  loading={currentFormState.status === 'saving-draft'}
                  onClick={() => handleSave(form, 'draft')}
                >
                  <Save className="w-4 h-4" aria-hidden="true" />
                  Save draft
                </Button>
                <Button
                  variant="primary"
                  size="small"
                  disabled={!storageEnabled || !initData || isFormBusy}
                  loading={currentFormState.status === 'submitting'}
                  onClick={() => handleSave(form, 'submitted')}
                >
                  <Send className="w-4 h-4" aria-hidden="true" />
                  Submit form
                </Button>
              </div>
            </div>
          </div>
        </div>
        );
      })}
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
  const location = useLocation();
  const activeSection = (() => {
    if (location.pathname === '/patient/bookings') {
      return 'booking';
    }
    if (location.pathname === '/patient/payments') {
      return 'payments';
    }
    return normalizeSection(searchParams.get('tab'));
  })();
  const [formsPreview, setFormsPreview] = useState(null);
  const [formsStatus, setFormsStatus] = useState('idle');
  const [formsError, setFormsError] = useState('');
  const [formsInitData, setFormsInitData] = useState('');
  // P1 fix: implemented API calls for patient appointments and results.
  // Backend endpoints: GET /patients/appointments, GET /patients/results (Patient role)
  const [appointments, setAppointments] = useState([]);
  const [results, setResults] = useState([]);

  useEffect(() => {
    // P1 fix: backend endpoints /patients/appointments and /patients/results
    // are patient-role scoped — patient_id берётся из JWT токена на backend.
    // Frontend не нужен patientId (он был артефактом копирования из FormsPanel).
    let cancelled = false;

    async function loadPatientData() {
      try {
        const [apptRes, resultsRes] = await Promise.allSettled([
          api.get('/patients/appointments'),
          api.get('/patients/results'),
        ]);
        if (cancelled) return;
        if (apptRes.status === 'fulfilled') {
          setAppointments(Array.isArray(apptRes.value.data) ? apptRes.value.data : []);
        }
        if (resultsRes.status === 'fulfilled') {
          setResults(Array.isArray(resultsRes.value.data) ? resultsRes.value.data : []);
        }
      } catch (error) {
        logger.error('Error loading patient data:', error);
      }
    }

    loadPatientData();
    return () => { cancelled = true; };
  }, []);
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
      className="patient-root"
    >
      <div className="patient-container">
        <Card
          className="patient-search-card"
        >
          <div className="patient-flex-center-12">
            <div className="patient-search-wrap">
              <Icon
                name="magnifyingglass"
                size="small"
                className="patient-search-icon"
              />
              <Input
                aria-label={
                  hasPatientData
                    ? 'Search patient records and quick actions'
                    : 'Patient records search unavailable'
                }
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                disabled={!hasPatientData}
                className="patient-search-input"
                placeholder={
                  hasPatientData
                    ? 'Search patient records or use quick actions from links'
                    : 'Patient records are not loaded yet'
                }
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
              ) : activeSection === 'booking' ? (
                <PatientBookingPanel />
              ) : activeSection === 'cabinet' ? (
                <PatientCabinetSummary />
              ) : activeSection === 'payments' ? (
                <PatientCabinetSummary mode="payments" />
              ) : activeSection === 'documents' ? (
                <PatientCabinetSummary mode="reports" />
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
