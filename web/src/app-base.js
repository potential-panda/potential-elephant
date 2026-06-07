// Detects the mount base path at runtime so the app works when served
// at any subpath (e.g. /elephant/ via nginx) without build-time config.
//
// In production, Vite bundles all JS into /assets/*.js. We extract
// everything before /assets/ from the current module's URL.
// In dev the server always runs at root, so we return ''.

function detectAppBase() {
  if (import.meta.env.DEV) return '';
  return new URL(import.meta.url).pathname.replace(/\/assets\/.*$/, '');
}

export const APP_BASE = detectAppBase();
