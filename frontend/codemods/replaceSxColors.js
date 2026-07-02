/**
 * jscodeshift codemod: Replace hardcoded hex colors with theme.palette references
 * Usage: jscodeshift -t codemods/replaceSxColors.js src/components
 */

module.exports = function(fileInfo, api) {
  const j = api.jscodeshift;
  const root = j(fileInfo.source);
  let hasChanges = false;

  // Color mapping - customize based on your design tokens
  const colorMap = {
    '#1976d2': 'theme.palette.primary.main',
    '#1565c0': 'theme.palette.primary.dark',
    '#2196f3': 'theme.palette.primary.light',
    '#dc2626': 'theme.palette.error.main',
    '#d32f2f': 'theme.palette.error.dark',
    '#f44336': 'theme.palette.error.light',
    '#388e3c': 'theme.palette.success.main',
    '#1b5e20': 'theme.palette.success.dark',
    '#4caf50': 'theme.palette.success.light',
    '#f57c00': 'theme.palette.warning.main',
    '#e65100': 'theme.palette.warning.dark',
    '#ff9800': 'theme.palette.warning.light',
    '#0288d1': 'theme.palette.info.main',
    '#01579b': 'theme.palette.info.dark',
    '#03a9f4': 'theme.palette.info.light',
    '#999999': 'theme.palette.divider',
    '#eeeeee': 'theme.palette.divider',
    '#f5f5f5': 'theme.palette.background.default',
    '#fafafa': 'theme.palette.background.paper',
    '#ffffff': 'theme.palette.background.paper',
    '#000000': 'theme.palette.text.primary',
  };

  // Find sx prop assignments
  root.find(j.JSXAttribute, {
    name: { name: 'sx' },
  }).forEach(path => {
    const value = path.value.value;
    
    if (value.type === 'JSXExpressionContainer') {
      const obj = value.expression;
      
      if (obj.type === 'ObjectExpression') {
        obj.properties.forEach(prop => {
          if (prop.type === 'Property') {
            const propValue = prop.value;
            
            // Replace string literals (e.g., color: '#1976d2')
            if (propValue.type === 'Literal' && typeof propValue.value === 'string') {
              const colorKey = propValue.value.toLowerCase();
              if (colorMap[colorKey]) {
                prop.value = j.identifier(colorMap[colorKey]);
                hasChanges = true;
              }
            }
            
            // Replace object properties (e.g., backgroundColor: '#1976d2')
            if (propValue.type === 'ObjectExpression') {
              propValue.properties.forEach(nestedProp => {
                if (nestedProp.type === 'Property' && 
                    nestedProp.value.type === 'Literal' && 
                    typeof nestedProp.value.value === 'string') {
                  const colorKey = nestedProp.value.value.toLowerCase();
                  if (colorMap[colorKey]) {
                    nestedProp.value = j.identifier(colorMap[colorKey]);
                    hasChanges = true;
                  }
                }
              });
            }
          }
        });
      }
    }
  });

  // Find inline style prop assignments
  root.find(j.JSXAttribute, {
    name: { name: 'style' },
  }).forEach(path => {
    const value = path.value.value;
    
    if (value.type === 'JSXExpressionContainer' && value.expression.type === 'ObjectExpression') {
      const obj = value.expression;
      obj.properties.forEach(prop => {
        if (prop.type === 'Property' && 
            prop.value.type === 'Literal' && 
            typeof prop.value.value === 'string') {
          const colorKey = prop.value.value.toLowerCase();
          if (colorMap[colorKey]) {
            // Recommend moving to sx prop instead
            console.warn(`Found hardcoded color in style prop: ${colorKey}. Consider using sx prop instead.`);
          }
        }
      });
    }
  });

  return hasChanges ? root.toSource({ quote: 'single' }) : fileInfo.source;
};
