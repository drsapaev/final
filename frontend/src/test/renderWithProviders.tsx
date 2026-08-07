/**
 * Test renderer helper — wraps components with the minimum set of providers
 * required to render most UI components in tests.
 *
 * Design rationale:
 * - Models the test environment, NOT the full app. Only "safe" providers with
 *   no mount-time side effects (no network, no WebSocket) are included by default.
 * - Optional flags (`withChat`, `withNotificationWs`, `withModal`, `withForm`)
 *   enable heavier/stateful providers when a test actually needs them.
 * - Prevents the "missing NotificationCenterProvider" class of test failures
 *   that occurs when tests hand-wrap only Theme + Translation.
 *
 * Default providers (always included, in order):
 *   1. MemoryRouter — react-router context (most components use useNavigate/useLocation)
 *   2. MacOSThemeProvider — design-token theme context
 *   3. ThemeProvider — color-scheme + theme runtime
 *   4. TranslationProvider — i18n (most components use useTranslation)
 *   5. NotificationCenterProvider — notification inbox state (no mount-time network)
 *   6. ToastProvider — toast UI (used by notify service)
 *
 * Optional providers (opt-in via flags):
 *   - withNotificationWs — NotificationWebSocketProvider (opens WebSocket on mount)
 *   - withChat — ChatProvider (may establish chat state)
 *   - withModal — ModalProvider
 *   - withForm — FormProvider
 *
 * Usage:
 *   import { renderWithProviders } from '../test/renderWithProviders';
 *
 *   // Default — minimal safe providers:
 *   renderWithProviders(<HeaderNew />);
 *
 *   // With router state:
 *   renderWithProviders(<HeaderNew />, { routerProps: { initialEntries: ['/admin'] } });
 *
 *   // With WebSocket (rare — only if the test exercises WS behavior):
 *   renderWithProviders(<MyComponent />, { withNotificationWs: true });
 */

import React from 'react';
import { render, type RenderOptions, type RenderResult } from '@testing-library/react';
import { MemoryRouter, type MemoryRouterProps } from 'react-router-dom';
import { ThemeProvider } from '../contexts/ThemeContext';
import { MacOSThemeProvider } from '../theme/macosTheme';
import { TranslationProvider } from '../i18n/useTranslation';
import { NotificationCenterProvider } from '../contexts/NotificationCenterContext';
import { NotificationWebSocketProvider } from '../contexts/NotificationWebSocketContext';
import { ChatProvider } from '../contexts/ChatContext';
import { ToastProvider } from '../components/common/Toast';
import { ModalProvider } from '../components/common/Modal';
import { FormProvider } from '../components/common/Form';

export interface RenderWithProvidersOptions extends Omit<RenderOptions, 'wrapper'> {
  /** Props passed to MemoryRouter (initialEntries, future flags, etc.) */
  routerProps?: MemoryRouterProps;
  /** Skip the default MemoryRouter wrapper (use when the test provides its own Router). */
  skipRouter?: boolean;
  /** Include NotificationWebSocketProvider (opens WebSocket on mount — opt-in). */
  withNotificationWs?: boolean;
  /** Include ChatProvider (may establish chat state — opt-in). */
  withChat?: boolean;
  /** Include ModalProvider. */
  withModal?: boolean;
  /** Include FormProvider. */
  withForm?: boolean;
}

/**
 * Build the provider wrapper tree for a given set of options.
 * Exported separately so tests that use `rerender` or need the wrapper
 * function directly can access it.
 */
export function buildProviderWrapper(options: RenderWithProvidersOptions = {}) {
  const {
    routerProps,
    skipRouter = false,
    withNotificationWs = false,
    withChat = false,
    withModal = false,
    withForm = false,
  } = options;

  return function ProviderWrapper({ children }: { children: React.ReactNode }) {
    let tree: React.ReactNode = children;

    // Wrap from innermost (closest to children) to outermost.
    // Order matches AppProviders.tsx for the providers we share.
    if (withForm) {
      tree = <FormProvider>{tree}</FormProvider>;
    }
    if (withModal) {
      tree = <ModalProvider>{tree}</ModalProvider>;
    }
    if (withNotificationWs) {
      tree = <NotificationWebSocketProvider>{tree}</NotificationWebSocketProvider>;
    }
    // NotificationCenterProvider must wrap NotificationWebSocketProvider
    // (the latter calls useNotificationCenter).
    tree = <NotificationCenterProvider>{tree}</NotificationCenterProvider>;
    // ToastProvider wraps NotificationCenter (toast used by notification UI).
    tree = <ToastProvider>{tree}</ToastProvider>;
    if (withChat) {
      tree = <ChatProvider>{tree}</ChatProvider>;
    }
    tree = <TranslationProvider>{tree}</TranslationProvider>;
    tree = <ThemeProvider>{tree}</ThemeProvider>;
    tree = <MacOSThemeProvider>{tree}</MacOSThemeProvider>;
    if (!skipRouter) {
      tree = <MemoryRouter {...routerProps}>{tree}</MemoryRouter>;
    }
    return <>{tree}</>;
  };
}

/**
 * Render a component wrapped with the minimum safe provider set.
 * See RenderWithProvidersOptions for opt-in providers.
 */
export function renderWithProviders(
  ui: React.ReactElement,
  options: RenderWithProvidersOptions = {},
): RenderResult {
  const wrapper = buildProviderWrapper(options);
  return render(ui, { wrapper, ...options });
}
