import es from '../locales/es.json';

type Locale = 'es';
const translations = { es };

export function t(key: string, locale: Locale = 'es') {
  const keys = key.split('.');
  let result: any = translations[locale];
  
  for (const k of keys) {
    result = result?.[k];
  }
  
  return result || key;
}