import { useCallback, useEffect, useState } from 'react';
import { AxiosError } from 'axios';
import { useTranslation } from '../../i18n/useTranslation';
import {
  confirmStaffPublicBookingRequest,
  getStaffBookingRequestErrorCode,
  listStaffPublicBookingRequests,
  rejectPublicBookingRequest,
  requestNewTimeForPublicBookingRequest,
  STAFF_BOOKING_REQUEST_PAGE_SIZE,
  type StaffBookingRequestStatus,
  type StaffPublicBookingRequest,
} from '../../api/adminPublicBookingRequests';
import { useConfirm } from '../common/ConfirmDialog';
import { Badge, Button, Card } from '../ui/macos';

const STATUS_KEYS: Record<StaffBookingRequestStatus, string> = {
  pending: 'admin2.pbr_status_pending',
  needs_new_time: 'admin2.pbr_status_needs_new_time',
  confirmed: 'admin2.pbr_status_confirmed',
  rejected: 'admin2.pbr_status_rejected',
  withdrawn: 'admin2.pbr_status_withdrawn',
};

const STATUS_FILTERS = Object.keys(STATUS_KEYS) as StaffBookingRequestStatus[];

type StaffAction = 'confirm' | 'requestNewTime' | 'reject';

function getLocale(language: string): string {
  if (language === 'uz-Latn') return 'uz-Latn-UZ';
  if (language === 'uz-Cyrl') return 'uz-Cyrl-UZ';
  if (language === 'kk') return 'kk-KZ';
  if (language === 'en') return 'en-GB';
  return 'ru-RU';
}

function formatAppointmentTime(
  appointmentDate: string,
  appointmentTime: string,
  locale: string,
): string {
  const wallTime = appointmentTime.slice(0, 8);
  const date = new Date(`${appointmentDate}T${wallTime}+05:00`);
  const dateText = new Intl.DateTimeFormat(locale, {
    timeZone: 'Asia/Tashkent',
    dateStyle: 'medium',
  }).format(date);
  const timeText = new Intl.DateTimeFormat(locale, {
    timeZone: 'Asia/Tashkent',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
  return `${dateText} · ${timeText}`;
}

function formatCreatedAt(value: string, locale: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat(locale, {
    timeZone: 'Asia/Tashkent',
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

function getActionErrorKey(error: unknown): string {
  const code = getStaffBookingRequestErrorCode(error);
  if (code === 'booking_request_version_conflict' || code === 'booking_request_state_conflict') {
    return 'admin2.pbr_error_changed';
  }
  if (code === 'booking_request_unavailable' || code === 'public_booking_unavailable') {
    return 'admin2.pbr_error_unavailable';
  }
  if (code === 'booking_request_not_found') return 'admin2.pbr_error_missing';
  if (error instanceof AxiosError && error.response?.status === 403) {
    return 'admin2.pbr_error_forbidden';
  }
  return 'admin2.pbr_error_action';
}

function statusVariant(status: StaffBookingRequestStatus): string {
  if (status === 'confirmed') return 'success';
  if (status === 'rejected' || status === 'withdrawn') return 'secondary';
  if (status === 'needs_new_time') return 'warning';
  return 'primary';
}

export default function PublicBookingRequestsManager() {
  const { t, language } = useTranslation();
  const [confirm, confirmDialog] = useConfirm();
  const [status, setStatus] = useState<StaffBookingRequestStatus>('pending');
  const [items, setItems] = useState<StaffPublicBookingRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);
  const [errorKey, setErrorKey] = useState<string | null>(null);
  const [noticeKey, setNoticeKey] = useState<string | null>(null);
  const [busyRequestId, setBusyRequestId] = useState<string | null>(null);
  const locale = getLocale(language || 'ru');

  useEffect(() => {
    let active = true;
    setItems([]);
    setLoading(true);
    setHasMore(false);

    listStaffPublicBookingRequests({ status, offset: 0 })
      .then((page) => {
        if (!active) return;
        setItems(page);
        setHasMore(page.length === STAFF_BOOKING_REQUEST_PAGE_SIZE);
      })
      .catch(() => {
        if (active) setErrorKey('admin2.pbr_error_load');
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => { active = false; };
  }, [status, reloadToken]);

  const loadMore = useCallback(async () => {
    if (loadingMore || !hasMore) return;
    setLoadingMore(true);
    setErrorKey(null);
    try {
      const page = await listStaffPublicBookingRequests({ status, offset: items.length });
      setItems((current) => [...current, ...page]);
      setHasMore(page.length === STAFF_BOOKING_REQUEST_PAGE_SIZE);
    } catch {
      setErrorKey('admin2.pbr_error_load_more');
    } finally {
      setLoadingMore(false);
    }
  }, [hasMore, items.length, loadingMore, status]);

  const runAction = useCallback(async (
    item: StaffPublicBookingRequest,
    action: StaffAction,
  ) => {
    if (busyRequestId) return;

    const actionLabels: Record<StaffAction, string> = {
      confirm: t('admin2.pbr_confirm'),
      requestNewTime: t('admin2.pbr_request_new_time'),
      reject: t('admin2.pbr_reject'),
    };
    const confirmed = await confirm({
      title: t(`admin2.pbr_confirm_${action}`),
      message: t(`admin2.pbr_confirm_${action}_description`),
      confirmLabel: actionLabels[action],
      cancelLabel: t('admin2.pbr_cancel'),
      intent: action === 'reject' ? 'danger' : 'warning',
    });
    if (!confirmed) return;

    setBusyRequestId(item.id);
    setErrorKey(null);
    setNoticeKey(null);
    try {
      let result: StaffPublicBookingRequest;
      if (action === 'confirm') {
        result = await confirmStaffPublicBookingRequest(item.id, item.version);
      } else if (action === 'requestNewTime') {
        result = await requestNewTimeForPublicBookingRequest(item.id, item.version);
      } else {
        result = await rejectPublicBookingRequest(item.id, item.version);
      }

      if (action === 'confirm' && result.status === 'needs_new_time') {
        setNoticeKey('admin2.pbr_notice_time_unavailable');
      } else if (action === 'confirm') {
        setNoticeKey('admin2.pbr_notice_confirmed');
      } else if (action === 'requestNewTime') {
        setNoticeKey('admin2.pbr_notice_new_time');
      } else {
        setNoticeKey('admin2.pbr_notice_rejected');
      }
      setReloadToken((current) => current + 1);
    } catch (actionError) {
      setErrorKey(getActionErrorKey(actionError));
      const code = getStaffBookingRequestErrorCode(actionError);
      if (code === 'booking_request_version_conflict' || code === 'booking_request_state_conflict') {
        setReloadToken((current) => current + 1);
      }
    } finally {
      setBusyRequestId(null);
    }
  }, [busyRequestId, confirm, t]);

  const retry = () => {
    setErrorKey(null);
    setNoticeKey(null);
    setReloadToken((current) => current + 1);
  };

  return (
    <section className="mx-auto flex w-full max-w-6xl flex-col gap-5 p-4 sm:p-6" data-testid="public-booking-requests">
      <header className="flex flex-col gap-2">
        <h1 className="m-0 text-2xl font-semibold text-[var(--mac-text-primary, rgb(0 0 0))]">
          {t('admin2.pbr_title')}
        </h1>
        <p className="m-0 max-w-3xl text-sm leading-6 text-[var(--mac-text-secondary, rgb(69 85 104))]">
          {t('admin2.pbr_description')}
        </p>
        <p className="m-0 max-w-3xl text-sm leading-6 text-[var(--mac-text-secondary, rgb(69 85 104))]" role="note">
          {t('admin2.pbr_contact_note')}
        </p>
      </header>

      <div className="flex flex-col gap-2 sm:max-w-sm">
        <label htmlFor="public-booking-request-status" className="text-sm font-medium text-[var(--mac-text-primary, rgb(0 0 0))]">
          {t('admin2.pbr_filter_label')}
        </label>
        <select
          id="public-booking-request-status"
          value={status}
          onChange={(event) => {
            setNoticeKey(null);
            setErrorKey(null);
            setStatus(event.target.value as StaffBookingRequestStatus);
          }}
          disabled={loading || loadingMore || Boolean(busyRequestId)}
          className="min-h-11 rounded-lg border border-[var(--mac-border, rgb(184 200 218))] bg-[var(--mac-bg-primary, rgb(255 255 255))] px-3 text-sm text-[var(--mac-text-primary, rgb(0 0 0))] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--mac-accent-blue, rgb(0 122 255))]"
        >
          {STATUS_FILTERS.map((option) => (
            <option key={option} value={option}>{t(STATUS_KEYS[option])}</option>
          ))}
        </select>
      </div>

      {noticeKey && (
        <p role="status" className="m-0 rounded-lg border border-[var(--mac-success, rgb(52 199 89))] px-4 py-3 text-sm text-[var(--mac-text-primary, rgb(0 0 0))]">
          {t(noticeKey)}
        </p>
      )}

      {errorKey && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[var(--mac-error, rgb(255 59 48))] px-4 py-3">
          <p className="m-0 text-sm text-[var(--mac-text-primary, rgb(0 0 0))]">{t(errorKey)}</p>
          <Button type="button" variant="secondary" size="small" onClick={retry} disabled={loading || loadingMore}>
            {t('admin2.pbr_retry')}
          </Button>
        </div>
      )}

      {loading ? (
        <p className="m-0 py-8 text-center text-sm text-[var(--mac-text-secondary, rgb(69 85 104))]" role="status">
          {t('admin2.pbr_loading')}
        </p>
      ) : items.length === 0 && !errorKey ? (
        <Card className="p-6">
          <p className="m-0 text-sm text-[var(--mac-text-secondary, rgb(69 85 104))]">{t('admin2.pbr_empty')}</p>
        </Card>
      ) : (
        <div className="flex flex-col gap-3" aria-busy={Boolean(busyRequestId)}>
          {items.map((item) => {
            const isBusy = busyRequestId === item.id;
            const canConfirm = item.status === 'pending';
            const canRequestTime = item.status === 'pending';
            const canReject = item.status === 'pending' || item.status === 'needs_new_time';
            const requestedAt = formatAppointmentTime(item.appointmentDate, item.appointmentTime, locale);

            return (
              <Card key={item.id} className="p-4 sm:p-5">
                <article className="flex flex-col gap-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="flex min-w-0 flex-col gap-1">
                      <h2 className="m-0 text-lg font-semibold text-[var(--mac-text-primary, rgb(0 0 0))]">
                        {requestedAt}
                      </h2>
                      <p className="m-0 text-xs text-[var(--mac-text-secondary, rgb(69 85 104))]">
                        {t('admin2.pbr_tashkent_time')}
                      </p>
                    </div>
                    <Badge variant={statusVariant(item.status)}>{t(STATUS_KEYS[item.status])}</Badge>
                  </div>

                  <dl className="m-0 grid grid-cols-1 gap-x-6 gap-y-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
                    <div className="min-w-0">
                      <dt className="text-xs text-[var(--mac-text-secondary, rgb(69 85 104))]">{t('admin2.pbr_patient')}</dt>
                      <dd className="m-0 break-words font-medium text-[var(--mac-text-primary, rgb(0 0 0))]">{item.patientDisplayName}</dd>
                    </div>
                    <div className="min-w-0">
                      <dt className="text-xs text-[var(--mac-text-secondary, rgb(69 85 104))]">{t('admin2.pbr_service')}</dt>
                      <dd className="m-0 break-words text-[var(--mac-text-primary, rgb(0 0 0))]">{item.serviceName}</dd>
                    </div>
                    <div className="min-w-0">
                      <dt className="text-xs text-[var(--mac-text-secondary, rgb(69 85 104))]">{t('admin2.pbr_doctor')}</dt>
                      <dd className="m-0 break-words text-[var(--mac-text-primary, rgb(0 0 0))]">{item.doctorDisplayName}</dd>
                    </div>
                    <div className="min-w-0">
                      <dt className="text-xs text-[var(--mac-text-secondary, rgb(69 85 104))]">{t('admin2.pbr_received_at')}</dt>
                      <dd className="m-0 text-[var(--mac-text-primary, rgb(0 0 0))]">{formatCreatedAt(item.createdAt, locale)}</dd>
                    </div>
                  </dl>

                  {(canConfirm || canRequestTime || canReject) && (
                    <div className="flex flex-wrap gap-2 border-t border-[var(--mac-border, rgb(184 200 218))] pt-3">
                      {canConfirm && (
                        <Button type="button" variant="primary" size="small" onClick={() => void runAction(item, 'confirm')} disabled={Boolean(busyRequestId)} loading={isBusy}>
                          {t('admin2.pbr_confirm')}
                        </Button>
                      )}
                      {canRequestTime && (
                        <Button type="button" variant="secondary" size="small" onClick={() => void runAction(item, 'requestNewTime')} disabled={Boolean(busyRequestId)} loading={isBusy}>
                          {t('admin2.pbr_request_new_time')}
                        </Button>
                      )}
                      {canReject && (
                        <Button type="button" variant="danger" size="small" onClick={() => void runAction(item, 'reject')} disabled={Boolean(busyRequestId)} loading={isBusy}>
                          {t('admin2.pbr_reject')}
                        </Button>
                      )}
                    </div>
                  )}
                </article>
              </Card>
            );
          })}
          {hasMore && (
            <div className="flex justify-center py-2">
              <Button type="button" variant="secondary" onClick={() => void loadMore()} loading={loadingMore} disabled={loadingMore || Boolean(busyRequestId)}>
                {t('admin2.pbr_load_more')}
              </Button>
            </div>
          )}
        </div>
      )}
      {confirmDialog}
    </section>
  );
}
