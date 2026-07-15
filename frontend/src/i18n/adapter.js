/**
 * DEPRECATED: Use `../i18n/useTranslation` instead.
 *
 * This file is kept as a backward-compatibility shim so existing consumers
 * of the lab module's i18n adapter continue to work while they are migrated
 * to the unified i18n system.
 *
 * Migration path:
 *   - Replace:  import { useTranslation, t, tInterpolate, i18n } from '../../i18n/adapter';
 *   - With:     import { useTranslation } from '../../i18n/useTranslation';
 *   - For non-React: import i18n from '../../i18n'; i18n.t('key');
 *
 * This shim will be removed once all consumers are migrated.
 */

export { useTranslation } from './useTranslation';
export { t, tInterpolate, i18n } from '../components/laboratory/utils/labTranslations';
