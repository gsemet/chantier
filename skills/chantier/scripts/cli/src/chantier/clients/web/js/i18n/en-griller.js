// English words of the board's Griller: the Grill button, the notice before the first message, the
// conversation and its buttons. Merged into en.js.
export default {
  'griller.button': 'Grill',
  'griller.button_title': "Grill this item with the board's Griller",
  'griller.loading': 'Reading the Griller…',
  'griller.lost': 'The Griller could not be read: {error}',
  'griller.notice':
    'This runs `{cli}` on {machine}, the machine the board runs on, with `{model}`, and spends the tokens of the account signed in there. Your first message is your yes.',
  'griller.shared':
    "This conversation is shared: anyone holding the board's key sees it and may stop or end it.",
  'griller.http':
    "The board speaks plain HTTP: on the network, the key (the link and its 30-day cookie) and every turn's text travel in clear. `{command} --new-key` revokes the key.",
  'griller.other': 'sent from another client',
  'griller.working': 'The Griller is working…',
  'griller.stopped': 'Stopped.',
  'griller.failed': 'The turn failed.',
  'griller.cut': 'cut at 10 minutes',
  'griller.wrote': 'Written: {files}',
  'griller.wrote_cut': 'This turn was cut; what it wrote stays: {files}',
  'griller.grilled': 'Grilled enough: {destination}',
  'griller.area': 'Your message to the Griller',
  'griller.send': 'Send',
  'griller.stop': 'Stop',
  'griller.end': 'End',
  'griller.busy': 'A Griller turn runs on {project}/{slug}',
  'griller.end_title': 'End this conversation?',
  'griller.end_note': 'The conversation is forgotten for everyone; the files of the CR stay.',
  'griller.end_confirm': 'End it',
};
