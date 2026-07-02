/**
 * Нативные UI компоненты
 * Замена для дизайн-системы с улучшенной производительностью
 */

export { default as Button } from './Button';
export { default as Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from './Card';
export { default as Badge } from './Badge';
export { default as Skeleton } from './Skeleton';
export { default as Input } from './Input';
export { default as Select, Option } from './Select';
export { default as Label } from './Label';
export { default as Textarea } from './Textarea';

// Хуки (совместимые с дизайн-системой)
export {
  useBreakpoint,
  useTouchDevice,
  useFade,
  useSlide,
  useScale,
  useFadeIn,
  useAnimation,
  useProgress,
  useStagger,
  useMediaQuery
} from './hooks';

// Дополнительные компоненты
export { default as Modal, ModalHeader, ModalTitle, ModalContent, ModalFooter } from './Modal';
export { default as Tooltip } from './Tooltip';
export { default as Spinner, DotsSpinner, PulseSpinner } from './Spinner';
export { default as Dropdown, DropdownItem, DropdownSeparator, DropdownLabel, Select as DropdownSelect } from './Dropdown';
export { default as AnimatedTransition } from './AnimatedTransition';
