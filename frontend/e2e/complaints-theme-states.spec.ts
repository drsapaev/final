import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { expect, test, type Locator } from '@playwright/test';

// Match main.tsx and the EMR section styles. Include theme.css's relative import
// explicitly because the synthetic document has no stylesheet URL to resolve it.
const stylesheets = [
  '../src/styles/emr-tokens.css',
  '../src/styles/theme.css',
  '../src/styles/dark-theme-visibility-fix.css',
  '../src/styles/global-fixes.css',
  '../src/design-system/tokens.css',
  '../src/styles/macos.css',
  '../src/components/admin/admin.css',
  '../src/components/emr-v2/sections/EMRSection.css',
  '../src/components/emr-v2/sections/ComplaintsField.css',
].map((path) => readFileSync(fileURLToPath(new URL(path, import.meta.url)), 'utf8'));

function getPlaceholderContrast(field: Locator) {
  return field.evaluate((element) => {
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = 1;
    const context = canvas.getContext('2d');
    if (!context) throw new Error('Canvas is required to resolve computed colors');

    context.fillStyle = getComputedStyle(element).backgroundColor;
    context.fillRect(0, 0, 1, 1);
    const background = context.getImageData(0, 0, 1, 1).data;
    if (background[3] !== 255) throw new Error('Expected an opaque textarea background');

    const placeholder = getComputedStyle(element, '::placeholder');
    context.fillStyle = placeholder.color;
    context.globalAlpha = Number(placeholder.opacity);
    context.fillRect(0, 0, 1, 1);
    const text = context.getImageData(0, 0, 1, 1).data;
    const luminance = (color: Uint8ClampedArray) => [0, 1, 2]
      .map((index) => color[index] / 255)
      .map((channel) => channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4)
      .reduce((sum, channel, index) => sum + channel * [0.2126, 0.7152, 0.0722][index], 0);
    const first = luminance(text);
    const second = luminance(background);
    return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05);
  });
}

for (const theme of ['light', 'dark'] as const) {
  test(`complaints focus and error states follow the ${theme} application theme`, async ({ page }) => {
    const snapshots = [];
    for (const osTheme of ['light', 'dark'] as const) {
      await page.emulateMedia({ colorScheme: osTheme, reducedMotion: 'reduce' });
      await page.setContent(`<!doctype html><html><head></head><body>
        <section class="emr-section">
          <div class="emr-section__body emr-section__body--open">
            <div class="emr-section__body-inner">
              <div class="emr-section__content">
                <div class="complaints-wrapper">
                  <label for="complaints" class="complaints-label">SYNTHETIC field</label>
                  <div class="complaints-container">
                    <textarea id="complaints" class="complaints-field" placeholder="SYNTHETIC placeholder" rows="3"></textarea>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
      </body></html>`);
      await page.evaluate((selectedTheme) => {
        for (const element of [document.documentElement, document.body]) {
          element.dataset.theme = selectedTheme;
          element.dataset.colorScheme = selectedTheme;
          element.classList.add(`${selectedTheme}-theme`, `theme-${selectedTheme}`, `scheme-${selectedTheme}`, `color-scheme-${selectedTheme}`);
          element.style.colorScheme = selectedTheme;
        }
      }, theme);
      for (const content of stylesheets) {
        await page.addStyleTag({ content });
      }

      const field = page.getByRole('textbox', { name: 'SYNTHETIC field' });
      const colors = await field.evaluate((element) => {
        const probe = document.createElement('span');
        element.parentElement!.appendChild(probe);
        const resolve = (value: string) => {
          probe.style.color = value;
          return getComputedStyle(probe).color;
        };
        const result = {
          background: resolve('var(--mac-background)'),
          text: resolve('var(--mac-text-primary)'),
          border: resolve('var(--mac-border)'),
          focus: resolve('var(--mac-accent-blue)'),
          error: resolve('var(--mac-error)'),
          readonly: resolve('var(--mac-background-tertiary)'),
        };
        probe.remove();
        return result;
      });

      await expect(field).toHaveCSS('background-color', colors.background);
      await expect(field).toHaveCSS('color', colors.text);
      await expect(field).toHaveCSS('border-top-color', colors.border);
      await expect(field).toHaveValue('');
      await expect(field).not.toBeFocused();
      expect(await getPlaceholderContrast(field), `placeholder before focus with ${theme} app and ${osTheme} OS`)
        .toBeGreaterThanOrEqual(4.5);
      await field.focus();
      await expect(field).toBeFocused();
      await expect(field).toHaveCSS('border-top-color', colors.focus);
      // The rendered color is intentional: this pins the visible focus ring.
      // eslint-disable-next-line custom/no-hardcoded-colors
      await expect(field).toHaveCSS('box-shadow', 'rgba(0, 122, 255, 0.15) 0px 0px 0px 3px');
      expect(await getPlaceholderContrast(field), `placeholder on focus with ${theme} app and ${osTheme} OS`)
        .toBeGreaterThanOrEqual(4.5);

      await field.blur();
      await field.evaluate((element) => element.classList.add('complaints-field--error'));
      await expect(field).toHaveCSS('border-top-color', colors.error);
      await expect(field).toHaveCSS('color', colors.text);
      // eslint-disable-next-line custom/no-hardcoded-colors
      await expect(field).toHaveCSS('background-color', 'rgba(255, 59, 48, 0.03)');
      await expect(field).toHaveCSS('box-shadow', 'none');

      await field.focus();
      await field.evaluate((element) => element.classList.add('complaints-field--focused'));
      await expect(field).toHaveCSS('border-top-color', colors.error);
      // eslint-disable-next-line custom/no-hardcoded-colors
      await expect(field).toHaveCSS('box-shadow', 'rgba(255, 59, 48, 0.15) 0px 0px 0px 3px');
      await field.blur();
      await field.evaluate((element) => element.classList.remove('complaints-field--focused'));
      await expect(field).toHaveCSS('border-top-color', colors.error);
      await expect(field).toHaveCSS('box-shadow', 'none');

      await field.evaluate((element) => {
        element.classList.remove('complaints-field--error');
        element.classList.add('complaints-field--focused');
      });
      await expect(field).toHaveCSS('border-top-color', colors.focus);
      await field.evaluate((element) => {
        // A render disabling the field can still carry its previous focus state.
        element.classList.add('complaints-field--readonly');
        element.setAttribute('disabled', '');
      });
      await expect(field).toBeDisabled();
      await expect(field).toHaveCSS('background-color', colors.readonly);
      await field.focus();
      await expect(field).not.toBeFocused();
      await expect(field).toHaveCSS('border-top-color', colors.border);
      await expect(field).toHaveCSS('box-shadow', 'none');
      snapshots.push(colors);
    }
    expect(snapshots[0]).toEqual(snapshots[1]);
  });
}
