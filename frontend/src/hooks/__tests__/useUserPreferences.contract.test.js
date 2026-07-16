import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const useUserPreferencesPath = path.resolve(__dirname, '../useUserPreferences.ts');

const readSource = () => fs.readFileSync(useUserPreferencesPath, 'utf8');

describe('useUserPreferences API contract', () => {
  it('uses canonical user-management preferences paths', () => {
    const source = readSource();

    expect(source).toContain('`/users/users/${userId}/preferences`');
    expect(source).toContain('\'/users/me/preferences\'');
  });

  it('does not call the stale /user-management preferences path', () => {
    const source = readSource();

    expect(source).not.toContain('/user-management/users/');
  });
});
