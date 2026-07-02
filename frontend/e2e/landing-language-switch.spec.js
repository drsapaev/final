import { expect, test } from '@playwright/test';

const LANGUAGE_STATES = [
  {
    code: 'ru',
    heroTitle: 'Единая система управления клиникой, которая держит EMR, очередь и платежи в одном ритме.',
    modulesTitle: 'Модульная архитектура под реальные направления клиники',
    pricingTitle: 'Три тарифа для малых клиник, растущих команд и сетей',
    primaryCta: 'Открыть демо'
  },
  {
    code: 'uz',
    heroTitle: 'EMR, navbat va tolovlarni bitta ritmda ushlab turadigan yagona klinika boshqaruv tizimi.',
    modulesTitle: 'Klinikaning real yonalishlari uchun modulli arxitektura',
    pricingTitle: 'Kichik klinikalar, osayotgan jamoalar va tarmoqlar uchun uchta tarif',
    primaryCta: 'Demo ochish'
  },
  {
    code: 'en',
    heroTitle: 'One clinic management system that keeps EMR, queue and payments in the same rhythm.',
    modulesTitle: 'A modular architecture for real clinic specialties',
    pricingTitle: 'Three plans for small clinics, growing teams and networks',
    primaryCta: 'Open demo'
  },
  {
    code: 'kk',
    heroTitle: 'EMR, кезек және төлемдерді бір ырғақта ұстайтын клиниканы басқарудың бірыңғай жүйесі.',
    modulesTitle: 'Клиниканың нақты бағыттарына арналған модульдік архитектура',
    pricingTitle: 'Шағын клиникаларға, өсіп жатқан командаларға және желілерге арналған үш тариф',
    primaryCta: 'Демоны ашу'
  }
];

test.describe('Landing language switching', () => {
  test('cycles through ru -> uz -> en -> kk and updates deep sections', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const languageButton = page.locator('.landing-language-button');

    for (const [index, state] of LANGUAGE_STATES.entries()) {
      await expect(page.getByRole('heading', { name: state.heroTitle })).toBeVisible();
      await expect(page.getByRole('heading', { name: state.modulesTitle })).toBeVisible();
      await expect(page.getByRole('heading', { name: state.pricingTitle })).toBeVisible();
      await expect(page.getByRole('button', { name: state.primaryCta })).toBeVisible();

      if (index < LANGUAGE_STATES.length - 1) {
        await languageButton.click();
      }
    }
  });
});
