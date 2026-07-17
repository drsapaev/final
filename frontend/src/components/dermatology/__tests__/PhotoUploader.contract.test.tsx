import fs from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '..');

const readSource = (fileName) =>
  fs.readFileSync(path.join(ROOT, fileName), 'utf8').replace(/\r\n/g, '\n');

describe('derma PhotoUploader wiring contract (CRITICAL #1 + MEDIUM #9)', () => {
  it('validates patientId/visitId BEFORE starting FileReader (not inside onload)', () => {
    const source = readSource('PhotoUploader.tsx');

    // The check must be at the top of handleFileDrop, before FileReader is created.
    // Previously it was inside reader.onload — an async callback — causing
    // unhandled promise rejection.
    const handleFileDropBlock = source.slice(
      source.indexOf('const handleFileDrop = useCallback'),
      source.indexOf('const deletePhoto'),
    );

    // Must have early validation before FileReader
    const fileReaderIdx = handleFileDropBlock.indexOf('new FileReader()');
    const validationIdx = handleFileDropBlock.indexOf('if (!patientId && !visitId)');

    expect(validationIdx).toBeGreaterThan(-1);
    expect(validationIdx).toBeLessThan(fileReaderIdx);
  });

  it('does NOT throw inside reader.onload (uses try/catch instead)', () => {
    const source = readSource('PhotoUploader.tsx');

    // The old `throw new Error('Photo upload requires patientId or visitId')`
    // inside reader.onload must be gone.
    expect(source).not.toContain('throw new Error(\'Photo upload requires');
    expect(source).not.toContain('throw new Error("Photo upload requires');
  });

  it('passes updated photos (not stale) to onDataUpdate on upload', () => {
    const source = readSource('PhotoUploader.tsx');

    // The old bug: `onDataUpdate(photos)` where `photos` was stale
    // (setPhotos had not yet applied). The fix computes `updated` inside
    // the setPhotos callback and passes that to onDataUpdate.
    expect(source).not.toContain('onDataUpdate && onDataUpdate(photos);');

    // Must compute updated photos inside setPhotos callback
    expect(source).toContain('const updated = {');
    expect(source).toContain('onDataUpdate && onDataUpdate(updated)');
  });

  it('passes updated photos (not undefined) to onDataUpdate on delete', () => {
    const source = readSource('PhotoUploader.tsx');

    // The old bug: `onDataUpdate()` called with no argument → parent
    // received undefined.
    expect(source).not.toContain('onDataUpdate && onDataUpdate();');
    expect(source).not.toContain('onDataUpdate && onDataUpdate()\n');

    // Delete must also compute updated photos inside setPhotos callback
    const deleteBlock = source.slice(
      source.indexOf('const deletePhoto = async'),
      source.indexOf('const openViewer'),
    );
    expect(deleteBlock).toContain('onDataUpdate && onDataUpdate(updated)');
  });

  it('imports notify service for user-facing error messages', () => {
    const source = readSource('PhotoUploader.tsx');

    expect(source).toContain('from \'../../services/notify\'');
    expect(source).toMatch(/notify\.error\(/);
    expect(source).toMatch(/notify\.success\(/);
  });

  it('handles FileReader.onerror callback (not just onload)', () => {
    const source = readSource('PhotoUploader.tsx');

    // Previously only onload was handled — if FileReader failed, the
    // upload progress stayed at 0% with no feedback.
    expect(source).toContain('reader.onerror');
  });
});
