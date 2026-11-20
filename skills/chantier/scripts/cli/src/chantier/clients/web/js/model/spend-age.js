// The age of the spend a batch shows: "computed 3 min ago", or "age unknown"; nothing without a spend.
import { age } from '../core/format.js';
import { t } from './words.js';

export function spentAge(batch, now) {
  if (batch.spent_usd == null) return '';
  const when = age(batch.cost_at, now);
  return when ? t('batch.spent_age', { age: when }) : t('batch.spent_age_unknown');
}
