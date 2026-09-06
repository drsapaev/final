/**
 * Fix E — keyboard & a11y behavior tests for PatientStepV2 (gender radio
 * group, field labels, error announcements).
 *
 * Audit finding (isolated check #4): with no gender selected BOTH radio
 * buttons had tabIndex={-1}, so the required gender group was unreachable
 * by keyboard. Audit finding (isolated check #5): the wizard's global
 * Enter handler hijacked Enter on BUTTON, so pressing Enter on a patient
 * suggestion button advanced the wizard instead of selecting the patient.
 *
 * These tests render the real component and interact via keyboard events
 * (behavior, not source-text assertions).
 */
import React, { useRef } from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import PatientStepV2 from '../PatientStepV2';

const baseProps = {
  errors: {} as Record<string, any>,
  suggestions: [] as Array<Record<string, any>>,
  showSuggestions: false,
  isSearching: false,
  onSearch: vi.fn(),
  onSelectPatient: vi.fn(),
  onUpdate: vi.fn(),
  onPhoneChange: vi.fn(),
  onBirthDateChange: vi.fn(),
  formattedBirthDate: '',
  fioRef: null,
  phoneRef: null,
  cart: { items: [], discount_mode: 'none', all_free: false, notes: '' },
  onUpdateCart: vi.fn(),
  phoneError: null,
};

// Wrapper mirrors how AppointmentWizardV2 passes refs (useRef objects).
const PatientStepWithRefs = (props: Record<string, unknown>) => {
  const fioRef = useRef<HTMLInputElement>(null);
  const phoneRef = useRef<HTMLInputElement>(null);
  const birthDateRef = useRef<HTMLInputElement>(null);
  const genderGroupRef = useRef<HTMLDivElement>(null);
  return (
    <PatientStepV2
      {...baseProps}
      {...props}
      fioRef={fioRef}
      phoneRef={phoneRef}
      birthDateRef={birthDateRef}
      genderGroupRef={genderGroupRef}
    />
  );
};

const getGenderRadios = () => {
  const group = screen.getByRole('radiogroup');
  const radios = group.querySelectorAll<HTMLButtonElement>('[role="radio"]');
  expect(radios.length).toBe(2);
  return { group, male: radios[0], female: radios[1] };
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe('PatientStepV2 gender radiogroup keyboard access (Fix E)', () => {
  it('keeps the group reachable by Tab when no gender is selected', () => {
    // Regression: previously both buttons had tabIndex={-1} here.
    render(<PatientStepWithRefs data={{ fio: '', phone: '', address: '' }} />);
    const { male, female } = getGenderRadios();
    expect(male).toHaveAttribute('tabindex', '0');
    expect(female).toHaveAttribute('tabindex', '-1');
  });

  it('moves the tab stop to the selected gender', () => {
    render(<PatientStepWithRefs data={{ fio: '', phone: '', address: '', gender: 'female' }} />);
    const { male, female } = getGenderRadios();
    expect(male).toHaveAttribute('tabindex', '-1');
    expect(female).toHaveAttribute('tabindex', '0');
    expect(female).toHaveAttribute('aria-checked', 'true');
  });

  it('selects the first option and moves focus when pressing ArrowRight on an empty group', async () => {
    const onUpdate = vi.fn();
    render(<PatientStepWithRefs data={{ fio: '', phone: '', address: '' }} onUpdate={onUpdate} />);
    const { group, male } = getGenderRadios();

    group.focus();
    await userEvent.keyboard('{ArrowRight}');

    expect(onUpdate).toHaveBeenCalledWith('gender', 'male');
    // Fix E: arrows move focus together with selection (ARIA radio pattern).
    expect(document.activeElement).toBe(male);
  });

  it('cycles male -> female with ArrowRight when a value is selected', async () => {
    const onUpdate = vi.fn();
    render(<PatientStepWithRefs data={{ fio: '', phone: '', address: '', gender: 'male' }} onUpdate={onUpdate} />);
    const { group, female } = getGenderRadios();

    group.focus();
    await userEvent.keyboard('{ArrowRight}');

    expect(onUpdate).toHaveBeenCalledWith('gender', 'female');
    expect(document.activeElement).toBe(female);
  });

  it('cycles female -> male with ArrowLeft when a value is selected', async () => {
    const onUpdate = vi.fn();
    render(<PatientStepWithRefs data={{ fio: '', phone: '', address: '', gender: 'female' }} onUpdate={onUpdate} />);
    const { group, male } = getGenderRadios();

    group.focus();
    await userEvent.keyboard('{ArrowLeft}');

    expect(onUpdate).toHaveBeenCalledWith('gender', 'male');
    expect(document.activeElement).toBe(male);
  });

  it('activates a gender radio with Enter (native button action is not suppressed)', async () => {
    const onUpdate = vi.fn();
    render(<PatientStepWithRefs data={{ fio: '', phone: '', address: '' }} onUpdate={onUpdate} />);
    const { male } = getGenderRadios();

    male.focus();
    await userEvent.keyboard('{Enter}');

    expect(onUpdate).toHaveBeenCalledWith('gender', 'male');
  });
});

describe('PatientStepV2 patient suggestion keyboard action (Fix E)', () => {
  it('selects a suggested patient with Enter on the suggestion button', async () => {
    const onSelectPatient = vi.fn();
    render(
      <PatientStepWithRefs
        data={{ fio: 'Тест', phone: '', address: '' }}
        showSuggestions
        onSelectPatient={onSelectPatient}
        suggestions={[{ id: 'p-1', fio: 'Тестов Тест Тестович', phone: '+998901000001', birth_date: '1990-05-15' }]}
      />
    );

    const suggestion = screen.getByRole('button', { name: /Тестов Тест Тестович/i });
    suggestion.focus();
    await userEvent.keyboard('{Enter}');

    expect(onSelectPatient).toHaveBeenCalledTimes(1);
    expect(onSelectPatient).toHaveBeenCalledWith(expect.objectContaining({ id: 'p-1' }));
  });
});

describe('PatientStepV2 field labels & error announcements (Fix E)', () => {
  it('associates visible labels with their inputs', () => {
    render(<PatientStepWithRefs data={{ fio: 'Иванов Иван', phone: '+998 90 111 22 33', address: 'ул. Тестовая 1' }} formattedBirthDate="15.05.1990" />);

    // Accessible names come from the visible labels (htmlFor/id pairs).
    expect(screen.getByLabelText('ФИО пациента *')).toBeTruthy();
    expect(screen.getByLabelText(/Телефон/)).toBeTruthy();
    expect(screen.getByLabelText(/Дата рождения/)).toBeTruthy();
    expect(screen.getByLabelText(/Адрес/)).toBeTruthy();
  });

  it('announces validation errors via role="alert"', () => {
    render(
      <PatientStepWithRefs
        data={{ fio: '', phone: '', address: '' }}
        errors={{ fio: 'Введите ФИО', gender: 'Укажите пол', birth_date: 'Некорректная дата' }}
        formattedBirthDate="31.02.2020"
      />
    );

    const alerts = screen.getAllByRole('alert');
    expect(alerts.length).toBeGreaterThanOrEqual(3);
    expect(screen.getByText('Введите ФИО')).toBeTruthy();
    expect(screen.getByText('Укажите пол')).toBeTruthy();
    expect(screen.getByText('Некорректная дата')).toBeTruthy();
  });
});

describe('PatientStepV2 gender radiogroup ARIA semantics', () => {
  it('keeps radiogroup semantics with aria-required', () => {
    render(<PatientStepWithRefs data={{ fio: '', phone: '', address: '' }} />);
    const group = screen.getByRole('radiogroup');
    expect(group).toHaveAttribute('aria-required', 'true');
    const radios = group.querySelectorAll('[role="radio"]');
    expect(radios.length).toBe(2);
    radios.forEach((radio) => {
      expect(radio.getAttribute('aria-checked')).toMatch(/^(true|false)$/);
    });
  });
});
