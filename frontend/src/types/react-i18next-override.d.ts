// Override react-i18next's useTranslation to return a permissive t()
// that accepts any string key — matching the project's flat-key convention.
declare module 'react-i18next' {
  export const initReactI18next: any;
  export function useTranslation(
    ns?: string | string[],
    options?: Record<string, unknown>,
  ): {
    t: (key: string, options?: Record<string, unknown>) => string;
    i18n: any;
    ready: boolean;
    language: string;
    languages: string[];
  };
}
