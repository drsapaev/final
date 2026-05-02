import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import parser from '@babel/parser';
import traverseModule from '@babel/traverse';
import * as t from '@babel/types';

const traverse = traverseModule.default ?? traverseModule;

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '..');
const frontendRoot = path.join(repoRoot, 'frontend');
const eslintReportPath = path.join(frontendRoot, '.tmp-eslint-src.json');

const report = JSON.parse(fs.readFileSync(eslintReportPath, 'utf8'));
const targetFiles = report
  .filter((file) => Array.isArray(file.messages) && file.messages.some((msg) => msg.ruleId === 'react/prop-types'))
  .map((file) => file.filePath)
  .filter((filePath) => !normalizePath(filePath).includes('/components/emr-v2/'));

const parserOptions = {
  sourceType: 'module',
  plugins: [
    'jsx',
    'classProperties',
    'classPrivateProperties',
    'classPrivateMethods',
    'dynamicImport',
    'optionalChaining',
    'nullishCoalescingOperator',
    'objectRestSpread',
    'topLevelAwait'
  ]
};

const summary = [];

for (const filePath of targetFiles) {
  const absolutePath = normalizePath(filePath);
  const code = fs.readFileSync(absolutePath, 'utf8');
  const ast = parser.parse(code, parserOptions);
  const changes = buildChanges(ast, code);

  if (changes.length === 0) {
    continue;
  }

  const updated = applyChanges(code, changes);
  if (updated !== code) {
    fs.writeFileSync(absolutePath, updated);
    summary.push({ filePath: absolutePath, changes: changes.length });
  }
}

if (summary.length === 0) {
  console.log('No prop-types changes were needed.');
} else {
  console.log(`Updated ${summary.length} files with prop-types coverage.`);
  for (const item of summary.slice(0, 40)) {
    console.log(`- ${item.filePath.replace(repoRoot, '.')} (${item.changes} insertions)`);
  }
  if (summary.length > 40) {
    console.log(`- ...and ${summary.length - 40} more files`);
  }
}

function buildChanges(ast, code) {
  const changes = [];
  const componentMap = new Map();
  const importMap = collectImports(ast);

  traverse(ast, {
    FunctionDeclaration(path) {
      const name = path.node.id?.name;
      if (!isComponentName(name)) {
        return;
      }

      if (!containsJSX(path)) {
        return;
      }

      registerComponent(componentMap, {
        name,
        path,
        props: collectFunctionProps(path),
        anchor: getStatementEnd(path),
        existingPropTypes: collectExistingPropTypes(ast, name)
      });
    },
    ClassDeclaration(path) {
      const name = path.node.id?.name;
      if (!isComponentName(name)) {
        return;
      }

      if (!extendsReactComponent(path.node.superClass)) {
        return;
      }

      if (!containsJSX(path)) {
        return;
      }

      registerComponent(componentMap, {
        name,
        path,
        props: collectClassProps(path),
        anchor: getStatementEnd(path),
        existingPropTypes: collectExistingPropTypes(ast, name)
      });
    },
    VariableDeclarator(path) {
      const name = path.node.id && t.isIdentifier(path.node.id) ? path.node.id.name : null;
      if (!isComponentName(name)) {
        return;
      }

      if (!t.isVariableDeclaration(path.parent)) {
        return;
      }

      const functionPath = resolveComponentFunctionPath(path);
      if (!functionPath) {
        return;
      }

      if (!containsJSX(functionPath)) {
        return;
      }

      registerComponent(componentMap, {
        name,
        path: functionPath,
        props: collectFunctionProps(functionPath),
        anchor: getStatementEnd(path.parentPath),
        existingPropTypes: collectExistingPropTypes(ast, name)
      });
    }
  });

  for (const component of componentMap.values()) {
    const missingProps = [...component.props].filter((prop) => !component.existingPropTypes.has(prop));
    if (missingProps.length === 0) {
      continue;
    }

    const insertionIndex = getInsertionIndex(code, component.anchor);
    const indent = getIndentation(code, component.anchor);
    const assignment = buildPropTypesAssignment(component.name, missingProps, indent);
    changes.push({
      index: insertionIndex,
      text: `\n\n${assignment}\n`
    });
  }

  if (changes.length > 0 && !importMap.has('prop-types')) {
    const importIndex = getImportInsertionIndex(ast, code);
    changes.push({
      index: importIndex,
      text: `import PropTypes from 'prop-types';\n`
    });
  }

  return changes.sort((a, b) => b.index - a.index);
}

function registerComponent(map, component) {
  const current = map.get(component.name);
  if (!current) {
    map.set(component.name, {
      ...component,
      props: new Set(component.props),
      existingPropTypes: new Set(component.existingPropTypes)
    });
    return;
  }

  for (const prop of component.props) {
    current.props.add(prop);
  }
  for (const prop of component.existingPropTypes) {
    current.existingPropTypes.add(prop);
  }
  current.anchor = Math.max(current.anchor, component.anchor);
}

function resolveComponentFunctionPath(variablePath) {
  const initPath = variablePath.get('init');
  if (!initPath || !initPath.node) {
    return null;
  }

  if (initPath.isArrowFunctionExpression() || initPath.isFunctionExpression()) {
    return initPath;
  }

  let resolved = null;
  let nestedFunctionAncestor = false;

  initPath.traverse({
    FunctionExpression(innerPath) {
      if (!resolved) {
        resolved = innerPath;
      }
      innerPath.stop();
    },
    ArrowFunctionExpression(innerPath) {
      if (!resolved) {
        resolved = innerPath;
      }
      innerPath.stop();
    },
    FunctionDeclaration(innerPath) {
      if (!resolved) {
        resolved = innerPath;
      }
      innerPath.stop();
    }
  });

  if (!resolved) {
    return null;
  }

  let cursor = resolved;
  while (cursor.parentPath) {
    cursor = cursor.parentPath;
    if (cursor.isFunction() && cursor.node !== resolved.node) {
      nestedFunctionAncestor = true;
    }
    if (cursor === variablePath) {
      return nestedFunctionAncestor ? null : resolved;
    }
    if (cursor.isVariableDeclaration()) {
      return nestedFunctionAncestor ? null : resolved;
    }
  }

  return nestedFunctionAncestor ? null : resolved;
}

function collectFunctionProps(path) {
  const props = new Set();
  const aliases = new Set();

  const params = path.node.params ?? [];
  const firstParam = params[0];
  const targetParam = unwrapAssignmentPattern(firstParam);

  if (t.isObjectPattern(targetParam)) {
    for (const property of targetParam.properties) {
      if (t.isRestElement(property) && t.isIdentifier(property.argument)) {
        aliases.add(property.argument.name);
        continue;
      }

      if (!t.isObjectProperty(property)) {
        continue;
      }

      const keyName = getObjectPropertyName(property);
      if (keyName) {
        props.add(keyName);
      }

      if (t.isIdentifier(property.value)) {
        aliases.add(property.value.name);
      }
    }
  } else if (t.isIdentifier(targetParam)) {
    aliases.add(targetParam.name);
  }

  path.traverse({
    VariableDeclarator(innerPath) {
      const { node } = innerPath;
      if (!t.isObjectPattern(node.id)) {
        return;
      }

      const alias = getAliasName(node.init);
      if (!alias || !aliases.has(alias)) {
        return;
      }

      for (const property of node.id.properties) {
        if (t.isRestElement(property) && t.isIdentifier(property.argument)) {
          props.add(property.argument.name);
          continue;
        }

        if (t.isObjectProperty(property)) {
          const keyName = getObjectPropertyName(property);
          if (keyName) {
            props.add(keyName);
          }
        }
      }
    },
    MemberExpression(innerPath) {
      const { node } = innerPath;
      const objectName = getAliasName(node.object);
      if (!objectName || !aliases.has(objectName)) {
        return;
      }

      const propName = getMemberPropertyName(node);
      if (propName) {
        props.add(propName);
      }
    },
    OptionalMemberExpression(innerPath) {
      const { node } = innerPath;
      const objectName = getAliasName(node.object);
      if (!objectName || !aliases.has(objectName)) {
        return;
      }

      const propName = getMemberPropertyName(node);
      if (propName) {
        props.add(propName);
      }
    }
  });

  return props;
}

function collectClassProps(path) {
  const props = new Set();

  path.traverse({
    VariableDeclarator(innerPath) {
      const { node } = innerPath;
      if (!t.isObjectPattern(node.id)) {
        return;
      }

      if (!isThisProps(node.init)) {
        return;
      }

      for (const property of node.id.properties) {
        if (t.isRestElement(property) && t.isIdentifier(property.argument)) {
          props.add(property.argument.name);
          continue;
        }

        if (t.isObjectProperty(property)) {
          const keyName = getObjectPropertyName(property);
          if (keyName) {
            props.add(keyName);
          }
        }
      }
    },
    MemberExpression(innerPath) {
      const { node } = innerPath;
      if (!isThisProps(node.object)) {
        return;
      }

      const propName = getMemberPropertyName(node);
      if (propName) {
        props.add(propName);
      }
    },
    OptionalMemberExpression(innerPath) {
      const { node } = innerPath;
      if (!isThisProps(node.object)) {
        return;
      }

      const propName = getMemberPropertyName(node);
      if (propName) {
        props.add(propName);
      }
    }
  });

  return props;
}

function collectExistingPropTypes(ast, name) {
  const keys = new Set();

  traverse(ast, {
    AssignmentExpression(path) {
      const left = path.node.left;
      if (!t.isMemberExpression(left) || left.computed) {
        return;
      }

      if (!t.isIdentifier(left.object, { name }) || !t.isIdentifier(left.property, { name: 'propTypes' })) {
        return;
      }

      const right = path.node.right;
      if (!t.isObjectExpression(right)) {
        return;
      }

      for (const property of right.properties) {
        if (t.isObjectProperty(property)) {
          const keyName = getObjectPropertyName(property);
          if (keyName) {
            keys.add(keyName);
          }
        }
      }
    },
    ClassProperty(path) {
      if (!path.node.static || !t.isIdentifier(path.node.key, { name: 'propTypes' })) {
        return;
      }

      const classPath = path.findParent((parent) => parent.isClassDeclaration());
      if (!classPath || !classPath.node.id || classPath.node.id.name !== name) {
        return;
      }

      if (!t.isObjectExpression(path.node.value)) {
        return;
      }

      for (const property of path.node.value.properties) {
        if (t.isObjectProperty(property)) {
          const keyName = getObjectPropertyName(property);
          if (keyName) {
            keys.add(keyName);
          }
        }
      }
    }
  });

  return keys;
}

function containsJSX(path) {
  let found = false;
  path.traverse({
    JSXElement(innerPath) {
      found = true;
      innerPath.stop();
    },
    JSXFragment(innerPath) {
      found = true;
      innerPath.stop();
    }
  });
  return found;
}

function extendsReactComponent(superClass) {
  if (!superClass) {
    return false;
  }

  if (t.isMemberExpression(superClass)) {
    return t.isIdentifier(superClass.object, { name: 'React' }) && t.isIdentifier(superClass.property, { name: 'Component' });
  }

  return t.isIdentifier(superClass, { name: 'Component' });
}

function collectImports(ast) {
  const imports = new Set();
  traverse(ast, {
    ImportDeclaration(path) {
      imports.add(path.node.source.value);
    }
  });
  return imports;
}

function getImportInsertionIndex(ast, code) {
  let lastImportEnd = 0;
  traverse(ast, {
    ImportDeclaration(path) {
      lastImportEnd = Math.max(lastImportEnd, path.node.end ?? 0);
    }
  });

  if (lastImportEnd === 0) {
    return 0;
  }

  return getLineEndIndex(code, lastImportEnd);
}

function getStatementEnd(path) {
  if (path.parentPath?.isExportNamedDeclaration() || path.parentPath?.isExportDefaultDeclaration()) {
    return path.parentPath.node.end ?? path.node.end ?? 0;
  }

  return path.node.end ?? 0;
}

function buildPropTypesAssignment(name, props, indent) {
  const lines = [
    `${indent}${name}.propTypes = {`,
    `${indent}  ...(${name}.propTypes || {}),`
  ];

  for (const prop of props.sort()) {
    lines.push(`${indent}  ${formatObjectKey(prop)}: PropTypes.any,`);
  }

  lines.push(`${indent}};`);
  return lines.join('\n');
}

function formatObjectKey(key) {
  return /^[A-Za-z_$][A-Za-z0-9_$]*$/.test(key) ? key : JSON.stringify(key);
}

function getIndentation(code, index) {
  const lineStart = code.lastIndexOf('\n', Math.max(0, index - 1));
  const start = lineStart === -1 ? 0 : lineStart + 1;
  const match = code.slice(start, index).match(/^[ \t]*/);
  return match ? match[0] : '';
}

function getInsertionIndex(code, anchor) {
  const lineEnd = getLineEndIndex(code, anchor);
  return lineEnd;
}

function getLineEndIndex(code, index) {
  const nextNewline = code.indexOf('\n', index);
  if (nextNewline === -1) {
    return code.length;
  }
  return nextNewline + 1;
}

function applyChanges(code, changes) {
  let result = code;
  for (const change of changes) {
    result = `${result.slice(0, change.index)}${change.text}${result.slice(change.index)}`;
  }
  return result;
}

function isComponentName(name) {
  return typeof name === 'string' && /^[A-Z][A-Za-z0-9]*$/.test(name);
}

function normalizePath(filePath) {
  return path.resolve(filePath);
}

function unwrapAssignmentPattern(node) {
  if (t.isAssignmentPattern(node)) {
    return node.left;
  }
  return node;
}

function getObjectPropertyName(property) {
  const key = property.key;
  if (t.isIdentifier(key)) {
    return key.name;
  }
  if (t.isStringLiteral(key)) {
    return key.value;
  }
  if (t.isNumericLiteral(key)) {
    return String(key.value);
  }
  return null;
}

function getAliasName(node) {
  if (t.isIdentifier(node)) {
    return node.name;
  }
  if (t.isThisExpression(node)) {
    return 'this';
  }
  if (t.isMemberExpression(node) && isThisProps(node)) {
    return 'this.props';
  }
  if (t.isOptionalMemberExpression(node) && isThisProps(node)) {
    return 'this.props';
  }
  return null;
}

function getMemberPropertyName(node) {
  if (node.computed) {
    if (t.isStringLiteral(node.property)) {
      return node.property.value;
    }
    if (t.isNumericLiteral(node.property)) {
      return String(node.property.value);
    }
    return null;
  }

  if (t.isIdentifier(node.property)) {
    return node.property.name;
  }

  return null;
}

function isThisProps(node) {
  if (t.isMemberExpression(node)) {
    return t.isThisExpression(node.object) && t.isIdentifier(node.property, { name: 'props' });
  }
  if (t.isOptionalMemberExpression(node)) {
    return t.isThisExpression(node.object) && t.isIdentifier(node.property, { name: 'props' });
  }
  return false;
}
