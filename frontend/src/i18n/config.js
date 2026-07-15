/**
 * DEPRECATED: Use `./index` instead.
 *
 * This file is kept as a backward-compatibility shim. main.jsx now imports
 * `./i18n` (the new unified entry point) directly.
 *
 * This module just re-exports the unified i18n instance so any other code
 * that imports `./i18n/config` continues to work.
 */

export { default, SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE } from './index';
