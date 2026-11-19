import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';

const { post, logError } = vi.hoisted(() => ({ post: vi.fn(), logError: vi.fn() }));
vi.mock('../../../api/client', () => ({ api: { post } }));
vi.mock('../../../utils/logger', () => ({ default: { error: logError } }));
vi.mock('../../../i18n/useTranslation', () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
vi.mock('react-toastify', () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

import ForgotPassword from '../ForgotPassword';

afterEach(() => { cleanup(); post.mockReset(); logError.mockReset(); });

it('does not log recovery request bodies when the API fails', async () => {
  post.mockRejectedValue({ config: { data: '{"email":"SYNTHETIC_PRIVATE@example.test"}' } });
  render(<ForgotPassword />);
  fireEvent.change(screen.getByLabelText('final.fp_email_label'), { target: { value: 'SYNTHETIC_PRIVATE@example.test' } });
  fireEvent.click(screen.getByLabelText('final.fp_continue'));
  await waitFor(() => expect(logError).toHaveBeenCalledWith('Error sending email reset'));
  expect(JSON.stringify(logError.mock.calls)).not.toContain('SYNTHETIC_PRIVATE');
  expect(await screen.findByText('final.fp_email_error')).toBeTruthy();
});
