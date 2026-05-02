# Theme Audit And Admin Appearance Settings

- unified runtime theme catalog in `frontend/src/theme/colorScheme.js`
- introduced shared color helpers in `frontend/src/theme/colorUtils.js`
- made `MacOSThemeProvider` map accent selection to real macOS accent CSS variables
- added derived accent/status tokens for components that rely on `--mac-accent-bg`, `--mac-success-bg`, etc.
- rebuilt `ColorSchemeSelector` so previews, descriptions, and active theme details come from the same catalog
- clarified theme vs accent persistence in `Settings.jsx` and `UnifiedSettings.jsx`
- retuned custom theme structural CSS in `frontend/src/styles/macos.css`
- added regression coverage for theme selector and accent propagation
