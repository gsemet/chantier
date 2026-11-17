// A typed twin of prs-feed-machine.js, to grade XState v6's type safety (not shipped).
import { createActor, createAsyncLogic, setup, types } from 'xstate';

type Prs = { rows: { pr: string }[]; all_done?: boolean; error?: string; failed?: boolean; unread?: boolean };
type Ctx = { project: string; visible: boolean; links: string[]; asked: string[]; prs: Prs | null };

const readPrs = createAsyncLogic({ run: async ({ input }: { input: { project: string } }): Promise<Prs> => ({ rows: [] }) });

const s = setup({
  schemas: {
    context: types<Ctx>(),
    input: types<{ project: string; visible: boolean; links: string[]; prs?: Prs | null }>(),
    events: {
      hidden: types<{}>(),
      shown: types<{}>(),
      links: types<{ links: string[] }>(),
    },
    emitted: { prs: types<{ prs: Prs }>() },
  },
  actors: { readPrs },
});

export const m = s.createMachine({
  context: ({ input }) => ({ project: input.project, visible: input.visible, links: input.links, asked: input.links, prs: input.prs ?? null }),
  initial: 'reading',
  on: {
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
      },
    },
    waiting: {
      after: { 10000: ({ context }) => (context.visible ? { target: 'reading' } : undefined) },
    },
  },
});

createActor(m, { input: { project: 'p', visible: true, links: [] } }).start();
