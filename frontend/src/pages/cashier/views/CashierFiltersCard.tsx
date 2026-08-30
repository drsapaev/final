/**
 * PR-UI-14-5: cashier filters card (verbatim JSX move from CashierPanel).
 *
 * Search input (UX Audit #2.4 hint), status filter (history tab only —
 * law of Hickson: redundant on the pending tab), date mode segmented
 * control + date fields + quick presets (UX Audit #1.4).
 */

import { Calendar, Search } from 'lucide-react';

import { Card } from '../../../components/ui/macos';
import SegmentedControl from '../../../components/ui/macos/SegmentedControl';
import Input from '../../../components/ui/macos/Input';
import type { CashierTranslationFn } from '../cashierPaymentContracts';

export interface CashierDatePreset {
  id: string;
  label: string;
  getRange: () => { from: string; to: string };
}

interface CashierFiltersCardProps {
  query: string;
  onQueryChange: (value: string) => void;
  searchFocused: boolean;
  onSearchFocusedChange: (focused: boolean) => void;
  /** Status filter renders only on the history tab (redundant on pending). */
  showStatusFilter: boolean;
  status: string;
  onStatusChange: (value: string) => void;
  dateMode: string;
  onDateModeChange: (value: string) => void;
  selectedDate: string;
  onSelectedDateChange: (value: string) => void;
  dateFrom: string;
  onDateFromChange: (value: string) => void;
  dateTo: string;
  onDateToChange: (value: string) => void;
  datePresets: CashierDatePreset[];
  tI18n: CashierTranslationFn;
}

const CashierFiltersCard = ({
  query, onQueryChange,
  searchFocused, onSearchFocusedChange,
  showStatusFilter, status, onStatusChange,
  dateMode, onDateModeChange,
  selectedDate, onSelectedDateChange,
  dateFrom, onDateFromChange,
  dateTo, onDateToChange,
  datePresets,
  tI18n,
}: CashierFiltersCardProps) => (
  <Card
    variant="default"
    padding="default"
    className="cashier-mb-4">

    <div className="cashier-filter-row">
      {/* Поиск */}
      {/* UX Audit #2.4: улучшенный placeholder + раскрывающаяся подсказка
          с примерами синтаксиса (patient:ID). Раньше placeholder был обрезан
          и не раскрывал скрытые возможности поиска. */}
      <div className="cashier-search-wrap">
        <Search className="cashier-search-icon" />
        <input
          id="cashier-search-input"
          aria-label={tI18n('cashier.search_aria')}
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          onFocus={() => onSearchFocusedChange(true)}
          onBlur={() => onSearchFocusedChange(false)}
          className="cashier-text-sm cashier-text-primary"
          placeholder={tI18n('cashier.search_placeholder')}
          title={tI18n('cashier.search_title')} />
        {searchFocused && !query && (
          <div className="cashier-search-hint" role="status" aria-live="polite">
            <span className="cashier-search-hint-label">{tI18n('cashier.search_hint_label')}</span>
            <code className="cashier-search-hint-code">{tI18n('cashier.search_example_name')}</code>
            <code className="cashier-search-hint-code">patient:123</code>
            <code className="cashier-search-hint-code">+99890...</code>
          </div>
        )}
      </div>

      {/* Статус — показывается только на табе истории платежей.
          На табе «Ожидающие оплаты» статус заведомо = pending,
          поэтому фильтр избыточен (закон Хика — убираем лишний выбор). */}
      {showStatusFilter && (
        <select
          value={status}
          onChange={(e) => onStatusChange(e.target.value)}
          aria-label={tI18n('cashier.filter_status')}
          className="cashier-text-sm cashier-text-primary">
          <option value="all">{tI18n('cashier.all_statuses')}</option>
          <option value="paid">{tI18n('cashier.status_paid')}</option>
          <option value="partial">{tI18n('cashier.status_partial')}</option>
          <option value="pending">{tI18n('cashier.status_pending')}</option>
          <option value="cancelled">{tI18n('cashier.status_cancelled')}</option>
          <option value="refunded">{tI18n('cashier.status_refunded')}</option>
        </select>
      )}

      {/* Переключатель режима даты */}
      <div className="cashier-date-mode">
        <Calendar className="cashier-date-icon" />
        <SegmentedControl
          options={[
          { label: tI18n('cashier.single_date'), value: 'single' },
          { label: tI18n('cashier.date_mode_range'), value: 'range' }]
          }
          value={dateMode}
          onChange={(v: unknown) => onDateModeChange(String(v))}
          size="default" />

      </div>

      {/* Поля даты */}
      {dateMode === 'single' ?
      <>
          <Input
          type="date"
          value={selectedDate}
          onChange={(e) => onSelectedDateChange(e.target.value)}
          className="cashier-min-w-160" />

          {/* UX Audit #1.4: Quick date presets replace single "Сегодня" button.
              Reduces 2-3 clicks (open date picker → navigate to yesterday) to 1 click. */}
          <SegmentedControl
            options={datePresets.map((p) => ({ label: p.label, value: p.id }))}
            value="__none__"
            onChange={(id: string | number) => {
              const preset = datePresets.find((p) => p.id === id);
              if (!preset) return;
              onSelectedDateChange(preset.getRange().to);
            }}
            size="default"
            aria-label={tI18n('cashier.date_preset_aria')}
          />
        </> :

      <>
          <Input
          type="date"
          value={dateFrom}
          onChange={(e) => onDateFromChange(e.target.value)}
          className="cashier-min-w-140" />

          <span className="cashier-date-sep">—</span>

          <Input
          type="date"
          value={dateTo}
          onChange={(e) => onDateToChange(e.target.value)}
          className="cashier-min-w-140" />

          <SegmentedControl
            options={datePresets.map((p) => ({ label: p.label, value: p.id }))}
            value="__none__"
            onChange={(id: string | number) => {
              const preset = datePresets.find((p) => p.id === id);
              if (!preset) return;
              const { from, to } = preset.getRange();
              onDateFromChange(from);
              onDateToChange(to);
            }}
            size="default"
            aria-label={tI18n('cashier.date_range_preset_aria')}
          />
        </>
      }
    </div>
  </Card>
);

export default CashierFiltersCard;
