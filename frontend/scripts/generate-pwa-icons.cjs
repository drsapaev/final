/**
 * Generate PWA icons from the brand logo mark.
 *
 * Usage: node scripts/generate-pwa-icons.cjs
 *
 * Renders frontend/public/brand/logo-mark.svg centered on the manifest
 * background color at 72% of each canvas (inside the maskable safe zone, so
 * the same file serves both "any" and "maskable" purposes) and writes the
 * PNGs referenced by public/manifest.json:
 *   /icons/icon-{72,96,128,144,152,192,384,512}x{...}.png
 *   /icons/{registrar,doctor,cashier}.png (96x96 shortcut icons)
 *
 * Requires: playwright (devDependency) with the chromium browser installed.
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const OUT_DIR = path.join(ROOT, 'public', 'icons');
const SVG_PATH = path.join(ROOT, 'public', 'brand', 'logo-mark.svg');

const BACKGROUND = '#ffffff'; // matches manifest background_color
const MARK_SCALE = 0.72; // maskable safe zone: content within ~80%

const APP_ICONS = [72, 96, 128, 144, 152, 192, 384, 512];
const SHORTCUT_ICONS = [
  { file: 'registrar.png', size: 96 },
  { file: 'doctor.png', size: 96 },
  { file: 'cashier.png', size: 96 },
];

(async () => {
  const svg = fs.readFileSync(SVG_PATH, 'utf8');
  fs.mkdirSync(OUT_DIR, { recursive: true });

  // Prefer the managed chromium; fall back to a system browser when the
  // playwright browser cache is not installed on this machine.
  let browser;
  try {
    browser = await chromium.launch();
  } catch {
    for (const channel of ['msedge', 'chrome']) {
      try {
        browser = await chromium.launch({ channel });
        console.log(`using system browser channel: ${channel}`);
        break;
      } catch {
        // try next channel
      }
    }
  }
  if (!browser) {
    throw new Error(
      'No browser available — run `npx playwright install chromium` first.'
    );
  }
  const page = await browser.newPage();

  async function render(size, outFile) {
    const inner = Math.round(size * MARK_SCALE);
    const sized = svg.replace(
      /<svg\b/,
      `<svg width="${inner}" height="${inner}" `
    );
    const html = `<!doctype html><html><head><style>
        html,body{margin:0;padding:0;width:${size}px;height:${size}px;overflow:hidden}
        body{display:flex;align-items:center;justify-content:center;background:${BACKGROUND}}
      </style></head><body>${sized}</body></html>`;

    await page.setViewportSize({ width: size, height: size });
    await page.setContent(html, { waitUntil: 'load' });
    const out = path.join(OUT_DIR, outFile);
    await page.screenshot({ path: out, clip: { x: 0, y: 0, width: size, height: size } });
    console.log(`wrote ${outFile} (${size}x${size})`);
  }

  for (const size of APP_ICONS) {
    await render(size, `icon-${size}x${size}.png`);
  }
  for (const { file, size } of SHORTCUT_ICONS) {
    await render(size, file);
  }

  await browser.close();
  console.log('done');
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
