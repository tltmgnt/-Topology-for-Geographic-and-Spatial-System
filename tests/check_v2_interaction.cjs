// Exercise emitted, CSP-authorized interaction code with a minimal DOM.
// This checks handlers and numeric transforms, not browser layout or visual rendering.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto');
const html = fs.readFileSync(process.argv[2], 'utf8');
const source = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const digest = crypto.createHash('sha256').update(source).digest('base64');
assert(html.includes(`sha256-${digest}`));
let viewBox = '0 0 960 500';
const svg = {
  getAttribute: () => viewBox,
  setAttribute: (key, value) => { assert.equal(key, 'viewBox'); viewBox = value; },
  getBoundingClientRect: () => ({width: 960, height: 500}),
  setPointerCapture: () => {}
};
const buttons = {'#in': {}, '#out': {}, '#reset': {}};
vm.runInNewContext(source, {document: {querySelector: s => s === 'svg' ? svg : buttons[s]}});
buttons['#in'].onclick();
assert.equal(viewBox, '96 50 768 400');
buttons['#out'].onclick();
assert.equal(viewBox, '0 0 960 500');
svg.onkeydown({key: 'ArrowRight', preventDefault() {}});
assert.equal(viewBox, '96 0 960 500');
svg.onpointerdown({clientX: 10, clientY: 10, pointerId: 1});
svg.onpointermove({clientX: 30, clientY: 20});
assert.equal(viewBox, '76 -10 960 500');
svg.onpointerup();
buttons['#reset'].onclick();
assert.equal(viewBox, '0 0 960 500');
console.log('Emitted CSP digest, zoom, reset, keyboard pan and pointer pan passed');
