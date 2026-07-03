/**
 * UI компоненты — единый kit.
 *
 * R-14 / P-009 (UX audit): previously this file re-exported from ./native
 * (the now-deleted secondary UI kit). All exports now point to ./macos —
 * the single canonical UI kit. The backwards-compat aliases (UIButton,
 * UICard, UIBadge, etc.) are preserved so legacy imports keep working.
 */

// Re-export everything from the macos kit (Button, Card, Badge, Input,
// Select, Label, Textarea, Skeleton, Avatar, Checkbox, Radio, Table,
// Modal, Dialog, Tooltip, Progress, etc.).
export * from './macos';

// AnimatedTransition was previously in ./native — now lives in ./macos.
export { default as AnimatedTransition } from './macos/AnimatedTransition';

// Специализированные компоненты, которые остаются в ui/
export { default as PhoneInput } from './PhoneInput';
export { default as FileUpload } from './FileUpload';

// Компоненты из других папок
export { default as AnimatedLoader } from '../AnimatedLoader';
// SW-01 fix: removed AnimatedToast export (dead code, no consumers)

// Для обратной совместимости — алиасы на macos компоненты.
// (Раньше ссылались на ./native — обновлено в R-14.)
export {
  Button as UIButton,
  Card as UICard,
  Badge as UIBadge,
  Input as UIInput,
  Select as UISelect,
  Label as UILabel,
  Textarea as UITextarea,
  Skeleton as UISkeleton
} from './macos';
