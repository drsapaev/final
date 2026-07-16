// macOS UI Components
// SW-01 fix: collapsed 12 MacOS*/plain duplicate pairs into single exports.
// Remaining MacOS*-only components (no plain equivalent) keep their names.

// Form Components
export { default as Input } from './Input';
export { default as Select } from './Select';
export { default as Avatar } from './Avatar';
export { default as Textarea } from './Textarea';
export { default as Checkbox } from './Checkbox';
export { default as Radio } from './Radio';
export { default as Button } from './Button';

// Badge Component
export { default as Badge } from './Badge';

// Navigation Components (MacOS-only, no plain equivalent)
export { default as MacOSTab } from './MacOSTab';
export { default as MacOSBreadcrumb } from './MacOSBreadcrumb';
export { default as MacOSPagination } from './MacOSPagination';

// Data Display Components
export { default as Table } from './Table';
export { default as MacOSStatCard } from './MacOSStatCard';
export { default as MacOSMetricCard } from './MacOSMetricCard';
export { default as List } from './List';

// Utility Components
export { AppLoading, AppEmpty, AppError } from './AppState';
export { default as MacOSEmptyState } from './MacOSEmptyState';
export { default as Skeleton } from './Skeleton';
export { default as Alert } from './Alert';
export { default as Modal } from './Modal';
// UX Audit Registrar #1: AccentPicker — экспортируем из macos index,
// чтобы `import { AccentPicker } from '../components/ui/macos'` работал.
// Раньше файл существовал, но не был в barrel-export, из-за чего production-build падал.
export { default as AccentPicker } from './AccentPicker';
// UX Audit Registrar #1: AnimatedTransition — экспортируем из macos index.
// Используется в DoctorPanel и др. До этого build падал на этом импорте.
export { default as AnimatedTransition } from './AnimatedTransition';

// Basic UI Components
export { default as Box } from './Box';
export { default as Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from './Card';
// Backward compatibility alias for macOS-styled Card
export { default as MacOSCard } from './Card';
export { default as Dialog, DialogTitle, DialogContent, DialogActions } from './Dialog';
export { default as Grid } from './Grid';
export { default as Icon } from './Icon';
export { default as Label } from './Label';
export { default as Option } from './Option';
export { default as Paper } from './Paper';
export { default as Progress, CircularProgress } from './Progress';
export { default as SegmentedControl } from './SegmentedControl';
export { default as Sidebar } from './Sidebar';
export { default as Switch } from './Switch';
export { default as Tooltip } from './Tooltip';
export { default as Typography } from './Typography';
