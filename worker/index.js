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
const SECTIONS = new Set(["hero", "run", "ask", "app", "speed", "why", "compare", "tools", "needs", "dl"]);
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

// ---- Feedback: the form on /feedback, emailed to the maker through Resend (https://resend.com) ----
// Secrets (wrangler secret put, never in this public repository): RESEND_API_KEY, FEEDBACK_TO (the address that gets
// the mail); optional FEEDBACK_FROM (a sender on a domain verified in Resend; default Resend's test sender, which can
// only write to the Resend account's own address) and TURNSTILE_SECRET (Cloudflare Turnstile, checked when set).
// Nothing is stored: only a count per kind goes to EVENTS. A filled trap field or a form sent within 3 s of opening
// is a bot: it gets "ok" and nothing is sent.
const KINDS = new Set(["problem", "idea", "question", "other"]);
const EMAIL = /^[^\s@<>(),;:"]{1,64}@[^\s@<>(),;:"]{1,190}\.[A-Za-z]{2,24}$/;

function json(body, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json; charset=utf-8" } });
}

function clean(value, max) {  // one line or a text, with control characters (but not new lines and tabs) taken out
  return typeof value === "string" ? value.replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, "").trim().slice(0, max) : "";
}

async function feedback(request, env, url) {
  if (request.headers.get("Origin") !== url.origin) return json({ error: "Send it from the feedback page." }, 403);
  const text = await request.text();
  if (text.length > 12000) return json({ error: "That message is too long." }, 413);
  let f;
  try {
    f = JSON.parse(text);
  } catch {
    return json({ error: "The message was not readable. Please try again." }, 400);
  }
  if (!f || typeof f !== "object") return json({ error: "The message was not readable. Please try again." }, 400);
  if (clean(f.website, 200) || !(Number(f.ms) >= 3000)) return json({ ok: true });  // a bot: answer as if sent
  const kind = KINDS.has(f.kind) ? f.kind : "other";
  const message = clean(f.message, 5000), version = clean(f.version, 40).replace(/\s+/g, " ");
  const mac = clean(f.mac, 80).replace(/\s+/g, " "), email = clean(f.email, 200);
  if (message.length < 10) return json({ error: "Please write a little more (at least 10 characters)." }, 400);
  if (email && !EMAIL.test(email)) return json({ error: "That email address does not look right. Fix it, or leave it empty." }, 400);
  if (!env.RESEND_API_KEY || !env.FEEDBACK_TO) return json({ error: "Feedback is not set up yet. Please try again later." }, 503);
  if (env.TURNSTILE_SECRET) {
    const check = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", { method: "POST",
      body: new URLSearchParams({ secret: env.TURNSTILE_SECRET, response: clean(f["cf-turnstile-response"], 2048) }) })
      .then((r) => r.json()).catch(() => ({}));
    if (!check.success) return json({ error: "The spam check did not pass. Please reload the page and try again." }, 400);
  }
  const country = request.cf?.country || "";
  const lines = [message, "", "—", `Kind: ${kind}`, `AI-OS: ${version || "not given"}`, `Mac: ${mac || "not given"}`,
    `Reply to: ${email || "not given"}`, `Country: ${country || "unknown"}`, `Sent: ${new Date().toISOString()}`];
  const first = message.split("\n")[0].slice(0, 60);
  const sent = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${env.RESEND_API_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      from: env.FEEDBACK_FROM || "AI-OS feedback <onboarding@resend.dev>",
      to: [env.FEEDBACK_TO],
      ...(email ? { reply_to: email } : {}),
      subject: `AI-OS ${kind}: ${first}`,
      text: lines.join("\n"),
    }),
  }).catch(() => null);
  if (!sent || !sent.ok) {
    console.log("feedback: Resend answered", sent ? sent.status : "nothing");  // the status only, never the message
    return json({ error: "The message was not sent. Please try again in a minute." }, 502);
  }
  record(env, "feedback", [kind, country]);
  return json({ ok: true });
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
    if (pathname === "/feedback" && request.method === "POST") return finish(await feedback(request, env, url), pathname);
    if (pathname === "/releases") return finish(Response.redirect(RELEASES, 302), pathname);
    const asset = await env.ASSETS.fetch(request);
    return finish(MEDIA.test(pathname) ? await ranged(request, asset) : asset, pathname);
  },
};
