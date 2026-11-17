// Rebuild the board's vendored XState: one minified ES module, with its MIT notice on top and its
// only link to another origin turned into the package's own bundled docs (the board's frame names
// no other origin). Run from poc-xstate/ after `npm ci`: `node vendor.mjs`.
import { readFileSync, writeFileSync } from 'node:fs';
import { buildSync } from 'esbuild';

const OUT = '../skills/chantier/scripts/cli/src/chantier/board/web/js/vendor/xstate.js';
const ERRORS = 'https://github.com/statelyai/xstate/blob/next/docs/errors.md';
const version = JSON.parse(readFileSync('node_modules/xstate/package.json', 'utf8')).version;

const built = buildSync({
  stdin: {
    contents:
      "export { createActor, createAsyncLogic, setup, SimulatedClock } from 'xstate';",
    resolveDir: '.',
  },
  bundle: true,
  format: 'esm',
  minify: true,
  write: false,
  legalComments: 'none',
});
const code = built.outputFiles[0].text;
if (!code.includes(ERRORS)) throw new Error('the errors link moved: check the bundle by hand');
const license = readFileSync('node_modules/xstate/LICENSE', 'utf8').trim();
const head = `/*! xstate ${version}, bundled for chantier's board by poc-xstate/vendor.mjs\n${license}\n*/\n`;
writeFileSync(OUT, head + code.replaceAll(ERRORS, 'node_modules/xstate/docs/errors.md'));
console.log(`vendored xstate ${version}: ${(head.length + code.length) / 1000} kB`);
