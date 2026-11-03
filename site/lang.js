// The site's language, remembered in this browser only (localStorage); nothing is sent anywhere.
// - A translated page (<html data-localized>) notes the language being read; the menu notes a language chosen on purpose.
// - The site's own address (/), opened again after choosing a language in the menu, shows that language.
// - A page that exists only in English (privacy, feedback, not found) sends its way home to the language being read.
// The homes come from tools/i18n/build.py's list of languages (between the markers); do not edit them by hand.
(() => {
  const HOMES = /* i18n:homes */{"en": "/", "vi": "/vi/"}/* /i18n:homes */;
  const READING = 'aios-lang', CHOSEN = 'aios-lang-chosen';
  const get = (k) => { try { return localStorage.getItem(k); } catch { return null; } };
  const put = (k, v) => { try { localStorage.setItem(k, v); } catch {} };
  const root = document.documentElement, localized = root.hasAttribute('data-localized'), here = root.lang;
  const chosen = get(CHOSEN);
  if (localized && location.pathname === '/' && chosen && chosen !== here && HOMES[chosen]) {
    location.replace(HOMES[chosen] + location.search + location.hash);
    return;
  }
  if (localized) put(READING, here);
  document.addEventListener('click', (e) => {
    const a = e.target.closest && e.target.closest('.langs a[hreflang]');
    if (a && HOMES[a.hreflang]) { put(CHOSEN, a.hreflang); put(READING, a.hreflang); }
  });
  const home = !localized && HOMES[get(READING)];
  if (home && home !== '/') {
    const fix = () => document.querySelectorAll('a[href="/"], a[href^="/#"]').forEach((a) => a.setAttribute('href', home + a.getAttribute('href').slice(1)));
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fix); else fix();
  }
})();
