// Clip · terminal (t4): a code-drawn terminal window for "show the screen" tips. A command or a prompt is typed, output
// lines arrive, keys are pressed, the status bar changes. A headline above the window carries the hook, then the step names.
// data: { title? (window title, default 'terminal'), accent? ('#FFC83C') }
// cues: title     text = the headline (the hook); data.key = one word of it to tint
//       cmd       text = a shell command, typed after `$`
//       prompt    text = what the user types to the agent, typed after `>`; a "working" line runs until the next `out`
//       out       text = output, one row per \n. A leading + or - draws a diff row; ✓ ok PASS green; ✗ error FAIL red;
//                 # dim; ! warn. data.color = ok | err | warn | dim | accent overrides
//       key       text = "Shift+Tab", "Esc Esc": keycaps pressed over the window ("+" = together, space = one after the other)
//       clear     wipes the screen
//       highlight data.word = a word in a row on screen (the latest row that holds it); without it, the latest typed row
//       any cue:  sub = a new headline from this cue on (data.key tints a word); data.label = status bar text from this cue on
// Motion never stops (cursor, drifting dots, a slow camera drift), so the film has no stills. safe: everything sits in ctx.box.
// alpha: no backdrop.
CLIPS.t4_terminal = (() => {
const { clamp, lerp } = U;
const MONO = 'JetBrainsMono-400', MONOB = 'JetBrainsMono-700', HEAD = 'PuHui-Black', SANS = 'PuHui-Bold';
const COL = { bg0: '#080C13', bg1: '#111A2B', win: '#0D1117', bar: '#161B22', rule: '#30363D', fg: '#F0F6FC', out: '#C9D1D9', dim: '#8B949E',
  ok: '#3FB950', err: '#FF7B72', warn: '#E3B341', accent: '#FFC83C' };
let L, rows, heads, keys, his, labels, clears, firstPre;

function wrap(text, cols) {
  const s = String(text); if (s.length <= cols) return [s];
  const lines = []; let cur = '';
  for (const w of s.split(' ')) {
    let word = w;
    while (word.length > cols) { if (cur) { lines.push(cur); cur = ''; } lines.push(word.slice(0, cols)); word = word.slice(cols); }
    if (!cur) cur = word; else if ((cur + ' ' + word).length <= cols) cur += ' ' + word; else { lines.push(cur); cur = word; }
  }
  if (cur) lines.push(cur);
  return lines;
}
function tintOf(line, data) {
  const named = { ok: COL.ok, err: COL.err, warn: COL.warn, dim: COL.dim, accent: L.accent }, c = data && data.color;
  if (c) return { color: named[c] || c };
  if (/^\s*\+/.test(line)) return { color: COL.ok, band: COL.ok };
  if (/^\s*-\s/.test(line)) return { color: COL.err, band: COL.err };
  if (/^\s*(✓|✔|ok\b|pass)/i.test(line)) return { color: COL.ok };
  if (/^\s*(✗|✘|error|fail)/i.test(line)) return { color: COL.err };
  if (/^\s*(#|\/\/)/.test(line)) return { color: COL.dim };
  if (/^\s*(!|warn)/i.test(line)) return { color: COL.warn };
  return { color: COL.out };
}
return {
  fonts: [HEAD],
  safe: true,
  init(ctx) {
    const { W, u, box } = ctx, g = document.createElement('canvas').getContext('2d');
    const hz = (ctx.portrait ? 290 : 190) * u, wx = box.x + 36 * u, ww = box.w - 72 * u, wy = box.y + hz, wh = box.h - hz - 6 * u;
    const tb = 74 * u, sb = 76 * u, pad = 34 * u, fs = (ctx.portrait ? 48 : 38) * u, lh = fs * 1.5;
    g.font = `${fs}px "${MONO}"`; const cw = g.measureText('M').width, cols = Math.max(12, Math.floor((ww - 2 * pad) / cw));
    L = { wx, wy, ww, wh, tb, sb, pad, fs, lh, cw, cols, hz, bx: wx + pad, by: wy + tb + pad * 0.7, bw: ww - 2 * pad, bh: wh - tb - sb - pad * 1.2, accent: ctx.data.accent || COL.accent };
    rows = []; keys = []; clears = []; labels = []; let screen = 0;
    const tc = ctx.of('cmd', 'prompt', 'out', 'key', 'clear');
    tc.forEach((q, i) => {
      const nx = tc[i + 1], nextAt = nx ? nx.at : ctx.dur + 1, lab = q.data && q.data.label;
      if (q.kind === 'clear') { clears.push(q.at); screen++; if (lab) labels.push({ at: q.at, text: lab }); return; }
      if (q.kind === 'key') {
        keys.push({ at: q.at, end: Math.max(q.at + 1.3, Math.min(nextAt - 0.05, q.at + 3.4)), groups: String(q.text || '').trim().split(/\s+/).map(s => s.split('+').filter(Boolean)).filter(a => a.length) });
        if (lab) labels.push({ at: q.at + 0.64, text: lab }); return;
      }
      if (q.kind === 'out') {
        String(q.text || '').split('\n').forEach((ln, k) => rows.push({ type: 'out', screen, at: q.at + k * 0.14, lines: wrap(ln, cols), tint: tintOf(ln, q.data) }));
        if (lab) labels.push({ at: q.at, text: lab }); return;
      }
      const lines = wrap(String(q.text || ''), cols - 2), n = lines.reduce((a, l) => a + l.length, 0);
      const typeDur = Math.min(clamp(n / 26, 0.45, 1.6), Math.max(0.4, nextAt - q.at - 0.3));
      rows.push({ type: 'in', screen, at: q.at, lines, n, typeDur, pre: q.kind === 'cmd' ? '$' : '>' });
      if (lab) labels.push({ at: q.at + typeDur, text: lab });
      const w0 = q.at + typeDur + 0.3;
      if (q.kind === 'prompt' && nx && nx.kind === 'out' && nextAt - w0 >= 0.5) rows.push({ type: 'work', screen, at: w0, end: nextAt, lines: [''] });
    });
    rows.forEach(r => { r.gone = clears[r.screen] ?? Infinity; });
    firstPre = (rows.find(r => r.type === 'in') || { pre: '$' }).pre;
    heads = ctx.cues.filter(q => q.kind === 'title' ? q.text : q.sub).map(q => {
      const text = q.kind === 'title' ? q.text : q.sub, size = (ctx.portrait ? 96 : 84) * u;
      let f = TY.fit(g, text, W * 0.88, size, HEAD, { maxLines: 2, min: 0.55, soft: true, balance: true });
      if (!f.ok) f = TY.fit(g, text, W * 0.88, size * 0.7, HEAD, { maxLines: 3, min: 0.4, balance: true });
      return { at: q.at, text, f, key: q.data && q.data.key };
    });
    his = ctx.of('highlight').map(h => {
      const word = h.data && h.data.word, live = rows.filter(r => r.type !== 'work' && r.at <= h.at + 1e-6 && r.gone > h.at);
      let row = null, j = -1, k = -1;
      if (word) for (const r of [...live].reverse()) { j = r.lines.findIndex(l => l.includes(word)); if (j >= 0) { row = r; k = r.lines[j].indexOf(word); break; } }
      if (!row) { row = [...live].reverse().find(r => r.type === 'in') || live[live.length - 1]; j = -1; if (word) console.warn(`t4 highlight at=${h.at}: no row on screen holds "${word}"; the latest typed row is boxed instead`); }
      return { at: h.at, row, j, k, word };
    }).filter(h => h.row);
    his.forEach((h, i) => { h.end = his[i + 1] ? his[i + 1].at : Infinity; });
    labels.sort((a, b) => a.at - b.at);
  },
  draw(c, t, ctx) {
    const { W, H, u } = ctx;
    if (!ctx.alpha) backdrop(c, t, ctx);
    headline(c, t, ctx);
    let bump = 1; for (const q of ctx.cues) { const l = t - q.at; if (l >= 0 && l < 0.4) bump += 0.008 * Math.exp(-l * 22); }
    const [dx, dy] = CAM.drift(t, 4 * u, 3), z = lerp(0.965, 1, MO.expoOut(clamp(t / 0.5 + 0.25))) * bump, cx = W / 2, cy = L.wy + L.wh / 2;
    c.save(); c.translate(cx + dx, cy + dy); c.scale(z, z); c.translate(-cx, -cy);
    chrome(c, t, ctx);
    c.save(); c.beginPath(); c.rect(L.wx + 2 * u, L.wy + L.tb, L.ww - 4 * u, L.wh - L.tb - L.sb); c.clip();
    const s = clears.filter(ct => ct <= t + 1e-6).length;
    if (s > 0) { const p = clamp((t - clears[s - 1]) / 0.22); if (p < 1) screenRows(c, t, ctx, s - 1, 1 - p, -60 * u * MO.cubicIn(p), false); }
    screenRows(c, t, ctx, s, 1, 0, true);
    keycaps(c, t, ctx);
    c.restore();
    statusbar(c, t, ctx);
    c.restore();
  },
};
function backdrop(c, t, ctx) {
  const { W, H, u } = ctx, g = c.createLinearGradient(0, 0, W * 0.4, H); g.addColorStop(0, COL.bg1); g.addColorStop(1, COL.bg0);
  c.fillStyle = g; c.fillRect(0, 0, W, H);
  const gx = W * (0.5 + 0.32 * Math.sin(t * 0.21)), gy = H * (0.36 + 0.1 * Math.cos(t * 0.17)), r = W * 0.9, rg = c.createRadialGradient(gx, gy, 0, gx, gy, r);
  rg.addColorStop(0, 'rgba(88,166,255,0.16)'); rg.addColorStop(1, 'rgba(88,166,255,0)'); c.fillStyle = rg; c.fillRect(0, 0, W, H);
  const sp = 60 * u, ox = (t * 22 * u) % sp, oy = (t * 13 * u) % sp;
  c.save(); c.globalAlpha = 0.085; c.fillStyle = '#FFFFFF';
  for (let y = -sp; y < H + sp; y += sp) for (let x = -sp; x < W + sp; x += sp) { c.beginPath(); c.arc(x + ox, y + oy, 3 * u, 0, 7); c.fill(); }
  c.restore();
}
function headline(c, t, ctx) {
  const { W, u } = ctx; let hi = -1; heads.forEach((h, i) => { if (t >= h.at - 1e-6) hi = i; });
  const h = heads[hi]; if (!h) return;
  const lt = ctx.lt(t, h.at), p = hi === 0 ? clamp((lt + 0.2) / 0.28) : clamp(lt / 0.28), e = MO.expoOut(p);
  const size = h.f.size, lh = size * 1.12, n = h.f.lines.length, y0 = ctx.box.y + L.hz / 2 - (n * lh) / 2 + size * 0.86 - 10 * u;
  const stroke = ctx.alpha ? { stroke: '#111', strokeW: size * 0.07 } : {};
  h.f.lines.forEach((ln, i) => {
    const y = y0 + i * lh + 34 * u * (1 - e), w = TY.width(c, ln, size, HEAD), x0 = W / 2 - w / 2, o = { size, fam: HEAD, align: 'left', alpha: clamp(p * 2.2), ...stroke };
    const ki = h.key ? ln.indexOf(h.key) : -1;
    if (ki < 0) return TY.text(c, ln, x0, y, { ...o, color: '#FFFFFF' });
    const pre = ln.slice(0, ki), post = ln.slice(ki + h.key.length), wp = TY.width(c, pre, size, HEAD), wk = TY.width(c, h.key, size, HEAD);
    if (pre) TY.text(c, pre, x0, y, { ...o, color: '#FFFFFF' }); TY.text(c, h.key, x0 + wp, y, { ...o, color: L.accent }); if (post) TY.text(c, post, x0 + wp + wk, y, { ...o, color: '#FFFFFF' });
  });
}
function chrome(c, t, ctx) {
  const { u } = ctx, { wx, wy, ww, wh, tb, sb } = L, r = 30 * u;
  c.save(); c.shadowColor = 'rgba(0,0,0,0.55)'; c.shadowBlur = 60 * u; c.shadowOffsetY = 24 * u;
  c.fillStyle = COL.win; c.beginPath(); c.roundRect(wx, wy, ww, wh, r); c.fill(); c.restore();
  c.save(); c.beginPath(); c.roundRect(wx, wy, ww, wh, r); c.clip();
  c.fillStyle = COL.bar; c.fillRect(wx, wy, ww, tb); c.fillRect(wx, wy + wh - sb, ww, sb);
  c.fillStyle = COL.rule; c.fillRect(wx, wy + tb - 2 * u, ww, 2 * u); c.fillRect(wx, wy + wh - sb, ww, 2 * u);
  c.restore();
  c.strokeStyle = COL.rule; c.lineWidth = 2 * u; c.beginPath(); c.roundRect(wx, wy, ww, wh, r); c.stroke();
  ['#FF5F57', '#FEBC2E', '#28C840'].forEach((col, i) => { c.fillStyle = col; c.beginPath(); c.arc(wx + (44 + i * 40) * u, wy + tb / 2, 11 * u, 0, 7); c.fill(); });
  TY.text(c, String(ctx.data.title || 'terminal'), wx + ww / 2, wy + tb / 2 + 11 * u, { size: 30 * u, fam: MONO, color: COL.dim, align: 'center' });
}
// one screen's rows: each row's height eases in, so the scroll that keeps the newest row in view is smooth
function screenRows(c, t, ctx, s, alpha, dy, live) {
  const { u, FPS } = ctx, { bx, by, bw, bh, fs, lh, cw } = L, mine = rows.filter(r => r.screen === s && t >= r.at - 1e-6);
  let y = 0; const items = mine.map(r => {
    let k = MO.cubicOut(clamp((t - r.at + 1 / FPS) / 0.18)); if (r.type === 'work') k *= 1 - MO.cubicOut(clamp((t - r.end + 1 / FPS) / 0.18));
    const it = { r, y, k, h: r.lines.length * lh * k }; y += it.h; return it;
  });
  const last = mine[mine.length - 1], typing = last && last.type === 'in' && t - last.at < last.typeDur + 0.25, working = mine.some(r => r.type === 'work' && t < r.end);
  const idle = live && !typing && !working && (!last || last.type === 'out');
  const idleK = idle ? MO.cubicOut(clamp(last ? (t - last.at - 0.3) / 0.2 : 1)) : 0;
  const sc = Math.max(0, y + (idleK > 0 ? lh : 0) - bh);
  c.save(); c.globalAlpha *= alpha; c.translate(0, dy - sc);
  for (const h of his) {                                             // boxes sit behind the text
    if (t < h.at - 1e-6 || t >= h.end || h.row.screen !== s) continue; const it = items.find(i => i.r === h.row); if (!it) continue;
    const p = MO.expoOut(clamp((t - h.at + 1 / FPS) / 0.3)), off = h.row.type === 'in' ? 2 * cw : 0, pulse = 0.5 + 0.5 * Math.sin((t - h.at) * 5);
    c.font = `${fs}px "${h.row.type === 'in' ? MONOB : MONO}"`;
    let x, w, yy, hh;
    if (h.j >= 0) { const ln = h.row.lines[h.j]; x = bx + off + c.measureText(ln.slice(0, h.k)).width; w = c.measureText(h.word).width; yy = by + it.y + h.j * lh; hh = lh; }
    else { x = bx; w = Math.min(bw, off + Math.max(...h.row.lines.map(l => c.measureText(l).width))); yy = by + it.y; hh = h.row.lines.length * lh; }
    c.save(); c.fillStyle = L.accent; c.globalAlpha *= 0.2 + 0.08 * pulse; c.beginPath(); c.roundRect(x - 12 * u, yy + 2 * u, (w + 24 * u) * p, hh - 4 * u, 10 * u); c.fill();
    c.globalAlpha = alpha * p; c.strokeStyle = L.accent; c.lineWidth = 3 * u; c.stroke(); c.restore();
  }
  for (const it of items) {
    const r = it.r, top = by + it.y, lt = t - r.at + 1 / FPS;
    if (r.type === 'in') {
      c.font = `${fs}px "${MONOB}"`; c.textBaseline = 'alphabetic'; c.textAlign = 'left';
      c.fillStyle = r.pre === '$' ? COL.ok : L.accent; c.fillText(r.pre, bx, top + fs * 1.06);
      const shown = Math.min(r.n, Math.floor(r.n * clamp(lt / r.typeDur) + 1e-6)); let used = 0, cxp = bx + 2 * cw, cyp = top;
      c.fillStyle = COL.fg;
      r.lines.forEach((ln, j) => { const take = clamp(shown - used, 0, ln.length); if (take > 0 || j === 0) { c.fillText(ln.slice(0, take), bx + 2 * cw, top + j * lh + fs * 1.06); cxp = bx + (2 + take) * cw; cyp = top + j * lh; } used += ln.length; });
      const isLast = live && last === r, blink = lt < r.typeDur + 0.25 || Math.floor((t - r.at) * 1.9) % 2 === 0;
      if (isLast && blink) { c.fillStyle = COL.fg; c.fillRect(cxp + 2 * u, cyp + fs * 0.2, cw * 0.62, fs * 1.02); }
    } else if (r.type === 'work') {
      const a = it.k, pulse = 0.55 + 0.45 * Math.sin(t * 7);
      c.save(); c.globalAlpha *= a; c.fillStyle = L.accent; c.globalAlpha *= pulse; c.beginPath(); c.arc(bx + cw * 0.5, top + lh * 0.52, fs * 0.2, 0, 7); c.fill(); c.restore();
      c.save(); c.globalAlpha *= a; c.font = `${fs}px "${MONO}"`; c.fillStyle = COL.dim; c.fillText('working' + '.'.repeat(1 + Math.floor(t * 3) % 3), bx + 2 * cw, top + fs * 1.06); c.restore();
    } else {
      const a = clamp(lt / 0.16), e = MO.cubicOut(a);
      c.save(); c.globalAlpha *= a;
      if (r.tint.band) { c.save(); c.globalAlpha *= 0.14; c.fillStyle = r.tint.band; c.fillRect(bx - 14 * u, top + 3 * u, bw + 28 * u, r.lines.length * lh - 6 * u); c.restore(); }
      c.font = `${fs}px "${MONO}"`; c.fillStyle = r.tint.color; c.textBaseline = 'alphabetic'; c.textAlign = 'left';
      r.lines.forEach((ln, j) => c.fillText(ln, bx + 14 * u * (1 - e), top + j * lh + fs * 1.06));
      c.restore();
    }
  }
  if (idleK > 0) {                                                   // an empty prompt waits under the output
    const pre = (mine.slice().reverse().find(r => r.type === 'in') || rows.find(r => r.type === 'in' && r.screen === s) || { pre: firstPre }).pre;
    c.save(); c.globalAlpha *= idleK; c.font = `${fs}px "${MONOB}"`; c.fillStyle = pre === '$' ? COL.ok : L.accent; c.fillText(pre, bx, by + y + fs * 1.06);
    if (Math.floor(t * 1.9) % 2 === 0) { c.fillStyle = COL.fg; c.fillRect(bx + 2 * cw + 2 * u, by + y + fs * 0.2, cw * 0.62, fs * 1.02); }
    c.restore();
  }
  c.restore();
}
function keycaps(c, t, ctx) {
  const { u } = ctx, K = keys.find(k => t >= k.at - 1e-6 && t < k.end); if (!K) return;
  const lt = ctx.lt(t, K.at), a = clamp(lt / 0.18) * (1 - clamp((t - (K.end - 0.2)) / 0.2));
  c.save(); c.globalAlpha = 0.78 * a; c.fillStyle = COL.win; c.fillRect(L.wx, L.wy + L.tb, L.ww, L.wh - L.tb - L.sb); c.restore();
  const fsz = 86 * u, kh = 196 * u, gapIn = 84 * u, gapOut = 60 * u, lip = 20 * u;
  c.font = `${fsz}px "${SANS}"`;
  const parts = []; let tw = 0;
  K.groups.forEach((grp, gi) => { if (gi) tw += gapOut; grp.forEach((name, ki) => { if (ki) tw += gapIn; const w = Math.max(kh, c.measureText(name).width + 96 * u); parts.push({ name, w, x: tw, gi, plus: ki > 0 }); tw += w; }); });
  const sc = Math.min(1, (L.bw * 0.94) / tw), cx = L.wx + L.ww / 2, cy = L.by + L.bh * 0.46;
  c.save(); c.translate(cx, cy); c.scale(sc, sc); c.translate(-tw / 2, -kh / 2);
  parts.forEach((p, i) => {
    const pop = MO.backOut(clamp((lt - i * 0.07) / 0.3), 2.0); if (pop <= 0) return;
    let down = 0, ring = -1;
    for (let tp = K.at + 0.5 + p.gi * 0.42; tp < K.end - 0.25; tp += 1.5) { const x = t - tp; if (x >= 0) { down = Math.max(down, x < 0.08 ? x / 0.08 : Math.max(0, 1 - (x - 0.08) / 0.22)); if (x < 0.5) ring = x / 0.5; } }
    if (p.plus) { c.save(); c.globalAlpha *= a; c.fillStyle = COL.dim; c.font = `${fsz * 0.9}px "${SANS}"`; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText('+', p.x - gapIn / 2, kh / 2); c.restore(); }
    c.save(); c.globalAlpha *= a; c.translate(p.x + p.w / 2, kh / 2); c.scale(pop, pop); c.translate(-p.w / 2, -kh / 2);
    if (ring >= 0) { c.save(); c.globalAlpha *= 1 - ring; c.strokeStyle = L.accent; c.lineWidth = 6 * u; c.beginPath(); c.roundRect(-ring * 26 * u, -ring * 26 * u, p.w + ring * 52 * u, kh + lip + ring * 52 * u, 30 * u); c.stroke(); c.restore(); }
    c.fillStyle = '#8B97A6'; c.beginPath(); c.roundRect(0, lip, p.w, kh, 26 * u); c.fill();
    const yy = lip * 0.85 * down; c.fillStyle = down > 0.3 ? L.accent : '#F3F6FA'; c.beginPath(); c.roundRect(0, yy, p.w, kh, 26 * u); c.fill();
    c.fillStyle = '#10151D'; c.font = `${fsz}px "${SANS}"`; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(p.name, p.w / 2, yy + kh / 2 + 4 * u);
    c.restore();
  });
  c.restore();
}
function statusbar(c, t, ctx) {
  const { u } = ctx, { wx, wy, ww, wh, sb } = L; let cur = null; for (const l of labels) if (t >= l.at - 1e-6) cur = l;
  if (!cur) return;
  const lt = ctx.lt(t, cur.at), size = 38 * u, cyy = wy + wh - sb / 2;
  const pause = /^\s*⏸/.test(cur.text), text = cur.text.replace(/^\s*⏸\s*/, ''), ic = pause ? 40 * u : 0;   // the pause sign is drawn: mono fonts lack the glyph
  c.font = `${size}px "${MONOB}"`; const tw = Math.min(ww - 110 * u - ic, c.measureText(text).width), pw = tw + 44 * u + ic, ph = 56 * u, x = wx + 24 * u;
  const pop = lerp(1.25, 1, MO.springHz(lt, 2.4, 9)), flash = Math.max(0, 1 - lt / 0.6);
  c.save(); c.translate(x + pw / 2, cyy); c.scale(pop, pop); c.translate(-pw / 2, 0);
  if (flash > 0) { c.save(); c.globalAlpha *= flash * 0.6; c.strokeStyle = L.accent; c.lineWidth = 5 * u; const g = (1 - flash) * 22 * u; c.beginPath(); c.roundRect(-g, -ph / 2 - g, pw + 2 * g, ph + 2 * g, 16 * u + g); c.stroke(); c.restore(); }
  c.fillStyle = L.accent; c.beginPath(); c.roundRect(0, -ph / 2, pw, ph, 14 * u); c.fill();
  c.fillStyle = '#10151D'; c.textAlign = 'left'; c.textBaseline = 'middle';
  if (pause) { c.fillRect(22 * u, -13 * u, 8 * u, 26 * u); c.fillRect(36 * u, -13 * u, 8 * u, 26 * u); }
  c.fillText(text, 22 * u + ic, 2 * u, tw);
  c.restore();
}
})();
