// The PRs view's feed as an XState v6 machine (proof of concept): what to read and when, with no
// DOM, no store and no clock of its own. The adapter in prs-feed.js sends it the page's facts
// (`shown`, `hidden`, `links`) and writes what it emits (`prs`) in the store.
//
//   reading --done/error--> waiting --10 s after the read, visible, a PR not done--> reading
//                           waiting --shown, a PR not done---------> reading
//                           waiting --links not asked yet, visible-> reading
//
// A read runs alone: an event that asks for one while reading waits for the read's end, where
// `always` reads again when the links moved meanwhile. Leaving the view stops the actor: the
// answer of a read still in flight is dropped, and no timer outlives the view.
import { createAsyncLogic, setup } from '../vendor/xstate.js';

export const EVERY_MS = 10000;

const same = (a, b) => a.length === b.length && a.every((link, i) => link === b[i]);

// The answer to show after a read that failed: the last one, with the error.
// With no good read yet, `unread` says the page knows no state at all.
export const failed = (last, error) => ({
  rows: [],
  unread: !last,
  ...last,
  error: error.message,
  failed: true,
});

const due = (context) => context.visible && !context.prs?.all_done;
const read = (context) => ({ target: 'reading', context: { ...context, asked: context.links } });

export const feedMachine = setup({
  actors: {
    // Replaced by the adapter and the tests: `{ project, signal }` in, the PRs answer out.
    readPrs: createAsyncLogic({
      run: async () => {
        throw new Error('readPrs is not provided');
      },
    }),
  },
}).createMachine({
  id: 'prsFeed',
  context: ({ input }) => ({
    project: input.project,
    visible: input.visible,
    links: input.links,
    asked: input.links,
    prs: input.prs ?? null,
  }),
  initial: 'reading',
  on: {
    hidden: ({ context }) => ({ context: { ...context, visible: false } }),
    shown: ({ context }) => ({ context: { ...context, visible: true } }),
    links: ({ context, event }) => ({ context: { ...context, links: event.links } }),
  },
  states: {
    reading: {
      invoke: {
        src: 'readPrs',
        input: ({ context }) => ({ project: context.project }),
        onDone: ({ context, event }, enq) => {
          enq.emit({ type: 'prs', prs: event.output });
          return { target: 'waiting', context: { ...context, prs: event.output } };
        },
        onError: ({ context, event }, enq) => {
          const prs = failed(context.prs, event.error);
          enq.emit({ type: 'prs', prs });
          return { target: 'waiting', context: { ...context, prs } };
        },
      },
    },
    waiting: {
      // A CR got a PR the last read did not ask for: read now, the page is no longer all done.
      always: ({ context }) => {
        if (context.visible && !same(context.asked, context.links)) return read(context);
      },
      // Nothing due at the tick: no new timer, since only `shown` and `links` can make a read due
      // again, and both read at once.
      after: {
        [EVERY_MS]: ({ context }) => {
          if (due(context)) return read(context);
        },
      },
      on: {
        // The page comes back to the front: read again only while a PR is not done.
        shown: ({ context }) => {
          const now = { ...context, visible: true };
          if (due(now)) return read(now);
          return { context: now };
        },
      },
    },
  },
});
