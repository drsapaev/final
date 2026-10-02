// QueueProfile's API accepts hex colors (max 20 characters), and native
// <input type="color"> cannot display CSS custom-property values.
/* eslint-disable custom/no-hardcoded-colors -- These values are persisted profile colors, not display-only UI tokens. */
export const QUEUE_PROFILE_COLOR_PRESETS = [
  '#E53E3E', // Red
  '#3182CE', // Blue
  '#9F7AEA', // Purple
  '#38A169', // Green
  '#DD6B20', // Orange
  '#718096', // Gray
  '#D53F8C', // Pink
  '#4A5568', // Dark gray
] as const;
/* eslint-enable custom/no-hardcoded-colors */
