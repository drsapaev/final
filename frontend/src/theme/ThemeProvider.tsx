/**
 * Theme Provider Setup
 * Minimal wrapper - delegates to MUI's ThemeProvider
 * Light/dark toggle via context
 */

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import {
  ThemeProvider as MuiThemeProvider,
  CssBaseline,
} from '@mui/material';
import { lightTheme, darkTheme } from './theme';

// ============================================================================
// THEME CONTEXT
// ============================================================================

interface ThemeContextType {
  mode: 'light' | 'dark';
  toggleTheme: () => void;
  setMode: (mode: 'light' | 'dark') => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within ThemeProviderSetup');
  }
  return context;
};

// ============================================================================
// THEME PROVIDER COMPONENT
// ============================================================================

interface ThemeProviderSetupProps {
  children: ReactNode;
  initialMode?: 'light' | 'dark';
  storageKey?: string;
}

/**
 * Main Theme Provider
 * - Provides MUI theme
 * - Provides light/dark toggle context
 * - Persists mode to localStorage
 * - Auto-detects system preference
 */
export const ThemeProviderSetup: React.FC<ThemeProviderSetupProps> = ({
  children,
  initialMode = 'light',
  storageKey = 'theme-mode',
}) => {
  const [mode, setModeState] = useState<'light' | 'dark'>(() => {
    // 1. Check localStorage
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem(storageKey);
      if (stored === 'light' || stored === 'dark') {
        return stored;
      }

      // 2. Check system preference
      if (window.matchMedia?.('(prefers-color-scheme: dark)').matches) {
        return 'dark';
      }
    }

    // 3. Fall back to initial mode
    return initialMode;
  });

  const theme = mode === 'dark' ? darkTheme : lightTheme;

  // Persist mode to localStorage
  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(storageKey, mode);
      document.documentElement.setAttribute('data-theme', mode);
    }
  }, [mode, storageKey]);

  const toggleTheme = () => {
    setModeState((prev) => (prev === 'light' ? 'dark' : 'light'));
  };

  const setMode = (newMode: 'light' | 'dark') => {
    setModeState(newMode);
  };

  return (
    <ThemeContext.Provider value={{ mode, toggleTheme, setMode }}>
      <MuiThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </MuiThemeProvider>
    </ThemeContext.Provider>
  );
};

export default ThemeProviderSetup;
