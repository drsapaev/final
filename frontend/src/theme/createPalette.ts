/**
 * Palette Factory
 * Constructs MUI palette from tokens with medical specialty colors
 */

import { PaletteOptions } from '@mui/material/styles';
import {
  colorsLight,
  colorsDark,
  medical,
} from './tokens/colors';

export const createLightPalette = (): PaletteOptions => ({
  mode: 'light',
  primary: {
    main: colorsLight.primary[500],
    light: colorsLight.primary[300],
    dark: colorsLight.primary[700],
    contrastText: '#ffffff',
  },
  secondary: {
    main: colorsLight.secondary[500],
    light: colorsLight.secondary[300],
    dark: colorsLight.secondary[700],
    contrastText: '#ffffff',
  },
  success: {
    main: colorsLight.success[500],
    light: colorsLight.success[300],
    dark: colorsLight.success[700],
    contrastText: '#ffffff',
  },
  warning: {
    main: colorsLight.warning[500],
    light: colorsLight.warning[300],
    dark: colorsLight.warning[700],
    contrastText: '#ffffff',
  },
  error: {
    main: colorsLight.danger[500],
    light: colorsLight.danger[300],
    dark: colorsLight.danger[700],
    contrastText: '#ffffff',
  },
  info: {
    main: colorsLight.info[500],
    light: colorsLight.info[300],
    dark: colorsLight.info[700],
    contrastText: '#ffffff',
  },
  background: {
    default: colorsLight.neutral[50],
    paper: colorsLight.neutral[0],
  },
  text: {
    primary: colorsLight.neutral[900],
    secondary: colorsLight.neutral[600],
    disabled: colorsLight.neutral[400],
  },
  divider: colorsLight.neutral[200],
  action: {
    active: colorsLight.primary[500],
    hover: colorsLight.primary[50],
    selected: colorsLight.primary[100],
    disabled: colorsLight.neutral[400],
    disabledBackground: colorsLight.neutral[100],
  },
  // Medical Specialty Colors (via augmentation)
  cardiology: {
    main: medical.cardiology.main,
    light: medical.cardiology.light,
    dark: medical.cardiology.dark,
    contrastText: '#ffffff',
  },
  dermatology: {
    main: medical.dermatology.main,
    light: medical.dermatology.light,
    dark: medical.dermatology.dark,
    contrastText: '#ffffff',
  },
  neurology: {
    main: medical.neurology.main,
    light: medical.neurology.light,
    dark: medical.neurology.dark,
    contrastText: '#ffffff',
  },
  orthopedics: {
    main: medical.orthopedics.main,
    light: medical.orthopedics.light,
    dark: medical.orthopedics.dark,
    contrastText: '#ffffff',
  },
  ophthalmology: {
    main: medical.ophthalmology.main,
    light: medical.ophthalmology.light,
    dark: medical.ophthalmology.dark,
    contrastText: '#ffffff',
  },
  dentistry: {
    main: medical.dentistry.main,
    light: medical.dentistry.light,
    dark: medical.dentistry.dark,
    contrastText: '#ffffff',
  },
});

export const createDarkPalette = (): PaletteOptions => ({
  mode: 'dark',
  primary: {
    main: colorsDark.primary[500],
    light: colorsDark.primary[400],
    dark: colorsDark.primary[600],
    contrastText: '#000000',
  },
  secondary: {
    main: colorsDark.secondary[500],
    light: colorsDark.secondary[400],
    dark: colorsDark.secondary[600],
    contrastText: '#000000',
  },
  success: {
    main: colorsDark.success[500],
    light: colorsDark.success[400],
    dark: colorsDark.success[600],
    contrastText: '#000000',
  },
  warning: {
    main: colorsDark.warning[500],
    light: colorsDark.warning[400],
    dark: colorsDark.warning[600],
    contrastText: '#000000',
  },
  error: {
    main: colorsDark.danger[500],
    light: colorsDark.danger[400],
    dark: colorsDark.danger[600],
    contrastText: '#000000',
  },
  info: {
    main: colorsDark.info[500],
    light: colorsDark.info[400],
    dark: colorsDark.info[600],
    contrastText: '#000000',
  },
  background: {
    default: colorsDark.neutral[900],
    paper: colorsDark.neutral[800],
  },
  text: {
    primary: colorsDark.neutral[50],
    secondary: colorsDark.neutral[300],
    disabled: colorsDark.neutral[500],
  },
  divider: colorsDark.neutral[700],
  action: {
    active: colorsDark.primary[500],
    hover: colorsDark.primary[900],
    selected: colorsDark.primary[800],
    disabled: colorsDark.neutral[600],
    disabledBackground: colorsDark.neutral[800],
  },
  // Medical Specialty Colors (dark mode)
  cardiology: {
    main: colorsDark.medical.cardiology.main,
    light: colorsDark.medical.cardiology.light,
    dark: colorsDark.medical.cardiology.dark,
    contrastText: '#ffffff',
  },
  dermatology: {
    main: colorsDark.medical.dermatology.main,
    light: colorsDark.medical.dermatology.light,
    dark: colorsDark.medical.dermatology.dark,
    contrastText: '#ffffff',
  },
  neurology: {
    main: colorsDark.medical.neurology.main,
    light: colorsDark.medical.neurology.light,
    dark: colorsDark.medical.neurology.dark,
    contrastText: '#ffffff',
  },
  orthopedics: {
    main: colorsDark.medical.orthopedics.main,
    light: colorsDark.medical.orthopedics.light,
    dark: colorsDark.medical.orthopedics.dark,
    contrastText: '#ffffff',
  },
  ophthalmology: {
    main: colorsDark.medical.ophthalmology.main,
    light: colorsDark.medical.ophthalmology.light,
    dark: colorsDark.medical.ophthalmology.dark,
    contrastText: '#ffffff',
  },
  dentistry: {
    main: colorsDark.medical.dentistry.main,
    light: colorsDark.medical.dentistry.light,
    dark: colorsDark.medical.dentistry.dark,
    contrastText: '#ffffff',
  },
});
