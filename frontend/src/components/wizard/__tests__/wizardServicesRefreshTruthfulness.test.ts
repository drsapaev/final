/**
 * REG-FE-070 (follow-up audit 2026-11-02): пользовательский рефRESH
 * списка услуг не рапортует успех при сетевом провале.
 *
 * Дефект: loadServices глотал ошибку fetchRegistrarServices (catch без
 * rethrow/результата), а handleReloadServices ПОСЛЕ await безусловно
 * показывал toast.success — на мёртвой сети кассир/регистратор видел
 * «список обновлён» со старым каталогом.
 *
 * Source-contract тест (прецедент репо: мастер не монтируется в тестах,
 * все wizard-тесты — контракты по исходнику; см. wizardSearchRecovery).
 * Red-first: в префиксном коде loadServices не возвращал результат, а
 * handleReloadServices не ветвился.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const wizardPath = path.resolve(__dirname, '../AppointmentWizardV2.tsx');
const source = fs.readFileSync(wizardPath, 'utf-8').replace(/\r\n/g, '\n');

const extractBlock = (source: string, startMarker: string, endMarker: string): string => {
  const start = source.indexOf(startMarker);
  expect(start, `start marker not found: ${startMarker}`).toBeGreaterThanOrEqual(0);
  const end = source.indexOf(endMarker, start);
  expect(end, `end marker not found: ${endMarker}`).toBeGreaterThan(start);
  return source.slice(start, end);
};

describe('REG-FE-070: service refresh truthfulness', () => {
  const loadServices = extractBlock(
    source,
    'const loadServices = useCallback(',
    '}, [catalogTargetDate]);',
  );

  it('loadServices reports its outcome instead of swallowing the failure', () => {
    // Успех — явный true.
    expect(loadServices).toContain('return true;');
    // Провал — явный false, а не молчаливый resolve.
    expect(loadServices).toMatch(/return false;/);
    // Подпись контракта: Promise<boolean>.
    expect(loadServices).toMatch(/async\s*\(\)\s*:\s*Promise<boolean>/);
  });

  it('the reload handler branches on the load result', () => {
    const reload = extractBlock(
      source,
      'const handleReloadServices = async () => {',
      '};',
    );
    // Один await, ветвление по результату.
    expect(reload).toMatch(/const ok = await loadServices\(\);/);
    expect(reload).toMatch(/toast\[ok \? 'success' : 'error'\]/);
    expect(reload).toContain("misc.aw_services_list_updated");
    expect(reload).toContain("misc.aw_services_list_update_failed");
  });

  it('no unconditional success toast remains on the reload path', () => {
    const reload = extractBlock(
      source,
      'const handleReloadServices = async () => {',
      '};',
    );
    expect(reload).not.toMatch(/^.*toast\.success.*$/);
  });
});
