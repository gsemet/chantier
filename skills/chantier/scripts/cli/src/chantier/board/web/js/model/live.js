// The live costs laid over the recorded ones, so every view shows the same figures. Pure.
// The record keeps the costs of the last `status --refresh`; the board also prices the transcripts
// in memory (`data.live`). When that figure is good, it replaces the recorded spend and the CRs'.

const usable = (live) => Boolean(live) && !live.error && live.spent_usd != null;

// The same data with the live spend, the live cost of each CR and the live time laid over.
export function withLive(data) {
  const live = data?.live;
  if (!data?.batch || !usable(live)) return data;
  const priced = (c) => live.per_cr?.[c.cr]?.usd ?? c.cost_usd;
  const crs = data.batch.crs.map((c) => ({ ...c, cost_usd: priced(c) }));
  return {
    ...data,
    batch: {
      ...data.batch,
      spent_usd: live.spent_usd,
      cost_at: live.at ?? data.batch.cost_at,
      crs,
    },
  };
}
