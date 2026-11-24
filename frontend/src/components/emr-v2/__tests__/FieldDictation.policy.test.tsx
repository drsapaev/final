import '@testing-library/jest-dom';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { FieldDictation } from '../workspace/FieldDictation';

const locale = vi.hoisted(() => ({ language: 'ru' }));
vi.mock('@/i18n/useTranslation', () => ({
  useTranslation: () => ({ language: locale.language, t: (key: string) => key }),
}));

const policyNames = ['permissionsPolicy', 'featurePolicy'] as const;
const policyDescriptors = policyNames.map(name => Object.getOwnPropertyDescriptor(document, name));
const available = vi.fn<() => Promise<string>>();
const install = vi.fn();
const construct = vi.fn<(recognition: LocalRecognition) => void>();

class LocalRecognition {
  static available = available;
  static install = install;
  private useLocalEngine = false;

  onresult: ((event: { results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }> }) => void) | null = null;
  onend: (() => void) | null = null;
  onerror: (() => void) | null = null;
  start = vi.fn();
  stop = vi.fn();
  abort = vi.fn();

  constructor() {
    construct(this);
  }

  get processLocally() { return this.useLocalEngine; }
  set processLocally(value: boolean) { this.useLocalEngine = value; }
}

function setPolicy(name: typeof policyNames[number], policy?: { allowsFeature: (key: string) => boolean }) {
  Object.defineProperty(document, name, { value: policy, configurable: true });
}

function toggleDictation() {
  fireEvent.click(screen.getByText('emr_workspace.dictation'));
}

beforeEach(() => {
  locale.language = 'ru';
  available.mockReset().mockResolvedValue('available');
  install.mockClear();
  construct.mockReset();
  for (const name of policyNames) setPolicy(name);
  vi.stubGlobal('SpeechRecognition', LocalRecognition);
  vi.stubEnv('VITE_EMR_DICTATION_DISABLED', 'false');
});

afterEach(() => {
  for (const [index, name] of policyNames.entries()) {
    const descriptor = policyDescriptors[index];
    if (descriptor) Object.defineProperty(document, name, descriptor);
    else Reflect.deleteProperty(document, name);
  }
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe('FieldDictation local recording controls', () => {
  it.each(policyNames)('shows the policy restriction without calling speech APIs via %s', async name => {
    const allowsFeature = vi.fn(() => false);
    setPolicy(name, { allowsFeature });
    const onInsert = vi.fn();
    render(<FieldDictation disabled={false} onInsert={onInsert} />);

    toggleDictation();

    expect(await screen.findByRole('status')).toHaveTextContent('emr_workspace.dictation_microphone_blocked');
    expect(allowsFeature).toHaveBeenCalledWith('microphone');
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
    expect(available).not.toHaveBeenCalled();
    expect(install).not.toHaveBeenCalled();
    expect(construct).not.toHaveBeenCalled();
    expect(onInsert).not.toHaveBeenCalled();
  });

  it.each([
    ['available', 'emr_workspace.dictation_start'],
    ['downloadable', 'emr_workspace.dictation_install'],
  ])('preserves %s local recognition when the browser has no policy API', async (state, label) => {
    available.mockResolvedValue(state);
    render(<FieldDictation disabled={false} onInsert={vi.fn()} />);

    toggleDictation();

    expect(await screen.findByRole('button', { name: label })).toBeInTheDocument();
    expect(available).toHaveBeenCalledWith({ langs: ['ru-RU'], processLocally: true });
    expect(install).not.toHaveBeenCalled();
    expect(construct).not.toHaveBeenCalled();
  });

  it('does not restore controls from a pending availability reply after the policy blocks the microphone', async () => {
    const allowsFeature = vi.fn(() => true);
    setPolicy('permissionsPolicy', { allowsFeature });
    let finishAvailability: (state: string) => void = () => {};
    available.mockReturnValue(new Promise(resolve => { finishAvailability = resolve; }));
    const onInsert = vi.fn();
    const { rerender } = render(<FieldDictation disabled={false} onInsert={onInsert} />);
    toggleDictation();
    await waitFor(() => expect(available).toHaveBeenCalledTimes(1));

    allowsFeature.mockReturnValue(false);
    rerender(<FieldDictation disabled={false} onInsert={onInsert} />);
    await act(async () => { finishAvailability('downloadable'); });

    expect(screen.getByRole('status')).toHaveTextContent('emr_workspace.dictation_microphone_blocked');
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
    expect(available).toHaveBeenCalledTimes(1);
    expect(install).not.toHaveBeenCalled();
  });

  it('keeps the transcript editable and allows a fresh local session after an error without an end event', async () => {
    const onInsert = vi.fn();
    render(<FieldDictation disabled={false} onInsert={onInsert} />);
    toggleDictation();

    fireEvent.click(await screen.findByRole('button', { name: 'emr_workspace.dictation_start' }));
    const first = construct.mock.calls[0][0];
    expect(first.processLocally).toBe(true);
    act(() => {
      first.onresult?.({ results: [{ isFinal: true, 0: { transcript: 'SYNTHETIC note' } }] });
      first.onerror?.();
      first.onresult?.({ results: [{ isFinal: true, 0: { transcript: 'SYNTHETIC late result' } }] });
    });

    expect(first.abort).toHaveBeenCalledOnce();
    expect(screen.getByRole('alert')).toHaveTextContent('emr_workspace.dictation_error');
    expect(screen.getByRole('textbox')).toHaveValue('SYNTHETIC note');
    fireEvent.click(screen.getByRole('button', { name: 'emr_workspace.dictation_insert' }));
    expect(onInsert).toHaveBeenCalledExactlyOnceWith('SYNTHETIC note');

    fireEvent.click(screen.getByRole('button', { name: 'emr_workspace.dictation_start' }));
    expect(construct).toHaveBeenCalledTimes(2);
    expect(construct.mock.calls[1][0].start).toHaveBeenCalledOnce();
  });

  it('keeps the transcript when closing the panel and stops the old session', async () => {
    const onInsert = vi.fn();
    render(<FieldDictation disabled={false} onInsert={onInsert} />);
    toggleDictation();
    fireEvent.click(await screen.findByRole('button', { name: 'emr_workspace.dictation_start' }));
    const session = construct.mock.calls[0][0];
    act(() => session.onresult?.({ results: [{ isFinal: true, 0: { transcript: 'SYNTHETIC transcript' } }] }));

    toggleDictation();
    await waitFor(() => expect(session.abort).toHaveBeenCalledOnce());
    act(() => session.onresult?.({ results: [{ isFinal: true, 0: { transcript: 'SYNTHETIC late callback' } }] }));
    toggleDictation();

    expect(await screen.findByRole('textbox')).toHaveValue('SYNTHETIC transcript');
    expect(construct).toHaveBeenCalledOnce();
    expect(onInsert).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'emr_workspace.dictation_insert' }));
    expect(onInsert).toHaveBeenCalledExactlyOnceWith('SYNTHETIC transcript');
  });

  it('keeps edited text through a locale change but clears it for a different visit', async () => {
    const onInsert = vi.fn();
    const { rerender } = render(<FieldDictation key="visit-a" disabled={false} onInsert={onInsert} />);
    toggleDictation();
    fireEvent.click(await screen.findByRole('button', { name: 'emr_workspace.dictation_start' }));
    const session = construct.mock.calls[0][0];
    act(() => {
      session.onresult?.({ results: [{ isFinal: true, 0: { transcript: 'SYNTHETIC transcript' } }] });
      session.onend?.();
    });
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'SYNTHETIC reviewed' } });

    locale.language = 'uz-Latn';
    available.mockResolvedValue('unavailable');
    rerender(<FieldDictation key="visit-a" disabled={false} onInsert={onInsert} />);

    expect(await screen.findByText('emr_workspace.dictation_unavailable')).toBeInTheDocument();
    expect(available).toHaveBeenLastCalledWith({ langs: ['uz-UZ'], processLocally: true });
    expect(screen.getByRole('textbox')).toHaveValue('SYNTHETIC reviewed');
    expect(screen.queryByRole('button', { name: 'emr_workspace.dictation_start' })).not.toBeInTheDocument();
    expect(onInsert).not.toHaveBeenCalled();

    rerender(<FieldDictation key="visit-b" disabled={false} onInsert={onInsert} />);
    toggleDictation();
    expect(await screen.findByText('emr_workspace.dictation_unavailable')).toBeInTheDocument();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    expect(onInsert).not.toHaveBeenCalled();
  });
});
