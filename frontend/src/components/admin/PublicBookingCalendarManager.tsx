import { useEffect, useMemo, useState } from 'react';
import { AlertCircle, CalendarDays, CheckCircle2, Plus, RefreshCw, Trash2 } from 'lucide-react';
import { AxiosError } from 'axios';

import {
  confirmPublicBookingCalendar,
  getPublicBookingCalendar,
  updatePublicBookingCalendar,
  type PublicBookingCalendarYear,
} from '../../api/adminBookingCalendar';
import { useTranslation } from '../../i18n/useTranslation';
import { Alert, Badge, Button, Card, Checkbox, Input } from '../ui/macos';

type HolidayDraft = {
  date: string;
  is_working_day: boolean;
};

function tashkentYear(): number {
  return Number(new Intl.DateTimeFormat('en', {
    year: 'numeric',
    timeZone: 'Asia/Tashkent',
  }).format(new Date()));
}

function getErrorCode(error: unknown): string | undefined {
  if (!(error instanceof AxiosError)) return undefined;
  const detail = error.response?.data?.detail;
  if (detail && typeof detail === 'object' && 'code' in detail) {
    const code = (detail as { code?: unknown }).code;
    return typeof code === 'string' ? code : undefined;
  }
  return undefined;
}

function normalizeHolidays(holidays: HolidayDraft[]): HolidayDraft[] {
  return [...holidays].sort((a, b) => a.date.localeCompare(b.date));
}

const PublicBookingCalendarManager = () => {
  const { t } = useTranslation();
  const currentYear = useMemo(tashkentYear, []);
  const [year, setYear] = useState(currentYear);
  const [calendar, setCalendar] = useState<PublicBookingCalendarYear | null>(null);
  const [holidays, setHolidays] = useState<HolidayDraft[]>([]);
  const [newDate, setNewDate] = useState('');
  const [loading, setLoading] = useState(true);
  const [reloadToken, setReloadToken] = useState(0);
  const [saving, setSaving] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [confirmReviewed, setConfirmReviewed] = useState(false);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const savedHolidays = useMemo(
    () => normalizeHolidays((calendar?.holidays ?? []).map((holiday) => ({
      date: holiday.date,
      is_working_day: holiday.is_working_day,
    }))),
    [calendar],
  );
  const isDirty = JSON.stringify(normalizeHolidays(holidays)) !== JSON.stringify(savedHolidays);
  const canSave = Boolean(calendar) && (isDirty || calendar?.version === 0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setCalendar(null);
    setHolidays([]);
    setNewDate('');
    setConfirmReviewed(false);
    setMessage(null);
    setErrorCode(null);

    getPublicBookingCalendar(year)
      .then((result) => {
        if (!active) return;
        setCalendar(result);
        setHolidays(result.holidays.map((holiday) => ({
          date: holiday.date,
          is_working_day: holiday.is_working_day,
        })));
      })
      .catch(() => {
        if (!active) return;
        // Any GET failure leaves the screen without a usable calendar draft.
        // Keep it in the retryable load state even when the API supplies a
        // structured domain error such as booking_calendar_settings_invalid.
        setErrorCode('load');
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [year, reloadToken]);

  const addHoliday = () => {
    if (!newDate || newDate.slice(0, 4) !== String(year)) return;
    if (holidays.some((holiday) => holiday.date === newDate)) return;
    setHolidays((previous) => normalizeHolidays([
      ...previous,
      { date: newDate, is_working_day: false },
    ]));
    setNewDate('');
    setConfirmReviewed(false);
    setMessage(null);
    setErrorCode(null);
  };

  const saveHolidays = async () => {
    if (!calendar || !canSave) return;
    setSaving(true);
    setErrorCode(null);
    setMessage(null);
    try {
      const updated = await updatePublicBookingCalendar(year, {
        expected_version: calendar.version,
        holidays: normalizeHolidays(holidays),
      });
      setCalendar(updated);
      setHolidays(updated.holidays.map((holiday) => ({
        date: holiday.date,
        is_working_day: holiday.is_working_day,
      })));
      setConfirmReviewed(false);
      setMessage('saved');
    } catch (error) {
      const code = getErrorCode(error);
      setErrorCode(code === 'booking_calendar_version_conflict' ? 'conflict' : 'save');
    } finally {
      setSaving(false);
    }
  };

  const confirmYear = async () => {
    if (!calendar || isDirty || calendar.version === 0 || !confirmReviewed) return;
    setConfirming(true);
    setErrorCode(null);
    setMessage(null);
    try {
      const updated = await confirmPublicBookingCalendar(year, {
        expected_version: calendar.version,
      });
      setCalendar(updated);
      setConfirmReviewed(false);
      setMessage('confirmed');
    } catch (error) {
      const code = getErrorCode(error);
      setErrorCode(code === 'booking_calendar_version_conflict' ? 'conflict' : 'confirm');
    } finally {
      setConfirming(false);
    }
  };

  const errorMessage = errorCode === 'conflict'
    ? t('admin2.pbc_error_conflict')
    : errorCode === 'load'
      ? t('admin2.pbc_error_load')
      : errorCode === 'confirm'
        ? t('admin2.pbc_error_confirm')
        : errorCode
          ? t('admin2.pbc_error_save')
          : null;

  return (
    <div className="flex flex-col gap-4">
      <Card className="p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <CalendarDays aria-hidden="true" className="mt-1 text-[var(--mac-accent-blue, rgb(0 122 255))]" size={22} />
            <div>
              <h2 className="m-0 text-lg font-semibold text-[var(--mac-text-primary, rgb(0 0 0))]">
                {t('admin2.pbc_title')}
              </h2>
              <p className="mb-0 mt-1 max-w-3xl text-sm text-[var(--mac-text-secondary, rgb(69 85 104))]">
                {t('admin2.pbc_description')}
              </p>
            </div>
          </div>
          {calendar && (
            <Badge variant={calendar.is_confirmed && !isDirty ? 'success' : 'warning'}>
              {isDirty
                ? t('admin2.pbc_status_unsaved')
                : calendar.is_confirmed
                  ? t('admin2.pbc_status_confirmed')
                  : t('admin2.pbc_status_closed')}
            </Badge>
          )}
        </div>
      </Card>

      {errorMessage && (
        <div className="flex flex-col items-start gap-2">
          <Alert
            type="error"
            title={t('admin2.pbc_error_title')}
            message={errorMessage}
            className="mb-0 w-full"
          />
          {(errorCode === 'conflict' || errorCode === 'load') && (
            <Button
              variant="outline"
              onClick={() => setReloadToken((value) => value + 1)}
              disabled={loading || saving || confirming}
            >
              {errorCode === 'conflict'
                ? t('admin2.pbc_reload_discard_draft')
                : t('admin2.pbc_retry_load')}
            </Button>
          )}
        </div>
      )}
      {message && (
        <Alert
          type="success"
          title={t('admin2.pbc_success_title')}
          message={message === 'confirmed' ? t('admin2.pbc_success_confirmed') : t('admin2.pbc_success_saved')}
          className="mb-0"
        />
      )}

      <Card className="p-4">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <label className="flex min-w-40 flex-col gap-1 text-sm font-medium text-[var(--mac-text-primary, rgb(0 0 0))]">
            {t('admin2.pbc_year_label')}
            <select
              aria-label={t('admin2.pbc_year_label')}
              className="h-10 rounded-lg border border-[var(--mac-border, rgb(184 200 218))] bg-[var(--mac-bg-primary, rgb(238 243 250))] px-3 text-[var(--mac-text-primary, rgb(0 0 0))]"
              disabled={loading || saving || confirming || isDirty}
              value={year}
              onChange={(event) => setYear(Number(event.target.value))}
            >
              {Array.from({ length: 6 }, (_, index) => currentYear + index).map((item) => (
                <option key={item} value={item}>{item}</option>
              ))}
            </select>
          </label>
          {calendar && !calendar.is_confirmed && (
            <p className="m-0 max-w-2xl text-sm text-[var(--mac-text-secondary, rgb(69 85 104))]">
              {t('admin2.pbc_closed_hint')}
            </p>
          )}
          {calendar?.is_confirmed && isDirty && (
            <p className="m-0 max-w-2xl text-sm text-[var(--mac-text-secondary, rgb(69 85 104))]">
              {t('admin2.pbc_reconfirm_after_save')}
            </p>
          )}
        </div>

        {loading ? (
          <div className="mt-5 flex items-center gap-2 text-sm text-[var(--mac-text-secondary, rgb(69 85 104))]" role="status">
            <RefreshCw aria-hidden="true" className="animate-spin" size={16} />
            {t('admin2.pbc_loading')}
          </div>
        ) : calendar ? (
          <>
            <div className="mt-5 flex flex-col gap-3">
              <div className="flex flex-wrap items-end gap-3">
                <label className="flex min-w-56 flex-1 flex-col gap-1 text-sm font-medium text-[var(--mac-text-primary, rgb(0 0 0))]">
                  {t('admin2.pbc_date_label')}
                  <Input
                    aria-label={t('admin2.pbc_date_label')}
                    type="date"
                    min={`${year}-01-01`}
                    max={`${year}-12-31`}
                    value={newDate}
                    onChange={(event) => setNewDate(event.target.value)}
                    disabled={saving || confirming}
                  />
                </label>
                <Button
                  variant="outline"
                  onClick={addHoliday}
                  disabled={!newDate || newDate.slice(0, 4) !== String(year) || holidays.some((holiday) => holiday.date === newDate) || saving || confirming}
                  startIcon={<Plus size={16} aria-hidden="true" />}
                >
                  {t('admin2.pbc_add_date')}
                </Button>
              </div>

              {holidays.length === 0 ? (
                <p className="m-0 rounded-xl border border-dashed border-[var(--mac-border, rgb(184 200 218))] p-4 text-sm text-[var(--mac-text-secondary, rgb(69 85 104))]">
                  {t('admin2.pbc_empty')}
                </p>
              ) : (
                <ul className="m-0 flex list-none flex-col gap-2 p-0">
                  {normalizeHolidays(holidays).map((holiday) => (
                    <li
                      key={holiday.date}
                      className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[var(--mac-border, rgb(184 200 218))] bg-[var(--mac-bg-secondary, rgb(227 235 245))] p-3"
                    >
                      <time dateTime={holiday.date} className="font-medium tabular-nums text-[var(--mac-text-primary, rgb(0 0 0))]">
                        {holiday.date}
                      </time>
                      <div className="flex flex-wrap items-center gap-3">
                        <Checkbox
                          checked={holiday.is_working_day}
                          onChange={(checked) => {
                            setHolidays((previous) => previous.map((item) => item.date === holiday.date
                              ? { ...item, is_working_day: checked }
                              : item));
                            setConfirmReviewed(false);
                            setMessage(null);
                          }}
                          label={t('admin2.pbc_working_override')}
                          aria-label={t('admin2.pbc_working_override_for_date', { date: holiday.date })}
                          disabled={saving || confirming}
                        />
                        <Button
                          variant="ghost"
                          color="danger"
                          size="small"
                          aria-label={t('admin2.pbc_remove_date', { date: holiday.date })}
                          onClick={() => {
                            setHolidays((previous) => previous.filter((item) => item.date !== holiday.date));
                            setConfirmReviewed(false);
                            setMessage(null);
                          }}
                          disabled={saving || confirming}
                          icon={<Trash2 size={16} aria-hidden="true" />}
                        />
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="mt-5 flex flex-col gap-4 border-t border-[var(--mac-border, rgb(184 200 218))] pt-4">
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="primary"
                  onClick={saveHolidays}
                  disabled={!canSave || saving || confirming}
                  loading={saving}
                  startIcon={<CheckCircle2 size={16} aria-hidden="true" />}
                >
                  {t('admin2.pbc_save')}
                </Button>
              </div>

              <div className="rounded-xl border border-[var(--mac-border, rgb(184 200 218))] p-3">
                <Checkbox
                  checked={confirmReviewed}
                  onChange={setConfirmReviewed}
                  label={t('admin2.pbc_confirm_reviewed')}
                  description={t('admin2.pbc_confirm_reviewed_hint')}
                  aria-label={t('admin2.pbc_confirm_reviewed')}
                  disabled={calendar.is_confirmed || isDirty || calendar.version === 0 || saving || confirming}
                />
                <div className="mt-3 flex items-center gap-2">
                  <Button
                    variant="secondary"
                    onClick={confirmYear}
                    disabled={calendar.is_confirmed || isDirty || calendar.version === 0 || !confirmReviewed || saving || confirming}
                    loading={confirming}
                  >
                    {t('admin2.pbc_confirm_year')}
                  </Button>
                  {isDirty && (
                    <span className="text-sm text-[var(--mac-text-secondary, rgb(69 85 104))]">
                      {t('admin2.pbc_unsaved')}
                    </span>
                  )}
                </div>
              </div>

              <p className="m-0 flex items-start gap-2 text-sm text-[var(--mac-text-secondary, rgb(69 85 104))]">
                <AlertCircle aria-hidden="true" className="mt-0.5 shrink-0" size={16} />
                {t('admin2.pbc_not_activated_hint')}
              </p>
            </div>
          </>
        ) : null}
      </Card>
    </div>
  );
};

export default PublicBookingCalendarManager;
