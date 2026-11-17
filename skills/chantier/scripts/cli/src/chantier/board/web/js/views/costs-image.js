// "Copy as image": the receipt's ticket as a PNG in the clipboard, with no third-party code. The
// ticket is cloned into an SVG `<foreignObject>` with the board's own styles and fonts, loaded as
// an image, drawn on a canvas and put in the clipboard by a `ClipboardItem` that holds the promise
// of the PNG, so the click's user gesture is still there when the browser asks for it.
// The image's source is `blob:` or `data:` (`SOURCE`); the page's content security policy
// (`img-src` in `reply.py`) names the same one.
import { $ } from '../core/dom.js';
import { snapshot, update } from '../core/store.js';
import { t } from '../model/words.js';
import { toast } from '../ui/toast.js';

const SOURCE = 'data'; // 'blob' or 'data': Chrome taints the canvas with 'blob:', so 'data:'
// The SVG's XML namespace: a name, not an address the page reads.
const SVG_NS = ['http:', '', 'www.w3.org', '2000', 'svg'].join('/');
const MARGIN = 24; // around the ticket, so its shadow and its scalloped bottom edge show
const SHEETS = [
  'css/tokens.css',
  'css/base.css',
  'css/components.css',
  'css/views/costs-receipt.css',
];
const FONTS = [
  ['400', 'fonts/Inter-Regular.woff2'],
  ['500', 'fonts/Inter-Medium.woff2'],
];

const fetched = async (path) => {
  const answer = await fetch(new URL(path, document.baseURI));
  if (!answer.ok) throw new Error(`${path}: ${answer.status}`);
  return answer;
};

function asDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

// The styles the ticket uses, with the Inter fonts inlined as `data:` URLs.
async function styles() {
  const sheets = await Promise.all(SHEETS.map(async (p) => (await fetched(p)).text()));
  const faces = await Promise.all(
    FONTS.map(async ([weight, path]) => {
      const url = await asDataUrl(await (await fetched(path)).blob());
      return `@font-face{font-family:"Inter";font-style:normal;font-weight:${weight};src:url("${url}") format("woff2");}`;
    }),
  );
  const own = '.ticket{position:relative;top:0}';
  return [...faces, ...sheets, own].join('\n');
}

const pageColor = () => {
  for (const el of [$('.main'), document.body, document.documentElement]) {
    const color = el && getComputedStyle(el).backgroundColor;
    if (color && color !== 'rgba(0, 0, 0, 0)' && color !== 'transparent') return color;
  }
  return '#fff';
};

// The ticket as the page draws it, without its interactive parts, in a box with the page's colour
// and font: a node of the page, taken at once (the page redraws when the copy starts).
function boxed(ticket, width) {
  const clone = ticket.cloneNode(true);
  for (const part of clone.querySelectorAll('.r-act, button')) part.remove();
  const body = getComputedStyle(document.body);
  const box = document.createElement('div');
  box.className = 'costs';
  // Through the style object: the page's policy refuses a `style` attribute set as text.
  box.style.cssText = `box-sizing:border-box;width:${width + 2 * MARGIN}px;padding:${MARGIN}px;background:${pageColor()};color:${body.color};font-family:${body.fontFamily};font-size:${body.fontSize};line-height:${body.lineHeight}`;
  box.append(clone);
  return box;
}

// The box with the styles, as an XHTML string.
function serialized(box, css) {
  const style = document.createElement('style');
  style.textContent = css;
  box.prepend(style);
  return new XMLSerializer().serializeToString(box);
}

// The image's address, `blob:` or `data:`, and what releases it. One function to switch between the
// two forms.
function sourceOf(svg) {
  if (SOURCE === 'data') {
    return { url: `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`, release() {} };
  }
  const url = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml;charset=utf-8' }));
  return { url, release: () => URL.revokeObjectURL(url) };
}

const loaded = (url) =>
  new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error('the receipt could not be drawn as an image'));
    image.src = url;
  });

// The ticket's PNG, as a promise of a Blob. The ticket is cloned before the first `await`.
async function ticketPng(ticket) {
  const { width, height } = ticket.getBoundingClientRect();
  const w = Math.ceil(width) + 2 * MARGIN;
  const h = Math.ceil(height) + 2 * MARGIN;
  const box = boxed(ticket, Math.ceil(width));
  const inner = serialized(box, await styles());
  const svg = `<svg xmlns="${SVG_NS}" width="${w}" height="${h}"><foreignObject x="0" y="0" width="100%" height="100%">${inner}</foreignObject></svg>`;
  const source = sourceOf(svg);
  try {
    const image = await loaded(source.url);
    const scale = Math.max(2, window.devicePixelRatio || 1);
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(w * scale);
    canvas.height = Math.round(h * scale);
    canvas.getContext('2d').drawImage(image, 0, 0, canvas.width, canvas.height);
    return await new Promise((resolve, reject) =>
      canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('no image'))), 'image/png'),
    );
  } finally {
    source.release();
  }
}

// Copy the receipt of `root` (the Costs view) to the clipboard, then say so in a toast.
export async function copyReceipt(root) {
  const ticket = $('.ticket', root);
  if (!ticket || snapshot().copying) return;
  try {
    // Built first: `ticketPng` measures and clones the ticket before the page redraws.
    const item = new ClipboardItem({ 'image/png': ticketPng(ticket) });
    update({ copying: true });
    await navigator.clipboard.write([item]);
    toast(t('costs.copied'));
  } catch (error) {
    toast(t('costs.copy_failed', { error: error?.message ?? String(error) }), { error: true });
  } finally {
    update({ copying: false });
  }
}
