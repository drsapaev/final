import fs from 'fs';
import path from 'path';

import { describe, expect, it } from 'vitest';

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../../..');

const source = fs.readFileSync(
  path.join(ROOT, 'components/laboratory/QueueCard.jsx'),
  'utf8'
);

describe('QueueCard STRAT#28 — React.memo wrapped card component', () => {
  it('exports QueueCard wrapped in memo', () => {
    expect(source).toContain('export default memo(QueueCard)');
    expect(source).toContain('import { memo }');
  });

  it('accepts appointment, isSelected, onOpenAppointment props', () => {
    expect(source).toContain('appointment');
    expect(source).toContain('isSelected');
    expect(source).toContain('onOpenAppointment');
  });

  it('has PropTypes for all props', () => {
    expect(source).toContain('appointment: PropTypes.object.isRequired');
    expect(source).toContain('isSelected: PropTypes.bool');
    expect(source).toContain('onOpenAppointment: PropTypes.func.isRequired');
  });

  it('uses t() for all i18n strings', () => {
    expect(source).toContain('t(\'queue.patient_no_name\')');
    expect(source).toContain('t(\'queue.visit\')');
    expect(source).toContain('t(\'queue.services\')');
    expect(source).toContain('t(\'queue.report_exists\')');
    expect(source).toContain('t(\'queue.report_new\')');
  });

  it('imports formatters from labUiLabels', () => {
    expect(source).toContain('from \'./labUiLabels\'');
    expect(source).toContain('formatLabStatus');
    expect(source).toContain('getLabStatusVariant');
    expect(source).toContain('formatPaymentStatus');
    expect(source).toContain('formatSpecialtyLabel');
  });

  it('has STRAT#28 marker in JSDoc', () => {
    expect(source).toContain('STRAT#28');
  });
});
