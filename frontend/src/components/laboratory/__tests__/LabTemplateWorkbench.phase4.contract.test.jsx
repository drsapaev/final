import fs from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../../..');

// L-H-6 fix: контракт-тест обновлён под декомпозицию LabTemplateWorkbench.
// Раньше проверки требовали, чтобы все tab-renderers жили внутри одного файла.
// Теперь они вынесены в templateEditor/{ContentTab,DesignTab,SignersTab,PreviewTab}.jsx —
// тест проверяет, что LabTemplateWorkbench импортирует и использует их.
const source = fs.readFileSync(
  path.join(ROOT, 'components/laboratory/LabTemplateWorkbench.jsx'),
  'utf8'
).replace(/\r\n/g, '\n');

const configSource = fs.readFileSync(
  path.join(ROOT, 'components/laboratory/templateEditor/config.js'),
  'utf8'
).replace(/\r\n/g, '\n');

const utilsSource = fs.readFileSync(
  path.join(ROOT, 'components/laboratory/templateEditor/utils.js'),
  'utf8'
).replace(/\r\n/g, '\n');

describe('LabTemplateWorkbench Phase 4+ structure contract', () => {
  it('renders 4 editor tabs: Content / Design / Signers / Preview', () => {
    // EDITOR_TABS теперь в templateEditor/config.js — но LabTemplateWorkbench
    // импортирует и использует их.
    expect(configSource).toContain("id: 'content'");
    expect(configSource).toContain("id: 'design'");
    expect(configSource).toContain("id: 'signers'");
    expect(configSource).toContain("id: 'preview'");
    expect(source).toContain('EDITOR_TABS');
  });

  it('uses a NewTemplateDialog instead of always-visible form', () => {
    expect(source).toContain('NewTemplateDialog');
    expect(source).toContain('showNewTemplateDialog');
    expect(source).toContain('setShowNewTemplateDialog');
    expect(source).not.toContain('const [newTemplate, setNewTemplate] = useState');
  });

  it('Content tab renders sections and fields (delegated to ContentTab.jsx)', () => {
    expect(source).toContain('ContentTab');
    expect(source).toContain('addSection');
    expect(source).toContain('addField');
    expect(source).toContain('removeField');
    expect(source).toContain('removeSection');
  });

  it('Design tab renders layout + branding + footer (delegated to DesignTab.jsx)', () => {
    expect(source).toContain('DesignTab');
    expect(source).toContain('layout_preset');
    expect(source).toContain('branding_overrides');
    expect(source).toContain('footer_notes');
  });

  it('Signers tab renders 4 signer defaults (delegated to SignersTab.jsx)', () => {
    expect(source).toContain('SignersTab');
    // L-H-6: signer field keys теперь в SignersTab.jsx + config.js
    const signersTabSource = fs.readFileSync(
      path.join(ROOT, 'components/laboratory/templateEditor/SignersTab.jsx'),
      'utf8'
    ).replace(/\r\n/g, '\n');
    expect(signersTabSource).toContain('lab_technician_label');
    expect(signersTabSource).toContain('lab_technician_name');
    expect(signersTabSource).toContain('approver_label');
    expect(signersTabSource).toContain('approver_name');
  });

  it('Preview tab renders a read-only sample of the template (delegated to PreviewTab.jsx)', () => {
    expect(source).toContain('PreviewTab');
    const previewTabSource = fs.readFileSync(
      path.join(ROOT, 'components/laboratory/templateEditor/PreviewTab.jsx'),
      'utf8'
    ).replace(/\r\n/g, '\n');
    expect(previewTabSource).toContain('Предпросмотр показывает структуру бланка');
  });

  it('preserves backend-owned template version action contract', () => {
    // hasTemplateVersionAction + TEMPLATE_VERSION_ACTION_CAN_FIELD
    // теперь в templateEditor/utils.js — тест проверяет оба файла.
    expect(utilsSource).toContain('function hasTemplateVersionAction(version, action) {');
    expect(source).toContain('async function ensureDraftVersion() {');
    expect(source).toContain('labReportingApi.createTemplateVersion');
    expect(utilsSource).toContain('TEMPLATE_VERSION_ACTION_CAN_FIELD');
  });

  it('preserves all template CRUD handlers', () => {
    expect(source).toContain('async function handleCreateTemplate');
    expect(source).toContain('async function handleSaveTemplate');
    expect(source).toContain('async function handlePublishVersion');
    expect(source).toContain('async function handleCloneTemplate');
  });

  // Phase 2: collapsible sections + field cards + duplicate + reorder
  it('Phase 2: sections are collapsible (expandedSections state + toggleSection)', () => {
    expect(source).toContain('expandedSections');
    expect(source).toContain('toggleSection');
  });

  it('Phase 2: field cards are collapsible (expandedFields state + toggleField)', () => {
    expect(source).toContain('expandedFields');
    expect(source).toContain('toggleField');
  });

  it('Phase 2: supports field duplication', () => {
    expect(source).toContain('function duplicateField');
  });

  it('Phase 2: supports field and section reordering (move up/down)', () => {
    expect(source).toContain('function moveField');
    expect(source).toContain('function moveSection');
    // L-H-6: 'up'/'down' теперь в ContentTab.jsx как строковые литералы
    // в onMoveField / onMoveSection колбэках.
    const contentTabSource = fs.readFileSync(
      path.join(ROOT, 'components/laboratory/templateEditor/ContentTab.jsx'),
      'utf8'
    ).replace(/\r\n/g, '\n');
    expect(contentTabSource).toContain("'up'");
    expect(contentTabSource).toContain("'down'");
  });
});
