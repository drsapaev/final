/**
 * useNavigationGuard - Prevent accidental navigation with unsaved changes
 * 
 * Features:
 * - beforeunload handler (browser close/refresh)
 * - React Router blocker (in-app navigation)
 * - NO double modals
 * - Auto-removes guard after successful save
 * 
 * Rules:
 * - Block ONLY if isDirty === true
 * - After save → guard removed automatically
 * - beforeunload + router blocker don't duplicate
 */

import { useEffect, useCallback, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

/**
 * useNavigationGuard Hook
 * 
 * @param {Object} options
 * @param {boolean} options.isDirty - Has unsaved changes
 * @param {boolean} options.enabled - Enable/disable guard (default: true)
 * @param {string} options.message - Warning message
 * @param {Function} options.onBlock - Callback when navigation is blocked
 */
export function useNavigationGuard({
    isDirty,
    enabled = true,
    message = 'У вас есть несохранённые изменения. Вы уверены, что хотите уйти?',
    onBlock,
}) {
    const isBlocking = isDirty && enabled;
    const navigate = useNavigate();
    const location = useLocation();
    const lastLocationRef = useRef(location);
    const isNavigatingRef = useRef(false);

    // =========================================================================
    // beforeunload - Browser close/refresh
    // =========================================================================
    useEffect(() => {
        if (!isBlocking) return;

        const handleBeforeUnload = (e) => {
            // Standard way to trigger browser's "unsaved changes" dialog
            e.preventDefault();
            e.returnValue = message; // Chrome requires this
            return message;
        };

        window.addEventListener('beforeunload', handleBeforeUnload);

        return () => {
            window.removeEventListener('beforeunload', handleBeforeUnload);
        };
    }, [isBlocking, message]);

    // =========================================================================
    // React Router - In-app navigation
    // =========================================================================
    useEffect(() => {
        if (!isBlocking) {
            lastLocationRef.current = location;
            return;
        }

        // If location changed and we're blocking, we need to detect navigation
        if (location.pathname !== lastLocationRef.current.pathname) {
            if (!isNavigatingRef.current) {
                // Navigation attempted while dirty - this shouldn't happen
                // if we set up blocker correctly, but just in case
                onBlock?.();
            }
        }

        lastLocationRef.current = location;
    }, [isBlocking, location, onBlock]);

    /**
     * Confirm navigation - for use with custom modal
     * Returns true if navigation should proceed
     *
     * P-013 note: this hook intentionally keeps window.confirm() because:
     *   1. Hooks cannot render JSX (useConfirm returns a dialog node that must
     *      be mounted by a component).
     *   2. Navigation guards require synchronous confirmation — React Router
     *      blockers do not await async dialogs.
     * If a custom modal is desired here, the calling component must own the
     * dialog state and call forceNavigate() instead of safeNavigate().
     */
    const confirmNavigation = useCallback((to) => {
        if (!isBlocking) {
            return true;
        }

        // Show browser confirm dialog (kept intentionally — see P-013 note above)
        const shouldNavigate = window.confirm(message);

        if (shouldNavigate) {
            isNavigatingRef.current = true;

            // If destination provided, navigate
            if (to) {
                navigate(to);
            }
        } else {
            onBlock?.();
        }

        return shouldNavigate;
    }, [isBlocking, message, navigate, onBlock]);

    /**
     * Safe navigate - use this instead of navigate() directly
     *
     * P-013 note: kept as window.confirm() — same reason as confirmNavigation.
     */
    const safeNavigate = useCallback((to: string, options) => {
        if (!isBlocking || window.confirm(message)) {
            isNavigatingRef.current = true;
            navigate(to, options);
        } else {
            onBlock?.();
        }
    }, [isBlocking, message, navigate, onBlock]);

    /**
     * Force navigate - bypass guard (use after save)
     */
    const forceNavigate = useCallback((to: string, options) => {
        isNavigatingRef.current = true;
        navigate(to, options);
    }, [navigate]);

    return {
        isBlocking,
        confirmNavigation,
        safeNavigate,
        forceNavigate,
    };
}

/**
 * Simple hook for just beforeunload (no router integration)
 * Use when React Router integration is not needed
 */
export function useBeforeUnload(isDirty, message = 'У вас есть несохранённые изменения.') {
    useEffect(() => {
        if (!isDirty) return;

        const handleBeforeUnload = (e) => {
            e.preventDefault();
            e.returnValue = message;
            return message;
        };

        window.addEventListener('beforeunload', handleBeforeUnload);
        return () => window.removeEventListener('beforeunload', handleBeforeUnload);
    }, [isDirty, message]);
}

export default useNavigationGuard;
