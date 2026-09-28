import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const source = fs.readFileSync(path.join(__dirname, '../EMRContainerV2.tsx'), 'utf8');

describe('EMRContainerV2 visit completion contract', () => {
  it('saves unsaved or newly initialized EMR data before a forced server re-read', () => {
    expect(source).toContain('String(emr.status ?? \'\').trim().toLowerCase() === \'draft\'');
    expect(source).toContain('shouldSave:');
    expect(source).toContain('|| !emr.id');
    expect(source).toContain('save: () => saveEMR({ isDraft: false })');
    expect(source).toContain('reload: () => loadEMR(true)');
    expect(source).toContain('if (!completionScope.active || completionScope.visitId !== visitId) return;');
    expect(source).toContain('await onComplete(savedData)');
  });

  it('blocks completion when load, save, conflict, access, or signed-draft state is unsafe', () => {
    const handler = source.match(/const handleCompleteVisit = useCallback\([\s\S]*?\n\s*\},\s*\[/);
    expect(handler).not.toBeNull();
    for (const condition of [
      'isLoading',
      'isSaving',
      'accessDenied',
      'conflict',
      '!emr',
      '(isSigned && isDirty)',
    ]) {
      expect(handler?.[0]).toContain(condition);
    }
    expect(source).toContain('onCompletionBlocked?.()');
  });

  it('requires the freshly read server EMR to be non-draft before completion', () => {
    const helper = fs.readFileSync(path.join(__dirname, '../emrCompletion.ts'), 'utf8');
    expect(helper).toContain('hasCompletionReadyStatus(latestEMR)');
    expect(helper).toContain('value.status.trim().toLowerCase() !== \'draft\'');
  });

  it('locks every EMR section, keyboard edit action, and mutation dialog for completed visits', () => {
    expect(source.match(/disabled=\{editingDisabled\}/g)?.length).toBeGreaterThanOrEqual(10);
    expect(source).toContain('enabled: (!isReadOnly || canSignReadOnly) && !isPreparingCompletion && !completionBusy');
    expect(source).toContain('{isReadOnly ? (');
    expect(source).toContain('{!isReadOnly && Boolean(conflict)');
    expect(source).toContain('{!isReadOnly && onComplete && (');
  });

  it('allows only confirmed signing for a saved unsigned EMR on a completed visit', () => {
    expect(source).toContain('const canSignReadOnly = isReadOnly');
    expect(source).toContain('savedEMRStatus !== \'draft\'');
    expect(source).toContain('&& !isDirty');
    expect(source).toContain('&& version > 0');
    // R34 regression (#3433 P2): the read-only sign must pass the optimistic-lock
    // token (rowVersion) — NOT the clinical revision (version).
    expect(source).toContain('&& rowVersion > 0');
    expect(source).toContain('signSavedEMR({ confirm: confirmSigning, rowVersion, sign: signEMR })');
    expect(source).not.toContain('signSavedEMR({ confirm: confirmSigning, rowVersion: version, sign: signEMR })');

    const readOnlyBranch = source.match(/\{isReadOnly \? \([\s\S]*?\) : !isSigned \?/);
    expect(readOnlyBranch).not.toBeNull();
    expect(readOnlyBranch?.[0]).toContain('{canSignReadOnly && (');
    expect(readOnlyBranch?.[0]).not.toContain('saveEMR');
    expect(readOnlyBranch?.[0]).not.toContain('emr_save_sign');
  });
});
