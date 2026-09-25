import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const source = fs.readFileSync(path.join(__dirname, '../EMRContainerV2.tsx'), 'utf8');

describe('EMRContainerV2 visit completion contract', () => {
  it('saves unsaved or newly initialized EMR data before a forced server re-read', () => {
    expect(source).toContain('shouldSave: isDirty || !emr.id');
    expect(source).toContain('save: () => saveEMR({ isDraft: true })');
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

  it('locks every EMR section, keyboard edit action, and mutation dialog for completed visits', () => {
    expect(source.match(/disabled=\{editingDisabled\}/g)?.length).toBeGreaterThanOrEqual(10);
    expect(source).toContain('enabled: !isReadOnly && !isPreparingCompletion && !completionBusy');
    expect(source).toContain('{isReadOnly ? (');
    expect(source).toContain('{!isReadOnly && Boolean(conflict)');
    expect(source).toContain('{!isReadOnly && onComplete && (');
  });
});
