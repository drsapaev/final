import { describe, expect, it } from 'vitest';
import { readVerifiedMedicalAiCache } from '../EMRContainerV2';

describe('medical AI cache provenance', () => {
  const suggestions = [{ id: 'synthetic', content: 'synthetic' }];
  it('does not reuse the old bare cached suggestions', () => {
    expect(readVerifiedMedicalAiCache(suggestions)).toBeNull();
  });
  it.each([undefined, null, {}, { requires_doctor_confirmation: false },
    { requires_doctor_confirmation: 1 }, { requires_doctor_confirmation: 'true' }])(
    'rejects cache when the original server safety metadata is invalid: %j', (ai_safety_meta) => {
      expect(readVerifiedMedicalAiCache({ response: { ai_safety_meta }, suggestions })).toBeNull();
    },
  );
  it('reuses suggestions only with the original verified response', () => {
    expect(readVerifiedMedicalAiCache({
      response: { ai_safety_meta: { requires_doctor_confirmation: true } }, suggestions,
    })).toEqual(suggestions);
  });
  it('rejects malformed suggestions even with a valid envelope', () => {
    expect(readVerifiedMedicalAiCache({
      response: { ai_safety_meta: { requires_doctor_confirmation: true } }, suggestions: 'invalid',
    })).toBeNull();
  });
});

import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, vi } from 'vitest';

const mocks = vi.hoisted(() => {
  const noop = () => {};
  return {
    input: { complaints: 'old', diagnosis: 'diagnosis', specialty: 'general', patient_age: 30, patient_gender: 'x' },
    suggest: vi.fn(), cacheGet: vi.fn(), cacheSet: vi.fn(), setField: vi.fn(),
    hookFunctions: { loadEMR: noop, saveEMR: noop, signEMR: noop, amendEMR: noop, setNestedField: noop, undo: noop, redo: noop, reloadFromServer: noop },
    getSignal: () => new AbortController().signal,
  };
});
vi.mock('../../../hooks/useEMR', () => ({ useEMR: () => ({
  ...mocks.hookFunctions, setField: mocks.setField, data: mocks.input, emr: { id: 1, status: 'in_progress' },
  status: 'idle', isDirty: false, isLoading: false, lastSaved: null, conflict: null, error: null,
  isSaving: false, isSigned: false, isAmended: false, accessDenied: false, serverFinalized: false,
  version: 1, rowVersion: 1, canUndo: false, canRedo: false,
}) }));
vi.mock('../../../hooks/useEMRAutosave', () => ({ useEMRAutosave: () => ({ suppressOnDiscard: vi.fn(), config: {} }) }));
vi.mock('../../../hooks/useEMRLeaveGuard', () => ({ useEMRLeaveGuard: () => {} }));
vi.mock('../../../hooks/useEMRWorkspace', () => ({
  useEMRWorkspace: () => ({ status: 'loading', scope: '900:42', reload: vi.fn() }),
}));
vi.mock('../sections/VitalsWidget', () => ({ default: () => null }));
vi.mock('../sections/LabResultsSection', () => ({ default: () => null }));
vi.mock('../../../hooks/useNavigationGuard', () => ({ useBeforeUnload: () => {} }));
vi.mock('../../../hooks/useEMRKeyboard', () => ({ useEMRKeyboard: () => {} }));
vi.mock('../../../hooks/useVisitLifecycle', () => ({ useVisitLifecycle: () => ({ getAbortSignal: mocks.getSignal }) }));
vi.mock('../../../hooks/useDebouncedCallback', () => ({ useDebouncedCallback: (callback: unknown) => callback }));
vi.mock('../../../contexts/AppDataContext', () => ({ useAppData: () => ({ currentUser: { id: 1 } }) }));
vi.mock('../../../hooks/useMcpClient', () => ({ useMcpClient: () => ({ suggestICD10: mocks.suggest }) }));
vi.mock('../../../i18n/useTranslation', () => ({ useTranslation: () => ({ t: (key: string) => key, language: 'ru' }) }));
vi.mock('../../common/ConfirmDialog', () => ({ useConfirm: () => [async () => false, null] }));
vi.mock('../../../core/cache', () => ({
  cacheService: { get: mocks.cacheGet, set: mocks.cacheSet, cacheEMR: vi.fn(),
    generateKey: (...parts: unknown[]) => parts.join(':') },
  CACHE_CONFIG: { aiTTL: 300000 }, CACHE_TAGS: { aiAnalysis: 'ai', visit: () => 'visit', patient: () => 'patient' },
}));
vi.mock('../../ui/macos', () => ({ Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => <button {...props}>{children}</button> }));
vi.mock('../EMRStatusIndicator', () => ({ default: () => null }));
vi.mock('../EMRHelpDialog', () => ({ default: () => null }));
vi.mock('../sections/specialty', () => ({ CardiologySection: () => null, DermatologySection: () => null, DentistrySection: () => null }));
vi.mock('../sections', () => {
  const Empty = () => null;
  const Diagnosis = ({ onRequestAI, suggestions, aiLoading }: { onRequestAI: (name: string) => void; suggestions: unknown[]; aiLoading: boolean }) => (
    <div><button onClick={() => onRequestAI('diagnosis')}>request AI</button><span data-testid="suggestions">{JSON.stringify(suggestions)}</span><span data-testid="loading">{String(aiLoading)}</span></div>
  );
  const Complaints = ({ value, onChange }: { value: string; onChange: (value: string) => void }) => (
    <input aria-label="manual complaints" value={value} onChange={event => onChange(event.target.value)} />
  );
  return { ComplaintsSection: Complaints, AnamnesisMorbiSection: Empty, AnamnesisVitaeSection: Empty,
    ExaminationSection: Empty, DiagnosisSection: Diagnosis, TreatmentSection: Empty,
    RecommendationsSection: Empty, NotesSection: Empty };
});
import { EMRContainerV2 } from '../EMRContainerV2';

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(r => { resolve = r; });
  return { promise, resolve };
}
const safeResponse = (label: string) => ({
  status: 'success', ai_safety_meta: { requires_doctor_confirmation: true },
  data: { suggestions: [{ code: 'A01', label }] },
});

describe('EMR AI results stay with the clinical input that requested them', () => {
  beforeEach(() => {
    mocks.input = { complaints: 'old', diagnosis: 'diagnosis', specialty: 'general', patient_age: 30, patient_gender: 'x' };
    mocks.suggest.mockReset(); mocks.cacheGet.mockReset(); mocks.cacheSet.mockReset(); mocks.setField.mockReset();
  });

  it('drops late response A after same-visit input changes without a second request', async () => {
    const old = deferred<ReturnType<typeof safeResponse>>();
    mocks.suggest.mockReturnValueOnce(old.promise);
    const { rerender } = render(<EMRContainerV2 visitId={900} patientId={42} specialty="cardiology" />);
    fireEvent.click(screen.getByText('request AI'));
    expect(mocks.suggest).toHaveBeenCalledOnce();
    mocks.input = { ...mocks.input, complaints: 'new' };
    rerender(<EMRContainerV2 visitId={900} patientId={42} specialty="cardiology" />);
    await act(async () => { old.resolve(safeResponse('OLD SUGGESTION')); await old.promise; });
    expect(screen.getByTestId('suggestions').textContent).not.toContain('OLD SUGGESTION');
    expect(mocks.cacheSet).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText('manual complaints'), { target: { value: 'manual entry' } });
    expect(mocks.setField).toHaveBeenCalledWith('complaints', 'manual entry', undefined);
  });

  it('keeps B cache hit when an earlier request A resolves late', async () => {
    const old = deferred<ReturnType<typeof safeResponse>>();
    mocks.suggest.mockReturnValueOnce(old.promise);
    const { rerender } = render(<EMRContainerV2 visitId={900} patientId={42} specialty="cardiology" />);
    fireEvent.click(screen.getByText('request AI'));
    mocks.input = { ...mocks.input, complaints: 'new' };
    rerender(<EMRContainerV2 visitId={900} patientId={42} specialty="cardiology" />);
    mocks.cacheGet.mockReturnValueOnce({ response: safeResponse('NEW'), suggestions: [{ content: 'B CACHED' }] });
    fireEvent.click(screen.getByText('request AI'));
    expect(screen.getByTestId('suggestions').textContent).toContain('B CACHED');
    await act(async () => { old.resolve(safeResponse('OLD SUGGESTION')); await old.promise; });
    expect(screen.getByTestId('suggestions').textContent).toContain('B CACHED');
    expect(screen.getByTestId('suggestions').textContent).not.toContain('OLD SUGGESTION');
    expect(mocks.cacheSet).not.toHaveBeenCalled();
  });

  it('does not publish A after newer B fails safety validation', async () => {
    const old = deferred<ReturnType<typeof safeResponse>>();
    mocks.suggest.mockReturnValueOnce(old.promise).mockResolvedValueOnce({ status: 'success', data: { suggestions: [{ code: 'B01', label: 'UNSAFE' }] } });
    const { rerender } = render(<EMRContainerV2 visitId={900} patientId={42} specialty="cardiology" />);
    fireEvent.click(screen.getByText('request AI'));
    mocks.input = { ...mocks.input, complaints: 'new' };
    rerender(<EMRContainerV2 visitId={900} patientId={42} specialty="cardiology" />);
    fireEvent.click(screen.getByText('request AI'));
    await waitFor(() => expect(screen.getByTestId('loading').textContent).toBe('false'));
    await act(async () => { old.resolve(safeResponse('OLD SUGGESTION')); await old.promise; });
    expect(screen.getByTestId('suggestions').textContent).toBe('[]');
    expect(mocks.cacheSet).not.toHaveBeenCalled();
  });

  it('does not let an older completion clear the newer request loading state', async () => {
    const old = deferred<ReturnType<typeof safeResponse>>();
    const current = deferred<ReturnType<typeof safeResponse>>();
    mocks.suggest.mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise);
    render(<EMRContainerV2 visitId={900} patientId={42} specialty="cardiology" />);
    fireEvent.click(screen.getByText('request AI'));
    fireEvent.click(screen.getByText('request AI'));
    await act(async () => { old.resolve(safeResponse('OLD SUGGESTION')); await old.promise; });
    expect(screen.getByTestId('loading').textContent).toBe('true');
    expect(screen.getByTestId('suggestions').textContent).toBe('[]');
    await act(async () => { current.resolve(safeResponse('CURRENT SUGGESTION')); await current.promise; });
    expect(screen.getByTestId('loading').textContent).toBe('false');
    expect(screen.getByTestId('suggestions').textContent).toContain('CURRENT SUGGESTION');
  });
});
