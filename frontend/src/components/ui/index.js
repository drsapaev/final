/**
 * UI компоненты - переход на нативные компоненты
 * Все основные компоненты теперь в ui/native/
 */

// Экспортируем все нативные компоненты
export * from './native';

// Явно экспортируем AnimatedTransition для обратной совместимости
export { AnimatedTransition } from './native';

// Специализированные компоненты, которые остаются в ui/
export { default as PhoneInput } from './PhoneInput';

// Компоненты из других папок
export { default as AnimatedLoader } from '../AnimatedLoader';
export { default as AnimatedToast } from '../AnimatedToast';

// Для обратной совместимости - алиасы на нативные компоненты
export { 
  Button as UIButton,
  Card as UICard,
  Badge as UIBadge,
  Input as UIInput,
  Select as UISelect,
  Label as UILabel,
  Textarea as UITextarea,
  Skeleton as UISkeleton
} from './native';
