// The AI-OS site: the static page in ./site, plus /download, which always sends the newest release's zip.
// A new release (release.sh in the AI-OS repository) needs no change here: /download reads latest.json each time
// (cached for 5 minutes) and falls back to the releases page when GitHub does not answer.
const REPO = "https://github.com/vxtien2000/AI-OS-releases";
const LATEST = `${REPO}/releases/latest/download/latest.json`;
const RELEASES = `${REPO}/releases/latest`;
const HEADERS = {  // on every answer
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "X-Frame-Options": "DENY",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
  "Strict-Transport-Security": "max-age=31536000",
};
const LONG_CACHE = /^\/(images\/|og\.png$|favicon\.svg$)/;  // pictures and video change rarely: a day in browsers

async function newestZip() {
  try {
    const r = await fetch(LATEST, { cf: { cacheTtl: 300, cacheEverything: true } });
    if (!r.ok) return null;
    const info = await r.json();
    // only a zip of this repository's releases, never an address taken from elsewhere
    return typeof info.url === "string" && info.url.startsWith(`${REPO}/releases/download/`) ? info.url : null;
  } catch {
    return null;
  }
}

function finish(response, pathname) {
  const r = new Response(response.body, response);
  for (const [k, v] of Object.entries(HEADERS)) r.headers.set(k, v);
  if (r.status === 200 && LONG_CACHE.test(pathname)) r.headers.set("Cache-Control", "public, max-age=86400");
  return r;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.protocol === "http:" && !["localhost", "127.0.0.1"].includes(url.hostname)) {  // https only (not for wrangler dev)
      url.protocol = "https:";
      return Response.redirect(url.toString(), 301);
    }
    const { pathname } = url;
    if (pathname === "/download" || pathname === "/download/") {
      return finish(Response.redirect((await newestZip()) || RELEASES, 302), pathname);
    }
    if (pathname === "/releases") return finish(Response.redirect(RELEASES, 302), pathname);
    return finish(await env.ASSETS.fetch(request), pathname);
  },
};
