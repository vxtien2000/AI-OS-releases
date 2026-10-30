# AI-OS

End-to-end app testing on iOS simulators and real iPhones, for AI agents (through MCP: Claude Code, Claude Desktop,
Codex, any MCP client) and for QA (a local dashboard and a CLI). Free and open source (MIT).

## Download
**[Download the latest AI-OS for Mac](https://aiosqa.dpdns.org/download)** (or from
[Releases](https://github.com/vxtien2000/AI-OS-releases/releases/latest)), the file
`AI-OS-<version>.zip`. It needs a Mac with Apple silicon and Xcode (setup opens the App Store if Xcode is missing).

1. Open the zip, then open **AI-OS.app**. The first time, macOS stops it because it is not signed by an Apple
   developer: click Done, open System Settings > Privacy & Security, click **Open Anyway**, then Open Anyway again.
2. Click **Set up** and follow the window. macOS asks for your password in its own window when Xcode needs it.
3. When it says AI-OS is ready, open the device page and ask your AI agent to test an app.

After that the app updates itself: it checks once a day, shows what changed, and installs the new version when you
click Update. Each update is signed; the app takes no other.

## What is in this repository
- **Releases:** each version's zip, plus `latest.json` and `latest.json.sig`, which the app reads to update itself.
  They are published from the AI-OS source repository with its `release.sh`.
- **`site/`:** the landing page (static HTML and CSS, with captures of the real app and a recorded test run).
- **`worker/index.js` and `wrangler.jsonc`:** the Cloudflare Worker for https://aiosqa.dpdns.org. It serves `site/`
  (https only, with a not-found page), plus `/download`, which always sends the newest release's zip (it reads
  `latest.json`), and `/releases`.

## Changing the site
Edit `site/`, then push to `main`: Cloudflare deploys it (Workers Builds, connected to this repository). By hand:
`npx wrangler deploy` in this folder. Try it first with `npx wrangler dev` (http://127.0.0.1:8787).
A new release needs no change here: the download buttons point to `/download`.

## Licence
MIT, copyright Bruce Vu.
