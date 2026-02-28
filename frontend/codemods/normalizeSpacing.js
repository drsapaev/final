/**
 * jscodeshift codemod: Normalize spacing values to theme.spacing()
 * Usage: jscodeshift -t codemods/normalizeSpacing.js src/components
 * 
 * Converts hardcoded spacing (8, 16, 24px) to theme.spacing(1, 2, 3)
 */

module.exports = function(fileInfo, api) {
  const j = api.jscodeshift;
  const root = j(fileInfo.source);
  let hasChanges = false;

  // Mapping: pixel value → spacing units
  // Based on 8px base unit (theme.spacing(1) = 8px)
  const spacingMap = {
    '4px': 'spacing(0.5)',
    '8px': 'spacing(1)',
    '12px': 'spacing(1.5)',
    '16px': 'spacing(2)',
    '20px': 'spacing(2.5)',
    '24px': 'spacing(3)',
    '28px': 'spacing(3.5)',
    '32px': 'spacing(4)',
    '40px': 'spacing(5)',
    '48px': 'spacing(6)',
    '56px': 'spacing(7)',
    '64px': 'spacing(8)',
    '72px': 'spacing(9)',
    '80px': 'spacing(10)',
  };

  // Helper function to check if value is a spacing value
  function getSpacingReplacement(value) {
    const str = String(value).toLowerCase();
    
    // Direct px matches
    if (spacingMap[str]) {
      return `theme.${spacingMap[str]}`;
    }
    
    // Numeric pixel values
    const pxMatch = str.match(/^(\d+)px$/);
    if (pxMatch) {
      const px = parseInt(pxMatch[1]);
      if (px % 8 === 0) {
        const units = px / 8;
        return `theme.spacing(${units})`;
      }
    }
    
    return null;
  }

  // Find sx prop assignments
  root.find(j.JSXAttribute, {
    name: { name: 'sx' },
  }).forEach(path => {
    const value = path.value.value;
    
    if (value.type === 'JSXExpressionContainer' && value.expression.type === 'ObjectExpression') {
      const obj = value.expression;
      
      obj.properties.forEach(prop => {
        if (prop.type === 'Property') {
          const propName = prop.key.name || prop.key.value;
          const propValue = prop.value;
          
          // Check if this is a spacing-related property
          const spacingProps = ['p', 'padding', 'paddingTop', 'paddingBottom', 'paddingLeft', 'paddingRight',
                                'm', 'margin', 'marginTop', 'marginBottom', 'marginLeft', 'marginRight',
                                'gap', 'spacing', 'pt', 'pb', 'pl', 'pr', 'mt', 'mb', 'ml', 'mr'];
          
          if (spacingProps.includes(propName) && propValue.type === 'Literal') {
            const replacement = getSpacingReplacement(propValue.value);
            if (replacement) {
              prop.value = j.templateLiteral(
                [j.templateElement({ cooked: replacement, raw: replacement }, false)],
                []
              );
              hasChanges = true;
            }
          }
        }
      });
    }
  });

  // Find direct style object assignments (e.g., const styles = { padding: '16px' })
  root.find(j.VariableDeclarator).forEach(path => {
    if (path.value.init && path.value.init.type === 'ObjectExpression') {
      const obj = path.value.init;
      obj.properties.forEach(prop => {
        if (prop.type === 'Property' && prop.value.type === 'Literal') {
          const propName = prop.key.name || prop.key.value;
          const spacingProps = ['p', 'padding', 'paddingTop', 'paddingBottom', 'paddingLeft', 'paddingRight',
                                'm', 'margin', 'marginTop', 'marginBottom', 'marginLeft', 'marginRight',
                                'gap', 'spacing', 'pt', 'pb', 'pl', 'pr', 'mt', 'mb', 'ml', 'mr'];
          
          if (spacingProps.includes(propName)) {
            const replacement = getSpacingReplacement(prop.value.value);
            if (replacement) {
              // Mark for review since this needs useTheme() hook
              console.warn(`Detected spacing in inline object: ${propName}. May need useTheme() hook.`);
            }
          }
        }
      });
    }
  });

  return hasChanges ? root.toSource({ quote: 'single' }) : fileInfo.source;
};
