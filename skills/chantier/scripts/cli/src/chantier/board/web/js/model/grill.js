// Where an intake item stands in the grill, from the record's `grill` field. Pure.
import { t } from './words.js';

// The record's names, folded into the four the page shows. A CR being specified counts as in grill.
const STAGE = {
  raw: 'raw',
  grill: 'grill',
  specifying: 'grill',
  specified: 'spec',
  automatable: 'auto',
};

export const STAGES = ['raw', 'grill', 'spec', 'auto'];

export const stageOf = (item) => STAGE[item?.grill] ?? 'raw';

export const stageWord = (item) => t(`grill.${stageOf(item)}`);

// An item that has been specified, whether or not it is automatable.
export const isSpecified = (item) => ['spec', 'auto'].includes(stageOf(item));

// How many of `items` stand at each stage.
export function tally(items) {
  const out = Object.fromEntries(STAGES.map((s) => [s, 0]));
  for (const item of items) out[stageOf(item)] += 1;
  return out;
}

// The backlog's buckets that hold items: the inbox, the priorities, then the ready column.
export const BUCKETS = ['inbox', 'P1', 'P2', 'P3', 'P4', '3-ready'];

export const itemsOf = (backlog) => BUCKETS.flatMap((b) => backlog?.[b] ?? []);

// Items still to grill: not yet specified.
export const toGrill = (items) => items.filter((item) => !isSpecified(item));
