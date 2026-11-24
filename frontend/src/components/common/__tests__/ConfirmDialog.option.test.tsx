import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { useConfirm } from '../ConfirmDialog';
import { ThemeProvider } from '../../../contexts/ThemeContext';

function Harness({ onResult }: { onResult: (result: boolean, option: boolean) => void }) {
  const [confirm, dialog] = useConfirm();
  return <>
    <button onClick={async () => {
      let checked = false;
      const result = await confirm({
        title: 'Finish visit?',
        confirmLabel: 'Finish',
        cancelLabel: 'Back',
        confirmationOption: {
          label: 'Call the next patient',
          onConfirm: (value: boolean) => { checked = value; },
        },
      });
      onResult(result, checked);
    }}>Open</button>
    {dialog}
  </>;
}

describe('ConfirmDialog per-request option', () => {
  it('defaults to unchecked, supports explicit keyboard selection and forgets prior choice', async () => {
    const user = userEvent.setup();
    const onResult = vi.fn();
    render(<ThemeProvider><Harness onResult={onResult} /></ThemeProvider>);

    const open = () => user.click(screen.getByRole('button', { name: 'Open' }));
    const finish = () => user.click(screen.getByRole('button', { name: 'Finish' }));
    const option = () => screen.getByRole('checkbox', { name: 'Call the next patient' });
    await open();
    expect(option()).not.toBeChecked();
    await finish();
    expect(onResult).toHaveBeenLastCalledWith(true, false);

    await open();
    option().focus();
    await user.keyboard(' ');
    expect(option()).toBeChecked();
    await finish();
    expect(onResult).toHaveBeenLastCalledWith(true, true);

    await open();
    expect(option()).not.toBeChecked();
    await user.click(option());
    await user.click(screen.getByRole('button', { name: 'Back' }));
    expect(onResult).toHaveBeenLastCalledWith(false, false);

    await open();
    expect(option()).not.toBeChecked();
  });
});
