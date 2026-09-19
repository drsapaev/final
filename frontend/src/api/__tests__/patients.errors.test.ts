/**
 * E-054 leftover 3 (wizard-пятёрка PR 3084, закрыт как superseded) —
 * структурированные коды ошибок доменных дублей patients.
 *
 * Backend: HTTP 400 detail теперь {code, message} для
 * patient_phone_exists / patient_doc_exists (человекочитаемый текст
 * сохранён в message). API-клиент нормализует оба вида: структурный
 * (машиночитаемый code) и легаси-строку; code пробрасывается в ошибку.
 *
 * RED→GREEN: до реализации parsePatientErrorDetail не существовало,
 * словарный detail попадал в сообщение как «[object Object]» и код
 * не пробрасывался.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}));

import { api } from '../client';
import { createPatient, parsePatientErrorDetail, updatePatient } from '../patients';

const apiMock = api as unknown as {
  post: ReturnType<typeof vi.fn>;
  put: ReturnType<typeof vi.fn>;
};

const apiError = (status: number, detail: unknown) => ({
  isAxiosError: true,
  response: { status, data: { detail } },
});

describe('parsePatientErrorDetail', () => {
  it('структурный detail {code, message} → message + code', () => {
    expect(
      parsePatientErrorDetail({ code: 'patient_phone_exists', message: 'Пациент с таким номером телефона уже существует' }),
    ).toEqual({ message: 'Пациент с таким номером телефона уже существует', code: 'patient_phone_exists' });
  });

  it('легаси-строка проходит как есть, без кода', () => {
    expect(parsePatientErrorDetail('Пациент с таким номером телефона уже существует')).toEqual({
      message: 'Пациент с таким номером телефона уже существует',
      code: undefined,
    });
  });

  it('null → пустая строка', () => {
    expect(parsePatientErrorDetail(null)).toEqual({ message: '' });
  });
});

describe('createPatient — structured duplicate error', () => {
  beforeEach(() => vi.clearAllMocks());

  it('400 {code: patient_phone_exists}: код пробрасывается, текст человекочитаемый', async () => {
    apiMock.post.mockRejectedValue(
      apiError(400, { code: 'patient_phone_exists', message: 'Пациент с таким номером телефона уже существует' }),
    );
    await expect(createPatient({ phone: '+998900000000' })).rejects.toMatchObject({
      status: 400,
      code: 'patient_phone_exists',
      message: 'Пациент с таким номером телефона уже существует',
    });
  });

  it('400 {code: patient_doc_exists}: код документа пробрасывается', async () => {
    apiMock.post.mockRejectedValue(
      apiError(400, { code: 'patient_doc_exists', message: 'Пациент с таким номером документа уже зарегистрирован' }),
    );
    await expect(createPatient({ doc_number: 'AA1234567' })).rejects.toMatchObject({
      status: 400,
      code: 'patient_doc_exists',
      message: 'Пациент с таким номером документа уже зарегистрирован',
    });
  });

  it('легаси-строковый 400 остаётся совместим (без кода)', async () => {
    apiMock.post.mockRejectedValue(apiError(400, 'Пациент с таким номером телефона уже существует'));
    await expect(createPatient({ phone: '+998900000000' })).rejects.toMatchObject({
      status: 400,
      code: undefined,
      message: 'Пациент с таким номером телефона уже существует',
    });
  });
});

describe('updatePatient — structured duplicate error', () => {
  beforeEach(() => vi.clearAllMocks());

  it('400 {code, message}: сообщение не превращается в [object Object]', async () => {
    apiMock.put.mockRejectedValue(
      apiError(400, { code: 'patient_phone_exists', message: 'Пациент с таким номером телефона уже существует' }),
    );
    await expect(updatePatient(1, { phone: '+998900000000' })).rejects.toMatchObject({
      status: 400,
      code: 'patient_phone_exists',
      message: 'Пациент с таким номером телефона уже существует',
    });
  });
});
