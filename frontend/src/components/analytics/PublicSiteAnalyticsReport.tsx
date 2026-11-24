import { useEffect, useId, useState } from 'react';
import { getPublicSiteAnalyticsReport, type PublicSiteAnalyticsReportData } from '../../api/adminPublicSiteAnalytics';
import { useTranslation } from '../../i18n/useTranslation';
import Button from '../ui/macos/Button';
import './PublicSiteAnalyticsReport.css';

type ReportState =
  | { status: 'loading' | 'error' }
  | { status: 'ready'; report: PublicSiteAnalyticsReportData };

export default function PublicSiteAnalyticsReport() {
  const { language, t } = useTranslation();
  const titleId = useId();
  const [open, setOpen] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<ReportState>({ status: 'loading' });

  useEffect(() => {
    if (!open) return undefined;

    const controller = new AbortController();
    void getPublicSiteAnalyticsReport(controller.signal).then(
      (report) => {
        if (!controller.signal.aborted) setState({ status: 'ready', report });
      },
      () => {
        if (!controller.signal.aborted) setState({ status: 'error' });
      },
    );

    return () => controller.abort();
  }, [open, attempt]);

  const refresh = () => {
    if (state.status === 'loading') return;
    setState({ status: 'loading' });
    setAttempt((previous) => previous + 1);
  };

  const dateFormat = new Intl.DateTimeFormat(language, {
    dateStyle: 'medium',
    timeZone: 'UTC',
  });
  const numberFormat = new Intl.NumberFormat(language);

  return (
    <details
      className="public-site-analytics-report"
      onToggle={(event) => {
        const nextOpen = event.currentTarget.open;
        if (nextOpen && !open) setState({ status: 'loading' });
        setOpen(nextOpen);
      }}
    >
      <summary id={titleId}>{t('publicSiteAnalytics.title')}</summary>
      {open && (
        <div className="public-site-analytics-report__body">
          <div className="public-site-analytics-report__toolbar">
            <p>{t('publicSiteAnalytics.period')}</p>
            <Button
              type="button"
              size="small"
              aria-disabled={state.status === 'loading'}
              onClick={refresh}
            >
              {t(state.status === 'error' ? 'publicSiteAnalytics.retry' : 'publicSiteAnalytics.refresh')}
            </Button>
          </div>
          {state.status === 'loading' && <p role="status">{t('publicSiteAnalytics.loading')}</p>}
          {state.status === 'error' && <p role="alert">{t('publicSiteAnalytics.loadError')}</p>}
          {state.status === 'ready' && (
            <>
              {!state.report.enabled && <p role="status">{t('publicSiteAnalytics.paused')}</p>}
              <div
                aria-labelledby={titleId}
                className="public-site-analytics-report__scroll"
                role="region"
                tabIndex={0}
              >
                <table aria-labelledby={titleId}>
                  <thead>
                    <tr>
                      <th scope="col">{t('publicSiteAnalytics.day')}</th>
                      <th scope="col">{t('publicSiteAnalytics.siteViews')}</th>
                      <th scope="col">{t('publicSiteAnalytics.phoneClicks')}</th>
                      <th scope="col">{t('publicSiteAnalytics.bookingFormOpens')}</th>
                      <th scope="col">{t('publicSiteAnalytics.bookingRequestsSubmitted')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {state.report.days.map((day) => (
                      <tr key={day.clinic_day}>
                        <th scope="row">
                          <time dateTime={day.clinic_day}>
                            {dateFormat.format(new Date(day.clinic_day))}
                          </time>
                        </th>
                        <td>{numberFormat.format(day.site_views)}</td>
                        <td>{numberFormat.format(day.phone_clicks)}</td>
                        <td>{numberFormat.format(day.booking_form_opens)}</td>
                        <td>{numberFormat.format(day.booking_requests_submitted)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}
    </details>
  );
}
