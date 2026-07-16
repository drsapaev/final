// Централизованный экспорт всех сервисов.
// Phase 1 note: 'auth.js' service file does not exist on disk — pre-existing
// broken export caught by TypeScript after .js → .ts migration. Removed.
// If authService is needed in the future, create the file first then re-add
// the export.
export { queueService } from './queue.js';
export { paymentService } from './payment.js';
export { printService } from './print.js';
