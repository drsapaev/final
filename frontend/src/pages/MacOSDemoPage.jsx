import React, { Suspense, lazy } from 'react';

// Динамический импорт для уменьшения размера основного бандла
const MacOSDemo = lazy(() => import('../components/examples/MacOSDemo'));

/**
 * macOS UI Demo Page
 * Dedicated route for showcasing macOS components
 */
const MacOSDemoPage = () => {
  return (
    <Suspense fallback={<div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', fontSize: '18px' }}>Загрузка macOS компонентов...</div>}>
      <MacOSDemo />
    </Suspense>
  );
};

export default MacOSDemoPage;

