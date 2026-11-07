/**
 * DOCFLOW-FE-001 / DOCFLOW-FE-002 (audit 3886, ledger group «specialty
 * visit completion and auto-call») — source contract for the cardiologist
 * and dermatologist panels:
 *
 * - DOCFLOW-FE-001: the panel must not treat a non-throwing
 *   `queueService.completeVisit` as a confirmed completion. Only an explicit
 *   `success === true` DTO may show success, reset the clinical state and
 *   auto-call the next patient. An ambiguous (unreadable 2xx) or rejected
 *   response keeps the state intact.
 * - DOCFLOW-FE-002: the confirm dialog is an async boundary — the panel must
 *   re-verify the selected patient/visit identity after it resolves and
 *   before the irreversible POST + UI reset (the dermatology
 *   `isSameDermatologyVisit` recheck is the repo's positive reference).
 *
 * Red-first: on pre-fix source the ack-guard and cardio identity markers are
 * absent, so the corresponding assertions fail.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const readSource = (relative: string) =>
  fs.readFileSync(path.join(__dirname, relative), 'utf8');

describe('DOCFLOW-FE-001/002 — cardiology visit completion honesty (source contract)', () => {
  const source = readSource('../CardiologistPanelUnified.tsx');
  const completionHandler =
    source.match(/const handleSaveVisit = async[\s\S]*?\n {2}\};/)?.[0] ?? '';

  it('pins the handler block that owns completion', () => {
    expect(completionHandler).not.toBe('');
    expect(completionHandler).toContain('queueService.completeVisit');
  });

  it('DOCFLOW-FE-002: rechecks the selected patient identity after the confirm resolves (before the POST)', () => {
    // A ref to the live selection + an identity recheck inside the handler.
    expect(source).toContain('selectedPatientRef');
    expect(completionHandler).toContain('selectedPatientRef.current');
    expect(completionHandler).toMatch(/selection changed during completion|stale completion/i);
  });

  it('DOCFLOW-FE-001: guards the completion on an explicit success ack before any success/reset/auto-call', () => {
    // The completeVisit result is captured and checked; success/reset and
    // callNextWaiting may only run on the confirmed branch.
    expect(completionHandler).toMatch(/const completionAck = await queueService\.completeVisit/);
    expect(completionHandler).toMatch(/completionAck\?\.success !== true|completionAck\.success !== true/);
    expect(completionHandler).toContain('cardio.cardio_panel_action_failed');
  });

  it('DOCFLOW-FE-001: the ambiguous branch reconciles the queue with the canonical server snapshot', () => {
    expect(completionHandler).toMatch(/loadMacOSCardiologyAppointments/);
  });
});

describe('DOCFLOW-FE-001/002 — dermatology visit completion honesty (source contract)', () => {
  const source = readSource('../DermatologistPanelUnified.tsx');
  const completionHandler =
    source.match(/const handleSaveVisit = async[\s\S]*?\n {2}\};/)?.[0] ?? '';

  it('pins the handler block that owns completion', () => {
    expect(completionHandler).not.toBe('');
    expect(completionHandler).toContain('queueService.completeVisit');
  });

  it('DOCFLOW-FE-002 (existing positive reference): keeps the post-confirm identity recheck', () => {
    expect(completionHandler).toContain('isSameDermatologyVisit(completionContext, currentVisitContextRef.current)');
  });

  it('DOCFLOW-FE-001: guards the completion on an explicit success ack before any success/reset/auto-call', () => {
    expect(completionHandler).toMatch(/const completionAck = await queueService\.completeVisit/);
    expect(completionHandler).toMatch(/completionAck\?\.success !== true|completionAck\.success !== true/);
  });

  it('DOCFLOW-FE-001: the ambiguous branch reconciles the queue with the canonical server snapshot', () => {
    expect(completionHandler).toMatch(/loadDermatologyAppointments\(true\)/);
  });
});
