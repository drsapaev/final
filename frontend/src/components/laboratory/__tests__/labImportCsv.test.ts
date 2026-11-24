import { describe, expect, it } from 'vitest';
import { LAB_IMPORT_CSV_HEADER, parseLabImportCsv } from '../utils/labImportCsv';

describe('parseLabImportCsv', () => {
  const messageId = '00000000-0000-4000-8000-000000000001';
  const siblingId = '00000000-0000-4000-8000-000000000002';
  const legacyHeader = 'message_id,report_instance_id,specimen_barcode,analyte_code,unit_code,value,method_code,observed_at';

  it('keeps decimal comma, comparators and all analytes in a message together', () => {
    const parsed = parseLabImportCsv(
      `${legacyHeader}\r\n${messageId},42,SYNTHETIC-1,hgb,g_l,"<0,01",,\r\n${messageId},42,SYNTHETIC-1,plt,unit,0,,`,
    );
    expect(parsed).toHaveLength(1);
    expect(parsed[0]?.values.map((item) => item.value_text)).toEqual(['<0,01', '0']);
  });

  it('rejects ambiguous repeated columns before selecting any identity or value', () => {
    expect(() => parseLabImportCsv(
      `${legacyHeader},value\n${messageId},42,SYNTHETIC-1,hgb,g_l,5,,,6`,
    )).toThrow('csv');
  });

  it('keeps exact instrument flags and preserves valid siblings of an ambiguous message', () => {
    const parsed = parseLabImportCsv(
      `${LAB_IMPORT_CSV_HEADER}\n${messageId},42,SYNTHETIC-1,hgb,g_l,5,,,\n${siblingId},44,SYNTHETIC-3,hgb,g_l,7,,,"[""Flag-H"",""H?""]"\n${messageId},43,SYNTHETIC-2,hgb,g_l,6,,,`,
    );
    expect(parsed.map((row) => row.message_id)).toEqual([messageId, siblingId]);
    expect(parsed[0]).toMatchObject({ report_instance_id: 0, values: [] });
    expect(parsed[1]?.values[0]?.instrument_flags).toEqual(['Flag-H', 'H?']);
  });

  it.each(['0x2a', '4.2e1', '2147483648', '42.0'])('does not coerce report ID %s to a different report', (badId) => {
    const parsed = parseLabImportCsv(
      `${legacyHeader}\n${messageId},${badId},SYNTHETIC-1,hgb,g_l,5,,\n${siblingId},42,SYNTHETIC-3,hgb,g_l,7,,`,
    );
    expect(parsed.map((row) => row.values.length)).toEqual([0, 1]);
  });
});
