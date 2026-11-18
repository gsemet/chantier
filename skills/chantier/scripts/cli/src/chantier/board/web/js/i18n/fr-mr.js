// Mots français qui disent « MR » là où le mot de base dit « PR » : un projet GitLab. Une clé `mr.<x>`
// est la forme MR de `pr.<x>`, et `mr.<k>` celle de toute autre clé `<k>` ; words.js la lit d'abord.
export default {
  'mr.nav.prs': 'MR',
  'mr.pv.nopr': "Aucune CR n'a encore de MR.",
  'mr.open': 'ouvrir la MR',
  'mr.tag': 'MR',
  'mr.draft': 'MR en draft, ne pas merger',
  'mr.home.open_prs': 'MR ouvertes',
  'mr.home.review_go': 'MR prêtes à merger',
  'mr.home.draft': '{n} MR en draft',
  'mr.prs.nothing': "Rien à revoir pour l'instant : aucune CR n'a rendu de MR prête à merger.",
  'mr.prs.review': 'MR à revoir',
  'mr.prs.drafts': 'MR en draft, pas encore à merger',
  'mr.prs.click': 'Un clic ouvre la MR.',
  'mr.prs.hint_stack_ok':
    'La stack est prête à merger : tu la merges en une action, depuis sa MR du haut. Les numéros sont des places dans la stack, pas un ordre de merge.',
  'mr.prs.hint_stack_no':
    "La stack n'est pas encore prête à merger : MR en draft, rien à merger. Les numéros sont des places dans la stack.",
  'mr.state.draft': 'MR en draft',
  'mr.gate.open': 'ouvrir la MR du CR qui valide la gate',
  'mr.kanban.handed_sub':
    'rendu : prête à merger quand la MR est sortie de draft sur {branch} ou sur un CR prêt à merger',
  'mr.mode.stack.text':
    'chaque MR repose sur la précédente, la release en haut ; une fois la stack vérifiée sur le forge, tu la merges en une action depuis sa MR du haut.',
  'mr.mode.series.text':
    "un CR après l'autre : le suivant part de la branche du précédent, sa MR reste brouillon jusqu'au merge du précédent ; la release en dernier.",
  'mr.mode.parallel.text':
    "chaque MR part de la branche par défaut, ou de sa dépendance ouverte : tu merges dans l'ordre où elles sont prêtes, la release après les autres.",
  'mr.stats.reviews': 'MR à revoir',
  'mr.stats.reviews.one': 'MR à revoir',
  'mr.ev.ship': 'MR {pr} poussée',
  'mr.costs.receipt_thanks': 'merci · {n} MR',
  'mr.costs.receipt_thanks.one': 'merci · 1 MR',
  'mr.overview.review': 'MR à revoir',
  'mr.overview.card_review': '{n} MR à revoir',
  'mr.overview.note':
    'Une ligne par projet de la surface. Un clic ouvre le projet ; un lien CR ouvre la MR à revoir.',
  'mr.pv.nomatch': 'Aucune MR ne correspond à ce filtre.',
};
