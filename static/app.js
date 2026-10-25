(() => {
  const root = document.getElementById('app');
  const S = { view: 'chat', bots: [], bot: null, msgs: [], health: {}, drawer: false, draft: '', busy: false,
    notes: [], note: null, q: '', status: '', graph: false, newNote: false, call: null, calls: [], approvals: [], audit: [], policies: [], verify: '', err: '' };
  let token = sessionStorage.getItem('cfa_token') || '';

  const h = (tag, a = {}, ...kids) => {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(a)) {
      if (k === 'class') el.className = v; else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
      else if (v === true) el.setAttribute(k, ''); else if (v !== false && v != null) el.setAttribute(k, v);
    }
    for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid);
    return el;
  };
  const btn = (t, f, cls = 'btn', extra = {}) => h('button', { class: cls, type: 'button', onclick: f, ...extra }, t);
  const NS = 'http://www.w3.org/2000/svg';
  function avatar(color, size = 40) {
    const c = /^#[0-9a-f]{6}$/i.test(color) ? color : '#12294F';
    const s = document.createElementNS(NS, 'svg'); s.setAttribute('width', size); s.setAttribute('height', size); s.setAttribute('viewBox', '0 0 40 40'); s.setAttribute('aria-hidden', 'true');
    const add = (n, at) => { const e = document.createElementNS(NS, n); for (const k in at) e.setAttribute(k, at[k]); s.append(e); };
    add('circle', { cx: 20, cy: 20, r: 20, fill: c }); add('circle', { cx: 14, cy: 17, r: 3.2, fill: '#F6F0E3' }); add('circle', { cx: 26, cy: 17, r: 3.2, fill: '#F6F0E3' });
    return s;
  }
  const when = (t) => (t || '').slice(0, 16).replace('T', ' ');

  async function api(path, opt = {}) {
    const headers = { 'Content-Type': 'application/json' }; if (token) headers.Authorization = 'Bearer ' + token;
    const r = await fetch(path, { method: opt.method || 'GET', headers, body: opt.body ? JSON.stringify(opt.body) : undefined });
    if (r.status === 401) { token = prompt('Workspace access password') || ''; sessionStorage.setItem('cfa_token', token); if (token) return api(path, opt); }
    if (!r.ok) { let d = ''; try { d = (await r.json()).detail; } catch {} throw new Error(typeof d === 'string' && d ? d : `Request failed (${r.status})`); }
    return r.json();
  }
  const run = async (f) => { S.err = ''; try { await f(); } catch (e) { S.err = e.message; } render(); };

  async function go(view) {
    S.view = view; S.drawer = false; S.err = '';
    render();
    await run(async () => {
      if (view === 'brain') S.notes = await api('/api/brain/notes?' + new URLSearchParams({ q: S.q, status: S.status }));
      if (view === 'council') S.calls = await api('/api/calls');
      if (view === 'control') [S.approvals, S.audit, S.policies] = await Promise.all([api('/api/security/approvals'), api('/api/security/audit?limit=15').then((d) => d.events || d.items || d), api('/api/security/policies').then((d) => d.policies)]);
    });
  }
  async function pick(id) {
    S.bot = S.bots.find((b) => b.id === id); S.view = 'chat'; S.drawer = false;
    await run(async () => { S.msgs = await api(`/api/bots/${id}/messages`); });
  }
  async function openNote(id) { S.view = 'brain'; S.drawer = false; await run(async () => { S.notes = await api('/api/brain/notes'); S.note = await api('/api/brain/notes/' + id); S.graph = false; }); }

  async function send() {
    const text = S.draft.trim(); if (!text || S.busy) return;
    S.draft = ''; S.busy = true; S.msgs.push({ role: 'user', content: text }); render();
    await run(async () => {
      try { const r = await api(`/api/bots/${S.bot.id}/messages`, { method: 'POST', body: { content: text } }); S.msgs.push({ role: 'agent', content: r.reply, note: r.draft_note_id }); }
      finally { S.busy = false; }
    });
  }

  // ---------- views ----------
  function chatView() {
    const b = S.bot; if (!b) return h('div', { class: 'body' }, h('p', { class: 'empty muted' }, 'Choose an agent.'));
    const ta = h('textarea', { rows: 1, placeholder: `Message ${b.name}`, 'aria-label': `Message ${b.name}` }); ta.value = S.draft;
    ta.addEventListener('input', () => { S.draft = ta.value; sendBtn.disabled = !ta.value.trim() || S.busy; ta.style.height = 'auto'; ta.style.height = ta.scrollHeight + 'px'; });
    ta.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } });
    const sendBtn = h('button', { class: 'send', type: 'button', 'aria-label': 'Send', disabled: !S.draft.trim() || S.busy, onclick: send }, '↑');
    return h('div', { style: 'display:flex;flex-direction:column;min-height:0;flex:1' },
      h('div', { class: 'bar' }, avatar(b.color, 32), h('h1', {}, `${b.name}`), h('span', { class: 'muted' }, b.role), h('span', { class: 'chip' }, b.model)),
      h('div', { class: 'body', id: 'scroll', 'aria-live': 'polite' }, h('div', { class: 'col msgs' },
        S.msgs.length ? S.msgs.map((m) => h('div', { class: 'msg ' + m.role }, m.content,
          m.note ? h('small', {}, btn('Saved to Brain as draft', () => openNote(m.note), 'link')) : null))
          : h('p', { class: 'empty muted' }, `Start a conversation with ${b.name}.`),
        S.busy ? h('div', { class: 'msg agent muted' }, `${b.name} is answering…`) : null)),
      h('div', { class: 'composer' }, h('div', { class: 'col' }, ta, sendBtn)));
  }

  const STANCE = { support: 'Support', oppose: 'Oppose', unsure: 'Unsure' };
  function councilView() {
    const topic = h('textarea', { class: 'field', rows: 3, placeholder: 'What should the agents decide? Include goal, constraints and what a good answer looks like.', maxlength: 2000 });
    const picks = S.bots.filter((b) => b.id !== 'chair').map((b) => h('label', { class: 'row' }, h('input', { type: 'checkbox', value: b.id, checked: true }), b.name));
    const rounds = h('select', { class: 'field', style: 'width:auto' }, [1, 2, 3].map((n) => h('option', { value: n }, `${n} discussion round${n > 1 ? 's' : ''}`)));
    const start = btn('Start call', () => run(async () => {
      const ids = picks.map((l) => l.firstChild).filter((i) => i.checked).map((i) => i.value);
      S.call = 'running'; render();
      try { S.call = await api('/api/calls', { method: 'POST', body: { topic: topic.value, bot_ids: ids, rounds: +rounds.value } }); S.calls = await api('/api/calls'); }
      catch (e) { S.call = null; throw e; }
    }), 'btn primary');
    const c = S.call;
    const result = c === 'running' ? h('p', { class: 'muted', role: 'status' }, 'The agents are in the call…') : c ? [
      c.mode === 'demo' ? h('p', { class: 'chip warn' }, 'Demo mode: scripted text. No model is configured.') : null,
      ...[...new Set(c.events.map((e) => e.round))].map((r) => [
        h('div', { class: 'rnd' }, r === 0 ? 'Independent openings (no agent saw the others)' : `Discussion round ${r}`),
        c.events.filter((e) => e.round === r).map((e) => h('div', { class: 'turn' }, avatar((S.bots.find((b) => b.id === e.bot_id) || {}).color, 32),
          h('div', { class: 't' }, h('b', {}, e.name + ' '), h('span', { class: 'chip' }, STANCE[e.stance]), e.revised ? h('span', { class: 'chip ok' }, ' changed position') : null, h('div', {}, e.text))))]),
      h('h2', {}, 'Disagreement map'),
      h('table', {}, h('thead', {}, h('tr', {}, h('th', {}, 'Agent'), ...(Object.values(c.map)[0] || []).map((_, i) => h('th', {}, i === 0 ? 'Opening' : `Round ${i}`)))),
        h('tbody', {}, Object.entries(c.map).map(([n, st]) => h('tr', {}, h('td', {}, n), ...st.map((s) => h('td', {}, STANCE[s])))))),
      h('h2', {}, 'Decision'), h('div', { class: 'notebody' }, c.decision),
      h('p', { class: 'muted' }, 'Memory from this call is stored as drafts. ', btn('Review in Brain', () => openNote(c.draft_note_ids[0]), 'link'))] : null;
    return h('div', { class: 'body' }, h('div', { class: 'col' },
      h('h2', { style: 'margin-top:0' }, 'Council call'),
      h('p', { class: 'muted' }, 'Agents answer independently first, then respond to each other and may change their position. Dissent stays in the record.'),
      topic, h('div', { style: 'margin:10px 0' }, picks), h('div', { style: 'display:flex;gap:10px;align-items:center' }, rounds, start), result,
      S.calls.length ? [h('h2', {}, 'Previous calls'), S.calls.map((x) => h('div', {}, btn(x.topic, () => run(async () => { S.call = await api('/api/calls/' + x.id); }), 'link'), h('span', { class: 'muted mono' }, ' ' + when(x.created_at) + ' ' + x.mode)))] : null));
  }

  function noteBody(n) {
    const box = h('div', { class: 'notebody' });
    n.body.split(/(\[\[[^\[\]]+\]\])/).forEach((part) => {
      const m = part.match(/^\[\[(.+)\]\]$/); const t = m && S.notes.find((x) => x.title === m[1]);
      box.append(t ? btn(m[1], () => openNote(t.id), 'link') : part);
    });
    return box;
  }
  function graphView() {
    const el = h('div', { class: 'notebody' }); el.textContent = 'Loading graph…';
    api('/api/brain/graph').then((g) => {
      const W = 520, H = 380, cx = W / 2, cy = H / 2, R = 150, pos = {};
      g.nodes.forEach((n, i) => { const a = (2 * Math.PI * i) / Math.max(g.nodes.length, 1); pos[n.id] = [cx + R * Math.cos(a), cy + R * Math.sin(a)]; });
      const s = document.createElementNS(NS, 'svg'); s.setAttribute('viewBox', `0 0 ${W} ${H}`); s.setAttribute('width', '100%');
      const add = (n, at, txt) => { const e = document.createElementNS(NS, n); for (const k in at) e.setAttribute(k, at[k]); if (txt) e.textContent = txt; s.append(e); return e; };
      g.edges.forEach((e) => add('line', { x1: pos[e.from][0], y1: pos[e.from][1], x2: pos[e.to][0], y2: pos[e.to][1], stroke: 'currentColor', 'stroke-opacity': '.3' }));
      g.nodes.forEach((n) => { const [x, y] = pos[n.id]; const c = add('circle', { cx: x, cy: y, r: 7, fill: n.status === 'verified' ? 'currentColor' : 'none', stroke: 'currentColor', style: 'cursor:pointer' });
        c.addEventListener('click', () => openNote(n.id)); add('text', { x: x + 10, y: y + 4, 'font-size': 10, fill: 'currentColor' }, n.title.slice(0, 22)); });
      el.replaceChildren(g.nodes.length ? s : 'No notes yet.', h('p', { class: 'muted' }, 'Filled circle = verified. Hollow = draft or rejected. Lines are [[links]].'));
    }).catch((e) => { el.textContent = e.message; });
    return el;
  }
  function brainView() {
    const q = h('input', { class: 'field', placeholder: 'Search notes', value: S.q, 'aria-label': 'Search notes' });
    q.addEventListener('keydown', (e) => { if (e.key === 'Enter') { S.q = q.value; go('brain'); } });
    const filt = ['', 'draft', 'verified'].map((s) => btn(s || 'All', () => { S.status = s; go('brain'); }, 'chip' + (S.status === s ? ' ok' : ''), { 'aria-pressed': S.status === s }));
    const n = S.note;
    let right;
    if (S.newNote) {
      const t = h('input', { class: 'field', placeholder: 'Title' }), b = h('textarea', { class: 'field', rows: 8, placeholder: 'Write in Markdown. Link with [[Other note]].' });
      const k = h('select', { class: 'field', style: 'width:auto' }, ['note', 'fact', 'decision', 'rule', 'hypothesis'].map((x) => h('option', {}, x)));
      right = h('div', {}, t, h('div', { style: 'height:8px' }), b, h('div', { style: 'display:flex;gap:8px;margin-top:8px' }, k, btn('Save note', () => run(async () => { const r = await api('/api/brain/notes', { method: 'POST', body: { title: t.value, body: b.value, kind: k.value } }); S.newNote = false; S.notes = await api('/api/brain/notes'); S.note = r; }), 'btn primary')));
    } else if (S.graph) right = graphView();
    else if (n) right = h('div', {}, h('h2', { style: 'margin-top:0' }, n.title),
      h('p', {}, h('span', { class: 'chip' }, n.kind), ' ', h('span', { class: 'chip ' + (n.status === 'verified' ? 'ok' : n.status === 'rejected' ? 'warn' : '') }, n.status), h('span', { class: 'muted mono' }, ` by ${n.owner} · ${n.source}`)),
      noteBody(n),
      n.status === 'draft' ? h('p', { class: 'muted' }, 'Drafts are never used in agent prompts until an admin verifies them.') : null,
      n.status === 'draft' ? h('div', { style: 'display:flex;gap:8px' }, ['verify', 'reject'].map((a) => btn(a === 'verify' ? 'Verify' : 'Reject', () => run(async () => { S.note = await api(`/api/brain/notes/${n.id}/${a}`, { method: 'POST' }); S.notes = await api('/api/brain/notes'); }), a === 'verify' ? 'btn primary' : 'btn'))) : null,
      n.backlinks && n.backlinks.length ? [h('h2', {}, 'Linked from'), n.backlinks.map((t) => { const x = S.notes.find((y) => y.title === t); return h('div', {}, x ? btn(t, () => openNote(x.id), 'link') : t); })] : null);
    else right = h('p', { class: 'muted' }, 'Select a note. Agent memory from chats and calls arrives here as drafts.');
    return h('div', { class: 'body' }, h('div', { class: 'col', style: 'max-width:1000px' },
      h('div', { style: 'display:flex;gap:8px;margin-bottom:14px' }, btn('New note', () => { S.newNote = true; S.graph = false; render(); }), btn(S.graph ? 'Notes' : 'Graph', () => { S.graph = !S.graph; S.newNote = false; render(); })),
      h('div', { class: 'split' }, h('div', { class: 'list' }, q, h('div', { style: 'margin:8px 0;display:flex;gap:6px' }, filt),
        S.notes.length ? S.notes.map((x) => h('button', { class: 'item', type: 'button', 'aria-current': n && n.id === x.id ? 'true' : false, onclick: () => openNote(x.id) }, x.title, h('small', { class: 'muted', style: 'display:block' }, `${x.kind} · ${x.status}`))) : h('p', { class: 'muted' }, 'No notes.')), right)));
  }

  function controlView() {
    return h('div', { class: 'body' }, h('div', { class: 'col' },
      h('h2', { style: 'margin-top:0' }, 'Approval queue'),
      h('p', { class: 'muted' }, 'Approvals record a human decision. They do not execute tools.'),
      S.approvals.filter((a) => a.status === 'pending').length ? S.approvals.filter((a) => a.status === 'pending').map((a) => h('div', { class: 'turn' }, h('div', { class: 't' }, h('b', {}, a.action_type), ` (${a.risk_level}): ${a.description}`,
        h('div', { style: 'display:flex;gap:8px;margin-top:8px' }, ['approved', 'rejected'].map((d) => btn(d === 'approved' ? 'Approve' : 'Reject', () => run(async () => { await api(`/api/security/approvals/${a.id}/decision`, { method: 'POST', body: { decision: d, decided_by: 'ui' } }); await go('control'); }), 'btn')))))) : h('p', { class: 'muted' }, 'Nothing pending.'),
      h('h2', {}, 'Policies'), h('table', {}, h('tbody', {}, (S.policies || []).map((p) => h('tr', {}, h('td', { class: 'mono' }, p.action_type), h('td', {}, p.decision))))),
      h('h2', {}, 'Audit log'), btn('Verify integrity', () => run(async () => { const v = await api('/api/security/audit/verify'); S.verify = v.valid ? `Chain intact (${v.checked ?? v.events ?? '?'} events). This detects edits; it is not an external signature.` : 'Chain broken: ' + JSON.stringify(v); })),
      S.verify ? h('p', { class: 'muted' }, S.verify) : null,
      h('table', {}, h('tbody', {}, (Array.isArray(S.audit) ? S.audit : []).map((e) => h('tr', {}, h('td', { class: 'mono' }, when(e.created_at)), h('td', {}, e.event_type), h('td', {}, e.actor))))),
      h('h2', {}, 'Playbooks'), h('a', { class: 'link', href: '/review/agent-launch' }, 'Agent launch review (go / no-go for an AI agent)')));
  }

  function drawer() {
    const item = (label, view, extra) => h('button', { class: 'item', type: 'button', 'aria-current': S.view === view && !extra ? 'true' : false, onclick: () => (extra ? pick(extra) : go(view)) }, label);
    return [h('div', { class: 'scrim', onclick: () => { S.drawer = false; render(); } }),
      h('nav', { class: 'drawer', 'aria-label': 'Menu' },
        h('div', { class: 'm-only' }, h('h3', {}, 'Agents'), S.bots.map((b) => item(b.name, 'chat', b.id))),
        h('h3', {}, 'Council'), item('Start a call', 'council'),
        h('h3', {}, 'Brain'), item('Notes and graph', 'brain'),
        h('h3', {}, 'Control'), item('Approvals, policies, audit', 'control'))];
  }

  function render() {
    const hd = S.health;
    const side = h('aside', { class: 'side' },
      h('div', { class: 'side-top' }, h('button', { class: 'ibtn', type: 'button', 'aria-label': 'Menu', 'aria-expanded': S.drawer, onclick: () => { S.drawer = !S.drawer; render(); } }, '☰'), h('span', { class: 'sp' }),
        h('button', { class: 'ibtn', type: 'button', 'aria-label': 'Search notes', onclick: () => go('brain') }, '⌕'),
        h('button', { class: 'ibtn', type: 'button', 'aria-label': 'New council call', onclick: () => { S.call = null; go('council'); } }, '+')),
      h('div', { class: 'agents' }, S.bots.map((b) => h('button', { class: 'agent', type: 'button', 'aria-current': S.view === 'chat' && S.bot && S.bot.id === b.id ? 'true' : false, onclick: () => pick(b.id) },
        avatar(b.color), h('span', {}, h('b', {}, `${b.name}`), h('small', {}, b.preview || b.role))))),
      h('div', { class: 'side-foot' }, h('div', {}, hd.model_configured ? 'Model connected' : 'No model configured (demo mode)'), h('div', {}, hd.auth === 'enabled' ? 'Access token required' : 'Open dev mode: no authentication'), hd.storage_warning ? h('div', {}, 'Storage is temporary on this host') : null));
    const view = { chat: chatView, council: councilView, brain: brainView, control: controlView }[S.view]();
    root.replaceChildren(h('div', { class: 'shell' }, side, h('main', { class: 'main' }, S.err ? h('div', { class: 'banner', role: 'alert' }, S.err) : null, view)), ...(S.drawer ? drawer() : []));
    const sc = document.getElementById('scroll'); if (sc) sc.scrollTop = sc.scrollHeight;
  }
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && S.drawer) { S.drawer = false; render(); } });

  (async () => {
    try { [S.health, S.bots] = await Promise.all([api('/api/health'), api('/api/bots')]); S.bot = S.bots[0]; S.msgs = await api(`/api/bots/${S.bot.id}/messages`); }
    catch (e) { S.err = e.message; }
    render();
  })();
})();
