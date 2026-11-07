/**
 * LABAI-FE-001 (audit 3886, ledger group «lab report API, PDF preview and
 * AI result ownership») — fail-first regressions for the AI dialog's
 * report identity:
 *
 * The AI interpretation dialog stayed mounted across `activeInstance`
 * changes: its header/data updated to report B while report A's result
 * stayed in the dialog, and a pending A response could resolve into B's
 * dialog, visually attributing A's clinical interpretation to patient B.
 *
 * Red-first: on the pre-fix source (1) the dialog stays open across the
 * report switch, and (2) a pending analysis publishes into a newer input.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const interpretLabResultsMock = vi.hoisted(() => vi.fn());

vi.mock('../../../api/mcpClient', () => ({
  mcpAPI: {
    interpretLabResults: interpretLabResultsMock,
    suggestIcd10: vi.fn(),
    analyzeComplaint: vi.fn(),
    analyzeImaging: vi.fn(),
  },
}));
vi.mock('../../../api/client', () => ({
  apiClient: { post: vi.fn(), get: vi.fn() },
  forceRefreshToken: vi.fn(),
}));

import { ThemeProvider } from '../../../contexts/ThemeContext';
import AIAssistantRaw from '../AIAssistant';
import ReportSidebarRaw from '../../laboratory/ReportSidebar';

const AIAssistant = AIAssistantRaw as unknown as React.ComponentType<Record<string, unknown>>;
const ReportSidebar = ReportSidebarRaw as unknown as React.ComponentType<Record<string, unknown>>;

const INSTANCE_A = {
  id: 91,
  patient_id: 444,
  patient_snapshot: { age_years: 30, sex: 'male' },
  sections: [
    { fields: [{ label: 'Гемоглобин', value_text: '140', unit: 'г/л', reference_text: '130-170' }] },
  ],
};

const INSTANCE_B = {
  id: 92,
  patient_id: 555,
  patient_snapshot: { age_years: 40, sex: 'female' },
  sections: [
    { fields: [{ label: 'Гемоглобин', value_text: '110', unit: 'г/л', reference_text: '120-150' }] },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe('LABAI-FE-001 — the AI dialog is reset by report identity', () => {
  it('closes the analysis dialog when the active report changes (pre-fix: stayed open with A\'s header data)', async () => {
    const notify = vi.fn();
    const { rerender } = render(
      <ThemeProvider>
        <ReportSidebar activeInstance={INSTANCE_A} notify={notify} />
      </ThemeProvider>
    );

    // Open the AI dialog for report A.
    fireEvent.click(screen.getByRole('button', { name: /AI Talqini|AI-интерпретация|AI/i }));
    const dialogForA = await screen.findByText(/#91/);
    expect(dialogForA).toBeInTheDocument();

    // The operator switches to report B — the dialog must not keep A's
    // context mounted (remount by report identity resets it closed).
    rerender(
      <ThemeProvider>
        <ReportSidebar activeInstance={INSTANCE_B} notify={notify} />
      </ThemeProvider>
    );

    await new Promise((resolve) => { setTimeout(resolve, 80); });
    expect(screen.queryByText(/#91/)).toBeNull();
    // The fresh analysis block starts closed for report B.
    expect(screen.queryByText(/#92/)).toBeNull();
  });

  it('a pending A analysis never publishes into a newer input (pre-fix: unconditional setResult)', async () => {
    let releaseInterpretation: () => void = () => {
      throw new Error('interpretation release not armed');
    };
    interpretLabResultsMock.mockImplementation(() => new Promise((resolve) => {
      releaseInterpretation = () => resolve({
        status: 'success',
        data: {
          summary: 'SYNTHETIC A INTERPRETATION',
          results: [],
        },
      });
    }));

    const dataA = {
      results: [{ name: 'Гемоглобин', value: '140', unit: 'г/л', reference: '130-170', flag: '' }],
      patient_age: 30,
      patient_gender: 'male',
    };
    const dataB = {
      results: [{ name: 'Гемоглобин', value: '110', unit: 'г/л', reference: '120-150', flag: 'low' }],
      patient_age: 40,
      patient_gender: 'female',
    };
    const onResult = vi.fn();

    const first = render(
      <ThemeProvider>
        <AIAssistant analysisType="lab" useMCP data={dataA} onResult={onResult} />
      </ThemeProvider>
    );

    // Start A's analysis (manual analyze button) — it hangs.
    fireEvent.click(screen.getByRole('button', { name: /Обновить|Refresh|Yangilash/i }));
    await waitFor(() => expect(interpretLabResultsMock).toHaveBeenCalled());

    // The input changes to B while A's analysis is in flight.
    first.rerender(
      <ThemeProvider>
        <AIAssistant analysisType="lab" useMCP data={dataB} onResult={onResult} />
      </ThemeProvider>
    );

    // A's response arrives late.
    releaseInterpretation();
    await new Promise((resolve) => { setTimeout(resolve, 120); });

    // The stale A interpretation must not be published for the newer input.
    expect(onResult).not.toHaveBeenCalled();
    expect(screen.queryByText(/SYNTHETIC A INTERPRETATION/)).toBeNull();
  });

  it('control: a current-input analysis publishes its result', async () => {
    interpretLabResultsMock.mockResolvedValue({
      status: 'success',
      data: { summary: 'SYNTHETIC CURRENT', results: [] },
    });

    const onResult = vi.fn();
    render(
      <ThemeProvider>
        <AIAssistant
          analysisType="lab"
          useMCP
          data={{
            results: [{ name: 'Гемоглобин', value: '140', unit: 'г/л', reference: '130-170', flag: '' }],
            patient_age: 30,
            patient_gender: 'male',
          }}
          onResult={onResult}
        />
      </ThemeProvider>
    );

    fireEvent.click(screen.getByRole('button', { name: /Обновить|Refresh|Yangilash/i }));

    await waitFor(() => {
      expect(onResult).toHaveBeenCalledTimes(1);
    }, { timeout: 2500 });
    void screen;
  });
});

describe('LABAI-FE-002 — the loading flag and staleness follow the input CONTENT, not object identity', () => {
  // Post-merge review of #3909 (P2): an old AI analysis still cleared the
  // loading flag for a newer input. The deeper cause: the stale guard
  // compared INPUT OBJECT IDENTITY, while parents pass inline data
  // literals — every incidental parent re-render minted a "newer input"
  // out of IDENTICAL content, silently dropping the in-flight analysis
  // result and resetting the loading flag for a dialog whose content had
  // not changed.
  it('a same-content re-render must not drop the in-flight analysis result (pre-fix: identity-based staleness suppressed it)', async () => {
    let releaseInterpretation: () => void = () => {
      throw new Error('interpretation release not armed');
    };
    interpretLabResultsMock.mockImplementation(() => new Promise((resolve) => {
      releaseInterpretation = () => resolve({
        status: 'success',
        data: {
          summary: 'SYNTHETIC SAME-CONTENT INTERPRETATION',
          results: [],
        },
      });
    }));

    const dataA = {
      results: [{ name: 'Гемоглобин', value: '140', unit: 'г/л', reference: '130-170', flag: '' }],
      patient_age: 30,
      patient_gender: 'male',
    };
    // A NEW object with IDENTICAL content — what every incidental parent
    // re-render produces for inline data literals.
    const dataA2 = JSON.parse(JSON.stringify(dataA)) as typeof dataA;
    const onResult = vi.fn();

    const first = render(
      <ThemeProvider>
        <AIAssistant analysisType="lab" useMCP data={dataA} onResult={onResult} />
      </ThemeProvider>
    );

    fireEvent.click(screen.getByRole('button', { name: /Обновить|Refresh|Yangilash/i }));
    await waitFor(() => expect(interpretLabResultsMock).toHaveBeenCalled());

    // The parent re-renders with a new object of the SAME content while
    // the analysis is in flight (queue polling, autosave timers, toasts).
    first.rerender(
      <ThemeProvider>
        <AIAssistant analysisType="lab" useMCP data={dataA2} onResult={onResult} />
      </ThemeProvider>
    );

    releaseInterpretation();
    await new Promise((resolve) => { setTimeout(resolve, 120); });

    // Pre-fix: the identity-only stale guard dropped the result.
    expect(onResult).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/SYNTHETIC SAME-CONTENT INTERPRETATION/)).toBeInTheDocument();
  });

  it('a REAL content change still suppresses the stale result and releases the loading flag', async () => {
    let releaseInterpretation: () => void = () => {
      throw new Error('interpretation release not armed');
    };
    interpretLabResultsMock.mockImplementation(() => new Promise((resolve) => {
      releaseInterpretation = () => resolve({
        status: 'success',
        data: { summary: 'SYNTHETIC A INTERPRETATION', results: [] },
      });
    }));

    const dataA = {
      results: [{ name: 'Гемоглобин', value: '140', unit: 'г/л', reference: '130-170', flag: '' }],
      patient_age: 30,
      patient_gender: 'male',
    };
    const dataB = {
      results: [{ name: 'Гемоглобин', value: '110', unit: 'г/л', reference: '120-150', flag: 'low' }],
      patient_age: 40,
      patient_gender: 'female',
    };
    const onResult = vi.fn();

    const first = render(
      <ThemeProvider>
        <AIAssistant analysisType="lab" useMCP data={dataA} onResult={onResult} />
      </ThemeProvider>
    );

    const refreshButton = screen.getByRole('button', { name: /Обновить|Refresh|Yangilash/i });
    fireEvent.click(refreshButton);
    await waitFor(() => expect(interpretLabResultsMock).toHaveBeenCalled());

    // A REAL newer input replaces the dialog's data while A is in flight.
    first.rerender(
      <ThemeProvider>
        <AIAssistant analysisType="lab" useMCP data={dataB} onResult={onResult} />
      </ThemeProvider>
    );

    releaseInterpretation();
    await new Promise((resolve) => { setTimeout(resolve, 120); });

    // The stale A interpretation is still suppressed...
    expect(onResult).not.toHaveBeenCalled();
    expect(screen.queryByText(/SYNTHETIC A INTERPRETATION/)).toBeNull();
    // ...and the loading flag is honestly released for the newer input:
    // the refresh control is usable again (not stuck «analyzing»).
    expect(screen.getByRole('button', { name: /Обновить|Refresh|Yangilash/i })).toBeEnabled();
  });
});
