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
