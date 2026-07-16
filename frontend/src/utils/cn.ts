// src/utils/cn.ts
// Phase 1 — migrated from .js. CSS class utility; types added.

import { clsx } from 'clsx';

type ClassValue = string | number | null | undefined | false | Record<string, unknown>;

/**
 * Объединяет классы CSS в одну строку
 */
export function cn(...inputs: ClassValue[]): string {
  return clsx(inputs);
}

/**
 * Создает условные классы на основе условий
 */
export function conditionalClasses(conditions: Record<string, string | false | null | undefined>): string {
  const classes: string[] = [];

  for (const [condition, className] of Object.entries(conditions)) {
    // Note: original JS iterated Object.entries where keys are always strings,
    // so `if (condition)` was always truthy. We preserve that behavior.
    if (condition && className) {
      classes.push(className);
    }
  }

  return classes.join(' ');
}

/**
 * Создает классы для состояний компонента
 */
export function stateClasses(base: string, states: Record<string, string | false | null | undefined> = {}): string {
  const classes: string[] = [base];

  for (const [state, className] of Object.entries(states)) {
    if (state && className) {
      classes.push(className);
    }
  }

  return classes.join(' ');
}

const BREAKPOINT_MAP: Readonly<Record<string, string>> = {
  xs: 'xs:',
  sm: 'sm:',
  md: 'md:',
  lg: 'lg:',
  xl: 'xl:',
  '2xl': '2xl:',
};

/**
 * Создает responsive классы
 */
export function responsiveClasses(breakpoints: Record<string, string> = {}): string {
  const classes: string[] = [];

  for (const [breakpoint, className] of Object.entries(breakpoints)) {
    if (breakpoint && className) {
      const prefix = BREAKPOINT_MAP[breakpoint] ?? '';
      classes.push(`${prefix}${className}`);
    }
  }

  return classes.join(' ');
}

export default cn;
