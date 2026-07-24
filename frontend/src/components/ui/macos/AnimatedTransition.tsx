/**
 * AnimatedTransition — R-14 / P-009 (UX audit).
 *
 * Moved from components/ui/native/AnimatedTransition.jsx to the macos/ kit
 * as part of the UI-kit consolidation. The native/ kit is being deleted.
 *
 * This is a lightweight wrapper that applies a CSS transition to its
 * children based on the `type` prop. It does NOT use a transition library
 * (framer-motion / react-transition-group) — it just toggles inline styles
 * via state, which is enough for the current usage (admin panels,
 * DoctorPanel entrance animations).
 *
 * Supported types:
 *  - 'fade'    — opacity 0 → 1
 *  - 'scale'   — scale 0.95 → 1
 *  - 'slide'   — translateX(-100%) → 0
 *  - 'slideUp' — translateY(16px) → 0
 *
 * Props:
 *  - children  — content to animate
 *  - show      — whether to show (default true)
 *  - type      — animation type (default 'fade')
 *  - duration  — ms (default 300)
 *  - delay     — ms (default 0)
 *  - className — additional class names
 */

import { useEffect, useState } from 'react';
import type { ReactNode, CSSProperties } from 'react';

type AnimationType = 'fade' | 'scale' | 'slide' | 'slideUp';

const TYPE_STYLES: Record<AnimationType, (visible: boolean) => CSSProperties> = {
  fade: (visible: boolean) => ({
    opacity: visible ? 1 : 0,
  }),
  scale: (visible: boolean) => ({
    opacity: visible ? 1 : 0,
    transform: visible ? 'scale(1)' : 'scale(0.95)',
  }),
  slide: (visible: boolean) => ({
    opacity: visible ? 1 : 0,
    transform: visible ? 'translateX(0)' : 'translateX(-100%)',
  }),
  slideUp: (visible: boolean) => ({
    opacity: visible ? 1 : 0,
    transform: visible ? 'translateY(0)' : 'translateY(16px)',
  }),
};

interface AnimatedTransitionProps {
  children?: ReactNode;
  show?: boolean;
  type?: AnimationType | string;
  duration?: number;
  delay?: number;
  className?: string;
  [key: string]: unknown;
}

const AnimatedTransition = ({
  children,
  show = true,
  type = 'fade',
  duration = 300,
  delay = 0,
  className = '',
  ...props
}: AnimatedTransitionProps) => {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (show) {
      const timer = setTimeout(() => setVisible(true), delay);
      return () => clearTimeout(timer);
    }
    setVisible(false);
  }, [show, delay]);

  const typeStyle = TYPE_STYLES[type as AnimationType] || TYPE_STYLES.fade;
  const computedStyle = {
    ...typeStyle(visible),
    transition: `opacity ${duration}ms ease-in-out, transform ${duration}ms ease-in-out`,
  };

  // For 'fade' type with show=false, render nothing after fade-out
  if (!show && type === 'fade' && !visible) {
    return null;
  }

  return (
    <div className={className} style={computedStyle} {...props}>
      {children}
    </div>
  );
};
export default AnimatedTransition;
