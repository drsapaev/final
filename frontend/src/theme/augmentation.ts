/**
 * MUI Theme Augmentation
 * Extends MUI's default types to include custom palette colors (medical specialties)
 * This enables full TypeScript support for theme.palette.cardiology, etc.
 */

import { PaletteOptions, PaletteColor } from '@mui/material/styles';

declare module '@mui/material/styles' {
  interface Palette {
    cardiology: PaletteColor;
    dermatology: PaletteColor;
    neurology: PaletteColor;
    orthopedics: PaletteColor;
    ophthalmology: PaletteColor;
    dentistry: PaletteColor;
  }

  interface PaletteOptions {
    cardiology?: PaletteColor;
    dermatology?: PaletteColor;
    neurology?: PaletteColor;
    orthopedics?: PaletteColor;
    ophthalmology?: PaletteColor;
    dentistry?: PaletteColor;
  }
}

declare module '@mui/material' {
  interface ButtonPropsColorOverrides {
    cardiology: true;
    dermatology: true;
    neurology: true;
    orthopedics: true;
    ophthalmology: true;
    dentistry: true;
  }

  interface ChipPropsColorOverrides {
    cardiology: true;
    dermatology: true;
    neurology: true;
    orthopedics: true;
    ophthalmology: true;
    dentistry: true;
  }

  interface BadgePropsColorOverrides {
    cardiology: true;
    dermatology: true;
    neurology: true;
    orthopedics: true;
    ophthalmology: true;
    dentistry: true;
  }
}
