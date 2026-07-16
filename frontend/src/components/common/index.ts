// Централизованный экспорт всех UI компонентов
export { default as ErrorBoundary, withErrorBoundary, useErrorHandler } from './ErrorBoundary';
export { ToastProvider, useToast, toast } from './Toast';
export { Loading, ButtonLoading, TableLoading, CardLoading, ListLoading, useLoading } from './Loading';
export { ModalProvider, useModal, Modal, modal } from './Modal';
export { FormProvider, useForm, Form, FormField, FormTextArea, FormSelect, SubmitButton } from './Form';
export { Table, TableExport } from './Table';
export { RoleGuard, withRoleGuard, useRoleAccess, ConditionalRender, RoleConditionalRender, UserInfo } from './RoleGuard';
// P-013 fix: shared ConfirmDialog + useConfirm hook replacing window.confirm()
export { default as ConfirmDialog, useConfirm } from './ConfirmDialog';
// P-025 fix: generic loading/error/empty wrapper for Unified* panels
export { default as StateWrapper } from './StateWrapper';
