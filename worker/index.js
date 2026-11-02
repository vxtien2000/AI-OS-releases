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

// ---- Measurement: counts only, no cookies, no IP addresses, no visitor ids (Workers Analytics Engine "EVENTS") ----
// download: one row per /download, with the button (?from=hero|footer, else direct), country and referring site.
// view / engage: sent by the page itself (navigator.sendBeacon to /e) when it opens and when it is left: seconds on
// the page, how far it was scrolled, which sections came into view and which tabs were opened. Browsers that ask
// not to be tracked (Global Privacy Control, Do Not Track) send nothing.
const FROM = new Set(["hero", "footer"]);
const SECTIONS = new Set(["hero", "run", "ask", "app", "speed", "tools", "needs", "dl"]);
const TABS = new Set(["setup", "check", "logins"]);

function host(value) {  // only the site name of a referrer, never its path or query
  try {
    return new URL(value).hostname.slice(0, 100);
  } catch {
    return "";
  }
}

function record(env, kind, blobs, doubles = []) {
  try {
    env.EVENTS?.writeDataPoint({ indexes: [kind], blobs, doubles });  // not configured (wrangler dev): nothing
  } catch {}  // measuring must never break the page or the download
}

function picks(list, allowed) {  // known names only, each once, in a fixed order
  return Array.isArray(list) ? [...allowed].filter((x) => list.includes(x)).join(",") : "";
}

async function beacon(request, env, url) {
  if (request.headers.get("Origin") !== url.origin) return new Response(null, { status: 403 });  // browsers send it with every POST
  const text = await request.text();
  if (text.length > 1024) return new Response(null, { status: 413 });
  let e;
  try {
    e = JSON.parse(text);
  } catch {
    return new Response(null, { status: 400 });
  }
  if (!e || typeof e !== "object" || !["view", "engage"].includes(e.k)) return new Response(null, { status: 400 });
  const country = request.cf?.country || "";
  if (e.k === "view") {
    record(env, "view", [host(e.r), country]);
  } else {
    const seconds = Math.min(Math.max(Number(e.s) || 0, 0), 3600);
    const depth = Math.min(Math.max(Number(e.d) || 0, 0), 100);
    record(env, "engage", [picks(e.v, SECTIONS), picks(e.t, TABS), country], [seconds, depth]);
  }
  return new Response(null, { status: 204 });
}

const MEDIA = /\.(mp4|webm)$/;  // Safari plays video only when it can ask for byte ranges (206)

async function ranged(request, response) {
  const m = /^bytes=(\d*)-(\d*)$/.exec(request.headers.get("Range") || "");
  if (request.method !== "GET" || !m || response.status !== 200 || (m[1] === "" && m[2] === "")) return response;
  const body = await response.arrayBuffer();  // the demo videos are under a megabyte
  const size = body.byteLength;
  const start = m[1] === "" ? Math.max(0, size - Number(m[2])) : Number(m[1]);
  const end = m[1] === "" || m[2] === "" ? size - 1 : Math.min(Number(m[2]), size - 1);
  if (start > end || start >= size) {
    return new Response(null, { status: 416, headers: { "Content-Range": `bytes */${size}` } });
  }
  const headers = new Headers(response.headers);
  headers.set("Content-Range", `bytes ${start}-${end}/${size}`);
  headers.set("Content-Length", String(end - start + 1));
  return new Response(body.slice(start, end + 1), { status: 206, headers });
}

function finish(response, pathname) {
  const r = new Response(response.body, response);
  for (const [k, v] of Object.entries(HEADERS)) r.headers.set(k, v);
  if ((r.status === 200 || r.status === 206) && LONG_CACHE.test(pathname)) r.headers.set("Cache-Control", "public, max-age=86400");
  if (MEDIA.test(pathname)) r.headers.set("Accept-Ranges", "bytes");
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
      const from = url.searchParams.get("from");
      record(env, "download", [FROM.has(from) ? from : "direct", request.cf?.country || "",
        host(request.headers.get("Referer") || "")]);
      return finish(Response.redirect((await newestZip()) || RELEASES, 302), pathname);
    }
    if (pathname === "/e") {
      if (request.method !== "POST") return finish(new Response(null, { status: 405, headers: { Allow: "POST" } }), pathname);
      return finish(await beacon(request, env, url), pathname);
    }
    if (pathname === "/releases") return finish(Response.redirect(RELEASES, 302), pathname);
    const asset = await env.ASSETS.fetch(request);
    return finish(MEDIA.test(pathname) ? await ranged(request, asset) : asset, pathname);
  },
};
