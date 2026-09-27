/**
 * Cardioplan slice 5 contract: "Упрощение экрана".
 *
 * Pins the screen-simplification slice:
 *  - the floating settings menu (FAB + popover) is gone, together with the
 *    unused "show ECG and Echo together" toggle and its duplicate Save
 *    button (localStorage persistence made it a no-op);
 *  - the LDL threshold remains the single persisted setting and its editor
 *    lives where it is consumed — the blood tests tab;
 *  - hotkeys match the four visible sidebar sections (queue, visit,
 *    patients, ai) with the former blood view kept as a legacy-compatible
 *    transition.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const panelSource = fs.readFileSync(
  path.join(__dirname, '../CardiologistPanelUnified.tsx'),
  'utf8',
);
const hotkeysSource = fs.readFileSync(
  path.join(__dirname, '../../hooks/useCardiologistHotkeys.ts'),
  'utf8',
);
const bloodTabSource = fs.readFileSync(
  path.join(__dirname, '../../components/cardiology/BloodTestsTab.tsx'),
  'utf8',
);

describe('Cardiology screen simplification contract', () => {
  it('removes the floating settings menu from the panel', () => {
    expect(panelSource).not.toContain('cardio-settings-fab');
    expect(panelSource).not.toContain('settingsOpen');
    expect(panelSource).not.toContain('showEcgEchoTogether');
    expect(panelSource).not.toContain('cardio_panel_settings_show_ecg_echo');
  });

  it('keeps only the LDL threshold as the persisted setting', () => {
    expect(panelSource).toContain("useLocalStorage('cardio.settings'");
    const settingsBlock = panelSource.match(/useLocalStorage\('cardio\.settings'[\s\S]*?\}\);/);
    expect(settingsBlock).not.toBeNull();
    expect(settingsBlock?.[0]).toContain('ldlThreshold');
    expect(settingsBlock?.[0]).not.toContain('showEcgEchoTogether');
  });

  it('hosts the LDL threshold editor in the blood tests tab', () => {
    expect(bloodTabSource).toContain('onLdlThresholdChange');
    expect(bloodTabSource).toContain('cardio_panel_settings_ldl_threshold');
    expect(panelSource).toContain('onLdlThresholdChange={(value: number)');
  });

  it('matches hotkeys to the four visible sections and keeps blood as legacy', () => {
    const tabMap = hotkeysSource.match(/const tabMap = \{[\s\S]*?\};/);
    expect(tabMap).not.toBeNull();
    const order = (tabMap?.[0].match(/'[^']+'/g) ?? []).map((s) => s.slice(1, -1));
    expect(order).toEqual(['1', 'queue', '2', 'visit', '3', 'patients', '4', 'ai', '5', 'blood']);
  });
});
