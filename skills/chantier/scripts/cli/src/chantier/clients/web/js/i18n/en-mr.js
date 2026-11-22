// English words that say "MR" where the base word says "PR": a GitLab project. A key `mr.<x>` is the
// MR form of `pr.<x>`, and `mr.<k>` that of any other key `<k>`; words.js reads it first on GitLab.
export default {
  'mr.nav.prs': 'MRs',
  'mr.pv.nopr': 'No CR has an MR yet.',
  'mr.open': 'open the MR',
  'mr.inbox.sub':
    'Questions, approvals, MRs to merge and blocked CRs that wait for you. Not the planning inbox: the requests to grill are in Triage.',
  'mr.tag': 'MR',
  'mr.draft': 'MR in draft, do not merge',
  'mr.home.open_prs': 'Open MRs',
  'mr.home.review_go': 'MRs ready to merge',
  'mr.home.draft': '{n} MR in draft',
  'mr.prs.nothing': 'Nothing to review yet: no CR has handed back an MR that is ready to merge.',
  'mr.prs.review': 'MRs to review',
  'mr.prs.drafts': 'MRs in draft, not to merge yet',
  'mr.prs.click': 'One click opens the MR.',
  'mr.prs.hint_stack_ok':
    'The stack is ready to merge: you merge it in one action, from its top MR. The numbers are places in the stack, not a merge order.',
  'mr.prs.hint_stack_no':
    'The stack is not ready to merge yet: MRs in draft, nothing to merge. The numbers are places in the stack.',
  'mr.state.draft': 'MR in draft',
  'mr.gate.open': 'open the MR of the CR whose gate validates it',
  'mr.kanban.handed_sub':
    'handed back: ready to merge once the MR is out of draft on {branch} or on a CR ready to merge',
  'mr.mode.stack.text':
    'each MR sits on the previous one, the release on top; once the stack is verified on the forge, you merge it in one action from its top MR.',
  'mr.mode.series.text':
    "one CR after the other: the next starts from the previous one's branch, its MR stays a draft until the previous one merges; the release last.",
  'mr.mode.parallel.text':
    'each MR starts from the default branch, or from its open dependency: you merge them in the order they were handed back, the release after the others.',
  'mr.stats.reviews': 'MRs to review',
  'mr.stats.reviews.one': 'MR to review',
  'mr.ev.ship': 'MR {pr} pushed',
  'mr.costs.receipt_thanks': 'thank you · {n} MRs',
  'mr.costs.receipt_thanks.one': 'thank you · 1 MR',
  'mr.overview.review': 'MRs to review',
  'mr.overview.card_review': '{n} MRs to review',
  'mr.overview.note':
    'One line per project of the surface. A click opens the project; a CR link opens the MR to review.',
  'mr.pv.nomatch': 'No MR matches this filter.',
};
