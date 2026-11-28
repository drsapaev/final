import { useEffect, useId, useRef, useState } from 'react';
import { ScanBarcode, Search } from 'lucide-react';
import { Button, Input } from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';
import {
  INITIAL_LAB_WORKLIST_QUERY,
  LAB_WORKLIST_VIEWS,
  type LabWorklistQuery,
  type LabWorklistSort,
  type LabWorklistView,
} from '../../types/features/labWorkspace';

interface Props {
  counts: Record<LabWorklistView, number> | null;
  onChange: (query: LabWorklistQuery) => void;
}

const SEARCH_DELAY_MS = 250;

export default function LabWorklistFilters({ counts, onChange }: Props) {
  const { t } = useTranslation();
  const id = useId();
  const [query, setQuery] = useState(INITIAL_LAB_WORKLIST_QUERY);
  const [barcode, setBarcode] = useState('');
  const [scanOpen, setScanOpen] = useState(false);
  const scanInput = useRef<HTMLInputElement | null>(null);
  const applied = useRef(INITIAL_LAB_WORKLIST_QUERY);
  const dateRangeInvalid = Boolean(query.fromDate && query.toDate && query.fromDate > query.toDate);

  useEffect(() => {
    if ((dateRangeInvalid && !query.barcode) || query === applied.current) return;
    const searchChanged = query.q !== applied.current.q;
    const timer = window.setTimeout(() => {
      applied.current = query;
      onChange(query.barcode ? {
        view: query.view, sort: query.sort, q: '', barcode: query.barcode,
      } : query);
    }, searchChanged ? SEARCH_DELAY_MS : 0);
    return () => window.clearTimeout(timer);
  }, [dateRangeInvalid, onChange, query]);

  useEffect(() => {
    if (scanOpen) scanInput.current?.focus();
  }, [scanOpen]);

  return (
    <div className="lab-worklist-filters">
      <label htmlFor={`${id}-search`}>{t('labWorkspace.search')}</label>
      <div className="lab-worklist-toolbar">
        <Input
          id={`${id}-search`}
          className="lab-worklist-search"
          icon={Search}
          type="search"
          autoComplete="off"
          maxLength={120}
          value={query.q}
          onChange={(event) => setQuery({ ...query, q: event.target.value, barcode: undefined })}
        />
        <Button
          type="button" variant="outline" aria-expanded={scanOpen} aria-controls={`${id}-scan`}
          onClick={() => setScanOpen(!scanOpen)}
        >
          <ScanBarcode size={16} aria-hidden="true" /> {t('labWorkspace.scan')}
        </Button>
      </div>
      <form
        id={`${id}-scan`}
        className="lab-worklist-scan"
        hidden={!scanOpen}
        onSubmit={(event) => {
          event.preventDefault();
          if (barcode.trim()) {
            setQuery({ ...query, barcode: barcode.trim() });
            setBarcode('');
          }
        }}
      >
        <label htmlFor={`${id}-barcode`}>{t('labWorkspace.barcode')}</label>
        <div className="lab-worklist-toolbar">
          <Input id={`${id}-barcode`} ref={scanInput} value={barcode} maxLength={64}
            autoComplete="off" onChange={(event) => setBarcode(event.target.value)} />
          <Button type="submit" variant="outline" disabled={!barcode.trim()}>{t('labWorkspace.findSpecimen')}</Button>
        </div>
      </form>
      {query.barcode && (
        <div className="lab-worklist-toolbar">
          <span role="status">{t('labWorkspace.barcodeSearch')}</span>
          <Button type="button" variant="ghost" onClick={() => setQuery({ ...query, barcode: undefined })}>
            {t('queue.search_clear')}
          </Button>
        </div>
      )}
      <div className="lab-worklist-toolbar">
        <label className="lab-worklist-field" htmlFor={`${id}-scope`}>
          {t('labWorkspace.scope')}
          <select id={`${id}-scope`} className="macos-input" value={query.view}
            onChange={(event) => setQuery({ ...query, view: event.target.value as LabWorklistView, barcode: undefined })}>
            {LAB_WORKLIST_VIEWS.map((view) => (
              <option key={view} value={view}>{t(`labWorkspace.view_${view}`)}{counts ? ` (${counts[view]})` : ''}</option>
            ))}
          </select>
        </label>
        <label className="lab-worklist-field" htmlFor={`${id}-sort`}>
          {t('queue.sort_label')}
          <select id={`${id}-sort`} className="macos-input" value={query.sort}
            onChange={(event) => setQuery({ ...query, sort: event.target.value as LabWorklistSort })}>
            <option value="oldest">{t('labWorkspace.sort_oldest')}</option>
            <option value="newest">{t('labWorkspace.sort_newest')}</option>
            <option value="name">{t('queue.sort_name')}</option>
          </select>
        </label>
      </div>
      <details>
        <summary>{t('labWorkspace.dateRange')}</summary>
        <div className="lab-worklist-toolbar">
          <label className="lab-worklist-field" htmlFor={`${id}-from`}>
            {t('labWorkspace.fromDate')}
            <Input id={`${id}-from`} type="date" value={query.fromDate ?? ''} aria-invalid={dateRangeInvalid}
              onChange={(event) => setQuery({ ...query, fromDate: event.target.value || undefined, barcode: undefined })} />
          </label>
          <label className="lab-worklist-field" htmlFor={`${id}-to`}>
            {t('labWorkspace.toDate')}
            <Input id={`${id}-to`} type="date" value={query.toDate ?? ''} aria-invalid={dateRangeInvalid}
              onChange={(event) => setQuery({ ...query, toDate: event.target.value || undefined, barcode: undefined })} />
          </label>
        </div>
        {dateRangeInvalid && <p role="alert">{t('labWorkspace.dateRangeInvalid')}</p>}
      </details>
    </div>
  );
}
