/**
 * Payment methods configuration.
 *
 * UX Audit R-4.3: centralized payment methods definition.
 *
 * Currently hardcoded — future: fetch from backend API
 * (GET /api/v1/payment-methods) when backend endpoint is available.
 *
 * Migration path:
 * 1. (this PR) Extract to config module with unique icons
 * 2. (future PR) Add usePaymentMethods() hook that fetches from API
 * 3. (future PR) Backend endpoint returns { value, label_key, icon_name }
 *    and frontend maps icon_name to lucide component
 */

import { CreditCard, Banknote, ArrowLeftRight, Globe } from 'lucide-react';

export const PAYMENT_METHOD_ICONS = {
  card: CreditCard,
  cash: Banknote,
  transfer: ArrowLeftRight,
  online: Globe,
};

export const DEFAULT_PAYMENT_METHODS = [
  {
    value: 'Карта',
    label: 'Банковская карта',
    iconKey: 'card',
    icon: <CreditCard size={16} />,
  },
  {
    value: 'Наличные',
    label: 'Наличные',
    iconKey: 'cash',
    icon: <Banknote size={16} />,
  },
  {
    value: 'Перевод',
    label: 'Банковский перевод',
    iconKey: 'transfer',
    icon: <ArrowLeftRight size={16} />,
  },
  {
    value: 'Онлайн',
    label: 'Онлайн платеж',
    iconKey: 'online',
    icon: <Globe size={16} />,
  },
];

/**
 * Get payment method icon by iconKey.
 * Used when backend returns icon_name instead of React component.
 * @param {string} iconKey - icon key (e.g. 'card', 'cash')
 * @returns {React.ComponentType} lucide icon component
 */
export function getPaymentMethodIcon(iconKey) {
  return PAYMENT_METHOD_ICONS[iconKey] || CreditCard;
}

/**
 * Map backend payment method response to frontend format.
 * @param {Array} backendMethods - [{ value, label_key, icon_name }]
 * @returns {Array} [{ value, label, icon, iconKey }]
 */
export function mapBackendPaymentMethods(backendMethods) {
  if (!Array.isArray(backendMethods)) return DEFAULT_PAYMENT_METHODS;
  return backendMethods.map((method) => {
    const IconComponent = getPaymentMethodIcon(method.icon_name || method.iconKey);
    return {
      value: method.value,
      label: method.label || method.label_key,
      iconKey: method.icon_name || method.iconKey,
      icon: <IconComponent size={16} />,
    };
  });
}
