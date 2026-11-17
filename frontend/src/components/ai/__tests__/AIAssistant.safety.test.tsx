import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ analyze: vi.fn(), post: vi.fn(), error: vi.fn(), success: vi.fn() }));
vi.mock('../../../hooks/useMcpClient', () => ({ useMcpClient: () => ({ analyzeComplaint: mocks.analyze }) }));
vi.mock('../../../api/client', () => ({ apiClient: { post: mocks.post } }));
vi.mock('../../../services/notify', () => ({ notify: { success: mocks.success, error: mocks.error, info: vi.fn() } }));
vi.mock('../../../contexts/ThemeContext', () => ({ useTheme: () => ({ theme: 'light' }) }));
import AIAssistant from '../AIAssistant';

const safe = { requires_doctor_confirmation: true };
const badMarkers = [undefined, null, {}, { requires_doctor_confirmation: false },
  { requires_doctor_confirmation: 1 }, { requires_doctor_confirmation: 'true' }];

describe('AIAssistant medical safety boundary', () => {
  beforeEach(() => vi.resetAllMocks());

  it.each(badMarkers)('does not publish MCP content without strict metadata: %j', async (marker) => {
    mocks.analyze.mockResolvedValue({ status: 'success', data: { preliminary_diagnosis: ['SYNTHETIC UNSAFE'] }, ai_safety_meta: marker });
    const onResult = vi.fn();
    render(<AIAssistant analysisType="complaint" data={{ complaint: 'SYNTHETIC' }} onResult={onResult} />);
    fireEvent.click(screen.getByRole('button', { name: /обновить/i }));
    await waitFor(() => expect(mocks.error).toHaveBeenCalled());
    expect(onResult).not.toHaveBeenCalled();
    expect(screen.queryByText('SYNTHETIC UNSAFE')).not.toBeInTheDocument();
    expect(mocks.success).not.toHaveBeenCalled();
  });

  it('accepts a marked MCP envelope before exposing its result', async () => {
    mocks.analyze.mockResolvedValue({ status: 'success', data: { preliminary_diagnosis: ['SYNTHETIC SAFE'] }, ai_safety_meta: safe });
    const onResult = vi.fn();
    render(<AIAssistant analysisType="complaint" data={{ complaint: 'SYNTHETIC' }} onResult={onResult} />);
    fireEvent.click(screen.getByRole('button', { name: /обновить/i }));
    await waitFor(() => expect(onResult).toHaveBeenCalledWith({ preliminary_diagnosis: ['SYNTHETIC SAFE'] }));
  });

  it('checks the legacy ICD envelope before extracting its array', async () => {
    mocks.post.mockResolvedValueOnce({ data: { data: [{ code: 'SYNTHETIC UNSAFE' }] } });
    const onResult = vi.fn();
    render(<AIAssistant analysisType="icd10" useMCP={false} data={{ symptoms: ['SYNTHETIC'] }} onResult={onResult} />);
    fireEvent.click(screen.getByRole('button', { name: /обновить/i }));
    await waitFor(() => expect(mocks.error).toHaveBeenCalled());
    expect(onResult).not.toHaveBeenCalled();
  });

  it('unwraps a safely marked legacy ICD list only after validation', async () => {
    const suggestions = [{ code: 'SYNTHETIC SAFE' }];
    mocks.post.mockResolvedValueOnce({ data: { data: suggestions, ai_safety_meta: safe } });
    const onResult = vi.fn();
    render(<AIAssistant analysisType="icd10" useMCP={false} data={{ symptoms: ['SYNTHETIC'] }} onResult={onResult} />);
    fireEvent.click(screen.getByRole('button', { name: /обновить/i }));
    await waitFor(() => expect(onResult).toHaveBeenCalledWith(suggestions));
  });

  it.each([
    ['complaint', { complaint: 'SYNTHETIC' }],
    ['lab', { results: [] }],
    ['ecg', { rhythm: 'SYNTHETIC' }],
    ['skin', { image: new Blob(['synthetic']) }],
  ])('blocks an unmarked direct %s response before publishing', async (analysisType, data) => {
    mocks.post.mockResolvedValueOnce({ data: { summary: 'SYNTHETIC UNSAFE' } });
    const onResult = vi.fn();
    render(<AIAssistant analysisType={analysisType as string} useMCP={false} data={data as Record<string, unknown>} onResult={onResult} />);
    fireEvent.click(screen.getByRole('button', { name: /обновить/i }));
    await waitFor(() => expect(mocks.error).toHaveBeenCalled());
    expect(onResult).not.toHaveBeenCalled();
    expect(screen.queryByText('SYNTHETIC UNSAFE')).not.toBeInTheDocument();
  });

  it('hides a previously completed result when clinical input changes', async () => {
    mocks.analyze.mockResolvedValue({ status: 'success', data: { preliminary_diagnosis: ['SYNTHETIC OLD'] }, ai_safety_meta: safe });
    const first = render(<AIAssistant analysisType="complaint" data={{ complaint: 'SYNTHETIC A' }} />);
    fireEvent.click(screen.getByRole('button', { name: /обновить/i }));
    await screen.findByText('SYNTHETIC OLD');
    first.rerender(<AIAssistant analysisType="complaint" data={{ complaint: 'SYNTHETIC B' }} />);
    expect(screen.queryByText('SYNTHETIC OLD')).not.toBeInTheDocument();
  });

  it('never calls onResult after unmount even for a marked late response', async () => {
    let release: (value: unknown) => void = () => { throw new Error('not armed'); };
    mocks.analyze.mockImplementation(() => new Promise((resolve) => { release = resolve; }));
    const onResult = vi.fn();
    const first = render(<AIAssistant analysisType="complaint" data={{ complaint: 'SYNTHETIC' }} onResult={onResult} />);
    fireEvent.click(screen.getByRole('button', { name: /обновить/i }));
    await waitFor(() => expect(mocks.analyze).toHaveBeenCalled());
    first.unmount();
    release({ status: 'success', data: { preliminary_diagnosis: ['SYNTHETIC LATE'] }, ai_safety_meta: safe });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(onResult).not.toHaveBeenCalled();
    expect(mocks.success).not.toHaveBeenCalled();
  });
});
