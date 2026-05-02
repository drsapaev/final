#!/usr/bin/env node

/**
 * Automated Theme Audit Script
 * Scans codebase for violations and generates structured report
 * Usage: node scripts/auditThemeUsage.js [--fix] [--strict] [--output=json|html|text]
 */

const fs = require('fs');
const path = require('path');
const glob = require('glob');
const { parse } = require('@babel/parser');

// Color codes for console output
const colors = {
  reset: '\x1b[0m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  green: '\x1b[32m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m',
};

class ThemeAudit {
  constructor(options = {}) {
    this.violations = [];
    this.warnings = [];
    this.filesScanned = 0;
    this.options = {
      strict: options.strict || false,
      fix: options.fix || false,
      outputFormat: options.output || 'text',
      projectRoot: path.resolve(process.cwd(), 'frontend'),
    };
  }

  async run() {
    console.log(`${colors.cyan}Starting Theme Audit...${colors.reset}`);
    console.log(`Project root: ${this.options.projectRoot}\n`);

    // Scan for violations
    await this.scanComponents();
    await this.scanStyles();
    await this.scanImports();

    // Generate report
    this.generateReport();
  }

  async scanComponents() {
    console.log(`${colors.blue}Scanning components...${colors.reset}`);
    const pattern = path.join(this.options.projectRoot, 'src/components/**/*.{jsx,tsx}');
    
    const files = glob.sync(pattern, { nodir: true });
    this.filesScanned += files.length;

    for (const file of files) {
      const content = fs.readFileSync(file, 'utf-8');
      
      // Check for hardcoded hex colors
      const hexPattern = /#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})/g;
      const hexMatches = [...content.matchAll(hexPattern)];
      if (hexMatches.length > 0) {
        this.violations.push({
          file,
          type: 'HARDCODED_HEX',
          severity: 'error',
          message: `Found ${hexMatches.length} hardcoded hex color(s)`,
          count: hexMatches.length,
        });
      }

      // Check for rgba() colors
      const rgbaPattern = /rgba?\s*\(\s*\d+\s*,\s*\d+\s*,\s*\d+/g;
      const rgbaMatches = [...content.matchAll(rgbaPattern)];
      if (rgbaMatches.length > 0) {
        this.violations.push({
          file,
          type: 'INLINE_RGBA',
          severity: 'error',
          message: `Found ${rgbaMatches.length} inline rgb/rgba color(s)`,
          count: rgbaMatches.length,
        });
      }

      // Check for inline style prop with color values
      const inlineStylePattern = /style\s*=\s*\{\s*[^}]*(?:color|background|border)[^}]*\}/g;
      const inlineMatches = [...content.matchAll(inlineStylePattern)];
      if (inlineMatches.length > 0) {
        this.violations.push({
          file,
          type: 'INLINE_STYLE_COLOR',
          severity: 'warning',
          message: `Found ${inlineMatches.length} inline style prop(s) with color properties`,
          count: inlineMatches.length,
        });
      }

      // Check for hardcoded padding/margin/spacing
      const spacingPattern = /(?:padding|margin|gap|spacing)\s*:\s*['"]?(\d+)(?:px)?['"]?/g;
      const spacingMatches = [...content.matchAll(spacingPattern)];
      const invalidSpacing = spacingMatches.filter(m => {
        const value = parseInt(m[1]);
        return value % 8 !== 0 && value % 4 !== 0; // Not on 4px or 8px grid
      });
      
      if (invalidSpacing.length > 0) {
        this.warnings.push({
          file,
          type: 'NON_STANDARD_SPACING',
          severity: 'warning',
          message: `Found ${invalidSpacing.length} spacing value(s) not on 4px/8px grid`,
          count: invalidSpacing.length,
        });
      }

      // Check for CSS class usage
      const classPattern = /className\s*=\s*['"]([\w-]+)['"]/g;
      const classMatches = [...content.matchAll(classPattern)];
      if (classMatches.length > 10) {
        this.warnings.push({
          file,
          type: 'EXCESSIVE_CSS_CLASSES',
          severity: 'info',
          message: `Found ${classMatches.length} CSS classes. Consider migrating to sx prop.`,
          count: classMatches.length,
        });
      }
    }

    console.log(`${colors.green}✓ Scanned ${files.length} component files${colors.reset}`);
  }

  async scanStyles() {
    console.log(`${colors.blue}Scanning CSS files...${colors.reset}`);
    const pattern = path.join(this.options.projectRoot, 'src/**/*.{css,module.css}');
    
    const files = glob.sync(pattern, { nodir: true });
    
    for (const file of files) {
      // Legacy CSS files should be removed
      if (!file.includes('node_modules')) {
        this.violations.push({
          file,
          type: 'LEGACY_CSS_FILE',
          severity: 'warning',
          message: 'Legacy CSS file should be migrated to MUI theme',
        });
      }
    }

    if (files.length > 0) {
      console.log(`${colors.yellow}⚠ Found ${files.length} CSS file(s) to migrate${colors.reset}`);
    }
  }

  async scanImports() {
    console.log(`${colors.blue}Scanning imports...${colors.reset}`);
    const pattern = path.join(this.options.projectRoot, 'src/**/*.{jsx,tsx}');
    
    const files = glob.sync(pattern, { nodir: true });
    let importIssues = 0;

    for (const file of files) {
      const content = fs.readFileSync(file, 'utf-8');
      
      // Check for missing useTheme hook where needed
      if (content.includes('theme.spacing') || content.includes('theme.palette')) {
        if (!content.includes('useTheme')) {
          importIssues++;
          this.violations.push({
            file,
            type: 'MISSING_THEME_HOOK',
            severity: 'error',
            message: 'File uses theme but missing useTheme() import',
          });
        }
      }
    }

    if (importIssues > 0) {
      console.log(`${colors.yellow}⚠ Found ${importIssues} import issue(s)${colors.reset}`);
    }
  }

  generateReport() {
    const totalViolations = this.violations.length + this.warnings.length;
    
    console.log(`\n${colors.cyan}═══════════════════════════════════${colors.reset}`);
    console.log(`${colors.cyan}AUDIT REPORT${colors.reset}`);
    console.log(`${colors.cyan}═══════════════════════════════════${colors.reset}\n`);

    console.log(`Files Scanned: ${this.filesScanned}`);
    console.log(`Violations: ${colors.red}${this.violations.length}${colors.reset}`);
    console.log(`Warnings: ${colors.yellow}${this.warnings.length}${colors.reset}\n`);

    // Group by type
    const byType = {};
    [...this.violations, ...this.warnings].forEach(v => {
      if (!byType[v.type]) byType[v.type] = [];
      byType[v.type].push(v);
    });

    Object.entries(byType).forEach(([type, items]) => {
      const count = items.reduce((sum, item) => sum + (item.count || 1), 0);
      console.log(`${colors.yellow}${type}:${colors.reset} ${count} issue(s)`);
      items.slice(0, 3).forEach(item => {
        const icon = item.severity === 'error' ? '❌' : '⚠️';
        console.log(`  ${icon} ${path.relative(this.options.projectRoot, item.file)}`);
        console.log(`     ${item.message}`);
      });
      if (items.length > 3) {
        console.log(`  ... and ${items.length - 3} more`);
      }
    });

    // Determine exit code
    const errorCount = this.violations.filter(v => v.severity === 'error').length;
    const shouldFail = this.options.strict || errorCount > 0;

    if (shouldFail) {
      console.log(`\n${colors.red}AUDIT FAILED${colors.reset}`);
      process.exit(1);
    } else {
      console.log(`\n${colors.green}AUDIT PASSED${colors.reset}`);
      process.exit(0);
    }
  }
}

// Run the audit
const args = process.argv.slice(2);
const options = {
  strict: args.includes('--strict'),
  fix: args.includes('--fix'),
  output: args.find(arg => arg.startsWith('--output='))?.split('=')[1] || 'text',
};

const audit = new ThemeAudit(options);
audit.run().catch(err => {
  console.error(`${colors.red}Audit error: ${err.message}${colors.reset}`);
  process.exit(1);
});
