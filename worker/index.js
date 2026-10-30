// The AI-OS site: the static page in ./site, plus /download, which always sends the newest release's zip.
// A new release (release.sh in the AI-OS repository) needs no change here: /download reads latest.json each time
// (cached for 5 minutes) and falls back to the releases page when GitHub does not answer.
const REPO = "https://github.com/vxtien2000/AI-OS-releases";
const LATEST = `${REPO}/releases/latest/download/latest.json`;
const RELEASES = `${REPO}/releases/latest`;

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

export default {
  async fetch(request, env) {
    const { pathname } = new URL(request.url);
    if (pathname === "/download" || pathname === "/download/") {
      return Response.redirect((await newestZip()) || RELEASES, 302);
    }
    if (pathname === "/releases") return Response.redirect(RELEASES, 302);
    return env.ASSETS.fetch(request);
  },
};
