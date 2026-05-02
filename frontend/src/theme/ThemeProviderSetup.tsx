/**
 * ThemeProvider Setup Component
 * Wraps app with MUI ThemeProvider + CssBaseline
 */

import React, { useMemo } from 'react';
import { ThemeProvider as MuiThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { lightTheme, darkTheme, getTheme } from './muiTheme';

interface ThemeProviderSetupProps {
  children: React.ReactNode;
  mode?: 'light' | 'dark';
}

export const ThemeProviderSetup: React.FC<ThemeProviderSetupProps> = ({
  children,
  mode = 'light',
}) => {
  const theme = useMemo(() => {
    return getTheme(mode);
  }, [mode]);

  return (
    <MuiThemeProvider theme={theme}>
      <CssBaseline />
      {children}
    </MuiThemeProvider>
  );
};

// ============================================================================
// ALTERNATIVE: Hook-based setup for dynamic theme switching
// ============================================================================
import { useCallback, useState } from 'react';

export const useThemeMode = (initialMode: 'light' | 'dark' = 'light') => {
  const [mode, setMode] = useState<'light' | 'dark'>(initialMode);

  const toggleTheme = useCallback(() => {
    setMode((prev) => (prev === 'light' ? 'dark' : 'light'));
  }, []);

  return { mode, setMode, toggleTheme, theme: getTheme(mode) };
};

// ============================================================================
// CONTEXT-BASED THEME MANAGEMENT
// ============================================================================
import { createContext, useContext } from 'react';

interface ThemeContextType {
  mode: 'light' | 'dark';
  setMode: (mode: 'light' | 'dark') => void;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const ThemeProviderWithContext: React.FC<{
  children: React.ReactNode;
  initialMode?: 'light' | 'dark';
}> = ({ children, initialMode = 'light' }) => {
  const [mode, setMode] = useState<'light' | 'dark'>(initialMode);

  const toggleTheme = useCallback(() => {
    setMode((prev) => (prev === 'light' ? 'dark' : 'light'));
  }, []);

  const theme = useMemo(() => getTheme(mode), [mode]);

  return (
    <ThemeContext.Provider value={{ mode, setMode, toggleTheme }}>
      <MuiThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </MuiThemeProvider>
    </ThemeContext.Provider>
  );
};

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within ThemeProviderWithContext');
  }
  return context;
};
