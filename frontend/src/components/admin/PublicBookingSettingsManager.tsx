import { useEffect, useMemo, useState } from 'react';
import { AxiosError } from 'axios';
import { AlertCircle, CalendarClock, RefreshCw } from 'lucide-react';

import {
  getPublicBookingSettings,
  updatePublicBookingSettings,
  type PublicBookingMode,
  type PublicBookingSettings,
  type PublicBookingSettingsUpdate,
} from '../../api/adminBookingSettings';
import { useTranslation } from '../../i18n/useTranslation';
import { Alert, Badge, Button, Card, Input } from '../ui/macos';

type Draft = Omit<PublicBookingSettingsUpdate, 'expected_version'>;

function getErrorCode(error: unknown): string | undefined {
  if (!(error instanceof AxiosError)) return undefined;
  const detail = error.response?.data?.detail;
  if (detail && typeof detail === 'object' && 'code' in detail) {
    const code = (detail as { code?: unknown }).code;
    return typeof code === 'string' ? code : undefined;
  }
  return undefined;
}

function toDraft(settings: PublicBookingSettings): Draft {
  return {
    is_enabled: settings.is_enabled,
    mode: settings.mode,
    booking_horizon_days: settings.booking_horizon_days,
    service_ids: [...settings.service_ids],
    doctor_ids: [...settings.doctor_ids],
  };
}

function canonical(draft: Draft): string {
  return JSON.stringify({
    ...draft,
    service_ids: [...draft.service_ids].sort((a, b) => a - b),
    doctor_ids: [...draft.doctor_ids].sort((a, b) => a - b),
  });
}

const PublicBookingSettingsManager = () => {
  const { t } = useTranslation();
  const [settings, setSettings] = useState<PublicBookingSettings | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setSettings(null);
    setDraft(null);
    setError(null);
    setMessage(false);

    getPublicBookingSettings()
      .then((result) => {
        if (!active) return;
        setSettings(result);
        setDraft(toDraft(result));
      })
      .catch(() => {
        if (active) setError('load');
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => { active = false; };
  }, [reloadToken]);

  const isDirty = useMemo(
    () => Boolean(settings && draft && canonical(draft) !== canonical(toDraft(settings))),
    [settings, draft],
  );

  const ready = useMemo(() => {
    if (!settings || !draft || !draft.mode || !draft.booking_horizon_days) return false;
    if (draft.service_ids.length === 0 || draft.doctor_ids.length === 0) return false;
    const eligibleServices = new Set(settings.services.filter((item) => item.eligible).map((item) => item.id));
    const eligibleDoctors = new Set(settings.doctors.filter((item) => item.eligible).map((item) => item.id));
    return draft.service_ids.every((id) => eligibleServices.has(id))
      && draft.doctor_ids.every((id) => eligibleDoctors.has(id));
  }, [settings, draft]);

  const changeSelection = (kind: 'service_ids' | 'doctor_ids', id: number, checked: boolean) => {
    setDraft((current) => {
      if (!current) return current;
      const selected = new Set(current[kind]);
      if (checked) selected.add(id);
      else selected.delete(id);
      return { ...current, [kind]: [...selected].sort((a, b) => a - b) };
    });
    setError(null);
    setMessage(false);
  };

  const save = async () => {
    if (!settings || !draft || !isDirty) return;
    setSaving(true);
    setError(null);
    setMessage(false);
    try {
      const updated = await updatePublicBookingSettings({
        ...draft,
        expected_version: settings.version,
      });
      setSettings(updated);
      setDraft(toDraft(updated));
      setMessage(true);
    } catch (saveError) {
      const code = getErrorCode(saveError);
      setError(code === 'booking_settings_version_conflict'
        ? 'conflict'
        : code === 'booking_settings_incomplete'
          ? 'incomplete'
          : 'save');
    } finally {
      setSaving(false);
    }
  };

  const errorMessage = error === 'load'
    ? t('admin2.pbs_error_load')
    : error === 'conflict'
      ? t('admin2.pbs_error_conflict')
      : error === 'incomplete'
        ? t('admin2.pbs_error_incomplete')
        : error
          ? t('admin2.pbs_error_save')
          : null;

  const renderOptions = (
    kind: 'service_ids' | 'doctor_ids',
    options: PublicBookingSettings['services'],
    titleKey: string,
    emptyKey: string,
  ) => (
    <section aria-labelledby={`public-booking-${kind}`} className="flex flex-col gap-2">
      <h3 id={`public-booking-${kind}`} className="m-0 text-base font-semibold text-[var(--mac-text-primary, rgb(0 0 0))]">
        {t(titleKey)}
      </h3>
      {options.length === 0 ? (
        <p className="m-0 text-sm text-[var(--mac-text-secondary, rgb(69 85 104))]">{t(emptyKey)}</p>
      ) : (
        <ul className="m-0 grid list-none gap-2 p-0 sm:grid-cols-2">
          {options.map((option) => {
            const checked = draft?.[kind].includes(option.id) ?? false;
            const unavailable = checked && !option.eligible;
            const inputId = `public-booking-${kind}-${option.id}`;
            return (
              <li key={option.id}>
                <label
                  htmlFor={inputId}
                  className="flex min-h-11 items-start gap-3 rounded-lg border border-[var(--mac-border, rgb(184 200 218))] p-3 text-sm text-[var(--mac-text-primary, rgb(0 0 0))]"
                >
                  <input
                    id={inputId}
                    type="checkbox"
                    aria-label={option.label ?? `#${option.id}`}
                    checked={checked}
                    disabled={saving || (!option.eligible && !checked)}
                    onChange={(event) => changeSelection(kind, option.id, event.target.checked)}
                    className="mt-0.5 size-4 accent-[var(--mac-accent-blue, rgb(0 122 255))]"
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block break-words">{option.label ?? `#${option.id}`}</span>
                    {unavailable && (
                      <span className="mt-1 block text-xs text-[var(--mac-text-secondary, rgb(69 85 104))]">
                        {t('admin2.pbs_option_unavailable')}
                      </span>
                    )}
                  </span>
                </label>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );

  return (
    <div className="flex flex-col gap-4">
      <Card className="p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <CalendarClock aria-hidden="true" className="mt-1 text-[var(--mac-accent-blue, rgb(0 122 255))]" size={22} />
            <div>
              <h2 className="m-0 text-lg font-semibold text-[var(--mac-text-primary, rgb(0 0 0))]">
                {t('admin2.pbs_title')}
              </h2>
              <p className="mb-0 mt-1 max-w-3xl text-sm text-[var(--mac-text-secondary, rgb(69 85 104))]">
                {t('admin2.pbs_description')}
              </p>
            </div>
          </div>
          {settings && (
            <Badge variant={draft?.is_enabled ? 'success' : 'warning'}>
              {draft?.is_enabled ? t('admin2.pbs_status_enabled') : t('admin2.pbs_status_disabled')}
            </Badge>
          )}
        </div>
      </Card>

      {errorMessage && (
        <div className="flex flex-col items-start gap-2">
          <Alert type="error" title={t('admin2.pbs_error_title')} message={errorMessage} className="mb-0 w-full" />
          {(error === 'load' || error === 'conflict') && (
            <Button variant="outline" onClick={() => setReloadToken((value) => value + 1)} disabled={loading || saving}>
              {t(error === 'conflict' ? 'admin2.pbs_reload' : 'admin2.pbs_retry')}
            </Button>
          )}
        </div>
      )}
      {message && (
        <Alert type="success" title={t('admin2.pbs_success_title')} message={t('admin2.pbs_success_saved')} className="mb-0" />
      )}

      <Card className="flex flex-col gap-5 p-4">
        {loading ? (
          <div className="flex items-center gap-2 text-sm text-[var(--mac-text-secondary, rgb(69 85 104))]" role="status">
            <RefreshCw aria-hidden="true" className="animate-spin" size={16} />
            {t('admin2.pbs_loading')}
          </div>
        ) : settings && draft ? (
          <>
            <div className="grid gap-4 md:grid-cols-2">
              <label className="flex flex-col gap-1 text-sm font-medium text-[var(--mac-text-primary, rgb(0 0 0))]">
                {t('admin2.pbs_mode_label')}
                <select
                  aria-label={t('admin2.pbs_mode_label')}
                  className="h-10 rounded-lg border border-[var(--mac-border, rgb(184 200 218))] bg-[var(--mac-bg-primary, rgb(238 243 250))] px-3 text-[var(--mac-text-primary, rgb(0 0 0))]"
                  value={draft.mode ?? ''}
                  disabled={saving}
                  onChange={(event) => setDraft((current) => current ? {
                    ...current,
                    mode: event.target.value ? event.target.value as PublicBookingMode : null,
                  } : current)}
                >
                  <option value="">{t('admin2.pbs_mode_none')}</option>
                  <option value="confirmed_appointment">{t('admin2.pbs_mode_confirmed')}</option>
                  <option value="registrar_request">{t('admin2.pbs_mode_registrar')}</option>
                </select>
              </label>
              <label className="flex flex-col gap-1 text-sm font-medium text-[var(--mac-text-primary, rgb(0 0 0))]">
                {t('admin2.pbs_horizon_label')}
                <Input
                  aria-label={t('admin2.pbs_horizon_label')}
                  type="number"
                  min={1}
                  max={365}
                  step={1}
                  value={draft.booking_horizon_days ?? ''}
                  disabled={saving}
                  onChange={(event) => setDraft((current) => current ? {
                    ...current,
                    booking_horizon_days: event.target.value === '' ? null : Number(event.target.value),
                  } : current)}
                />
              </label>
            </div>

            {renderOptions('service_ids', settings.services, 'admin2.pbs_services_title', 'admin2.pbs_no_services')}
            {renderOptions('doctor_ids', settings.doctors, 'admin2.pbs_doctors_title', 'admin2.pbs_no_doctors')}

            <div className="flex flex-col gap-2 rounded-lg border border-[var(--mac-border, rgb(184 200 218))] p-3">
              <label htmlFor="public-booking-enabled" className="flex items-start gap-3 text-sm font-medium text-[var(--mac-text-primary, rgb(0 0 0))]">
                <input
                  id="public-booking-enabled"
                  type="checkbox"
                  aria-label={t('admin2.pbs_enable')}
                  checked={draft.is_enabled}
                  disabled={saving || (!ready && !draft.is_enabled)}
                  onChange={(event) => setDraft((current) => current ? { ...current, is_enabled: event.target.checked } : current)}
                  className="mt-0.5 size-4 accent-[var(--mac-accent-blue, rgb(0 122 255))]"
                />
                {t('admin2.pbs_enable')}
              </label>
              <p className="m-0 flex items-start gap-2 text-sm text-[var(--mac-text-secondary, rgb(69 85 104))]">
                <AlertCircle aria-hidden="true" className="mt-0.5 shrink-0" size={16} />
                {t(ready ? 'admin2.pbs_enable_hint' : 'admin2.pbs_incomplete_hint')}
              </p>
              {settings.is_ready && (
                <Badge variant="success">{t('admin2.pbs_status_ready')}</Badge>
              )}
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3">
              {isDirty && <span className="text-sm text-[var(--mac-text-secondary, rgb(69 85 104))]">{t('admin2.pbs_unsaved')}</span>}
              <Button variant="primary" onClick={save} disabled={!isDirty || saving}>
                {saving ? t('admin2.pbs_saving') : t('admin2.pbs_save')}
              </Button>
            </div>
          </>
        ) : null}
      </Card>
    </div>
  );
};

export default PublicBookingSettingsManager;
