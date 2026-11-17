// The Costs receipt: the batch's cost as a supermarket ticket (lines, a cut, the total, the per-CR
// detail, a barcode). Built from the plain object of `model/receipt.js`. The cut line and the
// barcode are CSS only.
import { html, vars } from '../core/dom.js';
import { title } from '../core/format.js';
import { driverName, money, steeringName } from '../model/receipt.js';
import { t, tn } from '../model/words.js';

const SHADE = { steering: 'd1', drivers: 'd2', workers: 'd3', agents: 'd3' };

// "Nov 16, 19:45", in the device's local time; empty when unknown.
function when(iso) {
  const at = new Date(iso ?? '');
  if (Number.isNaN(at.getTime())) return '';
  return at.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

// "10 h 56 min" from minutes; "—" when the length is unknown.
export function lasted(minutes) {
  if (minutes == null) return '—';
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (!hours) return t('time.min', { n: rest });
  return rest
    ? `${t('time.h', { n: hours })} ${t('time.min', { n: rest })}`
    : t('time.h', { n: hours });
}

function head(r) {
  const pill = `${t(`costs.receipt_state_${r.stateName}`)} · ${t('costs.receipt_merged', { n: r.merged, total: r.crs.length })}`;
  return html`<div class="r-head"><div><div class="eyebrow">${t('costs.receipt_eyebrow', { project: r.project })}</div><div class="brand">${r.id}</div><span class="pill">${pill}</span></div><div class="meta">${r.mode}, ${r.steering}${dates(r)}</div></div>`;
}

// The dates and length lines of the head; an old record with no dates shows neither.
function dates(r) {
  const start = when(r.opened);
  const end = r.stateName === 'closed' ? when(r.closed) : t('costs.receipt_now');
  const span = start || end ? html`<br />${start || '—'} → ${end || '—'}` : '';
  return html`${span}${r.minutes == null ? '' : html`<br />${lasted(r.minutes)}`}`;
}

const recompute = (r) =>
  html`<button class="btn${r.computing ? '' : ' pri'}" type="button" data-recompute data-key="recompute-receipt" ${r.computing ? 'disabled' : ''}>${r.computing ? t('costs.recomputing') : t('costs.recompute')}</button>`;

// What a group shows when there is nothing to print: "roles not recorded", "not computed yet" or
// the live error.
const muted = (r) =>
  html`<div class="ln mut"><div>${r.figures === 'unrecorded' ? t('costs.receipt_unrecorded') : (r.note ?? t('costs.receipt_pending'))}</div></div>`;

const group = (shade, word, lines) =>
  html`<div class="r-grp"><h3><i class="d ${shade}"></i>${word}</h3>${lines}</div>`;

function steeringLine(r) {
  const s = r.receipt.steering;
  const wakes = s.wakes
    ? html`<small>${t('costs.receipt_wakes', { n: s.wakes.toLocaleString('en-US'), m: (s.context_avg ?? 0).toLocaleString('en-US') })}</small>`
    : '';
  return html`<div class="ln"><div>${steeringName(s.label)}${wakes}</div><span class="amt">${money(s.usd, s.unpriced)}</span></div>`;
}

const driverLine = (d) =>
  html`<div class="ln"><div>${driverName(d.type)}<small>${t('costs.receipt_calls', { n: d.calls.toLocaleString('en-US') })}</small></div><span class="amt">${money(d.usd, d.unpriced)}</span></div>`;

function groups(r) {
  if (r.figures !== 'figures') {
    if (r.figures === 'unrecorded') return html`<div class="r-grp">${muted(r)}</div>`;
    return html`${group('d1', t('costs.receipt_steering'), muted(r))}${group('d2', t('costs.receipt_drivers'), muted(r))}`;
  }
  const drivers = r.receipt.drivers;
  return html`${group('d1', t('costs.receipt_steering'), steeringLine(r))}${drivers.length ? group('d2', t('costs.receipt_drivers'), drivers.map(driverLine)) : ''}`;
}

// The parts of the split to draw: when agents are not told apart, they stand in place of the
// Drivers and the workers.
function parts(split) {
  const agents = split.some((p) => p.part === 'agents');
  return split.filter((p) => !agents || !['drivers', 'workers'].includes(p.part));
}

function split(r) {
  if (r.figures === 'unrecorded') return ''; // groups() already shows the one muted line
  if (r.figures !== 'figures') {
    return html`<div class="split">${muted(r)}${r.figures === 'pending' ? html`<div class="r-act">${recompute(r)}</div>` : ''}</div>`;
  }
  const shown = parts(r.receipt.split);
  const bars = shown.map(
    (p) =>
      html`<i class="${SHADE[p.part]}" data-vars="${vars({ '--w': String(Math.max(p.usd, 0)) })}"></i>`,
  );
  const legend = shown.map(
    (p) =>
      html`<span>${t(`costs.receipt_part_${p.part}`)} <b>${money(p.usd, p.unpriced)}</b></span>`,
  );
  return html`<div class="split"><div class="sbar">${bars}</div><div class="slg">${legend}</div></div>`;
}

function budgetCell(r) {
  const used = r.used == null ? '' : html` · ${t('costs.used', { n: r.used })}`;
  return html`<span>${t('costs.receipt_budget')} <b>${r.budget ? money(r.budget) : t('costs.receipt_none')}</b>${r.budget ? used : ''}</span>`;
}

// The two lines of the Outside-the-budget cell and the calls beside them.
function outsideCells(r) {
  const o = r.outside;
  const amount =
    o.kind === 'value'
      ? money(o.usd, o.unpriced)
      : o.kind === 'unknown'
        ? t('costs.receipt_unknown')
        : '—';
  const lines =
    o.kind === 'value'
      ? [
          [t('costs.receipt_grill'), o.out.grill],
          ...(o.out.steering ? [[t('costs.receipt_chief_steer'), o.out.steering]] : []),
        ]
      : [];
  const named = lines.map(([word, p]) => html`<small>${word} ${money(p.usd, p.unpriced)}</small>`);
  const calls = lines.map(
    ([, p]) =>
      html`<small>${t('costs.receipt_calls', { n: p.calls.toLocaleString('en-US') })}</small>`,
  );
  return html`<span>${t('costs.receipt_outside')} <b>${amount}</b>${named}</span><span class="calls">${calls}</span>`;
}

function foot(r) {
  const avg = r.avg == null ? '—' : money(r.avg);
  return html`<div class="tfoot">${budgetCell(r)}<span>${t('costs.receipt_avg')} <b>${avg}</b></span>${outsideCells(r)}</div>`;
}

function restLine(r) {
  if (r.total == null || r.rest.usd <= 0.005) return '';
  const { usd: amount, kind, steer, other } = r.rest;
  const text = t(`costs.receipt_rest_${kind}`, {
    x: money(amount, r.unpriced),
    a: money(steer),
    b: money(other),
  });
  return html`<p class="rest">${text}</p>`;
}

function detail(r) {
  const lines = r.crs.map(
    (c) =>
      html`<div class="r-cr"><b>${c.cr}</b><span class="t">${title(c.title)}</span><span class="amt">${money(c.usd, c.unpriced)}</span></div>`,
  );
  return html`<div class="rule" aria-hidden="true"></div><div class="eyebrow">${t('costs.receipt_detail')}</div><div class="r-crs">${lines}</div><div class="sum"><span>${t('costs.receipt_sum')}</span><b>${money(r.sum)}</b></div>${restLine(r)}`;
}

export function receipt(r) {
  return html`<section class="ticket" aria-label="${t('costs.receipt_label', { batch: r.id })}">${head(r)}${groups(r)}${split(r)}<div class="cut" aria-hidden="true"></div><div class="total"><span class="label">${t('costs.receipt_total')}</span><span class="big">${money(r.total, r.unpriced)}</span></div>${foot(r)}${detail(r)}<div class="code" aria-hidden="true"></div><div class="thanks">${tn('costs.receipt_thanks', r.prs)}</div></section>`;
}
