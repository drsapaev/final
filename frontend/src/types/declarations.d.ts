// src/types/declarations.d.ts
// Phase 0 — Manual ambient declarations for packages without bundled types.
// Plan: JS-to-TS-Migration-Plan v3, section 0.5
//
// Add new `declare module` entries here when a dependency ships no types
// and no @types/<pkg> package exists. Keep entries minimal but accurate.

declare module 'jspdf-autotable' {
  import jsPDF from 'jspdf';

  interface AutoTableOptions {
    head?: unknown[][];
    body?: unknown[][];
    startY?: number;
    theme?: 'striped' | 'grid' | 'plain';
    headStyles?: Record<string, unknown>;
    bodyStyles?: Record<string, unknown>;
    columnStyles?: Record<string, unknown>;
    margin?: { top?: number; right?: number; bottom?: number; left?: number };
    didParseCell?: (data: { row: { index: number }; column: { index: number }; cell: { raw: unknown; text: string }; section: 'head' | 'body' | 'foot' }) => void;
    willDrawCell?: (data: { doc: jsPDF; cell: { x: number; y: number; width: number; height: number }; row: { index: number }; column: { index: number } }) => void;
    didDrawCell?: (data: { doc: jsPDF; cell: { x: number; y: number; width: number; height: number }; row: { index: number }; column: { index: number } }) => void;
    didDrawPage?: (data: { doc: jsPDF; pageNumber: number }) => void;
    [key: string]: unknown;
  }

  function autoTable(doc: jsPDF, options: AutoTableOptions): jsPDF;
  export default autoTable;
  export { autoTable, type AutoTableOptions };
}

declare module 'heic2any' {
  interface HeicOptions {
    blob: Blob;
    toType?: string;
    quality?: number;
    multiple?: boolean;
  }
  function heic2any(options: HeicOptions): Promise<Blob | Blob[]>;
  export default heic2any;
}

declare module '@emoji-mart/react' {
  import type { ComponentType } from 'react';
  interface EmojiMartProps {
    data?: unknown;
    onEmojiSelect?: (emoji: unknown) => void;
    theme?: 'light' | 'dark' | 'auto';
    set?: string;
    previewPosition?: 'none' | 'top' | 'bottom';
    skinTonePosition?: 'none' | 'preview' | 'search';
    [key: string]: unknown;
  }
  const EmojiMart: ComponentType<EmojiMartProps>;
  export default EmojiMart;
}

declare module '@emoji-mart/data' {
  const emojiData: unknown;
  export default emojiData;
}

declare module '@vercel/speed-insights/react' {
  import type { ComponentType } from 'react';
  export const SpeedInsights: ComponentType<{ route?: string; sampleRate?: number }>;
}

declare module '@vercel/speed-insights' {
  export function inject(): void;
}

// Telegram WebApp SDK — injected by Telegram client
interface Window {
  Telegram?: {
    WebApp?: {
      initData: string;
      initDataUnsafe: {
        user?: {
          id: number;
          first_name?: string;
          last_name?: string;
          username?: string;
          language_code?: string;
          photo_url?: string;
        };
        auth_date?: number;
        hash?: string;
        start_param?: string;
      };
      colorScheme?: 'light' | 'dark';
      themeParams?: Record<string, string>;
      isExpanded?: boolean;
      viewportHeight?: number;
      viewportStableHeight?: number;
      headerColor?: string;
      backgroundColor?: string;
      BackButton?: {
        show: () => void;
        hide: () => void;
        onClick: (cb: () => void) => void;
        offClick: (cb: () => void) => void;
      };
      MainButton?: {
        text: string;
        show: () => void;
        hide: () => void;
        setText: (text: string) => void;
        onClick: (cb: () => void) => void;
        offClick: (cb: () => void) => void;
        enable: () => void;
        disable: () => void;
        showProgress: () => void;
        hideProgress: () => void;
      };
      HapticFeedback?: {
        impactOccurred: (style: string) => void;
        notificationOccurred: (type: string) => void;
        selectionChanged: () => void;
      };
      openLink: (url: string) => void;
      ready: () => void;
      expand: () => void;
      close: () => void;
    };
  };
}


// prop-types — minimal declaration for the legacy TranslationProvider.propTypes
// and routeGuards.tsx propTypes usage. The library ships its own .js without
// bundled types. PropTypes validators are typed as `any` because they're
// runtime validators, not TypeScript types — consumers use them as values
// (e.g. `PropTypes.string.isRequired`), not as type annotations.
declare module 'prop-types' {

  export const any: any;
  export const string: any;
  export const number: any;
  export const bool: any;
  export const array: any;
  export const object: any;
  export const func: any;
  export const node: any;
  export const element: any;
  export const elementType: any;
  export const symbol: any;
  export function arrayOf(type: any): any;
  export function objectOf(type: any): any;
  export function shape(shape: Record<string, any>): any;
  export function oneOfType(types: any[]): any;
  export function oneOf(types: any[]): any;
  export function instanceOf(cls: new (...args: any[]) => any): any;
  export function exact(shape: Record<string, any>): any;
  // Default export (for `import PropTypes from 'prop-types'` style)
  const PropTypes: {
    any: any;
    string: any;
    number: any;
    bool: any;
    array: any;
    object: any;
    func: any;
    node: any;
    element: any;
    elementType: any;
    symbol: any;
    arrayOf(type: any): any;
    objectOf(type: any): any;
    shape(shape: Record<string, any>): any;
    oneOfType(types: any[]): any;
    oneOf(types: any[]): any;
    instanceOf(cls: new (...args: any[]) => any): any;
    exact(shape: Record<string, any>): any;
  };
  export default PropTypes;
}
