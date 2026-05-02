import { describe, expect, it } from 'vitest';

import {
  buildDentistVisitProtocolSaveRequest,
} from '../dentistVisitProtocolBridge';

describe('dentistVisitProtocolBridge', () => {
  it('wraps the protocol payload in the EMR save request body', () => {
    const request = buildDentistVisitProtocolSaveRequest(
      {
        patient_id: 451,
        patient_name: 'Пациент Тест',
        visit_id: 746,
      },
      {
        chiefComplaint: 'Боль в зубе 11',
        historyOfPresentIllness: 'Боль усиливается при приёме холодного',
        procedures: [
          {
            name: 'Лечение кариеса',
            teeth: '11',
            startTime: '12:55',
            endTime: '13:10',
            description: 'Удалён кариозный очаг, выполнена пломба',
            completed: true,
          },
        ],
        recommendations: 'Контрольный осмотр через 7 дней',
      }
    );

    expect(request).toMatchObject({
      row_version: 0,
      client_session_id: null,
      is_draft: true,
      data: {
        specialty: 'dentistry',
        complaints: 'Боль в зубе 11',
        anamnesis_morbi: 'Боль усиливается при приёме холодного',
        recommendations: 'Контрольный осмотр через 7 дней',
        notes: 'Контрольный осмотр через 7 дней',
        visit_protocol: expect.objectContaining({
          patient_id: 451,
          patient_name: 'Пациент Тест',
          visit_id: 746,
          source: 'emr_v2',
        }),
      },
    });
  });
});
