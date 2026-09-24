import { fireEvent, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '../../../test/renderWithProviders';
import PhotoArchive from '../PhotoArchive';
import VisitProtocol from '../VisitProtocol';

describe('legacy dental media forms', () => {
  it('does not offer local-only upload, delete, or save actions in the photo archive', () => {
    renderWithProviders(
      <PhotoArchive patientId={7} patientName="SYNTHETIC-Patient" onClose={vi.fn()} />,
    );

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText(/protected storage|защищённого хранения/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /upload|загрузить|save|сохранить|delete|удалить/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/upload|загрузить/i)).not.toBeInTheDocument();
  });

  it('blocks the legacy protocol editor and its separate completion action', () => {
    const onClose = vi.fn();
    const onComplete = vi.fn();
    renderWithProviders(
      <VisitProtocol
        patientName="SYNTHETIC-Patient"
        onClose={onClose}
        onComplete={onComplete} />,
    );

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText(/attachments|вложения/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /save|сохранить|complete|завершить|upload|загрузить/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/upload|загрузить/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /close|закрыть/i }));
    expect(onClose).toHaveBeenCalledOnce();
    expect(onComplete).not.toHaveBeenCalled();
  });
});
