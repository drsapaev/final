import { describe, expect, it } from 'vitest';

import {
  QUEUE_PROFILES_CSV_HEADERS,
  buildQueueProfilesCsv,
  parseCsvRecords,
  parseQueueProfilesCsv,
  queueProfileToCsvPayload,
} from '../queueProfilesCsv';

// RQ-26.a — pure CSV contract helpers (F-22). SYNTHETIC/DEV-DEMO fixtures
// only: synthetic domain identifiers, no PHI/PII values anywhere.

describe('parseCsvRecords (RFC-4180 style)', () => {
  it('splits plain rows and fields', () => {
    expect(parseCsvRecords('a,b,c\nd,e,f')).toEqual([['a', 'b', 'c'], ['d', 'e', 'f']]);
  });

  it('keeps commas inside quoted fields', () => {
    expect(parseCsvRecords('"a, b",c')).toEqual([['a, b', 'c']]);
  });

  it('keeps CR/LF/CRLF newlines inside quoted fields', () => {
    expect(parseCsvRecords('"line1\nline2",x')).toEqual([['line1\nline2', 'x']]);
    expect(parseCsvRecords('"line1\r\nline2",x')).toEqual([['line1\r\nline2', 'x']]);
  });

  it('unescapes doubled quotes inside quoted fields', () => {
    expect(parseCsvRecords('"say ""hi""",ok')).toEqual([['say "hi"', 'ok']]);
  });

  it('treats CRLF as a row terminator outside quotes', () => {
    expect(parseCsvRecords('a,b\r\nc,d')).toEqual([['a', 'b'], ['c', 'd']]);
  });

  it('skips blank records but keeps quoted empty fields', () => {
    expect(parseCsvRecords('a,b\n\nc,d')).toEqual([['a', 'b'], ['c', 'd']]);
    expect(parseCsvRecords('a,""\nc,d')).toEqual([['a', ''], ['c', 'd']]);
  });

  it('flushes a trailing record without a final newline', () => {
    expect(parseCsvRecords('a,b\nc')).toEqual([['a', 'b'], ['c']]);
  });

  it('treats quotes inside unquoted fields literally', () => {
    expect(parseCsvRecords('a"b,c')).toEqual([['a"b', 'c']]);
  });
});

describe('buildQueueProfilesCsv', () => {
  it('writes the full current contract header', () => {
    const csv = buildQueueProfilesCsv([]);
    expect(csv.split('\n')[0]).toBe(QUEUE_PROFILES_CSV_HEADERS.join(','));
    expect(csv.split('\n')[0]).toContain('department_key');
    expect(csv.split('\n')[0]).toContain('show_on_qr_page');
  });

  it('quotes every field and escapes inner quotes', () => {
    const csv = buildQueueProfilesCsv([
      {
        key: 'synthetic-p',
        title: 'Название, с запятой и "кавычками"',
        title_ru: 'Синтетический профиль',
        queue_tags: ['tag1', 'tag2'],
        department_key: 'cardiology',
        icon: 'Heart',
        color: '#E53E3E',
        order: 3,
        is_active: false,
        show_on_qr_page: false,
      },
    ]);
    const rows = csv.split('\n');
    expect(rows[1]).toBe(
      '"synthetic-p","Название, с запятой и ""кавычками""","Синтетический профиль","tag1;tag2","cardiology","Heart","#E53E3E","3","false","false"'
    );
  });

  it('reads display_order from the display_order field with the order alias fallback', () => {
    const withDisplayOrder = buildQueueProfilesCsv([{ key: 'k', title: 't', display_order: 5 }]);
    const withOrderAlias = buildQueueProfilesCsv([{ key: 'k', title: 't', order: 7 }]);
    expect(withDisplayOrder.split('\n')[1]).toContain('"5"');
    expect(withOrderAlias.split('\n')[1]).toContain('"7"');
  });

  it('defaults flags to true (backend defaults) only when they are not explicitly false', () => {
    const csv = buildQueueProfilesCsv([{ key: 'k', title: 't' }]);
    expect(csv.split('\n')[1]).toContain('"true","true"');
  });
});

describe('parseQueueProfilesCsv', () => {
  it('parses the full-contract file with typed values', () => {
    const csv = [
      'key,title,title_ru,queue_tags,department_key,icon,color,display_order,is_active,show_on_qr_page',
      '"k1","Профиль, первый","Профиль один","a;b","cardiology","Heart","#E53E3E","3","false","false"',
    ].join('\n');
    const { rows, issues } = parseQueueProfilesCsv(csv);
    expect(issues).toEqual([]);
    expect(rows).toEqual([
      {
        key: 'k1',
        title: 'Профиль, первый',
        titleRu: 'Профиль один',
        queueTags: ['a', 'b'],
        departmentKey: 'cardiology',
        icon: 'Heart',
        color: '#E53E3E',
        displayOrder: 3,
        isActive: false,
        showOnQrPage: false,
      },
    ]);
  });

  it('round-trips through export without losing any contract field', () => {
    const source = [
      {
        key: 'synthetic-roundtrip',
        title: 'Круг, "с" запятой',
        title_ru: 'Синтетический round-trip',
        queue_tags: ['x;y', 'z'],
        department_key: null,
        icon: 'Package',
        color: '#718096',
        order: 12,
        is_active: true,
        show_on_qr_page: false,
      },
    ];
    const csv = buildQueueProfilesCsv(source);
    const { rows, issues } = parseQueueProfilesCsv(csv);
    expect(issues).toEqual([]);
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      key: 'synthetic-roundtrip',
      title: 'Круг, "с" запятой',
      titleRu: 'Синтетический round-trip',
      // A literal semicolon inside a tag is not representable with the ';'
      // separator — the round-trip contract documents ';' as the tag joiner.
      queueTags: ['x', 'y', 'z'],
      departmentKey: undefined,
      icon: 'Package',
      color: '#718096',
      displayOrder: 12,
      isActive: true,
      showOnQrPage: false,
    });
  });

  it('reports missing required columns and aborts', () => {
    const { rows, issues } = parseQueueProfilesCsv('key,is_active\n"k1","true"');
    expect(rows).toEqual([]);
    expect(issues.map((i) => i.code)).toContain('missing_column');
    expect(issues.find((i) => i.code === 'missing_column')?.column).toBe('title');
  });

  it('reports unknown columns as non-blocking warnings', () => {
    const csv = [
      'key,title,custom_column',
      '"k1","Профиль","значение"',
    ].join('\n');
    const { rows, issues } = parseQueueProfilesCsv(csv);
    expect(rows).toHaveLength(1);
    expect(issues.map((i) => i.code)).toContain('unknown_column');
  });

  it('blocks rows with missing key, missing title or duplicate keys', () => {
    const csv = [
      'key,title',
      ',"Без ключа"',
      '"k1",""',
      '"k1","Первый"',
      '"k1","Дубль"',
      '"k2","Второй"',
    ].join('\n');
    const { rows, issues } = parseQueueProfilesCsv(csv);
    expect(rows.map((r) => r.key)).toEqual(['k1', 'k2']);
    const codes = issues.map((i) => i.code);
    expect(codes).toContain('missing_key');
    expect(codes).toContain('missing_title');
    expect(codes).toContain('duplicate_key');
    expect(issues.find((i) => i.code === 'duplicate_key')?.row).toBe(4);
  });

  it('blocks rows with invalid booleans or display_order', () => {
    const csv = [
      'key,title,display_order,is_active,show_on_qr_page',
      '"k1","Профиль","abc","true","true"',
      '"k2","Профиль","2","maybe","true"',
      '"k3","Профиль","3","true","0"',
    ].join('\n');
    const { rows, issues } = parseQueueProfilesCsv(csv);
    expect(rows.map((r) => r.key)).toEqual(['k3']);
    const codes = issues.map((i) => i.code);
    expect(codes).toContain('invalid_display_order');
    expect(codes).toContain('invalid_boolean');
    expect(codes.filter((c) => c === 'invalid_boolean')).toHaveLength(1);
  });

  it('warns about unknown department keys only when a known set is provided', () => {
    const csv = [
      'key,title,department_key',
      '"k1","Профиль","not-a-department"',
    ].join('\n');

    const withoutSet = parseQueueProfilesCsv(csv);
    expect(withoutSet.issues).toEqual([]);

    const withEmptySet = parseQueueProfilesCsv(csv, { knownDepartmentKeys: new Set() });
    expect(withEmptySet.issues).toEqual([]);

    const withSet = parseQueueProfilesCsv(csv, {
      knownDepartmentKeys: new Set(['cardiology']),
    });
    expect(withSet.rows).toHaveLength(1);
    expect(withSet.issues.map((i) => i.code)).toContain('unknown_department');
  });

  it('treats empty optional cells as not-provided (payload omits them)', () => {
    const csv = [
      'key,title,title_ru,queue_tags,department_key,icon,color,display_order,is_active,show_on_qr_page',
      '"k1","Профиль",,"a",,,,,',
    ].join('\n');
    const { rows } = parseQueueProfilesCsv(csv);
    expect(rows[0]).toMatchObject({
      key: 'k1',
      title: 'Профиль',
      queueTags: ['a'],
      departmentKey: undefined,
      isActive: undefined,
      showOnQrPage: undefined,
      displayOrder: undefined,
    });
    expect(queueProfileToCsvPayload(rows[0])).toEqual({
      key: 'k1',
      title: 'Профиль',
      queue_tags: ['a'],
    });
  });

  it('accepts old-format files (8 columns) without the new contract fields', () => {
    const csv = [
      'key,title,title_ru,queue_tags,icon,color,display_order,is_active',
      '"k1","Старый формат","Старый","a;b","Heart","#E53E3E","3","false"',
    ].join('\n');
    const { rows, issues } = parseQueueProfilesCsv(csv);
    expect(issues).toEqual([]);
    expect(rows[0]).toMatchObject({
      key: 'k1',
      title: 'Старый формат',
      queueTags: ['a', 'b'],
      isActive: false,
    });
    expect(rows[0].departmentKey).toBeUndefined();
    expect(rows[0].showOnQrPage).toBeUndefined();
    expect(queueProfileToCsvPayload(rows[0])).not.toHaveProperty('department_key');
    expect(queueProfileToCsvPayload(rows[0])).not.toHaveProperty('show_on_qr_page');
  });

  it('reports column count mismatches as blocking issues', () => {
    const csv = ['key,title', '"k1","Профиль","лишняя"'].join('\n');
    const { rows, issues } = parseQueueProfilesCsv(csv);
    expect(rows).toEqual([]);
    expect(issues.map((i) => i.code)).toContain('column_mismatch');
  });

  it('reports an empty file', () => {
    const { rows, issues } = parseQueueProfilesCsv('');
    expect(rows).toEqual([]);
    expect(issues.map((i) => i.code)).toContain('empty_file');
  });
});

describe('queueProfileToCsvPayload', () => {
  it('always sends key and title, and only provided optional fields', () => {
    expect(queueProfileToCsvPayload({ key: 'k1', title: 'Профиль' })).toEqual({
      key: 'k1',
      title: 'Профиль',
    });
  });

  it('keeps explicit false flags and zero order in the payload', () => {
    expect(
      queueProfileToCsvPayload({
        key: 'k1',
        title: 'Профиль',
        queueTags: [],
        displayOrder: 0,
        isActive: false,
        showOnQrPage: false,
      })
    ).toEqual({
      key: 'k1',
      title: 'Профиль',
      queue_tags: [],
      display_order: 0,
      is_active: false,
      show_on_qr_page: false,
    });
  });
});
