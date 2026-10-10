import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { createServer } from 'node:http';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const fixturePort = Number(process.env.PUBLIC_SITE_FIXTURE_PORT || 5279);
const appPort = Number(process.env.PUBLIC_SITE_SSR_PORT || 5278);
const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const allowedLocales = new Set(['ru', 'uz-Latn']);

const services = {
  ru: [{
    slug: 'synthetic-service',
    name: 'Синтетическая тестовая услуга',
    description: 'Синтетические данные для проверки сайта; это не предложение медицинской услуги.',
    price: null,
    currency: null,
    category: 'Тестовая категория',
  }],
  'uz-Latn': [{
    slug: 'synthetic-service',
    name: 'Sintetik sinov xizmati',
    description: 'Saytni tekshirish uchun sintetik ma’lumot; bu tibbiy xizmat taklifi emas.',
    price: null,
    currency: null,
    category: 'Sinov toifasi',
  }],
};

const doctors = {
  ru: [{
    slug: 'synthetic-profile',
    name: 'Синтетический тестовый профиль',
    bio: 'Синтетические данные; это не реальный врач.',
    specialty: 'Тестовая специализация',
  }],
  'uz-Latn': [{
    slug: 'synthetic-profile',
    name: 'Sintetik sinov profili',
    bio: 'Sintetik ma’lumot; bu haqiqiy shifokor emas.',
    specialty: 'Sinov mutaxassisligi',
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
  if (pathname === '/services/synthetic-service') {
    sendJson(response, 200, services[locale][0]);
    return;
  }
  if (pathname.startsWith('/services/')) {
    sendJson(response, 404, { detail: { code: 'public_content_not_found' } });
    return;
  }
  if (pathname === '/doctors') {
    sendJson(response, 200, doctors[locale]);
    return;
  }
  if (pathname === '/doctors/synthetic-profile') {
    sendJson(response, 200, doctors[locale][0]);
    return;
  }
  if (pathname.startsWith('/doctors/')) {
    sendJson(response, 404, { detail: { code: 'public_content_not_found' } });
    return;
  }
  if (pathname === '/categories') {
    sendJson(response, 200, [{ name: services[locale][0].category }]);
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

  const functionEntrypoint = path.join(repositoryRoot, '.vercel', 'output', 'functions', 'index.func', 'index.mjs');
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
  try {
    runtime = (await import(pathToFileURL(functionEntrypoint).href)).default;
  } catch (error) {
    process.stderr.write('Could not load the built Vercel function: ' + error.message + '\n');
    fixtureServer.close();
    process.exit(1);
  }

  const appServer = createServer(async (incoming, outgoing) => {
    try {
      const headers = new Headers();
      for (const [name, value] of Object.entries(incoming.headers)) {
        if (value) headers.set(name, Array.isArray(value) ? value.join(', ') : value);
      }
      const host = headers.get('host') || '127.0.0.1:' + appPort;
      const request = new Request(new URL(incoming.url || '/', 'http://' + host), {
        method: incoming.method || 'GET',
        headers,
      });
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
