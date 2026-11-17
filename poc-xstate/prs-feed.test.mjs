// The PRs feed machine, driven by a simulated clock and reads the test answers by hand.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  EVERY_MS,
  feedMachine,
} from '../skills/chantier/scripts/cli/src/chantier/board/web/js/views/prs-feed-machine.js';
import {
  createActor,
  createAsyncLogic,
  SimulatedClock,
} from '../skills/chantier/scripts/cli/src/chantier/board/web/js/vendor/xstate.js';

const flush = () => new Promise((r) => setTimeout(r, 0));

// A feed whose reads wait for the test: `reads` holds one { resolve, reject } per read asked.
function feed({ visible = true, links = ['pr/1'], prs = null } = {}) {
  const reads = [];
  const readPrs = createAsyncLogic({
    run: ({ input }) =>
      new Promise((resolve, reject) => reads.push({ input, resolve, reject })),
  });
  const clock = new SimulatedClock();
  const actor = createActor(feedMachine.provide({ actors: { readPrs } }), {
    clock,
    input: { project: 'p', visible, links, prs },
  });
  const shown = [];
  actor.on('prs', (e) => shown.push(e.prs));
  actor.start();
  return { actor, clock, reads, shown, state: () => actor.getSnapshot().value };
}

const open = { rows: [{ pr: 'pr/1' }], all_done: false };
const done = { rows: [{ pr: 'pr/1' }], all_done: true };

test('reads at once, then every 10 s while visible and a PR is open', async () => {
  const f = feed();
  assert.equal(f.reads.length, 1);
  assert.deepEqual(f.reads[0].input, { project: 'p' });
  f.reads[0].resolve(open);
  await flush();
  assert.equal(f.state(), 'waiting');
  assert.deepEqual(f.shown, [open]);
  f.clock.increment(EVERY_MS - 1);
  assert.equal(f.reads.length, 1);
  f.clock.increment(1);
  assert.equal(f.reads.length, 2);
  assert.equal(f.state(), 'reading');
});

test('stops when every PR is done, until a CR gets a new PR', async () => {
  const f = feed();
  f.reads[0].resolve(done);
  await flush();
  f.clock.increment(EVERY_MS * 5);
  assert.equal(f.reads.length, 1);
  f.actor.send({ type: 'links', links: ['pr/1', 'pr/2'] });
  assert.equal(f.reads.length, 2);
});

test('hidden: no read on the tick; shown again: one read at once', async () => {
  const f = feed();
  f.reads[0].resolve(open);
  await flush();
  f.actor.send({ type: 'hidden' });
  f.clock.increment(EVERY_MS * 3);
  assert.equal(f.reads.length, 1);
  f.actor.send({ type: 'shown' });
  assert.equal(f.reads.length, 2);
});

test('shown with every PR done reads nothing', async () => {
  const f = feed({ visible: false });
  f.reads[0].resolve(done);
  await flush();
  f.actor.send({ type: 'shown' });
  assert.equal(f.reads.length, 1);
});

test('a failed read keeps the last answer, with the error', async () => {
  const f = feed();
  f.reads[0].resolve(open);
  await flush();
  f.clock.increment(EVERY_MS);
  f.reads[1].reject(new Error('gh: rate limited'));
  await flush();
  assert.deepEqual(f.shown[1], {
    ...open,
    unread: false,
    error: 'gh: rate limited',
    failed: true,
  });
  assert.equal(f.state(), 'waiting');
});

test('a failed first read says the page knows no state', async () => {
  const f = feed();
  f.reads[0].reject(new Error('boom'));
  await flush();
  assert.deepEqual(f.shown, [{ rows: [], unread: true, error: 'boom', failed: true }]);
});

test('links that move during a read are read right after it, once', async () => {
  const f = feed();
  f.actor.send({ type: 'links', links: ['pr/1', 'pr/2'] });
  f.actor.send({ type: 'links', links: ['pr/1', 'pr/2', 'pr/3'] });
  assert.equal(f.reads.length, 1); // one read at a time
  f.reads[0].resolve(open);
  await flush();
  assert.equal(f.reads.length, 2);
  f.reads[1].resolve(open);
  await flush();
  assert.equal(f.reads.length, 2);
});

test('stopped mid-read: the answer is dropped and no timer survives', async () => {
  const f = feed();
  f.actor.stop();
  f.reads[0].resolve(open);
  await flush();
  f.clock.increment(EVERY_MS * 10);
  assert.deepEqual(f.shown, []);
  assert.equal(f.reads.length, 1);
});
