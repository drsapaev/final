/**
 * PR-UI-14-5: cashier service badges presentation (verbatim move of
 * renderServiceBadges from CashierPanel — shared by the pending and
 * history tables).
 *
 * UX Audit #4.1: only the first 2 badges render + a «+N» counter
 * (all badges used to render, bloating rows with 5+ services).
 */

import Tooltip from '../../../components/ui/macos/Tooltip';
import { formatUZS } from '../../../utils/formatCurrency';
import type { CashierTranslationFn } from '../cashierPaymentContracts';

interface CashierServiceBadgesProps {
  serviceCodes: unknown;
  serviceNames: unknown;
  tI18n: CashierTranslationFn;
}

type ServiceObject = { id?: string | number; name?: string; code?: string; price?: number; quantity?: number };

const CashierServiceBadges = ({ serviceCodes, serviceNames, tI18n }: CashierServiceBadgesProps) => {
  // Если нет кодов, возвращаем пустой элемент
  if (!serviceCodes || !Array.isArray(serviceCodes) || serviceCodes.length === 0) {
    return <span className="cashier-empty">—</span>;
  }

  // ✅ ИСПРАВЛЕНИЕ: Обрабатываем случай когда services - это массив объектов {id, name, price, quantity}
  let codes: unknown[] = serviceCodes;
  let names: unknown = serviceNames;

  // Проверяем, является ли первый элемент объектом
  if (serviceCodes.length > 0 && typeof serviceCodes[0] === 'object' && serviceCodes[0] !== null) {
    // Извлекаем имена услуг из объектов
    const serviceObjs = serviceCodes as ServiceObject[];
    codes = serviceObjs.map((s) => s.name || s.code || tI18n('cashier.service_fallback', { id: s.id || '?' }));
    names = serviceObjs.map((s) => {
      const parts: string[] = [];
      if (s.name) parts.push(s.name);
      if (s.price) parts.push(formatUZS(s.price));
      if (s.quantity && s.quantity > 1) parts.push(`x${s.quantity}`);
      return parts.length > 0 ? parts.join(' — ') : tI18n('cashier.service_fallback', { id: s.id || '?' });
    });
  }

  // Создаем tooltip с полными названиями услуг
  const tooltipContent =
    <div className="cashier-tooltip">
        {names && Array.isArray(names) && names.length === codes.length ?
      names.map((name, idx) =>
      <div key={idx} className="cashier-tooltip-row">
              {name}
            </div>
      ) :
      codes.map((code, idx) =>
      <div key={idx} className="cashier-tooltip-row">
              {typeof code === 'string' ? code : String(code)}
            </div>
      )
      }
      </div>;


  return (
    <Tooltip
      content={tooltipContent}
      position="bottom"
      delay={200}
      followCursor>

      <div className="cashier-badge-wrap">
        {/* UX Audit #4.1: показываем только первые 2 бейджа + счётчик «+N».
            Раньше все бейджи рендерились, что раздувало строку при 5+ услугах. */}
        {codes.slice(0, 2).map((code, idx) =>
        <span key={idx} className="cashier-badge">
              {typeof code === 'string' ? code : String(code)}
            </span>
        )}
        {codes.length > 2 && (
          <span className="cashier-badge cashier-badge-more" title={tI18n('cashier.services_more', { count: codes.length - 2 })}>
            +{codes.length - 2}
          </span>
        )}
      </div>
    </Tooltip>);
};

export default CashierServiceBadges;
