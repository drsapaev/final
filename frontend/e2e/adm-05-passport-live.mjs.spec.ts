import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';

const repoRoot = path.resolve(process.cwd(), '..');
const artifactsDir = path.join(repoRoot, 'output', 'playwright');

if (!fs.existsSync(artifactsDir)) {
  fs.mkdirSync(artifactsDir, { recursive: true });
}

const baseUrl = process.env.QA_BASE_URL || 'http://127.0.0.1:4176';
const apiOrigin = process.env.QA_API_ORIGIN || 'http://127.0.0.1:18006';
const username = process.env.QA_ADMIN_USERNAME || 'admin@example.com';
const password = process.env.QA_ADMIN_PASSWORD;
const suffix = process.env.QA_SUFFIX || String(Date.now()).slice(-8);

if (!password) {
  throw new Error('Set QA_ADMIN_PASSWORD to run ADM-05 live e2e proof.');
}

const patient = {
  lastName: `Админов${suffix.slice(-2)}`,
  firstName: 'Паспорт',
  middleName: 'Проверочный',
  birthDate: '1991-04-15',
  gender: 'male',
  phone: `+998 90 ${suffix.slice(-6, -3)} ${suffix.slice(-3, -1)} ${suffix.slice(-1)}0`,
  email: `qa_admin_patient_${suffix}@clinic.uz`,
  address: `г. Ташкент, QA ADM-05 ${suffix}`,
  passport: `AA${suffix.slice(-7).padStart(7, '0')}`
};

const evidence = {
  caseId: 'ADM-05-FIX',
  baseUrl,
  patient,
  primarySourceOfTruth: null,
  secondarySourceOfTruth: null
};

function artifact(name) {
  return path.join(artifactsDir, name);
}

async function bootstrapSession() {
  const response = await fetch(`${apiOrigin}/api/v1/auth/minimal-login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      username,
      password,
      remember_me: false
    })
  });

  if (!response.ok) {
    throw new Error(`Auth bootstrap failed: ${response.status} ${await response.text()}`);
  }

  const authData = await response.json();
  if (!authData.access_token || !authData.user) {
    throw new Error(`Auth bootstrap returned incomplete payload: ${JSON.stringify(authData)}`);
  }

  return authData;
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1200 }
  });
  const page = await context.newPage();

  let createResponse = null;
  let listResponse = null;

  page.on('response', async (response) => {
    const url = response.url();
    if (/\/api\/v1\/patients\/?$/.test(url) && response.request().method() === 'POST') {
      const body = await response.text().catch(() => '<unreadable>');
      createResponse = { status: response.status(), url, body };
    }
    if (url.includes('/api/v1/patients/?limit=1000') && response.request().method() === 'GET') {
      listResponse = { status: response.status(), url };
    }
  });

  try {
    await page.goto(`${baseUrl}/login`, { waitUntil: 'networkidle' });
    const authBootstrap = await page.evaluate(
      async ({ currentApiOrigin, currentUsername, currentPassword }) => {
        const response = await fetch(`${currentApiOrigin}/api/v1/auth/minimal-login`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            username: currentUsername,
            password: currentPassword,
            remember_me: false
          })
        });

        const data = await response.json();
        if (!response.ok) {
          return { ok: false, status: response.status, data };
        }

        sessionStorage.setItem('auth_token', data.access_token);
        sessionStorage.setItem('user', JSON.stringify(data.user));
        sessionStorage.setItem('auth_profile', JSON.stringify(data.user));
        localStorage.setItem('app_language', 'ru');
        localStorage.setItem('language', 'ru');
        return { ok: true, status: response.status, user: data.user };
      },
      {
        currentApiOrigin: apiOrigin,
        currentUsername: username,
        currentPassword: password
      }
    );

    evidence.authBootstrap = authBootstrap;
    if (!authBootstrap.ok) {
      throw new Error(`Auth bootstrap failed inside page: ${JSON.stringify(authBootstrap)}`);
    }

    await page.goto(`${baseUrl}/admin?section=patients`, { waitUntil: 'networkidle' });

    await page.getByRole('button', { name: 'Добавить пациента' }).first().click();
    const form = page.locator('form').last();

    await form.getByPlaceholder('Иванов', { exact: true }).fill(patient.lastName);
    await form.getByPlaceholder('Иван', { exact: true }).fill(patient.firstName);
    await form.getByPlaceholder('Иванович', { exact: true }).fill(patient.middleName);
    await form.locator('input[type="date"]').first().fill(patient.birthDate);
    await form.locator('select').first().selectOption(patient.gender);
    await form.getByPlaceholder('+998 90 123 45 67', { exact: true }).first().fill(patient.phone);
    await form.getByPlaceholder('ivan@example.com', { exact: true }).fill(patient.email);
    await form.getByPlaceholder('г. Ташкент, ул. Навои, д. 1', { exact: true }).fill(patient.address);
    await form.getByPlaceholder('AA1234567', { exact: true }).fill(patient.passport);

    await page.screenshot({
      path: artifact('adm-05-passport-before-save.png'),
      fullPage: true
    });

    const formValidity = await form.evaluate((formElement) => ({
      isValid: formElement.checkValidity(),
      invalidControls: Array.from(formElement.elements)
        .filter((element) => typeof element.checkValidity === 'function' && !element.checkValidity())
        .map((element) => ({
          tagName: element.tagName,
          type: element.getAttribute('type'),
          name: element.getAttribute('name'),
          placeholder: element.getAttribute('placeholder'),
          validationMessage: element.validationMessage,
          value: element.value
        }))
    }));

    evidence.formValidity = formValidity;
    if (!formValidity.isValid) {
      throw new Error(`Form failed native validity: ${JSON.stringify(formValidity.invalidControls)}`);
    }

    const createResponsePromise = page.waitForResponse(
      (response) =>
        /\/api\/v1\/patients\/?$/.test(response.url()) &&
        response.request().method() === 'POST',
      { timeout: 15000 }
    ).catch(() => null);

    await form.evaluate((formElement) => formElement.requestSubmit());
    const patientCreateResponse = await createResponsePromise;
    await page.waitForLoadState('networkidle');

    if (patientCreateResponse) {
      const body = await patientCreateResponse.text().catch(() => '<unreadable>');
      createResponse = {
        status: patientCreateResponse.status(),
        url: patientCreateResponse.url(),
        body
      };
    }

    const modalStillOpen = await form.isVisible().catch(() => false);
    if (modalStillOpen && !createResponse) {
      const visibleErrors = await page.locator('p').evaluateAll((nodes) =>
        nodes
          .map((node) => node.textContent?.trim())
          .filter((text) => text && text.length > 0)
      );

      throw new Error(`Patient modal stayed open without POST /patients. Visible messages: ${visibleErrors.join(' | ')}`);
    }

    if (createResponse && createResponse.status >= 400) {
      throw new Error(`Patient create failed: ${createResponse.status} ${createResponse.body}`);
    }

    await page.getByPlaceholder('Поиск пациентов...').fill(patient.lastName);
    await page.waitForLoadState('networkidle');
    await page.getByText(`${patient.lastName} ${patient.firstName} ${patient.middleName}`).first().waitFor({ timeout: 15000 });

    await page.screenshot({
      path: artifact('adm-05-passport-after-save.png'),
      fullPage: true
    });

    evidence.primarySourceOfTruth = {
      uiRowVisible: true,
      searchedByLastName: patient.lastName
    };

    const parsedCreate = createResponse ? JSON.parse(createResponse.body) : null;
    evidence.secondarySourceOfTruth = {
      createResponse,
      listResponse,
      createdPatientId: parsedCreate?.id ?? null,
      createdDocType: parsedCreate?.doc_type ?? null,
      createdDocNumber: parsedCreate?.doc_number ?? null
    };

    if (!parsedCreate || parsedCreate.doc_type !== 'passport' || parsedCreate.doc_number !== patient.passport) {
      throw new Error(`Unexpected create response: ${createResponse?.body || 'missing POST /patients response'}`);
    }

    fs.writeFileSync(
      artifact('adm-05-passport-live.json'),
      JSON.stringify(evidence, null, 2),
      'utf8'
    );
  } catch (error) {
    await page.screenshot({
      path: artifact('adm-05-passport-failed.png'),
      fullPage: true
    });

    fs.writeFileSync(
      artifact('adm-05-passport-live-error.json'),
      JSON.stringify(
        {
          ...evidence,
          createResponse,
          listResponse,
          error: error instanceof Error ? error.message : String(error)
        },
        null,
        2
      ),
      'utf8'
    );
    throw error;
  } finally {
    await context.close();
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
