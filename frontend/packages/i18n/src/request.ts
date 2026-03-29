import { getRequestConfig } from 'next-intl/server';
import { i18nConfig } from './index';

export default getRequestConfig(async ({ requestLocale }) => {
  const locale = (await requestLocale) ?? i18nConfig.defaultLocale;
  const validLocale = i18nConfig.locales.includes(locale as typeof i18nConfig.locales[number])
    ? locale
    : i18nConfig.defaultLocale;

  return {
    locale: validLocale,
    messages: (await import(`../messages/${validLocale}.json`)).default,
  };
});
