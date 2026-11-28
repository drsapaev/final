import { useTranslation } from '@/i18n/useTranslation';
import type { echoAdultTteFacts } from '@/utils/echoMeasurements';

export function AdultTteSummary({ facts }: { facts: ReturnType<typeof echoAdultTteFacts> }) {
  const { t, language } = useTranslation();
  const study = facts[0];
  if (!study) return null;

  const title = t('emr_workspace.echo_tte_reporting');
  const format = new Intl.NumberFormat(language, { maximumSignificantDigits: 15 });

  return (
    <section aria-label={title}>
      <p><strong>{title}</strong></p>
      {study.measuredAt && <p>{t('emr_workspace.measurement_date')} <time dateTime={study.measuredAt}>{study.measuredAt}</time></p>}
      <ul>
        {facts.map(fact => <li key={fact.key}>
          {t(`emr_workspace.echo_tte_${fact.key}`)} {format.format(fact.value)} {fact.unit}
          {fact.key === 'lvef' && ` · ${fact.methodCode
            ? t(`emr_workspace.echo_method_${fact.methodCode}`) : t('emr_workspace.unknown_method')}`}
        </li>)}
      </ul>
    </section>
  );
}
