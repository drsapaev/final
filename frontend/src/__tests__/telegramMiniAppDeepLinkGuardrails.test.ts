import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const appSource = fs.readFileSync(path.resolve(process.cwd(), 'src/pages/TelegramMiniAppPatientShell.tsx'), 'utf8').replace(/\r\n/g, '\n');

const CANONICAL_SECTIONS = ['appointments', 'visits', 'queue', 'forms', 'cabinet', 'payments', 'results'];
const ALIAS_MAPPINGS = {
  doctors: 'appointments',
  documents: 'results',
  navbat: 'queue',
};

function sourceBetween(source, start, end) {
  const startIndex = source.indexOf(start);
  expect(startIndex).toBeGreaterThanOrEqual(0);

  const endIndex = source.indexOf(end, startIndex + start.length);
  expect(endIndex).toBeGreaterThan(startIndex);

  return source.slice(startIndex, endIndex);
}

describe('Telegram Mini App deep-link guardrails', () => {
  it('keeps section deep links limited to canonical sections and approved aliases', () => {
    const aliases = sourceBetween(
      appSource,
      'const MINI_APP_SECTION_ALIASES = {',
      'const MINI_APP_EXPIRED_ENTRY_TOKEN_REASONS = new Set'
    );
    const selectedSectionParser = sourceBetween(
      appSource,
      'function getTelegramMiniAppSelectedSection(search) {',
      'function normalizeMiniAppLanguage(languageCode) {'
    );

    CANONICAL_SECTIONS.forEach((section) => {
      expect(aliases).toContain(`${section}: '${section}'`);
    });
    Object.entries(ALIAS_MAPPINGS).forEach(([alias, canonical]) => {
      expect(aliases).toContain(`${alias}: '${canonical}'`);
    });

    expect(aliases).not.toContain('patient:');
    expect(aliases).not.toContain('admin:');
    expect(aliases).not.toContain('record:');
    expect(aliases).not.toContain('billing:');
    expect(selectedSectionParser).toContain('new URLSearchParams(search || \'\').get(\'section\') || \'\'');
    expect(selectedSectionParser).toContain('section.trim().toLowerCase()');
    expect(selectedSectionParser).toContain('MINI_APP_SECTION_ALIASES[section.trim().toLowerCase()] || \'\'');
  });

  it('keeps unknown sections from opening a selected-section panel', () => {
    const shellSetup = sourceBetween(
      appSource,
      'function TelegramMiniAppPatientShell() {',
      'useEffect(() => {'
    );
    const selectedSectionPanel = sourceBetween(
      appSource,
      '{selectedSection && (',
      '{selectedSection === \'cabinet\' && cabinetSummary.status === \'loading\' && ('
    );

    expect(shellSetup).toContain('const selectedSection = getTelegramMiniAppSelectedSection(location.search);');
    expect(appSource).toContain('const selectedCapability = selectedSection ? capabilities[selectedSection] || {} : null;');
    expect(selectedSectionPanel).toContain('{selectedSection && (');
    expect(selectedSectionPanel).toContain('{capabilityLabels[selectedSection]}');
    expect(selectedSectionPanel).toContain('localizeMiniAppCapabilityStatus(languageCode, selectedCapability?.status)');
    expect(selectedSectionPanel).not.toContain('URLSearchParams');
    expect(selectedSectionPanel).not.toContain('location.search');
  });

  it('ties each runtime panel to the canonical selected section, not aliases or raw query text', () => {
    const panelGates = sourceBetween(
      appSource,
      'const canPreviewAppointments = Boolean(',
      'const handleMiniAppCapabilitySelect = (section) => {'
    );
    const capabilityGrid = sourceBetween(
      appSource,
      '<section style={miniAppGridStyle}>',
      '</section>'
    );

    CANONICAL_SECTIONS.forEach((section) => {
      expect(appSource).toContain(`selectedSection === '${section}'`);
    });
    Object.keys(ALIAS_MAPPINGS).forEach((alias) => {
      expect(panelGates).not.toContain(`selectedSection === '${alias}'`);
    });

    expect(panelGates).toContain('selectedCapability?.preview_enabled');
    expect(panelGates).toContain('selectedCapability?.create_enabled');
    expect(panelGates).not.toContain('URLSearchParams');
    expect(panelGates).not.toContain('location.search');
    expect(capabilityGrid).toContain('const isSelected = key === selectedSection;');
    expect(capabilityGrid).toContain('...(isSelected ? miniAppCapabilitySelectedStyle : {})');
  });

  it('lets capability cards switch canonical Mini App sections without legacy URLs or raw patient identifiers', () => {
    const capabilitySelectHandler = sourceBetween(
      appSource,
      'const handleMiniAppCapabilitySelect = (section) => {',
      'const handleAppointmentPreviewFieldChange = (field) => (event) => {'
    );
    const capabilityGrid = sourceBetween(
      appSource,
      '<section style={miniAppGridStyle}>',
      '</section>'
    );

    expect(capabilitySelectHandler).toContain('new URLSearchParams(location.search || \'\')');
    expect(capabilitySelectHandler).toContain('params.set(\'section\', section)');
    expect(capabilitySelectHandler).toContain('navigate({');
    expect(capabilitySelectHandler).toContain('pathname: location.pathname');
    expect(capabilitySelectHandler).toContain('search: `?${params.toString()}`');
    expect(capabilitySelectHandler).not.toContain('/patient?tab=');
    expect(capabilitySelectHandler).not.toMatch(/patientId|telegramUserId|chatId/);
    expect(capabilityGrid).toContain('interactive');
    expect(capabilityGrid).toContain('onClick={() => handleMiniAppCapabilitySelect(key)}');
    expect(capabilityGrid).toContain('aria-pressed={isSelected}');
    expect(capabilityGrid).toContain('aria-label={`${t(\'openSection\')}: ${label}`}');
  });

  it('keeps the Mini App shell away from legacy patient tab URLs', () => {
    const miniAppShell = sourceBetween(
      appSource,
      'function TelegramMiniAppPatientShell() {',
      'const miniAppPageStyle = {'
    );

    expect(miniAppShell).toContain('/telegram/mini-app/patient/manifest');
    expect(miniAppShell).not.toContain('/patient?tab=');
    expect(miniAppShell).not.toContain('tab=<section>');
    expect(miniAppShell).not.toContain('WebAppInfo');
  });
});
