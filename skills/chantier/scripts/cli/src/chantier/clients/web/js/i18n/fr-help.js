// Mots français de la page Aide : son intro et ses titres, puis, par sujet, son nom, sa phrase et son
// texte (texte simple, paragraphes séparés par une ligne vide, une liste en lignes commençant par `- `).
// Fusionné dans fr.js.
export default {
  'help.intro':
    'chantier en quelques cartes : ses concepts et les rôles de ses agents. Cliquez une carte pour en savoir plus.',
  'help.concepts': 'Concepts',
  'help.roles': 'Rôles',
  'help.close': 'Fermer',
  'help.read_more': 'En savoir plus (page en anglais)',
  'help.change_request.name': 'Change request',
  'help.change_request.line':
    'Un niveau au-dessus des tickets de votre tracker : un dossier qui décrit ce que vous voulez.',
  'help.change_request.body':
    "Une Change Request (CR) se place un niveau au-dessus des tickets de votre tracker. Les petites demandes qui n'ont pas leur place dans le tracker, une idée, un bug, un rapport, sont acceptées et priorisées ici sans y entrer. Le tracker garde la vision stratégique à long terme ; le dossier de planification est le plan tactique à court terme, au plus près du chantier.\n\nUne CR est un dossier, et son contenu varie, d'une seule ligne de texte à plusieurs prototypes HTML. Les agents le lisent et en déduisent l'intention de la demande.\n\nLes CR sont fongibles dans le plan : on peut les découper, les fusionner ou les abandonner.",
  'help.grill.name': 'Grill et spécification',
  'help.grill.line':
    "Les questions qu'un changement demande, posées une à une, puis consignées dans une spécification.",
  'help.grill.body':
    'Le Chief of Staff, ou un Griller, pose les questions dont un changement a besoin. Chaque réponse est consignée dans la CR.\n\nQuand vous dites « grilled enough », vous choisissez où va la CR : le prochain batch (3-ready, par défaut) ou le batch en cours, proposé seulement quand un batch est ouvert.\n\nEnsuite le spec-writer écrit la Change Specification en arrière-plan. Sur une CR à fort impact, le spec critic la vérifie après coup et ne la modifie jamais.\n\nRien ne démarre sans votre feu vert.',
  'help.planning_folder.name': 'Dossier de planification',
  'help.planning_folder.line': "L'endroit où chantier écrit tout, en Markdown et JSON simples.",
  'help.planning_folder.body':
    "Le dossier de planification est le seul endroit où chantier écrit. Tout y est en Markdown et en JSON, lisible par vous et par les agents.\n\nUne CR traverse ses étapes sous forme de dossiers :\n\n- l'inbox, où arrivent les idées\n- le backlog, de P1 à P4\n- 3-ready, le prochain batch\n- 4-batch, avec les CR en attente, actives et terminées\n- puis les archives\n\nC'est .agents/changes/ dans votre projet, ou le dossier du projet dans une surface de planification externe.",
  'help.batch.name': 'Batch et slots',
  'help.batch.line':
    "Un ensemble de CR construites ensemble, jusqu'à des pull requests prêtes à fusionner.",
  'help.batch.body':
    "chantier n'est pas de la livraison continue, où une intention donne une PR et une release. C'est n CR, m PR (normalement proche de n), p batchs, et une release.\n\nVous planifiez un ensemble de CR à l'avance, par exemple en grillant pendant la journée, et chantier construit le batch seul, jusqu'à des PR prêtes à fusionner.\n\nLes slots sont les CR qui tournent côte à côte. Une CR ajoutée pendant que le batch tourne est mise en file et prise quand un slot se libère.\n\nUn batch est en cours, en pause ou clos. Il se clôt sur votre accord, et vous fusionnez les pull requests vous-même.",
  'help.cr_lifecycle.name': "La vie d'une CR",
  'help.cr_lifecycle.line':
    "De la planification à l'archive : étude, implémentation, QA et release.",
  'help.cr_lifecycle.body':
    "Une CR est portée à travers la planification, l'étude, l'implémentation, la QA, le déploiement et enfin l'archive.\n\n- La planification se fait surtout avec le Chief of Staff.\n- La boucle d'implémentation centrale délègue à des Drivers, avec des revues strictes.\n- Une boucle de QA laisse un agent de validation agir comme un utilisateur, pour vérifier ce que l'intégration et les tests de bout en bout ne couvrent pas.\n- La release se fait avec une fusion automatique supervisée, et peut surveiller le déploiement, en production, sur les registres de paquets ou sur les pages de documentation.\n\nChaque étape a un agent qui agit, et plusieurs fichiers, surtout en Markdown, s'ajoutent au dossier de la CR en chemin.",
  'help.planning_modes.name': 'Modes de planification',
  'help.planning_modes.line': 'Planifier dans votre projet, ou dans un dépôt à part.',
  'help.planning_modes.body':
    "Chantier planifie à l'un de deux endroits.\n\n- Dans le projet, par défaut, sans rien à déclarer : .agents/changes/ dans votre projet.\n- Externe : un dépôt git à part, la surface de planification, avec un dossier par projet. Le dépôt de votre projet ne reçoit que le code et, si vous le voulez, l'archive nettoyée de chaque CR dans sa PR.\n\nLe Chief of Staff, le Foreman et le Griller travaillent sur la branche par défaut : le checkout principal de votre projet en mode projet, celui de la surface en mode externe. Seul le code a des worktrees, un par CR, dans votre projet.\n\nDans une surface de planification, le serveur de la surface commit et pousse le plan.",
  'help.steering.name': 'Direct ou Foreman',
  'help.steering.line':
    'Qui pilote le batch : le Chief of Staff lui-même, ou une session Foreman imbriquée.',
  'help.steering.body':
    "En mode direct, le Chief of Staff pilote le batch lui-même. En mode Foreman, une session Foreman imbriquée le pilote.\n\nLe mode suit l'endroit où vous êtes : Foreman au poste de travail, direct depuis le téléphone sous Remote Control, ou dans un terminal ou VS Code. Dire foreman ou direct en force un.\n\nDans les deux modes, une CR ajoutée pendant que le batch tourne est mise en file et prise quand un slot se libère.\n\nLe mode direct est plus simple à distance. En mode Foreman, le Chief of Staff reste libre de grill pendant que le Foreman mène le batch. En mode direct, il ne grille pas tant qu'un batch tourne : ouvrez plutôt une session Griller.",
  'help.batch_modes.name': 'Modes de batch',
  'help.batch_modes.line':
    "Parallèle, série ou pile : comment les pull requests d'un batch se relient.",
  'help.batch_modes.body':
    "Un batch a l'un de trois modes. Ils disent comment les PR se relient, et qui fusionne quoi, quand. Vous fusionnez, jamais chantier.\n\n- Parallèle, par défaut : chaque CR part de la branche par défaut en même temps. Vous fusionnez dans l'ordre où les PR deviennent prêtes ; après chaque fusion, les autres sont rebasées.\n- Série : les CR ont l'ordre que vous avez donné. La suivante démarre quand la précédente est rendue, et sa PR reste en brouillon jusqu'à la fusion de la précédente.\n- Pile : du parallèle, avec un stack driver qui fait une pile native de PR sur la forge.\n\nUne CR qui dépend d'une autre (depends.json) l'attend dans tous les modes. Un batch en cours peut changer de mode sur demande.",
  'help.project_rules.name': 'Les règles de votre projet',
  'help.project_rules.line':
    'Vos changements doivent pouvoir arriver sans chantier : vos propres fichiers sont la seule configuration.',
  'help.project_rules.body':
    "Vos changements doivent pouvoir arriver sans chantier. chantier est là pour industrialiser, pas pour remplacer vos règles.\n\nVotre AGENTS.md, et un chantier.yaml facultatif, sont la seule configuration. Le chantier.yaml fixe l'agent et le modèle de chaque rôle, et les skills dont il a besoin. Il peut être celui du projet, et celui de sa surface de planification.\n\nTout ce que chantier écrit est en Markdown et en JSON dans le dossier de planification.\n\nVous pouvez utiliser votre propre agent pour un rôle, ou ajouter une étape de revue après l'Inspector : dites-le, et le rôle l'exécute dès le prochain batch.",
  'help.gates.name': 'Gates',
  'help.gates.line': 'La gate rapide et la gate longue que vous déclarez dans votre AGENTS.md.',
  'help.gates.body':
    "Une gate est une commande qui décide si le travail est assez bon pour continuer. Vous en déclarez deux dans votre AGENTS.md.\n\n- La gate rapide tourne souvent, par exemple dans le tour d'un Coder.\n- La gate longue tourne sur la tête poussée d'une CR, par un Verifier, avant que la CR soit rendue.\n\nÀ l'init, le Chief of Staff vérifie la gate longue et propose les lignes exactes à écrire dans votre AGENTS.md. Il les écrit sur votre accord.\n\nVous pouvez les changer plus tard : dites par exemple que votre gate longue est npm test.",
  'help.costs.name': 'Coûts et limites',
  'help.costs.line': 'Ce que coûte un batch, et les limites qui le bornent.',
  'help.costs.body':
    "Un batch a un budget. Le pilotage et les Drivers en sont l'essentiel ; le code lui-même en est une petite part.\n\nLa session du Chief of Staff est comptée à part, sur ses propres lignes, et jamais dans le budget.\n\nPour mesurer les vôtres, demandez « what did it cost? » ou lancez chantier cost. Il donne la dépense par rôle, par CR, et ce qui explique chaque chiffre.\n\nDeux limites se règlent sur la page Configuration de ce board, dans son onglet Limits : les slots d'un nouveau batch (batch.slots), et le nombre de CR spécifiées à la fois (specifying.parallel).",
  'help.boards.name': 'Boards',
  'help.boards.line':
    'Trois façons de suivre un batch : ce board web, un volet dans Claude Code, une vue en terminal.',
  'help.boards.body':
    "Le même état est montré de trois façons.\n\n- Ce board web : les batchs en direct, ce qui vous attend, le backlog et les CR fusionnées. Il peut tourner aussi sur votre téléphone, où vous pouvez trier le backlog. C'est un client de l'API publiée du serveur, qu'un script peut utiliser aussi.\n- Un volet en lecture seule dans Claude Code, ouvert avec /chantier-board ou en chargeant le Chief of Staff.\n- chantier live, une vue en lecture seule d'un board en marche, dans votre terminal.\n\nLes boards montrent l'état ; la session de pilotage agit dessus.",
  'help.chief_of_staff.name': 'Chief of Staff',
  'help.chief_of_staff.line': 'La seule personne à qui vous parlez, dans votre propre session.',
  'help.chief_of_staff.body':
    "Vous parlez au Chief of Staff, dans votre propre session. Il tient le siège : l'unique session qui ouvre et mène les batchs dans le dépôt.\n\nIl tient le backlog, et pose les questions dont un changement a besoin. Rien ne démarre sans votre feu vert, et vous fusionnez les pull requests.\n\nIl ouvre un batch sur votre parole, et en mode direct il pilote le batch lui-même, en lançant les Drivers.\n\nSa session est comptée à part du budget du batch.",
  'help.griller.name': 'Griller',
  'help.griller.line': 'Une session facultative qui grille à côté du Chief of Staff.',
  'help.griller.body':
    "Un Griller est une session facultative à vous, lancée avec /chantier:griller. Il affine l'inbox et le backlog pendant que le Chief of Staff mène les batchs.\n\nIl n'ouvre jamais de batch. Le Chief of Staff reprend ce qu'il dépose.\n\nIl compte surtout en mode direct, où le Chief of Staff, occupé à piloter, ne grille pas tant qu'un batch tourne.",
  'help.foreman.name': 'Foreman',
  'help.foreman.line':
    'Une session imbriquée qui pilote un batch, pour que le Chief of Staff reste libre.',
  'help.foreman.body':
    'En mode Foreman, une session Foreman imbriquée pilote chaque batch. Elle lance les Drivers et suit le batch.\n\nVotre Chief of Staff reste libre pour une conversation naturelle et dynamique pendant que le batch tourne : vous pouvez grill les sujets à venir avec lui.\n\nLe Foreman est le choix par défaut au poste de travail. Depuis le téléphone, un terminal ou VS Code, le mode direct est utilisé, sauf si vous demandez foreman.',
  'help.driver.name': 'Driver',
  'help.driver.line':
    "Mène une CR dans son propre worktree, jusqu'à une pull request rendue prête.",
  'help.driver.body':
    "Un Driver, ou CR driver, mène une CR jusqu'au bout. Il travaille dans le worktree git propre à la CR, dans votre projet.\n\nIl délègue à des workers courts : l'Investigator, le Coder, l'Inspector, le Verifier et le Debugger, dont chacun peut être votre propre agent. Ses revues sont strictes.\n\nIl termine quand la pull request est rendue prête à fusionner. Le Foreman, ou le Chief of Staff en mode direct, lance les Drivers.",
  'help.spec_writer.name': 'Spec-writer et spec critic',
  'help.spec_writer.line': "L'un écrit la Change Specification, l'autre la vérifie.",
  'help.spec_writer.body':
    "Le spec-writer écrit la Change Specification en arrière-plan, dès que vous dites qu'une CR est grilled enough.\n\nSur une CR à fort impact, le spec critic vérifie ensuite la spécification. Il ne la modifie jamais.\n\nTous deux sont des agents du Chief of Staff ou du Griller : on ne vous demande pas de les attendre, et les Drivers du batch partent de la spécification qu'ils laissent.",
  'help.investigator.name': 'Investigator',
  'help.investigator.line': 'Facultatif : cartographie un code inconnu avant le premier tour.',
  'help.investigator.body':
    "L'Investigator est facultatif. Quand le code est inconnu, il le cartographie avant le tour 1.\n\nC'est l'un des workers courts que lance le CR driver. Comme les autres, il peut être votre propre agent.\n\nIl lit et cartographie ; il ne modifie pas le code.",
  'help.coder.name': 'Coder',
  'help.coder.line': "Écrit le code d'un tour et lance la gate rapide.",
  'help.coder.body':
    "Le Coder écrit le code d'un tour d'une CR, dans le worktree de la CR, et lance votre gate rapide.\n\nC'est un worker court que démarre le CR driver. Vous pouvez désigner votre propre agent, par exemple un spécialiste du langage : dites « use my rust-coder as the coder ».\n\nSi un Coder rencontre un problème, un nouveau peut repartir sur le modèle d'escalation du rôle.",
  'help.inspector.name': 'Inspector',
  'help.inspector.line': 'Relit chaque tour, en lisant le diff avant le commit.',
  'help.inspector.body':
    "L'Inspector relit chaque tour, et lit le diff avant le commit.\n\nVos propres étapes de revue supplémentaires passent après lui : dites « add a security review with sec-reviewer » et le Driver l'exécute après l'Inspector.\n\nComme les autres workers, l'Inspector peut être votre propre agent.",
  'help.verifier.name': 'Verifier',
  'help.verifier.line': "Lance la gate longue sur la tête poussée avant qu'une CR soit rendue.",
  'help.verifier.body':
    "Le Verifier lance votre gate longue sur la tête poussée d'une CR, avant que la CR soit rendue. Une CR n'est pas prête tant que le Verifier ne la déclare pas vérifiée.\n\nLe coût des Verifiers pèse lourd dans un batch parallèle, puisque chaque rebase peut demander une nouvelle vérification.\n\nIl peut être votre propre agent.",
  'help.debugger.name': 'Debugger',
  'help.debugger.line': 'Un worker court qui trouve pourquoi quelque chose échoue.',
  'help.debugger.body':
    "Le Debugger est un worker court que lance le CR driver, et il peut être votre propre agent.\n\nC'est l'un des trois rôles qui portent une escalation : le modèle sur lequel démarre un nouvel agent de ce rôle après un problème nommé. Les deux autres sont le Coder et le conflict resolver. Le modèle d'escalation est Opus par défaut, et se règle par rôle dans la configuration.\n\nSon modèle par défaut est le même que celui du Verifier.",
  'help.conflict_resolver.name': 'Conflict resolver',
  'help.conflict_resolver.line': "Règle les conflits d'un rebase.",
  'help.conflict_resolver.body':
    "Le conflict resolver est un worker qui règle les conflits d'un rebase. Le CR driver et le stack driver peuvent tous deux le lancer.\n\nAprès chaque fusion, en mode parallèle, chaque PR encore ouverte est rebasée sur la branche par défaut, avec ou sans conflit. C'est là que ce worker est appelé, et il pèse donc sur le coût d'un batch parallèle.",
  'help.stack_driver.name': 'Stack driver',
  'help.stack_driver.line': 'En mode pile, construit la pile native sur la forge et la restack.',
  'help.stack_driver.body':
    "En mode pile, le stack driver est responsable des piles de PR. Dès que deux PR sont rendues prêtes, il fait une pile native sur la forge, et les CR lancées ensuite se construisent dessus. C'est pour GitHub, avec l'extension gh stack.\n\nQuand un changement est inséré dans une pile prête à fusionner, il renvoie en brouillon les PR au-dessus, restack, et vérifie la pile avant qu'elles redeviennent prêtes.",
  'help.release_driver.name': 'Release driver',
  'help.release_driver.line': 'Mène une CR de release selon la procédure propre à votre projet.',
  'help.release_driver.body':
    "Une release est une CR comme les autres. Le Release driver la mène selon la procédure de release propre à votre projet, de votre « release » jusqu'à l'archive.\n\nVous approuvez chaque action irréversible, ou vous dites « auto ».\n\nUne procédure va d'une simple publication de paquet à une longue, avec une release, ses notes, un pipeline à suivre et une annonce. Elle reste écrite et maintenue dans votre projet, et une rétro l'améliore.",
};
