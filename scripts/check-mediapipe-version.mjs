// Fails when the MediaPipe WASM runtime the focus engine loads from the CDN is
// not the exact @mediapipe/tasks-vision version installed from package.json.
// A mismatch loads, then breaks face tracking at runtime in the browser.
import { readFileSync } from 'node:fs';

const pkg = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8'));
const lock = JSON.parse(readFileSync(new URL('../package-lock.json', import.meta.url), 'utf8'));
const engine = readFileSync(new URL('../app/lib/focus-detection/focus-engine.ts', import.meta.url), 'utf8');

const declared = pkg.dependencies['@mediapipe/tasks-vision'];
const installed = lock.packages['node_modules/@mediapipe/tasks-vision']?.version;
const pinned = engine.match(/MEDIAPIPE_VERSION = '([^']+)'/)?.[1];

const problems = [];
if (!/^\d+\.\d+\.\d+$/.test(declared ?? '')) {
  problems.push(`package.json should pin an exact @mediapipe/tasks-vision version, found "${declared}"`);
}
if (pinned !== installed) {
  problems.push(`focus-engine.ts loads WASM ${pinned} but package-lock.json installs ${installed}`);
}
if (/tasks-vision@latest/.test(engine)) {
  problems.push('focus-engine.ts still loads the WASM runtime from @latest');
}

if (problems.length) {
  for (const problem of problems) console.error(problem);
  process.exit(1);
}
console.log(`MediaPipe WASM and package both at ${installed}`);
