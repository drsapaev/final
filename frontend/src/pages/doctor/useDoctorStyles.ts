import type { CSSProperties } from 'react';

import { useBreakpoint } from '../../hooks/useEnhancedMediaQuery';
import { useTheme } from '../../contexts/ThemeContext';

/**
 * PR-UI-15-2: the DoctorPanel style objects + resolved theme colors,
 * extracted verbatim from pages/DoctorPanel.tsx (registrar/cashier
 * decomposition precedent). One hook so the slim orchestrator and the
 * ./doctor/views/* components share the exact same computed styles.
 */
export function useDoctorStyles() {
  const { isMobile, isTablet } = useBreakpoint();

  const {
    getColor,
    getSpacing,
    getFontSize,
    getShadow
  } = useTheme();

  // Цвета и стили
  const primaryColor = getColor('primary', 500);
  const successColor = getColor('success', 500);
  const warningColor = getColor('warning', 500);
  // PR-47: removed unused dangerColor
  const accentColor = getColor('info', 500);
  const interactiveSurface = 'var(--mac-nav-item-bg)';
  const interactiveSurfaceHover = 'var(--mac-card-hover-bg)';
  const panelSurface = 'var(--mac-card-bg)';
  const panelBorder = 'var(--mac-card-border)';
  // Используем централизованные функции темизации вместо прямых designTokens

  const pageStyle: CSSProperties = {
    minHeight: '100vh',
    background: 'var(--mac-gradient-window)',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
    fontSize: isMobile ? 'var(--mac-font-size-sm)' : 'var(--mac-font-size-base)',
    lineHeight: '1.5',
    color: 'var(--mac-text-primary)',
    transition: 'background var(--mac-duration-normal) var(--mac-ease)'
  };
  // UX Audit Doctor H-09: 5 мёртвых стилевых блоков удалены (header/inner/title/actions).
  // Они были labelled statements без присваивания — never used.

  const contentStyle: CSSProperties = {
    marginTop: '20px',
    padding: isMobile ? getSpacing('md') : getSpacing('lg'),
    maxWidth: '1400px',
    margin: '20px auto 0 auto'
  };

  const tabsStyle: CSSProperties = {
    display: 'flex',
    gap: isMobile ? getSpacing('sm') : getSpacing('md'),
    marginBottom: getSpacing('xl'),
    overflowX: 'auto',
    paddingBottom: getSpacing('sm')
  };

  const tabStyle: CSSProperties = {
    padding: isMobile ? `${getSpacing('sm')} ${getSpacing('md')}` : `${getSpacing('md')} ${getSpacing('lg')}`,
    borderRadius: 'var(--mac-radius-lg)',
    background: interactiveSurface,
    border: `1px solid ${panelBorder}`,
    color: 'var(--mac-text-secondary)',
    fontSize: isMobile ? getFontSize('sm') : getFontSize('base'),
    fontWeight: 'var(--mac-font-weight-medium)',
    cursor: 'default'  /* UX Audit Doctor M-33: stat cards not clickable */,
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    whiteSpace: 'nowrap',
    display: 'flex',
    alignItems: 'center',
    gap: getSpacing('sm'),
    minWidth: isMobile ? 'auto' : '120px',
    justifyContent: isMobile ? 'center' : 'flex-start'
  };

  const activeTabStyle: CSSProperties = {
    ...tabStyle,
    background: `linear-gradient(135deg, ${primaryColor} 0%, ${getColor('primary', 600)} 100%)`,
    color: 'var(--mac-text-on-accent)',
    boxShadow: '0 4px 14px 0 color-mix(in srgb, var(--mac-accent), transparent 70%)',
    transform: 'translateY(-2px)'
  };

  const dashboardGridStyle: CSSProperties = {
    display: 'grid',
    gridTemplateColumns: isMobile ? '1fr' : isTablet ? 'repeat(2, 1fr)' : 'repeat(4, 1fr)',
    gap: getSpacing('lg'),
    marginBottom: getSpacing('xl')
  };

  const statCardStyle: CSSProperties = {
    background: panelSurface,
    borderRadius: 'var(--mac-radius-xl)',
    padding: getSpacing('lg'),
    boxShadow: getShadow('lg'),
    border: `1px solid ${panelBorder}`,
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    cursor: 'default'  /* UX Audit Doctor M-33: stat cards not clickable */
  };

  const statCardHoverStyle: CSSProperties = {
    transform: 'translateY(-4px) scale(1.02)',
    boxShadow: getShadow('2xl')
  };

  const patientsTableStyle: CSSProperties = {
    background: panelSurface,
    borderRadius: 'var(--mac-radius-xl)',
    overflow: 'hidden',
    boxShadow: getShadow('lg'),
    border: `1px solid ${panelBorder}`
  };

  const tableHeaderStyle: CSSProperties = {
    background: 'linear-gradient(135deg, color-mix(in srgb, var(--mac-bg-secondary), white 8%) 0%, color-mix(in srgb, var(--mac-bg-secondary), transparent 10%) 100%)',
    padding: getSpacing('lg'),
    borderBottom: '1px solid var(--mac-separator)'
  };

  const tableStyle: CSSProperties = {
    width: '100%',
    borderCollapse: 'collapse'
  };

  // Phase 3: thStyle/tdStyle constants removed — replaced by .doctor-th / .doctor-td CSS classes.
  // The CSS classes use var(--mac-*) tokens directly, eliminating the need for JS-side
  // getSpacing/getColor/getFontSize calls that produced the same values.

  return {
    isMobile,
    isTablet,
    primaryColor,
    successColor,
    warningColor,
    accentColor,
    interactiveSurface,
    interactiveSurfaceHover,
    panelSurface,
    panelBorder,
    getColor,
    getShadow,
    pageStyle,
    contentStyle,
    tabsStyle,
    tabStyle,
    activeTabStyle,
    dashboardGridStyle,
    statCardStyle,
    statCardHoverStyle,
    patientsTableStyle,
    tableHeaderStyle,
    tableStyle,
  };
}

export type DoctorStyles = ReturnType<typeof useDoctorStyles>;
