// src/types/ui.ts
// Phase 0.5 — Common UI-only types (not domain-specific).
// Plan: JS-to-TS-Migration-Plan v3, section 0.5.6
//
// These types are NOT in OpenAPI — they are frontend-only state machines
// for cross-cutting UI concerns (theme, modals, toasts).

// ============================================================================
// Theme
// ============================================================================

export type ThemeMode = 'light' | 'dark' | 'system';
export type ThemeColorScheme = 'blue' | 'purple' | 'green' | 'orange' | 'pink' | 'red';

export interface ThemeState {
  mode: ThemeMode;
  colorScheme: ThemeColorScheme;
  /** Resolved mode after applying `system` → `light`/`dark` based on prefers-color-scheme. */
  resolvedMode: 'light' | 'dark';
}

// ============================================================================
// Modal
// ============================================================================

export type ModalSize = 'sm' | 'md' | 'lg' | 'xl' | 'fullscreen';

export interface ModalState {
  isOpen: boolean;
  /** Optional identifier for which modal is open (when multiple share one slot). */
  id?: string;
  size?: ModalSize;
  /** Payload passed to the modal — domain-specific, left opaque here. */
  data?: unknown;
}

// ============================================================================
// Toast
// ============================================================================

export type ToastVariant = 'success' | 'error' | 'warning' | 'info';

export interface ToastState {
  id: string;
  message: string;
  variant: ToastVariant;
  /** Auto-dismiss timeout in ms; 0 = sticky. */
  duration?: number;
  /** Optional action button (e.g. "Undo"). */
  action?: {
    label: string;
    onClick: () => void;
  };
}

// ============================================================================
// Loading / Error (cross-cutting)
// ============================================================================

export type LoadingState = 'idle' | 'loading' | 'success' | 'error';

export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: unknown;
  /** Timestamp of last successful fetch (ms since epoch). */
  lastFetchedAt: number | null;
}

// ============================================================================
// Form
// ============================================================================

export type FormStatus = 'idle' | 'editing' | 'submitting' | 'success' | 'error';

export interface FormState<T = Record<string, unknown>> {
  values: T;
  errors: Partial<Record<keyof T, string>>;
  status: FormStatus;
  isDirty: boolean;
}
