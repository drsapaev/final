import { Buffer } from 'node:buffer';
import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { createServer } from 'node:http';
import path from 'node:path';
import process from 'node:process';
import { URL, fileURLToPath, pathToFileURL } from 'node:url';

const fixturePort = Number(process.env.PUBLIC_SITE_FIXTURE_PORT || 5279);
const appPort = Number(process.env.PUBLIC_SITE_SSR_PORT || 5278);
const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const allowedLocales = new Set(['ru', 'uz-Latn']);
const catalogFilterFile = 'public-site-catalog-filter.js';

const serviceFields = {
  ru: {
    description: 'Синтетические данные для проверки сайта; это не предложение медицинской услуги.',
    price: null,
    currency: null,
  },
  'uz-Latn': {
    description: 'Saytni tekshirish uchun sintetik ma’lumot; bu tibbiy xizmat taklifi emas.',
    price: null,
    currency: null,
  },
};
const doctorFields = {
  ru: { bio: 'Синтетические данные; это не реальный врач.' },
  'uz-Latn': { bio: 'Sintetik ma’lumot; bu haqiqiy shifokor emas.' },
};

/** @type {Record<'ru' | 'uz-Latn', import('../../src/publicSiteApi').PublicSiteService[]>} */
const services = {
  ru: [{
    ...serviceFields.ru,
    slug: 'synthetic-service',
    name: 'Синтетическая тестовая услуга',
    category: 'Тестовая категория',
  }, {
    ...serviceFields.ru,
    slug: 'synthetic-service-match',
    name: 'Синтетическая услуга Ёлка',
    category: 'Тестовая категория',
  }, {
    ...serviceFields.ru,
    slug: 'synthetic-service-other',
    name: 'Другая синтетическая услуга Ёлка',
    category: 'Другая тестовая категория',
  }, {
    ...serviceFields.ru,
    slug: 'synthetic-service-no-category',
    name: 'Синтетическая услуга без категории',
  }],
  'uz-Latn': [{
    ...serviceFields['uz-Latn'],
    slug: 'synthetic-service',
    name: 'Sintetik sinov xizmati',
    category: 'Sinov toifasi',
  }, {
    ...serviceFields['uz-Latn'],
    slug: 'synthetic-service-match',
    name: 'Sintetik Oʻrik xizmati',
    category: 'Sinov toifasi',
  }, {
    ...serviceFields['uz-Latn'],
    slug: 'synthetic-service-other',
    name: 'Boshqa sintetik O‘rik xizmati',
    category: 'Boshqa sinov toifasi',
  }, {
    ...serviceFields['uz-Latn'],
    slug: 'synthetic-service-no-category',
    name: 'Toifasi yo‘q sintetik xizmat',
  }],
};

/** @type {Record<'ru' | 'uz-Latn', import('../../src/publicSiteApi').PublicSiteDoctor[]>} */
const doctors = {
  ru: [{
    ...doctorFields.ru,
    slug: 'synthetic-profile',
    name: 'Синтетический тестовый профиль',
    specialty: 'Тестовая специализация',
  }, {
    ...doctorFields.ru,
    slug: 'synthetic-profile-match',
    name: 'Синтетический профиль Ёлка',
    specialty: 'Тестовая специализация',
  }, {
    ...doctorFields.ru,
    slug: 'synthetic-profile-other',
    name: 'Другой синтетический профиль Ёлка',
    specialty: 'Другая тестовая специализация',
  }, {
    ...doctorFields.ru,
    slug: 'synthetic-profile-no-specialty',
    name: 'Синтетический профиль без специализации',
  }],
  'uz-Latn': [{
    ...doctorFields['uz-Latn'],
    slug: 'synthetic-profile',
    name: 'Sintetik sinov profili',
    specialty: 'Sinov mutaxassisligi',
  }, {
    ...doctorFields['uz-Latn'],
    slug: 'synthetic-profile-match',
    name: 'Sintetik Oʻrik profili',
    specialty: 'Sinov mutaxassisligi',
  }, {
    ...doctorFields['uz-Latn'],
    slug: 'synthetic-profile-other',
    name: 'Boshqa sintetik O‘rik profili',
    specialty: 'Boshqa sinov mutaxassisligi',
  }, {
    ...doctorFields['uz-Latn'],
    slug: 'synthetic-profile-no-specialty',
    name: 'Mutaxassisligi yo‘q sintetik profil',
  }],
};

function sendJson(response, status, body) {
  response.writeHead(status, {
    'Cache-Control': 'no-store',
    'Content-Type': 'application/json; charset=utf-8',
  });
  response.end(JSON.stringify(body));
}

function handleFixture(request, response) {
  if (request.method !== 'GET') {
    response.writeHead(405, { Allow: 'GET', 'Cache-Control': 'no-store' });
    response.end();
    return;
  }

  const url = new URL(request.url || '/', 'http://fixture.local');
  const pathname = url.pathname.replace(/^\/api\/v1\/public-site/, '');
  if (pathname === '/clinic') {
    sendJson(response, 200, { name: 'SYNTHETIC QA CLINIC', address: null, phone: null, email: null });
    return;
  }

  const locale = url.searchParams.get('locale');
  if (!allowedLocales.has(locale)) {
    sendJson(response, 422, { detail: 'Unsupported locale' });
    return;
  }

  if (pathname === '/services') {
    sendJson(response, 200, services[locale]);
    return;
  }
  if (pathname.startsWith('/services/')) {
    const service = services[locale].find(({ slug }) => pathname === `/services/${slug}`);
    if (!service) {
      sendJson(response, 404, { detail: { code: 'public_content_not_found' } });
      return;
    }
    const { slug, name } = doctors[locale][0];
    const relatedDoctors = service.slug === 'synthetic-service' ? [{ slug, name }] : [];
    /** @type {import('../../src/publicSiteApi').PublicSiteServiceDetail} */
    const detail = { ...service, related_doctors: relatedDoctors };
    sendJson(response, 200, detail);
    return;
  }
  if (pathname === '/doctors') {
    sendJson(response, 200, doctors[locale]);
    return;
  }
  if (pathname.startsWith('/doctors/')) {
    const doctor = doctors[locale].find(({ slug }) => pathname === `/doctors/${slug}`);
    if (doctor) sendJson(response, 200, doctor);
    else sendJson(response, 404, { detail: { code: 'public_content_not_found' } });
    return;
  }
  if (pathname === '/categories') {
    const categories = new Set(services[locale].map(({ category }) => category).filter(Boolean));
    sendJson(response, 200, Array.from(categories, (name) => ({ name })));
    return;
  }

  sendJson(response, 404, { detail: { code: 'public_content_not_found' } });
}

const fixtureServer = createServer(handleFixture);
await new Promise((resolve, reject) => {
  fixtureServer.once('error', reject);
  fixtureServer.listen(fixturePort, '127.0.0.1', resolve);
});

if (process.env.PUBLIC_SITE_FIXTURE_ONLY === '1') {
  process.stdout.write(`Synthetic public-site API ready on port ${fixturePort}\n`);
} else {
  const repositoryRoot = path.resolve(frontendRoot, '..');
  const viteCli = path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js');
  const safeEnv = {};
  for (const key of ['PATH', 'Path', 'PATHEXT', 'SystemRoot', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'TMPDIR', 'CI']) {
    if (process.env[key]) safeEnv[key] = process.env[key];
  }

  const vercelOutput = path.join(repositoryRoot, '.vercel', 'output');
  const functionEntrypoint = path.join(vercelOutput, 'functions', 'index.func', 'index.mjs');
  const reuseBuild = process.env.PUBLIC_SITE_REUSE_VERIFIED_BUILD === '1' && existsSync(functionEntrypoint);
  if (!reuseBuild) {
    const build = spawnSync(process.execPath, [viteCli, 'build', '--mode', 'ssr'], {
      cwd: frontendRoot,
      env: {
        ...safeEnv,
        NITRO_PRESET: 'vercel',
        VERCEL: '1',
        VERCEL_ENV: 'preview',
        FORCE_COLOR: '0',
      },
      stdio: 'inherit',
    });
    if (build.error || build.status !== 0) {
      process.stderr.write('Could not build the Vercel Nitro SSR function for the browser smoke.\n');
      fixtureServer.close();
      process.exit(1);
    }
  }

  for (const key of Object.keys(process.env)) {
    if (!['PATH', 'Path', 'PATHEXT', 'SystemRoot', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'TMPDIR', 'CI'].includes(key)) {
      delete process.env[key];
    }
  }
  process.env.NITRO_API_ORIGIN = 'http://127.0.0.1:' + fixturePort;
  process.env.VERCEL_ENV = 'preview';

  let runtime;
  let catalogFilterAsset;
  try {
    runtime = (await import(pathToFileURL(functionEntrypoint).href)).default;
    catalogFilterAsset = readFileSync(path.join(vercelOutput, 'static', catalogFilterFile));
  } catch (error) {
    process.stderr.write('Could not load the built Vercel function or catalog asset: ' + error.message + '\n');
    fixtureServer.close();
    process.exit(1);
  }

  const appServer = createServer(async (incoming, outgoing) => {
    try {
      const headers = new globalThis.Headers();
      for (const [name, value] of Object.entries(incoming.headers)) {
        if (value) headers.set(name, Array.isArray(value) ? value.join(', ') : value);
      }
      const host = headers.get('host') || '127.0.0.1:' + appPort;
      const request = new globalThis.Request(new URL(incoming.url || '/', 'http://' + host), {
        method: incoming.method || 'GET',
        headers,
      });
      if (new URL(request.url).pathname === '/' + catalogFilterFile) {
        if (request.method !== 'GET' && request.method !== 'HEAD') {
          outgoing.writeHead(405, { Allow: 'GET, HEAD', 'Cache-Control': 'no-store' });
          outgoing.end();
          return;
        }
        outgoing.writeHead(200, {
          'Cache-Control': 'no-store',
          'Content-Length': catalogFilterAsset.length,
          'Content-Type': 'text/javascript; charset=utf-8',
          'X-Content-Type-Options': 'nosniff',
        });
        outgoing.end(request.method === 'HEAD' ? undefined : catalogFilterAsset);
        return;
      }
      const response = await runtime.fetch(request, {});
      if (!response) {
        outgoing.writeHead(404, { 'Cache-Control': 'no-store' });
        outgoing.end();
        return;
      }
      const body = request.method === 'HEAD' || !response.body
        ? Buffer.alloc(0)
        : Buffer.from(await response.arrayBuffer());
      outgoing.writeHead(response.status, Object.fromEntries(response.headers.entries()));
      outgoing.end(body);
    } catch {
      outgoing.writeHead(500, { 'Cache-Control': 'no-store' });
      outgoing.end('Synthetic SSR runtime error');
    }
  });

  const stop = () => {
    appServer.close();
    fixtureServer.close();
  };
  process.once('SIGINT', () => { stop(); process.exit(130); });
  process.once('SIGTERM', () => { stop(); process.exit(143); });
  appServer.once('error', (error) => {
    process.stderr.write('Could not start the local Vercel function adapter: ' + error.message + '\n');
    stop();
    process.exit(1);
  });
  await new Promise((resolve, reject) => {
    appServer.once('error', reject);
    appServer.listen(appPort, '127.0.0.1', resolve);
  });

  process.stdout.write('Built Vercel Nitro function is serving the synthetic SSR browser smoke on port ' + appPort + '\n');
}
