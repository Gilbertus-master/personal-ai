export const i18nConfig = {
  defaultLocale: 'pl',
  locales: ['pl', 'en'],
} as const;

export type Locale = (typeof i18nConfig.locales)[number];

export { default as getRequestConfig } from './request';
