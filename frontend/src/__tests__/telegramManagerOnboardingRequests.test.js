import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const managerSource = fs.readFileSync(
  path.resolve(process.cwd(), 'src/components/TelegramManager.jsx'),
  'utf8'
).replace(/\r\n/g, '\n');

function sourceBetween(source, start, end) {
  const startIndex = source.indexOf(start);
  expect(startIndex).toBeGreaterThanOrEqual(0);

  const endIndex = source.indexOf(end, startIndex + start.length);
  expect(endIndex).toBeGreaterThan(startIndex);

  return source.slice(startIndex, endIndex);
}

describe('Telegram manager onboarding request review', () => {
  it('loads REQUEST_REVIEW requests from registrar endpoints only', () => {
    const loader = sourceBetween(
      managerSource,
      'const loadTelegramData = async () => {',
      'const handleCreateTemplate = async () => {'
    );

    expect(loader).toContain('/telegram/onboarding/requests');
    expect(loader).toContain("status_filter: 'pending_review'");
    expect(loader).not.toContain('/telegram/mini-app/onboarding');
    expect(loader).not.toContain('/telegram/mini-app/appointments');
    expect(loader).not.toMatch(/entryToken|payment|invoice|diagnosis|lab|emr/i);
  });

  it('limits review actions to staff review endpoints', () => {
    const actionHandler = sourceBetween(
      managerSource,
      'const handleOnboardingReviewAction = async (requestId, action) => {',
      'const handleCreateTemplate = async () => {'
    );

    expect(actionHandler).toContain('/telegram/onboarding/requests/');
    expect(actionHandler).toContain("action === 'link-existing'");
    expect(actionHandler).toContain("action === 'create-patient'");
    expect(actionHandler).toContain('/create-patient');
    expect(actionHandler).toContain('patient: {');
    expect(managerSource).toContain("'request-more-info'");
    expect(managerSource).toContain("'reject'");
    expect(actionHandler).not.toContain('/telegram/mini-app/appointments');
    expect(actionHandler).not.toMatch(/entryToken|raw|payment|invoice|diagnosis|lab|emr/i);
  });

  it('renders a safe staff inbox instead of exposing Telegram token details', () => {
    const reviewPanel = sourceBetween(
      managerSource,
      'REQUEST_REVIEW patient requests',
      '<Dialog open={showTemplateDialog}'
    );

    expect(reviewPanel).toContain('Unknown Telegram users can submit only an onboarding request');
    expect(reviewPanel).toContain('Existing patient ID');
    expect(reviewPanel).toContain('Last name');
    expect(reviewPanel).toContain('First name');
    expect(reviewPanel).toContain('Create patient');
    expect(reviewPanel).toContain('Patient-facing safe message');
    expect(reviewPanel).not.toMatch(/entryToken|telegramUserId|telegramChatId|raw API|stack trace/i);
  });
});
