/**
 * jscodeshift codemod: Replace legacy CSS imports with MUI theme approach
 * Usage: jscodeshift -t codemods/replaceCssImports.js src/components
 */

module.exports = function(fileInfo, api) {
  const j = api.jscodeshift;
  const root = j(fileInfo.source);
  let hasChanges = false;

  // List of CSS files to replace (customize based on your codebase)
  const legacyCssPatterns = [
    /\.\/.*\.css$/,
    /\.\/.*\.module\.css$/,
    /styles\//,
    /styleSheets\//,
    /legacy-styles/,
  ];

  // Find CSS imports
  root.find(j.ImportDeclaration).forEach(path => {
    const source = path.value.source.value;
    
    // Check if this is a legacy CSS import
    const isLegacyCss = legacyCssPatterns.some(pattern => pattern.test(source));
    
    if (isLegacyCss) {
      // Remove the import
      j(path).remove();
      hasChanges = true;
      console.log(`Removed CSS import: ${source}`);
    }
  });

  // Add useTheme import if needed and not already present
  const hasUseThemeImport = root.find(j.ImportDeclaration).some(path => {
    return path.value.source.value === '@mui/material/styles' &&
           path.value.specifiers.some(spec => spec.imported.name === 'useTheme');
  });

  if (!hasUseThemeImport && hasChanges) {
    const newImport = j.importDeclaration(
      [j.importSpecifier(j.identifier('useTheme'))],
      j.literal('@mui/material/styles')
    );
    
    root.find(j.Program).get('body').unshift(newImport);
    hasChanges = true;
    console.log('Added useTheme import from @mui/material/styles');
  }

  return hasChanges ? root.toSource({ quote: 'single' }) : fileInfo.source;
};
