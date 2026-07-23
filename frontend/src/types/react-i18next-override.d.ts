// Module augmentation for react-i18next / i18next.
//
// The project uses flat string keys (e.g. t('common.save'),
// t('cardio.cardio_panel_unit_mgdl')) without namespaced resource typing.
// We deliberately do NOT populate CustomTypeOptions.resources — that would
// force every t() call to use a namespaced key prefix (e.g. 'ru:common.save')
// and break the existing flat-key convention across 700+ call sites.
//
// Instead, we set the scalar type options that match the runtime init
// (see i18n/index.ts) and leave resources untyped so t() accepts any string.
//
// See ADR-0012 (docs/adr/ADR-0012-typescript-migration.md) for the full
// context on why this file exists and why strict resource typing is not
// enabled yet.

import 'react-i18next';

declare module 'react-i18next' {
  interface CustomTypeOptions {
    /**
     * Resources intentionally left untyped. Populating this would enforce
     * namespaced key prefixes (e.g. 'ru:common.save') on every t() call,
     * breaking the project's flat-key convention. Leaving it empty lets
     * t() accept any string key — matching the runtime behavior.
     *
     * Future work: populate this with typed resources (requires migrating
     * all t() call sites to namespaced keys, or generating types from the
     * locale files). See ADR-0012 "Future Work" section.
     */
    returnNull: false;
    returnObjects: false;
  }
}
