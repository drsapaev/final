/**
 * Test renderer helper — wraps components with the minimum set of providers
 * required to render most UI components in tests.
 *
 * ─────────────────────────────────────────────────────────────────────────
 * GOVERNANCE PRINCIPLE (do not violate without maintainer review):
 * ─────────────────────────────────────────────────────────────────────────
 * This helper is intentionally NOT a copy of `AppProviders`. The default
 * set MUST stay minimal and side-effect-free. Two rules:
 *
 * 1. DEFAULT = minimal safe providers only.
 *    A provider qualifies for the default set ONLY IF it:
 *       - has NO mount-time network I/O (no fetch, no WebSocket, no polling),
 *       - has NO mount-time global side effects (no window.* mutation,
 *         no localStorage writes outside the test's control),
 *       - is required by a broad class of components (not a niche feature).
 *    Violating this rule turns the helper into a second AppProviders and
 *    re-introduces the exact problem it was created to solve.
 *
 * 2. HEAVY / STATEFUL PROVIDERS = opt-in via explicit flag only.
 *    Providers that open sockets, fetch data on mount, or carry meaningful
 *    state (ChatProvider, NotificationWebSocketProvider) MUST be opt-in.
 *    Tests that need them pass `{ withNotificationWs: true }` etc.
 *
 * If you find yourself wanting to add a provider to the default set,
 * first ask: can the component be tested with just the existing defaults?
 * If yes, prefer that. If no, add the provider as an opt-in flag first;
 * only promote to default after explicit maintainer approval.
 * ─────────────────────────────────────────────────────────────────────────
 *
 * Design rationale:
 * - Models the test environment, NOT the full app.
 * - Prevents the "missing NotificationCenterProvider" class of test failures
 *   that occurs when tests hand-wrap only Theme + Translation.
 * - Avoids the opposite failure mode (rendering every test under the full
 *   AppProviders stack) where WebSocket/chat/network side effects bleed
 *   into unrelated tests.
 *
 * Default providers (always included, in order — ALL side-effect-free):
 *   1. MemoryRouter — react-router context (most components use useNavigate/useLocation)
 *   2. ThemeProvider — color-scheme + theme runtime + design-token accent context
 *   4. TranslationProvider — i18n (most components use useTranslation)
 *   5. NotificationCenterProvider — notification inbox state (no mount-time network)
 *   6. ToastProvider — toast UI (used by notify service)
 *
 * Optional providers (opt-in via flags — each has mount-time cost/side effect):
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
