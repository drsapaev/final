/**
 * UI компоненты — единый kit.
 *
 * R-14 / P-009 (UX audit): previously this file re-exported from ./native
 * (the now-deleted secondary UI kit). All exports now point to ./macos —
 * the single canonical UI kit. The backwards-compat aliases (UIButton,
 * UICard, UIBadge, etc.) are preserved so legacy imports keep working.
 */

// Re-export the macos kit (Button, Card, Badge, Input, Select, Label,
// Textarea, Skeleton, Avatar, Checkbox, Radio, Modal, Dialog, Tooltip,
// Progress, etc.). Track 3-3: the list is EXPLICIT (was `export *`) so a
// reintroduced macos/Icon export cannot silently propagate through this
// barrel — the ESLint no-restricted-imports register (importNames: Icon)
// also blocks the named import at every specifier.
export {
  Input, Select, Avatar, Textarea, Checkbox, Radio, Button, Badge, MacOSTab, MacOSBreadcrumb, MacOSPagination, StatCard, MacOSStatCard, List, AppLoading, AppEmpty, AppError, Skeleton, Alert, Modal, Box, Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter, Dialog, DialogTitle, DialogContent, DialogActions, Grid, Label, Option, Paper, Progress, CircularProgress, SegmentedControl, Sidebar, Switch, Tooltip, Typography, DataCard
} from './macos';
export type { SelectChangeEvent, DataCardProps, DataCardVariant, DataCardDensity } from './macos';

// PR-UI-09d: canonical table. The macos/Table alias was removed after the
// 09b–09c consumer migration, so the table component is re-exported here to
// keep a barrel path (`import { DataTable } from '../ui'`).
export { default as DataTable } from './DataTable';

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
