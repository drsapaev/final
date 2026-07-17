import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const userExportManagerPath = path.resolve(__dirname, '../UserExportManager.tsx');

const readSource = () => fs.readFileSync(userExportManagerPath, 'utf8');

describe('UserExportManager API contract', () => {
  it('uses the canonical user-management router paths mounted under /users', () => {
    const source = readSource();

    expect(source).toContain('api.get(\'/users/users/export/files\')');
    expect(source).toContain('api.post(\'/users/users/export\', exportData)');
    expect(source).toContain('api.get(`/users/users/export/download/${filename}`,');
    expect(source).toContain('api.delete(`/users/users/export/files/${filename}`)');
  });

  it('does not call the stale /user-management compatibility path', () => {
    const source = readSource();

    expect(source).not.toContain('/user-management/users/export');
  });
});
