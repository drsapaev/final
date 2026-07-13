import fs from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

const ROOT = path.resolve(process.cwd(), 'src');
const source = fs.readFileSync(
  path.join(ROOT, 'components/laboratory/LabTemplateWorkbench.jsx'),
  'utf8'
).replace(/\r\n/g, '\n');

describe('LabTemplateWorkbench Phase 4+ structure contract', () => {
  it('renders 4 editor tabs: Content / Design / Signers / Preview', () => {
    expect(source).toContain('id: \'content\'');
    expect(source).toContain('id: \'design\'');
    expect(source).toContain('id: \'signers\'');
    expect(source).toContain('id: \'preview\'');
    expect(source).toContain('EDITOR_TABS');
  });

  it('uses a NewTemplateDialog instead of always-visible form', () => {
    // Dialog component must be imported and used
    expect(source).toContain('NewTemplateDialog');
    expect(source).toContain('showNewTemplateDialog');
    expect(source).toContain('setShowNewTemplateDialog');

    // Must NOT contain the old always-visible newTemplate state + inline form
    expect(source).not.toContain('const [newTemplate, setNewTemplate] = useState');
  });

  it('Content tab renders sections and fields', () => {
    expect(source).toContain('renderContentTab');
    expect(source).toContain('addSection');
    expect(source).toContain('addField');
    expect(source).toContain('removeField');
    expect(source).toContain('removeSection');
  });

  it('Design tab renders layout + branding + footer', () => {
    expect(source).toContain('renderDesignTab');
    expect(source).toContain('layout_preset');
    expect(source).toContain('branding_overrides');
    expect(source).toContain('footer_notes');
  });

  it('Signers tab renders 4 signer defaults', () => {
    expect(source).toContain('renderSignersTab');
    expect(source).toContain('lab_technician_label');
    expect(source).toContain('lab_technician_name');
    expect(source).toContain('approver_label');
    expect(source).toContain('approver_name');
  });

  it('Preview tab renders a read-only sample of the template', () => {
    expect(source).toContain('renderPreviewTab');
    expect(source).toContain('Предпросмотр показывает структуру бланка');
  });

  it('preserves backend-owned template version action contract', () => {
    // These must still exist — the existing contract test depends on them.
    expect(source).toContain('function hasTemplateVersionAction(version, action) {');
    expect(source).toContain('async function ensureDraftVersion() {');
    expect(source).toContain('labReportingApi.createTemplateVersion');
    expect(source).toContain('TEMPLATE_VERSION_ACTION_CAN_FIELD');
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
    expect(source).toContain('aria-expanded={isSectionExpanded}');
  });

  it('Phase 2: field cards are collapsible (expandedFields state + toggleField)', () => {
    expect(source).toContain('expandedFields');
    expect(source).toContain('toggleField');
    expect(source).toContain('aria-expanded={isFieldExpanded}');
  });

  it('Phase 2: supports field duplication', () => {
    expect(source).toContain('function duplicateField');
    expect(source).toContain('Дублировать поле');
  });

  it('Phase 2: supports field and section reordering (move up/down)', () => {
    expect(source).toContain('function moveField');
    expect(source).toContain('function moveSection');
    expect(source).toContain('\'up\'');
    expect(source).toContain('\'down\'');
  });
});
