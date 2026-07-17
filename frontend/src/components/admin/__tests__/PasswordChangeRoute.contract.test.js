import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const unifiedSettingsPath = path.resolve(__dirname, '../UnifiedSettings.tsx');
const changePasswordRequiredPath = path.resolve(
  __dirname,
  '../../../pages/auth/ChangePasswordRequired.tsx'
);

const readSource = (filePath) => fs.readFileSync(filePath, 'utf8');

describe('password change API contract', () => {
  it('uses the canonical authentication password-change route', () => {
    const unifiedSettingsSource = readSource(unifiedSettingsPath);
    const changePasswordRequiredSource = readSource(changePasswordRequiredPath);

    expect(unifiedSettingsSource).toContain('api.post(\'/authentication/password-change\'');
    expect(changePasswordRequiredSource).toContain('api.post(\'/authentication/password-change\'');
  });

  it('does not call the stale auth password-change route', () => {
    const unifiedSettingsSource = readSource(unifiedSettingsPath);
    const changePasswordRequiredSource = readSource(changePasswordRequiredPath);

    expect(unifiedSettingsSource).not.toContain('/auth/password-change');
    expect(changePasswordRequiredSource).not.toContain('/auth/password-change');
  });
});
