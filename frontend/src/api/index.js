// Barrel exports for API modules.
// Важно: экспортируйте только реально существующие файлы.

export * from './client';
export * from './endpoints';
export * from './services';
export * from './visits';
export * from './ws';
export * from './health';
export * from './adminSettings';
export * from './boardDisplay';

// Совместимость со старыми импортами (`./api/queue`):
export * from './queue';
