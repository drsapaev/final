// Override react-i18next's useTranslation to return a permissive t()
// that accepts any string key — matching the project's flat-key convention.
declare module 'react-i18next' {
  // TECH-DEBT(i18n-001): Temporary cast required by react-i18next plugin chain.
  // Re-evaluate after library upgrade or proper module augmentation.
  export const initReactI18next: any;
  export function useTranslation(
    ns?: string | string[],
    options?: Record<string, unknown>,
  ): {
    t: (key: string, options?: Record<string, unknown>) => string;
    // TECH-DEBT(i18n-001): i18next instance type is complex; left as any for now.
    i18n: any;
    ready: boolean;
    language: string;
    languages: string[];
  };
}
