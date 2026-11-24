import { useCallback, useEffect, useRef, useState } from 'react';
import { ScanBarcode, TestTube2 } from 'lucide-react';
import { Alert, Badge, Button, Card, CardContent, CardHeader, CardTitle, Input } from '../ui/macos';
import { labSpecimensApi } from '../../api/labSpecimens';
import { useTranslation } from '../../i18n/useTranslation';
import {
  LAB_SPECIMEN_REJECTION_REASON_CODES,
  type LabSpecimen,
  type LabSpecimenAvailableAction,
  type LabSpecimenPage,
  type LabSpecimenRejectionReasonCode,
  type LabSpecimenStatus,
} from '../../types/features/labWorkspace';

export interface LabSpecimenTarget {
  id: number;
  label: string;
}

interface Props {
  orderId: number | null;
  visitId: number | null;
  activeReportId: number | null;
  services: LabSpecimenTarget[];
  disabled?: boolean;
  onPendingChange: (pending: boolean) => void;
  onChanged: () => void | Promise<void>;
  onOrderEstablished: (orderId: number, visitId: number) => void;
}

interface SpecimenForm {
  action: 'create' | 'aliquot' | 'recollect' | 'hold' | 'reject' | 'assign';
  specimen?: LabSpecimen;
}

const statusVariant: Record<LabSpecimenStatus, 'info' | 'success' | 'warning' | 'danger'> = {
  expected: 'info', collected: 'info', received: 'info', accepted: 'success', held: 'warning', rejected: 'danger',
};
const codePattern = '[a-z][a-z0-9_\\-]{0,31}';

function downloadLabel(blob: Blob, specimenId: number) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `specimen-${specimenId}.pdf`;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 10000);
}

export default function LabSpecimenWorkbench({
  orderId, visitId, activeReportId, services, disabled = false, onPendingChange, onChanged, onOrderEstablished,
}: Props) {
  const { t, language } = useTranslation();
  const [page, setPage] = useState<LabSpecimenPage | null>(orderId == null ? { items: [], data_status: 'unknown' } : null);
  const [loading, setLoading] = useState(orderId != null);
  const [unavailable, setUnavailable] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [labelReady, setLabelReady] = useState(false);
  const [pending, setPending] = useState(false);
  const [highlightedId, setHighlightedId] = useState<number | null>(null);
  const [scan, setScan] = useState('');
  const [scanning, setScanning] = useState(false);
  const [form, setForm] = useState<SpecimenForm | null>(null);
  const [material, setMaterial] = useState('');
  const [container, setContainer] = useState('');
  const [reason, setReason] = useState('');
  const [rejectionCode, setRejectionCode] = useState<LabSpecimenRejectionReasonCode | ''>('');
  const [serviceIds, setServiceIds] = useState<number[]>([]);
  const [linkReport, setLinkReport] = useState(false);
  const mounted = useRef(false);
  const busy = useRef(false);
  const loadRequest = useRef<AbortController | null>(null);
  const scanRequest = useRef<AbortController | null>(null);
  const retryCommand = useRef<{ key: string; requestId: string } | null>(null);
  const actionTrigger = useRef<HTMLElement | null>(null);
  const restoreFocus = useRef(false);
  const heading = useRef<HTMLSpanElement | null>(null);
  const dateTime = new Intl.DateTimeFormat(language, { dateStyle: 'short', timeStyle: 'short', timeZone: 'Asia/Tashkent' });

  const load = useCallback(async () => {
    if (orderId == null) return;
    loadRequest.current?.abort();
    const controller = new AbortController();
    loadRequest.current = controller;
    setLoading(true);
    try {
      const next = await labSpecimensApi.list(orderId, controller.signal);
      if (!controller.signal.aborted) {
        setPage(next);
        setUnavailable(false);
      }
    } catch (failure) {
      if (controller.signal.aborted) return;
      if ((failure as { status?: number } | null)?.status === 404) setUnavailable(true);
      else setError('specimenLoadError');
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, [orderId]);

  useEffect(() => {
    mounted.current = true;
    void load();
    return () => {
      mounted.current = false;
      loadRequest.current?.abort();
      scanRequest.current?.abort();
    };
  }, [load]);

  useEffect(() => {
    if (!pending && restoreFocus.current) {
      restoreFocus.current = false;
      if (actionTrigger.current?.isConnected) actionTrigger.current.focus();
      else heading.current?.focus();
    }
  }, [pending]);

  async function perform<T>(command: object, send: (requestId: string) => Promise<T>, showResult: (result: T) => void) {
    if (busy.current || disabled) return;
    const key = JSON.stringify(command);
    const requestId = retryCommand.current?.key === key ? retryCommand.current.requestId : crypto.randomUUID();
    retryCommand.current = { key, requestId };
    busy.current = true;
    onPendingChange(true);
    setPending(true);
    setError(null);
    setLabelReady(false);
    try {
      const result = await send(requestId);
      retryCommand.current = null;
      if (mounted.current) {
        showResult(result);
        setForm(null);
        restoreFocus.current = true;
        await Promise.all([load(), onChanged()]);
      }
    } catch (failure) {
      if (!mounted.current) return;
      const conflict = (failure as { status?: number } | null)?.status === 409;
      setError(conflict ? 'specimenConflict' : 'specimenCommandError');
      if (conflict) await load();
    } finally {
      busy.current = false;
      onPendingChange(false);
      if (mounted.current) setPending(false);
    }
  }

  function openForm(next: SpecimenForm, trigger: HTMLElement) {
    actionTrigger.current = trigger;
    setForm(next);
    setMaterial(next.specimen?.material_code ?? '');
    setContainer(next.specimen?.container_code ?? '');
    setReason('');
    setRejectionCode('');
    setServiceIds([]);
    setLinkReport(false);
    setError(null);
    setLabelReady(false);
  }

  async function scanSpecimen() {
    const barcode = scan.trim();
    if (!barcode || orderId == null || scanning || scanRequest.current) return;
    const controller = new AbortController();
    scanRequest.current = controller;
    setScanning(true);
    setError(null);
    setHighlightedId(null);
    try {
      const result = await labSpecimensApi.scan(orderId, barcode, controller.signal);
      if (controller.signal.aborted) return;
      if (result.order_id !== orderId) {
        setError('specimenNotInOrder');
        return;
      }
      setHighlightedId(result.id);
      setScan('');
      if (!page?.items.some((item) => item.id === result.id)) await load();
    } catch (failure) {
      if (!controller.signal.aborted) {
        setError((failure as { status?: number } | null)?.status === 404 ? 'specimenNotInOrder' : 'specimenLoadError');
      }
    } finally {
      if (scanRequest.current === controller) scanRequest.current = null;
      if (!controller.signal.aborted) setScanning(false);
    }
  }

  const selectResult = (specimen: LabSpecimen) => {
    if (orderId == null && visitId != null && specimen.visit_id === visitId) {
      onOrderEstablished(specimen.order_id, visitId);
    }
    setHighlightedId(specimen.id);
  };
  function handleAction(specimen: LabSpecimen, action: LabSpecimenAvailableAction, trigger: HTMLElement) {
    actionTrigger.current = trigger;
    if (action === 'hold' || action === 'reject' || action === 'assign' || action === 'recollect' || action === 'aliquot') {
      openForm({ action, specimen }, trigger);
      return;
    }
    const expected_revision = specimen.revision;
    if (action === 'print_label') {
      void perform({ action, id: specimen.id, expected_revision },
        (request_id) => labSpecimensApi.label(specimen.id, { expected_revision, request_id }),
        (blob) => {
          downloadLabel(blob, specimen.id);
          setLabelReady(true);
        });
      return;
    }
    void perform({ action, id: specimen.id, expected_revision },
      (request_id) => labSpecimensApi.addEvent(specimen.id, { action, expected_revision, request_id }), selectResult);
  }

  const formSpecimen = form?.specimen
    ? page?.items.find((item) => item.id === form.specimen?.id) ?? form.specimen
    : undefined;
  const assignableServices = services.filter((service) => (
    form?.action !== 'assign' || !formSpecimen?.visit_service_ids.includes(service.id)
  ));
  const canLinkReport = activeReportId != null && (
    form?.action !== 'assign' || !formSpecimen?.report_instance_ids.includes(activeReportId)
  );

  function submitForm() {
    if (!form) return;
    if (formSpecimen && form.action !== 'create' && !formSpecimen.available_actions.includes(form.action)) return;
    if (form.action === 'hold' || form.action === 'reject') {
      if (!formSpecimen || !reason.trim()) return;
      const payload = {
        action: form.action,
        expected_revision: formSpecimen.revision,
        reason: reason.trim(),
        ...(form.action === 'reject' && rejectionCode ? { reason_code: rejectionCode } : {}),
      };
      void perform({ ...payload, id: formSpecimen.id },
        (request_id) => labSpecimensApi.addEvent(formSpecimen.id, { ...payload, request_id }), selectResult);
      return;
    }
    const targets = {
      visit_service_ids: serviceIds.filter((item) => assignableServices.some((service) => service.id === item)),
      report_instance_ids: linkReport && activeReportId != null && canLinkReport ? [activeReportId] : [],
    };
    if (form.action === 'assign') {
      if (!formSpecimen || targets.visit_service_ids.length + targets.report_instance_ids.length === 0) return;
      const payload = { ...targets, expected_revision: formSpecimen.revision };
      void perform({ action: form.action, ...payload, id: formSpecimen.id },
        (request_id) => labSpecimensApi.assign(formSpecimen.id, { ...payload, request_id }), selectResult);
      return;
    }
    const payload = {
      ...targets,
      material_code: material.trim(),
      container_code: container.trim(),
      ...(form.action === 'aliquot' ? { parent_specimen_id: formSpecimen?.id } : {}),
      ...(form.action === 'recollect' ? { replaces_specimen_id: formSpecimen?.id } : {}),
    };
    if (orderId != null) {
      void perform(payload, (request_id) => labSpecimensApi.create(orderId, { ...payload, request_id }), selectResult);
    } else if (visitId != null && targets.visit_service_ids.length > 0) {
      void perform(payload, (request_id) => labSpecimensApi.createForVisit(visitId, { ...payload, request_id }), selectResult);
    }
  }

  const reasonRequired = form?.action === 'hold' || form?.action === 'reject';
  const actionStillAvailable = !formSpecimen || !form || form.action === 'create' || formSpecimen.available_actions.includes(form.action);
  const actionsDisabled = disabled || pending || loading || unavailable;

  return (
    <Card variant="filled" padding="none" className="lab-specimens" aria-busy={loading || pending || scanning}>
      <CardHeader className="lab-specimen-header">
        <CardTitle><span ref={heading} tabIndex={-1}>
          <TestTube2 size={17} aria-hidden="true" /> {t('labWorkspace.specimens')}
        </span></CardTitle>
        {page && !unavailable && (
          <Button type="button" variant="outline" disabled={actionsDisabled}
            onClick={(event) => openForm({ action: 'create' }, event.currentTarget)}>
            {t('labWorkspace.action_create')}
          </Button>
        )}
      </CardHeader>
      <CardContent className="lab-specimen-content">
        {error && (
          <Alert severity="error" action={error === 'specimenLoadError' ? (
            <Button type="button" variant="outline" onClick={() => { setError(null); void load(); }}>
              {t('common.refresh')}
            </Button>
          ) : undefined}>{t(`labWorkspace.${error}`)}</Alert>
        )}
        {labelReady && <p role="status">{t('labWorkspace.labelReady')}</p>}
        {!page && loading && <p role="status">{t('queue.loading')}</p>}
        {unavailable && <p>{t('labWorkspace.specimenUnavailable')}</p>}
        {page && !unavailable && (
          <>
            {orderId != null && <form onSubmit={(event) => { event.preventDefault(); void scanSpecimen(); }}>
              <label htmlFor={`lab-specimen-scan-${orderId}`}>{t('labWorkspace.scanInOrder')}</label>
              <div className="lab-worklist-toolbar">
                <Input id={`lab-specimen-scan-${orderId}`} value={scan} maxLength={128} autoComplete="off"
                  onChange={(event) => setScan(event.target.value)} />
                <Button type="submit" variant="outline" disabled={actionsDisabled || scanning || !scan.trim()}>
                  <ScanBarcode size={16} aria-hidden="true" /> {t('labWorkspace.findSpecimen')}
                </Button>
              </div>
            </form>}
            {page.data_status === 'unknown' && <p>{t('labWorkspace.specimenUnknown')}</p>}
            {form && (
              <form className="lab-specimen-form" aria-label={t(`labWorkspace.action_${form.action}`)}
                onSubmit={(event) => { event.preventDefault(); submitForm(); }}>
                <h3>{t(`labWorkspace.action_${form.action}`)} {formSpecimen?.barcode}</h3>
                {!actionStillAvailable && <Alert severity="warning">{t('labWorkspace.specimenActionChanged')}</Alert>}
                {reasonRequired ? (
                  <>
                    {form.action === 'reject' && (
                      <label className="lab-worklist-field">
                        {t('labWorkspace.rejectionCode')}
                        <select className="macos-input" value={rejectionCode} disabled={actionsDisabled}
                          onChange={(event) => setRejectionCode(event.target.value as LabSpecimenRejectionReasonCode | '')}>
                          <option value="">{t('labWorkspace.rejection_unknown')}</option>
                          {LAB_SPECIMEN_REJECTION_REASON_CODES.map((code) => (
                            <option key={code} value={code}>{t(`labWorkspace.rejection_${code}`)}</option>
                          ))}
                        </select>
                      </label>
                    )}
                    <label>{t('labWorkspace.reason')}
                      <Input autoFocus required value={reason} maxLength={300} disabled={actionsDisabled}
                        onChange={(event) => setReason(event.target.value)} />
                    </label>
                  </>
                ) : (
                  <>
                    {form.action !== 'assign' && (
                      <div className="lab-worklist-toolbar">
                        <label className="lab-worklist-field">{t('labWorkspace.material')}
                          <Input autoFocus={!formSpecimen} required pattern={codePattern} maxLength={32} value={material}
                            disabled={actionsDisabled} readOnly={Boolean(formSpecimen)}
                            onChange={(event) => setMaterial(event.target.value.toLowerCase())} />
                        </label>
                        <label className="lab-worklist-field">{t('labWorkspace.container')}
                          <Input autoFocus={Boolean(formSpecimen)} required pattern={codePattern} maxLength={32} value={container}
                            disabled={actionsDisabled} onChange={(event) => setContainer(event.target.value.toLowerCase())} />
                        </label>
                      </div>
                    )}
                    {(assignableServices.length > 0 || canLinkReport) && (
                      <fieldset className="lab-specimen-targets" disabled={actionsDisabled}>
                        <legend>{t('labWorkspace.assignments')}</legend>
                        {assignableServices.map((service) => (
                          <label key={service.id}><input type="checkbox" checked={serviceIds.includes(service.id)}
                            aria-label={`${service.label} #${service.id}`}
                            onChange={(event) => setServiceIds(event.target.checked
                              ? [...serviceIds, service.id] : serviceIds.filter((item) => item !== service.id))} />
                            {service.label} · #{service.id}
                          </label>
                        ))}
                        {canLinkReport && <label><input type="checkbox" checked={linkReport}
                          aria-label={`${t('labWorkspace.reportId')} #${activeReportId}`}
                          onChange={(event) => setLinkReport(event.target.checked)} />
                          {t('labWorkspace.reportId')} #{activeReportId}
                        </label>}
                      </fieldset>
                    )}
                  </>
                )}
                <div className="lab-worklist-toolbar">
                  <Button type="submit" variant="primary" disabled={actionsDisabled || !actionStillAvailable
                    || (reasonRequired && !reason.trim())
                    || (orderId == null && serviceIds.length === 0)
                    || (form.action === 'assign' && serviceIds.length === 0 && !linkReport)}>
                    {t('common.save')}
                  </Button>
                  <Button type="button" variant="ghost" disabled={pending} onClick={() => {
                    setForm(null);
                    actionTrigger.current?.focus();
                  }}>{t('common.cancel')}</Button>
                </div>
              </form>
            )}
            {highlightedId != null && <p role="status">{t('labWorkspace.specimenSelected', { id: highlightedId })}</p>}
            <ul className="lab-specimen-list">
              {page.items.map((specimen) => (
                <li key={specimen.id} className={highlightedId === specimen.id ? 'lab-specimen-selected' : undefined}>
                  <div className="lab-worklist-toolbar">
                    <strong>{specimen.barcode}</strong>
                    <Badge variant={statusVariant[specimen.status]}>{t(`labWorkspace.specimen_${specimen.status}`)}</Badge>
                  </div>
                  <p>{t('labWorkspace.material')}: {specimen.material_code} · {t('labWorkspace.container')}: {specimen.container_code}</p>
                  {specimen.latest_reason && <p>{t('labWorkspace.reason')}: {specimen.latest_reason}</p>}
                  {(specimen.parent_specimen_id || specimen.replaces_specimen_id) && (
                    <p>{t(specimen.parent_specimen_id ? 'labWorkspace.parentSpecimen' : 'labWorkspace.replacedSpecimen')}
                      {' '}#{specimen.parent_specimen_id ?? specimen.replaces_specimen_id}</p>
                  )}
                  {specimen.visit_service_ids.length > 0 && <p>
                    {t('labWorkspace.assignedServices')}: {specimen.visit_service_ids.join(', ')}
                  </p>}
                  {specimen.report_instance_ids.length > 0 && <p>
                    {t('labWorkspace.assignedReports')}: {specimen.report_instance_ids.join(', ')}
                  </p>}
                  <div className="lab-worklist-toolbar">
                    {specimen.available_actions.map((action) => (
                      <Button type="button" variant="outline" key={action} disabled={actionsDisabled
                        || (action === 'assign' && !services.some((service) => !specimen.visit_service_ids.includes(service.id))
                          && (activeReportId == null || specimen.report_instance_ids.includes(activeReportId)))}
                        onClick={(event) => handleAction(specimen, action, event.currentTarget)}>
                        {t(`labWorkspace.action_${action}`)}
                      </Button>
                    ))}
                  </div>
                  {specimen.events.length > 0 && <details>
                    <summary>{t('labWorkspace.specimenHistory')}</summary>
                    <ol className="lab-specimen-events">
                      {specimen.events.map((event) => (
                        <li key={event.id}>{dateTime.format(new Date(event.happened_at))} · {t(`labWorkspace.action_${event.action}`)}
                          {event.actor_user_id && <> · {t('labWorkspace.actor', { id: event.actor_user_id })}</>}
                          {event.reason_code && <> · {t(`labWorkspace.rejection_${event.reason_code}`)}</>}
                          {event.reason && <> · {event.reason}</>}
                        </li>
                      ))}
                    </ol>
                  </details>}
                </li>
              ))}
            </ul>
          </>
        )}
      </CardContent>
    </Card>
  );
}
