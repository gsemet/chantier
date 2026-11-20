// The Costs card "Where the money went": one stacked bar from $0 to the budget (a segment per
// model, or per role), the unspent rest hatched, then a row per model or role and, under a rule,
// the Chief of Staff's spend outside the budget. Built from `spendBy` (model/spend-by.js).
//   spendCard(r, state) returns the card's markup; bindSpendBy(root) binds its switch.
import { delegate, html, vars } from '../core/dom.js';
import { usd } from '../core/format.js';
import { update } from '../core/store.js';
import { money } from '../model/receipt.js';
import { spendBy } from '../model/spend-by.js';
import { t, tn } from '../model/words.js';
import { logo } from '../ui/logos.js';

const PERCENT = 100;
const MODES = ['model', 'role'];

// A partly priced figure reads "at least"; `money` takes the map of the models not priced.
const cost = (amount, partial) => money(amount, partial ? { calls: 1 } : {});

function switcher(by) {
  const buttons = MODES.map(
    (mode) =>
      html`<button type="button" data-spend-by="${mode}" data-key="spend-by-${mode}" aria-pressed="${by === mode}">${t(`costs.money_by_${mode}`)}</button>`,
  );
  return html`<div class="seg" role="group" aria-label="${t('costs.money_switch')}">${buttons}</div>`;
}

function axis(s) {
  const end = s.budget
    ? t('costs.money_axis_budget', { x: usd(s.budget) })
    : t('costs.money_axis_spent', { x: usd(s.spent) });
  return html`<div class="sp-axis"><span>${t('costs.money_zero')}</span><span>${end}</span></div>`;
}

function bar(s) {
  const segments = s.segments.map(
    (x) => html`<i data-vars="${vars({ '--g': String(x.usd), '--c': x.color })}"></i>`,
  );
  const rest = s.span - s.spent;
  const hatch =
    !s.over && rest > 0
      ? html`<i class="hatch" data-vars="${vars({ '--g': String(rest) })}"></i>`
      : '';
  const mark = s.over
    ? html`<b class="over" title="${t('costs.money_over_mark')}" data-vars="${vars({ '--at': `${(s.budget / s.span) * PERCENT}%` })}"></b>`
    : '';
  return html`<div class="sp-bar" role="img" aria-label="${s.line}">${segments}${hatch}${mark}</div>`;
}

function turns(n) {
  return html`<span class="sp-n">${n == null ? '' : tn('costs.money_turns', n)}</span>`;
}

function row(x, by) {
  const mark = by === 'model' ? (logo(x.provider) ?? '') : '';
  const version = x.version ? html` <span class="sp-v">${x.version}</span>` : '';
  const amount = x.usd == null ? t('costs.money_not_priced') : cost(x.usd, x.unpriced);
  const id = by === 'model' ? html` title="${x.key}"` : '';
  return html`<div class="sp-row"${id}><i class="sw" data-vars="${vars({ '--c': x.color })}"></i><span class="sp-logo">${mark}</span><span class="sp-name">${x.name}${version}</span>${turns(x.calls)}<b class="sp-usd">${amount}</b></div>`;
}

function chief(c) {
  const what = t(c.steering ? 'costs.money_chief_what_steer' : 'costs.money_chief_what');
  const amount = c.unknown ? t('costs.money_unknown') : cost(c.usd, c.unpriced);
  return html`<div class="sp-row chief"><i class="sw"></i><span class="sp-logo"></span><span class="sp-name">${t('costs.money_chief')} <span class="sp-v">${what}</span></span>${turns(c.unknown ? null : c.calls)}<b class="sp-usd">${amount}</b></div>`;
}

function body(s, by) {
  if (s.state !== 'figures') {
    const word =
      s.state === 'unrecorded' ? t('costs.money_unrecorded') : (s.note ?? t('costs.money_pending'));
    return html`<p class="sp-line mut">${word}</p>`;
  }
  return html`<p class="sp-line">${s.line}</p>${bar(s)}${axis(s)}<div class="sp-rows">${s.rows.map((x) => row(x, by))}${chief(s.chief)}</div>`;
}

export function spendCard(r, state) {
  const by = state.spendBy ?? 'model';
  const s = spendBy(r, by);
  return html`<section class="spend" aria-label="${t('costs.money_title')}"><div class="sp-head"><h2 class="sp-title">${t('costs.money_title')}</h2>${switcher(by)}</div>${body(s, by)}</section>`;
}

export function bindSpendBy(root) {
  return delegate(root, 'click', '[data-spend-by]', (_, button) =>
    update({ spendBy: button.dataset.spendBy }),
  );
}
