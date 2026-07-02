/**
 * Motion & Transitions
 * Consistent animation timings and easing curves
 */

export const transitions = {
  fast: 150,    // ms
  base: 200,    // ms
  slow: 300,    // ms
  slower: 500,  // ms
} as const;

export const easing = {
  easeOut: 'cubic-bezier(0.4, 0, 0.2, 1)',
  easeInOut: 'cubic-bezier(0.4, 0, 0.6, 1)',
  easeIn: 'cubic-bezier(0.4, 0, 1, 1)',
  sharp: 'cubic-bezier(0.4, 0, 0.6, 1)',
} as const;

export type TransitionToken = keyof typeof transitions;
export type EasingToken = keyof typeof easing;
