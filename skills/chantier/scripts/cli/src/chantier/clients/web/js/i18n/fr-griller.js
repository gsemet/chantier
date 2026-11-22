// Mots français du Griller du board : le bouton Grill, l'avis avant le premier message, la
// conversation et ses boutons. Fusionné dans fr.js.
export default {
  'griller.button': 'Griller',
  'griller.button_title': 'Griller cet élément avec le Griller du board',
  'griller.loading': 'Lecture du Griller…',
  'griller.lost': "Le Griller n'a pas pu être lu : {error}",
  'griller.notice':
    'Ceci lance `{cli}` sur {machine}, la machine où tourne le board, avec `{model}`, et dépense les jetons du compte connecté là. Votre premier message vaut accord.',
  'griller.shared':
    "Cette conversation est partagée : toute personne qui détient la clé du board la voit et peut l'arrêter ou la terminer.",
  'griller.http':
    'Le board parle en HTTP simple : sur le réseau, la clé (le lien et son cookie de 30 jours) et le texte de chaque tour circulent en clair. `{command} --new-key` révoque la clé.',
  'griller.other': 'envoyé depuis un autre client',
  'griller.working': 'Le Griller travaille…',
  'griller.stopped': 'Arrêté.',
  'griller.failed': 'Le tour a échoué.',
  'griller.cut': 'coupé à 10 minutes',
  'griller.wrote': 'Écrit : {files}',
  'griller.wrote_cut': "Ce tour a été coupé ; ce qu'il a écrit reste : {files}",
  'griller.grilled': 'Assez grillé : {destination}',
  'griller.area': 'Votre message au Griller',
  'griller.send': 'Envoyer',
  'griller.stop': 'Arrêter',
  'griller.end': 'Terminer',
  'griller.busy': 'Un tour du Griller tourne sur {project}/{slug}',
  'griller.end_title': 'Terminer cette conversation ?',
  'griller.end_note':
    'La conversation est oubliée pour tout le monde ; les fichiers de la CR restent.',
  'griller.end_confirm': 'Terminer',
};
