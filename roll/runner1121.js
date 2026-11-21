// Etsy carousel rollout runner (CAR1121) — runs in the top page, edits each listing in an iframe.
(() => {
  if (window.__RR && window.__RR.running) return 'already running';
  const LS = '__roll1121';
  const URLS = {
    VP: 'https://res.cloudinary.com/rntnboij/video/upload/v1795294632/pikachu_holographic.mp4',
    VF: 'https://res.cloudinary.com/rntnboij/video/upload/v1795295488/finishes_3s.mp4',
    HOW: 'https://res.cloudinary.com/rntnboij/image/upload/v1795231347/info_how_to_order.jpg',
    MIX: 'https://res.cloudinary.com/rntnboij/image/upload/v1795293025/info_mix_and_match_v2.jpg',
  };
  const VIDLINE = '📹 Videos: Holographic finish, then Triangle, Stars and Dots Holo.';
  // timers via a Worker: not throttled when the pane is in the background
  const TW = (() => { try { const w = new Worker(URL.createObjectURL(new Blob(['onmessage=e=>setTimeout(()=>postMessage(e.data),e.data.ms)'], { type: 'text/javascript' }))); const cb = {}; let n = 0; w.onmessage = e => { const f = cb[e.data.id]; delete cb[e.data.id]; f && f(); }; return ms => new Promise(r => { const id = ++n; cb[id] = r; w.postMessage({ id, ms }); }); } catch (e) { return ms => new Promise(r => setTimeout(r, ms)); } })();
  const sleep = async ms => { await TW(ms); if (window.__RR && window.__RR.abort) throw new Error('aborted (timeout)'); };
  const until = async (fn, ms = 10000, step = 150) => { const t = Date.now(); while (Date.now() - t < ms) { let v; try { v = fn(); } catch (e) { v = null; } if (v) return v; await sleep(step); } return null; };
  const st = () => { try { return JSON.parse(localStorage.getItem(LS) || '{}'); } catch (e) { return {}; } };
  const save = s => { try { localStorage.setItem(LS, JSON.stringify(s)); } catch (e) {} };
  const R = window.__RR = { running: false, stop: false, cur: null, log: [], blobs: {}, q: null };

  // ---------- UI ----------
  let box = document.getElementById('__rr_box');
  if (!box) {
    box = document.createElement('div'); box.id = '__rr_box';
    box.style.cssText = 'position:fixed;inset:0;z-index:2147483646;background:#fff;display:flex;flex-direction:column';
    box.innerHTML = '<div id="__rr_bar" style="font:13px/1.4 -apple-system,Arial;padding:6px 10px;background:#222;color:#fff;white-space:pre-wrap"></div><div id="__rr_frame" style="flex:1;position:relative"></div>';
    document.body.appendChild(box);
  }
  const bar = t => { const b = document.getElementById('__rr_bar'); if (b) b.textContent = t; };

  // ---------- helpers that work in the iframe realm ----------
  function H(w) {
    const doc = w.document;
    const setVal = (el, v) => { const P = el.tagName === 'TEXTAREA' ? w.HTMLTextAreaElement.prototype : w.HTMLInputElement.prototype; Object.getOwnPropertyDescriptor(P, 'value').set.call(el, v); el.dispatchEvent(new w.Event('input', { bubbles: true })); el.dispatchEvent(new w.Event('change', { bubbles: true })); };
    const setSel = (el, v) => { Object.getOwnPropertyDescriptor(w.HTMLSelectElement.prototype, 'value').set.call(el, v); el.dispatchEvent(new w.Event('change', { bubbles: true })); };
    const kd = (el, key, code) => el.dispatchEvent(new w.KeyboardEvent('keydown', { key, code, bubbles: true, cancelable: true }));
    const grid = () => [...doc.querySelectorAll('[aria-roledescription=sortable]')].map(e => ({ id: e.id, v: !!e.querySelector('video') || !!e.querySelector('[data-testid=video-delete-button]') }));
    const ids = () => { const seen = new Set(); return grid().map(g => g.id).filter(x => !seen.has(x) && seen.add(x)); };
    const dlgPhoto = () => [...doc.querySelectorAll('[role=dialog]')].find(x => x.getBoundingClientRect().height > 50 && /Photo and video/.test(x.innerText));
    const btnIn = (root, txt) => root && [...root.querySelectorAll('button')].find(b => b.innerText.trim() === txt);
    return { doc, setVal, setSel, kd, grid, ids, dlgPhoto, btnIn };
  }

  async function blob(k) { if (!R.blobs[k]) { const r = await fetch(URLS[k]); if (!r.ok) throw new Error('fetch ' + k + ' ' + r.status); R.blobs[k] = await r.blob(); } return R.blobs[k]; }

  async function pubInfo(id) {
    const r = await fetch('/listing/' + id + '?_=' + Date.now(), { credentials: 'include', cache: 'no-store' });
    const h = await r.text();
    const doc = new DOMParser().parseFromString(h, 'text/html');
    const m = h.match(/"image_ids_by_listing_variation_ids":(\{[^}]*\})/);
    const map = m ? JSON.parse(m[1]) : {};
    const opts = {}; doc.querySelectorAll('select[id^=variation-selector]').forEach(s => [...s.options].forEach(o => { if (o.value) opts[o.value] = o.textContent.trim(); }));
    const seq = []; for (const li of doc.querySelectorAll('li[data-index], li[data-carousel-pane]')) { const v = li.querySelector('video,source'); const im = li.querySelector('img'); const src = im ? (im.getAttribute('src') || im.getAttribute('data-src') || '') : ''; const iid = (src.match(/\/(\d{9,})\//) || [])[1]; if (v) seq.push('V'); else if (iid) seq.push(iid); else break; }
    let alts = {}; for (const s of doc.querySelectorAll('script[type="application/ld+json"]')) { try { const j = JSON.parse(s.textContent); for (const o of (Array.isArray(j) ? j : [j])) if (Array.isArray(o.image)) for (const im of o.image) { const iid = ((im.contentURL || '').match(/\/(\d{9,})\//) || [])[1]; if (iid) alts[iid] = im.description || ''; } } catch (e) {} }
    return { status: r.status, map, opts, seq, alts, vidline: h.includes('📹 Videos: Holographic finish') };
  }

  async function loadEditor(id) {
    const holder = document.getElementById('__rr_frame');
    holder.innerHTML = '';
    const f = document.createElement('iframe');
    f.style.cssText = 'width:100%;height:100%;border:0';
    holder.appendChild(f);
    f.src = '/your/shops/me/listing-editor/edit/' + id;
    const ok = await until(() => { const d = f.contentDocument; return d && d.querySelectorAll('[aria-roledescription=sortable]').length && d.getElementById('listing-description-textarea') && d.querySelector('input[name=listing-media-upload]'); }, 45000, 300);
    if (!ok) throw new Error('editor did not load');
    await sleep(1500);
    return f;
  }

  async function delTile(h, id) {
    const e = h.doc.getElementById(String(id)); if (!e) return 'missing';
    const b = e.querySelector('[data-testid=image-delete-button],[data-testid=video-delete-button]');
    if (!b) throw new Error('no delete button ' + id);
    b.click();
    const gone = await until(() => !h.doc.getElementById(String(id)), 8000);
    if (!gone) throw new Error('delete failed ' + id);
    await sleep(250);
    return 'ok';
  }

  async function upload(w, h, k, name, type) {
    const before = new Set(h.ids());
    const b = await blob(k);
    const inp = h.doc.querySelector('input[name=listing-media-upload]');
    const dt = new w.DataTransfer(); dt.items.add(new w.File([b], name, { type }));
    inp.files = dt.files; inp.dispatchEvent(new w.Event('change', { bubbles: true }));
    const nid = await until(() => h.ids().find(x => !before.has(x) && /^\d+$/.test(x)), 120000, 400);
    if (!nid) throw new Error('upload timeout ' + k);
    await sleep(500);
    return nid;
  }

  const dragging = h => !!h.doc.querySelector('[aria-roledescription=sortable][aria-pressed=true]');
  async function endDrag(h) { if (!dragging(h)) return; const a = h.doc.activeElement || h.doc.body; h.kd(a, 'Escape', 'Escape'); await until(() => !dragging(h), 2500, 100); await sleep(300); }
  const liveTxt = h => { const r = h.doc.querySelector('[id^=DndLiveRegion]'); return r ? r.textContent.trim() : ''; };
  async function step(h, id, dir) {
    await endDrag(h);
    const e = h.doc.getElementById(id); e.focus({ preventScroll: true }); await sleep(300);
    h.kd(e, ' ', 'Space');
    if (!await until(() => dragging(h), 2000, 100)) return false;
    await sleep(300);
    for (let n = 0; n < 6; n++) {
      h.kd(h.doc.activeElement || e, dir, dir); await sleep(450);
      const m = liveTxt(h).match(/moved over droppable area (\d+)/);
      if (m && m[1] !== id) break;
    }
    h.kd(h.doc.activeElement || e, ' ', 'Space');
    await until(() => !dragging(h), 2500, 100);
    await endDrag(h);
    await sleep(400);
    return true;
  }
  async function moveTo(h, id, target) {
    let tries = 0, lastJ = -1, still = 0;
    while (true) {
      const ids = h.ids(); const j = ids.indexOf(String(id));
      if (j < 0) throw new Error('move: missing ' + id);
      if (j === target) return;
      if (++tries > (Math.abs(j - target) + 4) * 4) throw new Error('move stuck ' + id + ' at ' + j + ' want ' + target);
      still = (j === lastJ) ? still + 1 : 0; lastJ = j;
      let dir = j > target ? 'ArrowLeft' : 'ArrowRight';
      if (still >= 2) { dir = j > target ? 'ArrowUp' : 'ArrowDown'; still = 0; }
      await step(h, String(id), dir);
    }
  }

  async function setAlt(h, id, val) {
    const e = h.doc.getElementById(String(id)); if (!e) throw new Error('alt: missing ' + id);
    e.querySelector('button.le-media-grid__item').click();
    const pd = await until(h.dlgPhoto, 8000); if (!pd) throw new Error('alt: no photo dialog');
    h.btnIn(pd, 'Alt text').click();
    const ta = await until(() => h.doc.getElementById('alt-text-input'), 8000); if (!ta) throw new Error('alt: no textarea');
    const old = ta.value;
    if (old !== val) h.setVal(ta, val);
    await sleep(200);
    const ad = ta.closest('[role=dialog]');
    h.btnIn(ad, old !== val ? 'Apply' : 'Cancel').click();
    await until(() => !h.doc.getElementById('alt-text-input'), 6000);
    await sleep(250);
    const pd2 = h.dlgPhoto(); if (pd2) { h.btnIn(pd2, 'Done').click(); await until(() => !h.dlgPhoto(), 6000); }
    await sleep(250);
    return old === val ? 'same' : 'set';
  }

  async function processOne(q) {
    const T = q.nt || q.t; const iss = []; const t0 = Date.now();
    const altOf = iid => T + (q.sfx[String(iid)] ? ' – ' + q.sfx[String(iid)] : '');
    const pre = await pubInfo(q.id);
    // option -> photo check (before)
    for (const [vid, lab] of Object.entries(pre.opts)) {
      const md = lab.match(/^Design (\d+)/); if (!md) continue;
      const img = pre.map[vid];
      if (!img) { iss.push('sin foto: ' + lab); continue; }
      const sx = q.sfx[String(img)] || '';
      if (!new RegExp('^Design ' + md[1] + '\\b').test(sx)) iss.push('liga dudosa: ' + lab + ' -> ' + img + ' (' + (sx || 'sin sufijo') + ')');
    }
    const f = await loadEditor(q.id); const w = f.contentWindow; const h = H(w);
    bar(`${R.pos}/${R.q.length} · ${T}\nborrando videos y fotos de acabados…`);
    const g0 = h.grid(); const imgs0 = g0.filter(x => !x.v).map(x => x.id);
    const known = new Set([...q.keep, ...q.del, ...(q.how ? [q.how] : [])].map(String));
    const unknown = imgs0.filter(x => !known.has(x));
    const missingKeep = q.keep.map(String).filter(x => !imgs0.includes(x));
    if (missingKeep.length) throw new Error('fotos de diseño cambiaron: faltan ' + missingKeep.join(','));
    if (unknown.length) iss.push('fotos extra no planeadas (se dejan al final): ' + unknown.join(','));
    // 1. delete videos + finish photos + old mix
    for (const g of h.grid().filter(x => x.v)) await delTile(h, g.id);
    for (const id of q.del) if (h.doc.getElementById(String(id))) await delTile(h, id);
    // 2. uploads
    bar(`${R.pos}/${R.q.length} · ${T}\nsubiendo videos e infografías…`);
    const vp = await upload(w, h, 'VP', 'pikachu_holographic.mp4', 'video/mp4');
    const vf = await upload(w, h, 'VF', 'finishes_3s.mp4', 'video/mp4');
    const how = q.how ? String(q.how) : await upload(w, h, 'HOW', 'how_to_order.jpg', 'image/jpeg');
    const mix = await upload(w, h, 'MIX', 'mix_and_match.jpg', 'image/jpeg');
    // 3. order
    bar(`${R.pos}/${R.q.length} · ${T}\nacomodando carrusel…`);
    const target = [String(q.keep[0]), vp, vf, ...q.keep.slice(1).map(String), ...unknown, how, mix];
    for (let i = 0; i < target.length; i++) await moveTo(h, target[i], i);
    const ord = h.ids();
    if (ord.join(',') !== target.join(',')) throw new Error('orden final distinto: ' + ord.join(','));
    // 4. alt text
    bar(`${R.pos}/${R.q.length} · ${T}\nalt text…`);
    for (const iid of q.chg) await setAlt(h, iid, altOf(iid));
    if (q.how && q.hc) await setAlt(h, q.how, '');
    // 5. title (EX fix), description, section
    const D = h.doc;
    if (q.nt) { const ti = D.getElementById('listing-title-input'); if (ti && ti.value !== q.nt) h.setVal(ti, q.nt); const te = D.getElementById('field-translations-0.title-input'); if (te && te.value !== q.nt) h.setVal(te, q.nt); }
    const fix = s => s.replace(/📹[^\n]*/, VIDLINE).replace(/\b(1,000|800)\+ designs/g, '2,500+ designs');
    for (const tid of ['listing-description-textarea', 'listing-en-US-translation-description-textarea']) { const ta = D.getElementById(tid); if (ta) { const nv = fix(ta.value); if (nv !== ta.value) h.setVal(ta, nv); if (!ta.value.includes(VIDLINE)) iss.push('descripción sin línea de video (' + tid + ')'); } }
    if (q.sec) { const s = D.getElementById('shop-section-select'); if (s && s.value !== String(q.sec)) h.setSel(s, String(q.sec)); }
    await sleep(600);
    // 6. publish
    bar(`${R.pos}/${R.q.length} · ${T}\npublicando…`);
    const pb = [...D.querySelectorAll('button')].find(b => /^Publish changes$/.test(b.innerText.trim()));
    if (!pb) throw new Error('no publish button');
    pb.click();
    const left = await until(() => { try { return !/listing-editor/.test(w.location.pathname); } catch (e) { return true; } }, 60000, 500);
    if (!left) { const errs = [...D.querySelectorAll('[role=alert],.wt-alert,.wt-validation__message')].map(e => e.innerText.trim()).filter(Boolean).slice(0, 3).join(' | '); throw new Error('no se publicó: ' + (errs || 'sin mensaje')); }
    document.getElementById('__rr_frame').innerHTML = '';
    // 7. verify public page
    bar(`${R.pos}/${R.q.length} · ${T}\nverificando…`);
    const expSeq = [String(q.keep[0]), 'V', 'V', ...q.keep.slice(1).map(String), ...unknown, how, mix];
    let post = null, okSeq = false;
    for (let k = 0; k < 4 && !okSeq; k++) { await sleep(k ? 15000 : 3000); post = await pubInfo(q.id); okSeq = post.seq.slice(0, expSeq.length).join(',') === expSeq.join(',') && post.seq.length === expSeq.length; }
    if (!okSeq) iss.push('VERIFICAR orden público: ' + post.seq.join(','));
    if (JSON.stringify(post.map) !== JSON.stringify(pre.map)) iss.push('VERIFICAR ligas cambiaron: ' + JSON.stringify(pre.map) + ' -> ' + JSON.stringify(post.map));
    for (const iid of q.keep) { const a = post.alts[String(iid)]; if (a !== undefined && a !== altOf(iid)) iss.push('alt distinto ' + iid); }
    if (!post.vidline) iss.push('VERIFICAR línea de video en descripción pública');
    return { st: iss.some(x => x.startsWith('VERIFICAR') || x.startsWith('liga') || x.startsWith('sin foto')) ? 'revisar' : 'ok', iss, s: Math.round((Date.now() - t0) / 1000), vp, vf, how, mix };
  }

  R.start = async function (queue, opts = {}) {
    if (R.running) return 'running';
    R.q = queue; R.running = true; R.stop = false;
    const s = st(); s.res = s.res || {};
    let n = 0;
    try {
      for (let i = 0; i < queue.length; i++) {
        if (R.stop) break;
        const q = queue[i]; R.pos = i + 1; R.cur = q.id;
        const prev = s.res[q.id];
        if (prev && (prev.st === 'ok' || prev.st === 'revisar')) continue;
        if (opts.limit && n >= opts.limit) break;
        n++;
        let res;
        try { R.abort = false; const wd = setTimeout(() => { R.abort = true; }, 8 * 60 * 1000); try { res = await processOne(q); } finally { clearTimeout(wd); R.abort = false; } }
        catch (e) { res = { st: 'fallo', err: String(e && e.message || e).slice(0, 300) }; document.getElementById('__rr_frame').innerHTML = ''; await sleep(3000); }
        res.t = new Date().toISOString(); res.i = i + 1;
        s.res[q.id] = res; save(s);
        R.log.push([q.id, res.st, res.err || (res.iss || []).join(' ; ')]);
        const vals = Object.values(s.res); const c = st => vals.filter(v => v.st === st).length;
        bar(`${i + 1}/${queue.length} hecho · ok ${c('ok')} · revisar ${c('revisar')} · fallos ${c('fallo')} · último: ${q.t.slice(0, 50)} (${res.st}${res.s ? ', ' + res.s + ' s' : ''})`);
        if (R.log.slice(-5).length === 5 && R.log.slice(-5).every(x => x[1] === 'fallo')) { bar('5 fallos seguidos: me detuve. ' + R.log.slice(-1)[0][2]); break; }
      }
    } finally { R.running = false; }
    return 'done';
  };
  return 'runner ready';
})();
