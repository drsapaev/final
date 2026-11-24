import { describe, expect, it } from 'vitest';
import { LAB_IMPORT_CSV_HEADER, parseLabImportCsv } from '../utils/labImportCsv';

describe('parseLabImportCsv', () => {
  const messageId = '00000000-0000-4000-8000-000000000001';

  it('keeps decimal comma, comparators and all analytes in a message together', () => {
    const parsed = parseLabImportCsv(
      `${LAB_IMPORT_CSV_HEADER}\r\n${messageId},42,SYNTHETIC-1,hgb,g_l,"<0,01",,\r\n${messageId},42,SYNTHETIC-1,plt,unit,0,,`,
    );
    expect(parsed).toHaveLength(1);
    expect(parsed[0]?.values.map((item) => item.value_text)).toEqual(['<0,01', '0']);
  });

  it('rejects one message ID naming two different specimen/report identities', () => {
    expect(() => parseLabImportCsv(
      `${LAB_IMPORT_CSV_HEADER}\n${messageId},42,SYNTHETIC-1,hgb,g_l,5,,\n${messageId},43,SYNTHETIC-2,hgb,g_l,6,,`,
    )).toThrow('csv');
  });
});
