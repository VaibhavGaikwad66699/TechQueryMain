// Keep aligned with backend/app/core/scope.py; API validation is authoritative.
export const SUPPORTED_LANGUAGES = ['C', 'C++', 'Java', 'Python'] as const;
export const LANGUAGE_FILTERS = ['All', ...SUPPORTED_LANGUAGES];
export const languageLabel = (value: string) => value === 'All' ? 'All my subjects' : value;
export const isSupportedLanguage = (value: string) => SUPPORTED_LANGUAGES.some(language => language === value);
export const languageFilter = (value: string) => value || 'All';
