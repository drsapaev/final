import React from 'react';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { DisplayTestReply } from '../../api/ws';
import i18n from '../../i18n';

const wsMock = vi.hoisted(() => ({
  openDisplayBoardWS: vi.fn(),
}));

const apiMock = vi.hoisted(() => ({
  api: {
    get: vi.fn(),
  },
}));

vi.mock('../../api/client', () => apiMock);
vi.mock('../../api/ws', () => wsMock);
vi.mock('../../contexts/ThemeContext', () => ({
  useTheme: () => ({ theme: 'light' }),
}));
vi.mock('../../utils/logger', () => ({
  default: {
    log: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  },
}));

import DisplayBoardUnified from '../DisplayBoardUnified';

// SYNTHETIC fixtures only (audit PR #3961): no real patient/staff identities.
describe('DisplayBoardUnified audit-3961 frontend plane', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.clearAllMocks();
    (window.localStorage.getItem as unknown as { mockReturnValue: (v: unknown) => void }).mockReturnValue(null);
    window.HTMLMediaElement.prototype.play = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(window, 'AudioContext', {
      writable: true,
      configurable: true,
      value: undefined,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  const renderBoard = async (
    props: Record<string, unknown> = {},
    settings: Record<string, unknown> = {},
    initialSnapshot = true,
  ) => {
    apiMock.api.get.mockResolvedValue({
      data: {
        department: 'Reg',
        date_str: '2026-05-23',
        is_open: true,
        last_ticket: 0,
        ...settings,
      },
    });
    let wsMessageHandler: ((data: unknown, reply?: DisplayTestReply) => void) | null = null;
    wsMock.openDisplayBoardWS.mockImplementation(
      (_boardId: string, onMessage: (data: unknown, reply?: DisplayTestReply) => void, onConnect?: () => void) => {
        wsMessageHandler = onMessage;
        onConnect?.();
        return vi.fn();
      }
    );
    const view = render(
      <DisplayBoardUnified
        department="Reg"
        dateStr="2026-05-23"
        boardId="main_board"
        refreshMs={60000}
        {...props}
      />
    );
    await waitFor(() => {
      expect(apiMock.api.get).toHaveBeenCalled();
    });
    const push = (msg: unknown, reply?: DisplayTestReply) => act(() => { wsMessageHandler!(msg, reply); });
    if (initialSnapshot) push({ type: 'initial_state', data: { queue_entries: [], current_call: null } });
    return {
      view,
      push,
    };
  };

  // DISPLAYCALL-FE-001: the highlighted last call expires per the
  // backend-owned display_duration and clears on a real lifecycle update.
  it('clears the highlighted call after display_duration expires', async () => {
    const { push } = await renderBoard();

    push({
      type: 'patient_call',
      display_duration: 5,
      data: { queue_number: 11, queue_id: 1, queue_entry_id: 11 },
    });
    const callNumber = () => screen.getByText(/№\s*11/);
    expect(callNumber()).toBeInTheDocument();

    // Still highlighted before the window passes.
    act(() => { vi.advanceTimersByTime(4999); });
    expect(callNumber()).toBeInTheDocument();

    act(() => { vi.advanceTimersByTime(1); });
    expect(screen.queryByText(/№\s*11/)).not.toBeInTheDocument();
  });

  it('clears the highlighted call when the entry reaches a terminal status', async () => {
    const { push } = await renderBoard();

    push({
      type: 'patient_call',
      display_duration: 300,
      data: { queue_number: 11, queue_id: 1, queue_entry_id: 11 },
    });
    expect(screen.getByText(/№\s*11/)).toBeInTheDocument();

    push({
      type: 'queue_update',
      event_type: 'queue.completed',
      data: { queue_id: 2, queue_entries: [{ id: 22, queue_id: 2, number: 11, status: 'served' }] },
    });
    expect(screen.getByText(/№\s*11/)).toBeInTheDocument();

    // Backend-formatted scoped update: entry 11 is now served.
    push({
      type: 'queue_update',
      event_type: 'queue.updated',
      data: {
        queue_id: 1,
        queue_entries: [
          { id: 11, queue_id: 1, number: 11, patient_name: 'Synthetic Patient 11', status: 'served', created_at: '2026-05-23T08:00:00' },
        ],
      },
    });

    expect(screen.queryByText(/№\s*11/)).not.toBeInTheDocument();
  });

  it('keeps the expiration timer when a different queue completes the same ticket number', async () => {
    const { push } = await renderBoard();
    push({
      type: 'patient_call',
      data: { queue_id: 1, queue_entry_id: 11, queue_number: 5, expires_at: new Date(Date.now() + 5000).toISOString() },
    });
    push({
      type: 'queue_update',
      data: { queue_id: 2, queue_entries: [{ id: 22, queue_id: 2, number: 5, status: 'completed' }] },
    });
    expect(screen.getByText(/№\s*5/)).toBeInTheDocument();
    act(() => { vi.advanceTimersByTime(5000); });
    expect(screen.queryByText(/№\s*5/)).not.toBeInTheDocument();
  });

  it.each(['in_progress', 'in_service', 'waiting'])(
    'clears the call when its entry changes to %s', async (status) => {
      const { push } = await renderBoard();
      push({ type: 'patient_call', data: { queue_id: 1, queue_entry_id: 11, queue_number: 5 } });
      push({ type: 'queue_update', data: { queue_id: 1, queue_entries: [
        { id: 11, queue_id: 1, number: 5, status },
      ] } });
      expect(screen.queryByText(/№\s*5/)).not.toBeInTheDocument();
    },
  );

  it('announces a live call that arrives while the first snapshot is being built', async () => {
    const speak = vi.fn((utterance: { onstart?: () => void }) => utterance.onstart?.());
    vi.stubGlobal('speechSynthesis', { getVoices: () => [{ lang: 'ru-RU' }], speak, cancel: vi.fn() });
    vi.stubGlobal('SpeechSynthesisUtterance', class { constructor(public text: string) {} });
    const { push } = await renderBoard({}, {
      sound_enabled: true, voice_announcements: true, voice_language: 'ru', volume_level: 50,
    }, false);
    const snapshotStarted = new Date(Date.now() - 1000).toISOString();
    const call = {
      event_id: 'live-during-snapshot', issued_at: new Date().toISOString(),
      queue_number: 7, queue_id: 1, queue_entry_id: 7, cabinet: '505',
      expires_at: new Date(Date.now() + 5000).toISOString(),
    };
    push({ type: 'patient_call', data: call });
    expect(speak).not.toHaveBeenCalled();
    push({ type: 'initial_state', data: {
      queue_entries: [], current_call: null, last_update: snapshotStarted,
    } });
    expect(screen.getByText(/№\s*7/)).toBeInTheDocument();
    await waitFor(() => expect(speak).toHaveBeenCalledTimes(1));
    expect(speak).toHaveBeenCalledWith(expect.objectContaining({
      text: expect.stringMatching(/7.*505/), volume: 0.5,
    }));
  });

  it('announces a live call once the selected audio settings finish loading', async () => {
    const speak = vi.fn((utterance: { onstart?: () => void }) => utterance.onstart?.());
    vi.stubGlobal('speechSynthesis', { getVoices: () => [{ lang: 'ru-RU' }], speak, cancel: vi.fn() });
    vi.stubGlobal('SpeechSynthesisUtterance', class { constructor(public text: string) {} });
    let finishSettings!: (response: unknown) => void;
    apiMock.api.get.mockImplementation(() => new Promise((resolve) => { finishSettings = resolve; }));
    let onMessage!: (message: unknown) => void;
    wsMock.openDisplayBoardWS.mockImplementation((_id, handler, onConnect) => {
      onMessage = handler;
      onConnect();
      return vi.fn();
    });
    render(<DisplayBoardUnified department="Reg" dateStr="2026-05-23" />);
    await waitFor(() => expect(apiMock.api.get).toHaveBeenCalled());
    act(() => {
      onMessage({ type: 'initial_state', data: { queue_entries: [] } });
      onMessage({ type: 'patient_call', data: {
        event_id: 'live-before-profile', queue_number: 8, cabinet: '506',
      } });
    });
    expect(screen.getByText(/№\s*8/)).toBeInTheDocument();
    expect(speak).not.toHaveBeenCalled();
    await act(async () => finishSettings({ data: {
      sound_enabled: true, voice_announcements: true, voice_language: 'ru', volume_level: 50,
    } }));
    await waitFor(() => expect(speak).toHaveBeenCalledTimes(1));
    expect(speak).toHaveBeenCalledWith(expect.objectContaining({
      text: expect.stringMatching(/8.*506/), volume: 0.5,
    }));
  });

  it.each([true, false])('announces the updated room before audio settings are ready (event ID: %s)', async (hasEventId) => {
    const speak = vi.fn((utterance: { onstart?: () => void }) => utterance.onstart?.());
    vi.stubGlobal('speechSynthesis', { getVoices: () => [{ lang: 'ru-RU' }], speak, cancel: vi.fn() });
    vi.stubGlobal('SpeechSynthesisUtterance', class { constructor(public text: string) {} });
    let finishSettings!: (response: unknown) => void;
    apiMock.api.get.mockImplementation(() => new Promise((resolve) => { finishSettings = resolve; }));
    let onMessage!: (message: unknown) => void;
    wsMock.openDisplayBoardWS.mockImplementation((_id, handler, onConnect) => {
      onMessage = handler;
      onConnect();
      return vi.fn();
    });
    render(<DisplayBoardUnified department="Reg" dateStr="2026-05-23" />);
    await waitFor(() => expect(apiMock.api.get).toHaveBeenCalled());
    act(() => {
      onMessage({ type: 'initial_state', data: { queue_entries: [] } });
      onMessage({ type: 'patient_call', data: {
        ...(hasEventId ? { event_id: 'room-change-before-audio' } : {}), queue_id: 1, queue_entry_id: 8,
        queue_number: 8, cabinet: '506',
      } });
      onMessage({ type: 'queue_update', data: { queue_id: 1, cabinet: '507', queue_entries: [
        { id: 8, queue_id: 1, number: 8, status: 'called', cabinet: '507' },
      ] } });
    });
    expect(screen.getAllByText('🚪 507')).not.toHaveLength(0);
    expect(speak).not.toHaveBeenCalled();
    await act(async () => finishSettings({ data: {
      sound_enabled: true, voice_announcements: true, voice_language: 'ru', volume_level: 50,
    } }));
    await waitFor(() => expect(speak).toHaveBeenCalledTimes(1));
    expect(speak).toHaveBeenCalledWith(expect.objectContaining({ text: expect.stringMatching(/8.*507/) }));
  });

  it('announces the updated room when it changes while the voice locale is loading', async () => {
    const locale = 'uz-Latn';
    const connector = i18n.services.backendConnector as unknown as {
      state: Record<string, number>;
      backend: { read: (language: string, namespace: string, callback: (error: Error | null, data: object | null) => void) => void };
    };
    const stateKey = `${locale}|translation`;
    const previousState = connector.state[stateKey];
    const previousBundle = i18n.getResourceBundle(locale, 'translation');
    i18n.removeResourceBundle(locale, 'translation');
    connector.state[stateKey] = -1;
    let finishLocale!: (error: Error | null, data: object | null) => void;
    const read = vi.spyOn(connector.backend, 'read').mockImplementation((_language, _namespace, callback) => {
      finishLocale = callback;
    });
    const speak = vi.fn((utterance: { onstart?: () => void }) => utterance.onstart?.());
    vi.stubGlobal('speechSynthesis', { getVoices: () => [{ lang: 'uz-UZ' }], speak, cancel: vi.fn() });
    vi.stubGlobal('SpeechSynthesisUtterance', class { constructor(public text: string) {} });
    try {
      const { push } = await renderBoard({}, {
        sound_enabled: true, voice_announcements: true, voice_language: 'uz', volume_level: 50,
      });
      await waitFor(() => expect(read).toHaveBeenCalled());
      push({ type: 'patient_call', data: {
        event_id: 'room-change-before-locale', queue_id: 1, queue_entry_id: 9,
        queue_number: 9, cabinet: '601',
      } });
      push({ type: 'queue_update', data: { queue_id: 1, cabinet: '602', queue_entries: [
        { id: 9, queue_id: 1, number: 9, status: 'called', cabinet: '602' },
      ] } });
      expect(speak).not.toHaveBeenCalled();
      await act(async () => finishLocale(null, { misc: { dbu_voice_patient_call: '{number}-raqamli talon, {cabinet}-xonaga oʻting' } }));
      await waitFor(() => expect(speak).toHaveBeenCalledTimes(1));
      expect(speak).toHaveBeenCalledWith(expect.objectContaining({ text: expect.stringMatching(/9-raqamli talon.*602/) }));
    } finally {
      read.mockRestore();
      i18n.removeResourceBundle(locale, 'translation');
      if (previousBundle) i18n.addResourceBundle(locale, 'translation', previousBundle);
      if (previousState === undefined) delete connector.state[stateKey];
      else connector.state[stateKey] = previousState;
    }
  });

  it('updates the current room and preserves an explicitly unknown resource room', async () => {
    const { push } = await renderBoard();
    push({ type: 'patient_call', data: { queue_id: 1, queue_entry_id: 11, queue_number: 5, cabinet: '101' } });
    push({ type: 'queue_update', data: { queue_id: 1, cabinet: '102', queue_entries: [
      { id: 11, queue_id: 1, number: 5, status: 'called', cabinet: '505' },
      { id: 12, queue_id: 1, number: 6, status: 'called', cabinet: null },
    ] } });
    expect(screen.getAllByText('🚪 505')).toHaveLength(2);
    expect(screen.queryByText('🚪 102')).not.toBeInTheDocument();
  });

  it('keeps the known invitation room when a later resource update cannot resolve it', async () => {
    const { push } = await renderBoard();
    push({ type: 'patient_call', data: { queue_id: 1, queue_entry_id: 11, queue_number: 5, cabinet: '505' } });
    push({ type: 'queue_update', data: { queue_id: 1, cabinet: '102', queue_entries: [
      { id: 11, queue_id: 1, number: 5, status: 'called', cabinet: null },
    ] } });
    expect(screen.getByText('🚪 505')).toBeInTheDocument();
    expect(screen.queryByText('🚪 102')).not.toBeInTheDocument();
  });

  it.each([['ru', 'ru-RU'], ['uz', 'uz-UZ']])(
    'restores silently and voices a live call in %s with the profile volume',
    async (voiceLanguage, voiceLocale) => {
      const speak = vi.fn((utterance: { onstart?: () => void }) => utterance.onstart?.());
      vi.stubGlobal('speechSynthesis', { getVoices: () => [{ lang: voiceLocale }], speak, cancel: vi.fn() });
      vi.stubGlobal('SpeechSynthesisUtterance', class {
        constructor(public text: string) {}
      });
      const { push } = await renderBoard({}, {
        sound_enabled: true, voice_announcements: true, voice_language: voiceLanguage, volume_level: 25,
      });
      const deadline = new Date(Date.now() + 5000).toISOString();
      push({
        type: 'initial_state',
        data: { queue_entries: [], current_call: {
          queue_number: 7, cabinet: '701', expires_at: deadline,
        } },
      });
      expect(screen.getByText(/№\s*7/)).toBeInTheDocument();
      expect(speak).not.toHaveBeenCalled();
      act(() => { vi.advanceTimersByTime(5000); });
      expect(screen.queryByText(/№\s*7/)).not.toBeInTheDocument();

      const invitation = {
        type: 'patient_call',
        data: {
          queue_number: 11, cabinet: '801', event_id: 'event-11', issued_at: new Date().toISOString(),
          expires_at: new Date(Date.now() + 6000).toISOString(),
        },
      };
      push(invitation);
      push(invitation);
      expect(screen.getByText(/№\s*11/)).toBeInTheDocument();
      await waitFor(() => expect(speak).toHaveBeenCalledTimes(1), { timeout: 5000 });
      expect(speak).toHaveBeenCalledWith(expect.objectContaining({
        text: expect.stringMatching(voiceLanguage === 'uz' ? /11-raqamli talon.*801/ : /Талон номер 11.*801/),
        lang: voiceLocale,
        volume: 0.25,
      }));
    },
  );

  it('recovers Uzbek voice after a temporary locale load failure without replaying the old call', async () => {
    const locale = 'uz-Latn';
    const connector = i18n.services.backendConnector as unknown as {
      state: Record<string, number>;
      backend: { read: (language: string, namespace: string, callback: (error: Error | null, data: object | null) => void) => void };
    };
    const stateKey = `${locale}|translation`;
    const previousState = connector.state[stateKey];
    const previousBundle = i18n.getResourceBundle(locale, 'translation');
    const previousPreload = i18n.options.preload;
    i18n.removeResourceBundle(locale, 'translation');
    // This is i18next's real state after the locale backend failed once.
    connector.state[stateKey] = -1;
    i18n.options.preload = [
      ...(Array.isArray(previousPreload) ? previousPreload.filter((language) => language !== locale) : []),
      locale,
    ];

    let networkAvailable = false;
    const read = vi.spyOn(connector.backend, 'read').mockImplementation((language, namespace, callback) => {
      if (language !== locale || namespace !== 'translation') throw new Error('Unexpected locale request');
      if (!networkAvailable) callback(new Error('Synthetic network outage'), null);
      else callback(null, { misc: { dbu_voice_patient_call: '{number}-raqamli talon, {cabinet}-xonaga oʻting' } });
    });
    const speak = vi.fn((utterance: { onstart?: () => void }) => utterance.onstart?.());
    vi.stubGlobal('speechSynthesis', { getVoices: () => [{ lang: 'uz-UZ' }], speak, cancel: vi.fn() });
    vi.stubGlobal('SpeechSynthesisUtterance', class { constructor(public text: string) {} });

    try {
      const { push } = await renderBoard({}, {
        sound_enabled: true, voice_announcements: true, voice_language: 'uz', volume_level: 50,
      });
      await act(async () => {});
      push({ type: 'patient_call', data: {
        event_id: 'outage-call', issued_at: new Date().toISOString(),
        queue_number: 21, cabinet: '701', expires_at: new Date(Date.now() + 5000).toISOString(),
      } });
      expect(screen.getByText(/№\s*21/)).toBeInTheDocument();
      expect(speak).not.toHaveBeenCalled();

      networkAvailable = true;
      await act(async () => { await vi.advanceTimersByTimeAsync(60000); });
      await waitFor(() => expect(i18n.hasResourceBundle(locale, 'translation')).toBe(true));
      expect(speak).not.toHaveBeenCalled();
      push({ type: 'patient_call', data: {
        event_id: 'recovered-call', issued_at: new Date().toISOString(),
        queue_number: 22, cabinet: '702', expires_at: new Date(Date.now() + 5000).toISOString(),
      } });
      await waitFor(() => expect(speak).toHaveBeenCalledTimes(1));
      expect(speak).toHaveBeenCalledWith(expect.objectContaining({ text: expect.stringMatching(/22-raqamli talon.*702/) }));
    } finally {
      read.mockRestore();
      i18n.removeResourceBundle(locale, 'translation');
      if (previousBundle) i18n.addResourceBundle(locale, 'translation', previousBundle);
      if (previousState === undefined) delete connector.state[stateKey];
      else connector.state[stateKey] = previousState;
      i18n.options.preload = previousPreload;
    }
  });

  it('acknowledges a visibly rendered test and yields to an active clinical call', async () => {
    const { push } = await renderBoard({}, { sound_enabled: false });
    const reply = vi.fn();
    const makeTest = (id: string) => ({
      type: 'display_test',
      data: {
        test_id: id, test_type: 'call', queue_number: 'T007', cabinet: '101',
        expires_at: new Date(Date.now() + 5000).toISOString(),
      },
    });
    push(makeTest('test-one'), reply);
    expect(screen.getByTestId('display-board-test')).toHaveTextContent('T007');
    await act(async () => { await vi.advanceTimersByTimeAsync(40); });
    expect(reply).toHaveBeenCalledWith({ test_id: 'test-one', status: 'displayed', audio_status: 'disabled' });

    push({ type: 'patient_call', data: { queue_number: 9, cabinet: '702' } });
    expect(screen.queryByTestId('display-board-test')).not.toBeInTheDocument();
    push(makeTest('test-two'), reply);
    expect(reply).toHaveBeenCalledWith({ test_id: 'test-two', status: 'busy' });
    expect(screen.getByText(/№\s*9/)).toBeInTheDocument();
  });

  // DISPLAYANNOUNCE-FE-001: each announcement lives its requested
  // display_duration window, independently of newer events.
  it('removes an announcement when its display_duration passes', async () => {
    const { push } = await renderBoard();

    push({
      type: 'announcement',
      display_duration: 5,
      data: { text: 'Synthetic warning', announcement_type: 'warning', created_at: 'a1' },
    });
    push({
      type: 'announcement',
      data: { text: 'Synthetic info', announcement_type: 'info', created_at: 'a2', display_duration: 60 },
    });

    expect(screen.getByText(/Synthetic warning/)).toBeInTheDocument();
    expect(screen.getByText(/Synthetic info/)).toBeInTheDocument();

    act(() => { vi.advanceTimersByTime(5000); });
    expect(screen.queryByText(/Synthetic warning/)).not.toBeInTheDocument();
    // The second notice keeps its own independent timer.
    expect(screen.getByText(/Synthetic info/)).toBeInTheDocument();
  });

  // DISPLAYERROR-FE-001: a backend failure snapshot is a visible error,
  // never a live-looking empty board; last good rows are kept.
  it('shows a visible error banner on an error snapshot and keeps last good rows', async () => {
    const { push } = await renderBoard();

    push({
      type: 'initial_state',
      data: {
        queue_entries: [
          { id: 1, number: 7, patient_name: 'Synthetic Patient 7', status: 'waiting', created_at: '2026-05-23T08:00:00' },
        ],
        current_call: null,
        announcements: [],
      },
    });
    expect(await screen.findByText('7')).toBeInTheDocument();

    push({
      type: 'initial_state',
      data: { queue_entries: [], current_call: null, announcements: [], error: 'Ошибка загрузки данных' },
    });

    expect(screen.getByTestId('dbu-snapshot-error')).toBeInTheDocument();
    // Last good rows are retained, not wiped into a fake empty board.
    expect(screen.getByText('7')).toBeInTheDocument();

    // A successful snapshot clears the error banner (positive control).
    push({
      type: 'initial_state',
      data: { queue_entries: [], current_call: null, announcements: [] },
    });
    expect(screen.queryByTestId('dbu-snapshot-error')).not.toBeInTheDocument();
  });

  // DISPLAYAUDIO-FE-001: an explicit soundInitial=false applies on the
  // first render and the manual mute survives the periodic stats refresh.
  it('honors soundInitial=false and keeps the manual mute across refreshes', async () => {
    const { push } = await renderBoard({ soundInitial: false });

    // The sound toggle starts muted (VolumeX icon): aria-label is the
    // "turn sound ON" title when currently muted.
    const soundButton = () =>
      screen.queryByRole('button', { name: /включить звук|enable sound/i });
    expect(soundButton()).not.toBeNull();

    // Manual unmute, then a REST refresh arrives with sound_default=true —
    // the session override must survive the poll.
    await userEvent.click(soundButton()!);
    expect(screen.queryByRole('button', { name: /включить звук|enable sound/i })).toBeNull();

    push({ type: 'initial_state', data: { queue_entries: [], current_call: null, announcements: [] } });
    const before = apiMock.api.get.mock.calls.length;
    act(() => { vi.advanceTimersByTime(61000); });
    expect(apiMock.api.get.mock.calls.length).toBeGreaterThan(before);
    // Still unmuted — the poll did not reset the manual choice.
    expect(screen.queryByRole('button', { name: /включить звук|enable sound/i })).toBeNull();
  });
});
