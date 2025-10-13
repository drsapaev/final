/**
 * macOS UI Components
 * Centralized exports for all macOS-style components
 */

// Core Components
export { default as Button } from './Button';
export { default as Input } from './Input';
export { default as Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from './Card';
export { default as Modal, ModalHeader, ModalTitle, ModalContent, ModalFooter } from './Modal';
export { default as Table, TableHeader, TableBody, TableRow, TableHeaderCell, TableCell } from './Table';
export { default as Tooltip } from './Tooltip';
export { default as Icon } from './Icon';

// Future Components (to be implemented)
// export { default as Avatar } from './Avatar';
// export { default as Sidebar } from './Sidebar';
// export { default as Header } from './Header';
// export { default as Badge } from './Badge';
// export { default as Progress } from './Progress';
// export { default as Switch } from './Switch';
// export { default as Slider } from './Slider';
// export { default as SegmentedControl } from './SegmentedControl';
// export { default as TabBar } from './TabBar';
// export { default as Navigation } from './Navigation';
// export { default as SearchField } from './SearchField';
// export { default as DatePicker } from './DatePicker';
// export { default as TimePicker } from './TimePicker';
// export { default as ColorPicker } from './ColorPicker';
// export { default as Popover } from './Popover';
// export { default as Dropdown } from './Dropdown';
// export { default as Menu } from './Menu';
// export { default as ContextMenu } from './ContextMenu';
// export { default as Alert } from './Alert';
// export { default as Toast } from './Toast';
// export { default as Banner } from './Banner';
// export { default as Sheet } from './Sheet';
// export { default as Dialog } from './Dialog';
// export { default as Drawer } from './Drawer';
// export { default as Accordion } from './Accordion';
// export { default as Tabs } from './Tabs';
// export { default as Carousel } from './Carousel';
// export { default as Pagination } from './Pagination';
// export { default as Breadcrumb } from './Breadcrumb';
// export { default as Stepper } from './Stepper';
// export { default as Wizard } from './Wizard';
// export { default as Form } from './Form';
// export { default as Fieldset } from './Fieldset';
// export { default as Checkbox } from './Checkbox';
// export { default as Radio } from './Radio';
// export { default as Toggle } from './Toggle';
// export { default as Textarea } from './Textarea';
// export { default as Select } from './Select';
// export { default as Combobox } from './Combobox';
// export { default as Autocomplete } from './Autocomplete';
// export { default as TagInput } from './TagInput';
// export { default as FileUpload } from './FileUpload';
// export { default as ImageUpload } from './ImageUpload';
// export { default as VideoPlayer } from './VideoPlayer';
// export { default as AudioPlayer } from './AudioPlayer';
// export { default as Calendar } from './Calendar';
// export { default as Timeline } from './Timeline';
// export { default as Tree } from './Tree';
// export { default as List } from './List';
// export { default as Grid } from './Grid';
// export { default as Masonry } from './Masonry';
// export { default as Kanban } from './Kanban';
// export { default as Chart } from './Chart';
// export { default as Gauge } from './Gauge';
// export { default as Sparkline } from './Sparkline';
// export { default as Heatmap } from './Heatmap';
// export { default as Map } from './Map';
// export { default as Diagram } from './Diagram';
// export { default as CodeBlock } from './CodeBlock';
// export { default as Markdown } from './Markdown';
// export { default as RichText } from './RichText';
// export { default as DataTable } from './DataTable';
// export { default as FilterBar } from './FilterBar';
// export { default as SortBar } from './SortBar';
// export { default as SearchBar } from './SearchBar';
// export { default as Toolbar } from './Toolbar';
// export { default as StatusBar } from './StatusBar';
// export { default as Dock } from './Dock';
// export { default as MenuBar } from './MenuBar';
// export { default as Window } from './Window';
// export { default as Panel } from './Panel';
// export { default as Section } from './Section';
// export { default as Group } from './Group';
// export { default as Stack } from './Stack';
// export { default as HStack } from './HStack';
// export { default as VStack } from './VStack';
// export { default as ZStack } from './ZStack';
// export { default as Spacer } from './Spacer';
// export { default as Divider } from './Divider';
// export { default as Separator } from './Separator';
// export { default as Skeleton } from './Skeleton';
// export { default as Placeholder } from './Placeholder';
// export { default as EmptyState } from './EmptyState';
// export { default as Loading } from './Loading';
// export { default as ErrorBoundary } from './ErrorBoundary';

// Design Tokens and Theme
export * from '../../../theme/macos-tokens.css';

// Re-export existing components for compatibility
// These can be gradually replaced with macOS versions
export { default as LegacyButton } from '../native/Button';
export { default as LegacyCard } from '../native/Card';
export { default as LegacyInput } from '../native/Input';
export { default as LegacyModal } from '../native/Modal';
export { default as LegacyTable } from '../native/Table';
export { default as LegacyTooltip } from '../native/Tooltip';
export { default as LegacyIcon } from '../native/Icon';
