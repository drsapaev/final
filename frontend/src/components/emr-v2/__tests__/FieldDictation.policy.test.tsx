import '@testing-library/jest-dom';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { FieldDictation } from '../workspace/FieldDictation';

vi.mock('@/i18n/useTranslation', () => ({
  useTranslation: () => ({ language: 'ru', t: (key: string) => key }),
}));

const policyNames = ['permissionsPolicy', 'featurePolicy'] as const;
const policyDescriptors = policyNames.map(name => Object.getOwnPropertyDescriptor(document, name));
const available = vi.fn<() => Promise<string>>();
const install = vi.fn();
const construct = vi.fn();

class LocalRecognition {
  static available = available;
  static install = install;

  constructor() {
    construct();
  }

  get processLocally() { return true; }
}

function setPolicy(name: typeof policyNames[number], policy?: { allowsFeature: (key: string) => boolean }) {
  Object.defineProperty(document, name, { value: policy, configurable: true });
}

function expandDictation() {
  fireEvent.click(screen.getByText('emr_workspace.dictation'));
}

beforeEach(() => {
  available.mockReset().mockResolvedValue('available');
  install.mockClear();
  construct.mockClear();
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

describe('FieldDictation microphone policy', () => {
  it.each(policyNames)('shows the policy restriction without calling speech APIs via %s', async name => {
    const allowsFeature = vi.fn(() => false);
    setPolicy(name, { allowsFeature });
    const onInsert = vi.fn();
    render(<FieldDictation disabled={false} onInsert={onInsert} />);

    expandDictation();

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

    expandDictation();

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
    expandDictation();
    await waitFor(() => expect(available).toHaveBeenCalledTimes(1));

    allowsFeature.mockReturnValue(false);
    rerender(<FieldDictation disabled={false} onInsert={onInsert} />);
    await act(async () => { finishAvailability('downloadable'); });

    expect(screen.getByRole('status')).toHaveTextContent('emr_workspace.dictation_microphone_blocked');
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
    expect(available).toHaveBeenCalledTimes(1);
    expect(install).not.toHaveBeenCalled();
  });
});
