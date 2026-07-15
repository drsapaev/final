/**
 * STRAT#49: i18n adapter — now backed by react-i18next.
 *
 * Previously this was a lightweight adapter that returned translations
 * from labTranslations.js directly. Now that react-i18next is installed,
 * we delegate to the real useTranslation hook.
 *
 * All call sites that import from '../../i18n/adapter' continue to work
 * without any changes — the API signature is identical.
 *
 * Usage (unchanged from STRAT#29):
 *   import { useTranslation } from '../../i18n/adapter';
 *   const { t } = useTranslation();
 *   <Button>{t('common.save')}</Button>
 *
 * For non-hook contexts (module-level constants, etc.):
 *   import { t } from '../../i18n/adapter';
 *   const label = t('common.save');
 */

import { useTranslation } from 'react-i18next';
import i18n from './config';

// Re-export useTranslation from react-i18next
export { useTranslation };

// Re-export i18n instance
export { i18n };

// For non-hook contexts: import the raw t function from labTranslations
// (react-i18next's t requires a component context, so we keep the raw version
// for module-level usage like PropTypes defaults, constants, etc.)
import { t, tInterpolate } from '../components/laboratory/utils/labTranslations';
export { t, tInterpolate };
