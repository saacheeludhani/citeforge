/* CiteForge live runner: connects the landing page to the backend (server.py -> citeforge.py).
   All server/LLM text is untrusted: it is only ever inserted with textContent or validated href values. */
(function () {
  'use strict';
  var meta = document.querySelector('meta[name="citeforge-api"]');
  var API = ((meta && meta.content) || '').replace(/\/$/, '');          // '' = same origin
  var $ = function (id) { return document.getElementById(id); };
  var form = $('lf'); if (!form) return;
  var go = $('lgo'), banner = $('lbanner'), prog = $('lprog'), bar = $('lbi'), msg = $('lmsg'), res = $('lres');
  var busy = false, backendOk = false;

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function safeUrl(u) { return /^https?:\/\//i.test(u || '') ? u : ''; }
  function pct(x) { return Math.round((x || 0) * 100) + '%'; }
  function note(text, kind) { banner.hidden = !text; banner.textContent = text || ''; banner.className = 'lnote' + (kind ? ' ' + kind : ''); }
  function api(path, opt) {
    return fetch(API + path, opt).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (j) {
        if (!r.ok) throw new Error(j.error || ('Server error ' + r.status));
        return j;
      });
    });
  }

  /* ---------- backend status ---------- */
  api('/api/health').then(function (h) {
    backendOk = true;
    if (h.mode !== 'LIVE') note('Backend is running in OFFLINE mode (' + (h.reason || 'no API key') + '). Add GEMINI_API_KEY to .env and restart server.py for real research, claim checks and citation tests. Offline runs only produce a placeholder skeleton.', 'warn');
    else note('', '');
    go.disabled = false;
  }).catch(function () {
    backendOk = false; go.disabled = true;
    note('Backend not reachable. Start it with "python server.py" and open http://127.0.0.1:8000/ (the simulation below still works without it).', 'warn');
  });
  go.disabled = true;

  /* ---------- run a job ---------- */
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    if (busy || !backendOk) return;
    var topic = $('lt').value.trim(), url = $('lu').value.trim();
    if (topic.length < 3) { note('Enter a topic of at least 3 characters.', 'warn'); $('lt').focus(); return; }
    busy = true; go.disabled = true; go.textContent = 'Running\u2026'; res.hidden = true; note('', '');
    setProgress(2, 'Starting');
    api('/api/jobs', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic: topic, url: url, rounds: 2, sample: url ? 6 : 0, max_claims: 8 }) })
      .then(function (j) { return poll(j.job_id, 0); })
      .then(function (job) { setProgress(100, 'Done'); render(job.result, job.id); applyToPage(job.result); })
      .catch(function (err) { prog.hidden = true; note('Run failed: ' + err.message, 'bad'); })
      .then(function () { busy = false; go.disabled = !backendOk; go.textContent = 'Run pipeline \u2197'; });
  });

  function setProgress(p, text) { prog.hidden = false; bar.style.width = Math.max(2, Math.min(100, p || 0)) + '%'; msg.textContent = text; }

  function poll(id, fails) {
    return new Promise(function (resolve, reject) {
      (function tick() {
        api('/api/jobs/' + id).then(function (job) {
          setProgress(job.percent, (job.message || job.stage) + (job.status === 'queued' ? ' (queued)' : ''));
          if (job.status === 'done') return resolve(job);
          if (job.status === 'error') return reject(new Error(job.error || 'pipeline failed'));
          fails = 0; setTimeout(tick, 1500);
        }).catch(function (err) {
          if (++fails > 5) reject(err); else setTimeout(tick, 3000);     // tolerate brief network blips
        });
      })();
    });
  }

  /* ---------- results panel ---------- */
  var VERDICT = { supported: ['Supported', 'ok'], insufficient_evidence: ['Insufficient evidence', 'mid'], contradicted: ['Contradicted', 'bad'], unverified: ['Not checked', 'mid'] };

  function tile(label, value, sub) {
    var t = el('div', 'ltile'); t.appendChild(el('span', 'mono', label)); t.appendChild(el('b', '', value)); t.appendChild(el('small', '', sub)); return t;
  }
  function render(r, id) {
    var m = r.metrics, p = r.page;
    res.textContent = '';
    var head = el('div', 'lhead');
    head.appendChild(el('span', 'chip ' + (r.mode === 'LIVE' ? 'ok' : 'mid'), r.mode));
    head.appendChild(el('span', 'mono', r.mode === 'LIVE' ? ('Model ' + r.model) : 'No model used'));
    res.appendChild(head);
    (r.notes || []).forEach(function (n) { res.appendChild(el('p', 'lnote warn', n)); });

    res.appendChild(el('h3', 'ltitle', p.title));
    var sum = el('p', 'lsum'); sum.appendChild(el('span', 'mono', 'Short answer')); sum.appendChild(document.createElement('br')); sum.appendChild(document.createTextNode(p.summary)); res.appendChild(sum);

    var tiles = el('div', 'ltiles');
    tiles.appendChild(tile('Passage coverage', pct(m.coverage), m.covered + ' of ' + m.queries + ' generated questions match a passage (lexical)'));
    tiles.appendChild(tile('Facts supported', m.claims_total ? (m.supported + ' / ' + m.claims_total) : 'n/a', m.claims_total ? 'checked against live search' : 'needs LIVE mode'));
    tiles.appendChild(tile('Citation test', m.citations_tested ? (m.citation_hits + ' / ' + m.citations_tested) : 'not run', m.citations_tested ? 'live answers that cited your host' : (r.citation && r.citation.reason ? r.citation.reason : 'add your page URL')));
    tiles.appendChild(tile('Integrity audit', r.audit.passed ? 'Passed' : (r.audit.issues.length + ' issue' + (r.audit.issues.length === 1 ? '' : 's')), r.audit.visible_words + ' visible words'));
    res.appendChild(tiles);

    if (!r.audit.passed) { var ul = el('ul', 'lissues'); r.audit.issues.slice(0, 8).forEach(function (i) { ul.appendChild(el('li', '', i)); }); res.appendChild(ul); }

    if (r.claims && r.claims.length) {
      res.appendChild(el('p', 'mono lsub', 'Key facts and what the evidence says'));
      r.claims.forEach(function (c) {
        var v = VERDICT[c.verdict] || VERDICT.unverified, row = el('div', 'lclaim');
        row.appendChild(el('span', 'chip ' + v[1], v[0]));
        var body = el('div', 'lcb'); body.appendChild(el('p', 'lct', c.claim));
        if (c.explanation) body.appendChild(el('p', 'lce', c.explanation));
        var src = el('p', 'lcs');
        (c.evidence || []).filter(function (x) { return safeUrl(x.source_url); }).slice(0, 3).forEach(function (x) {
          var a = el('a', '', x.source_title || x.source_url); a.href = safeUrl(x.source_url); a.target = '_blank'; a.rel = 'noopener noreferrer'; src.appendChild(a);
        });
        if (!src.childNodes.length && c.sources && c.sources.length) src.textContent = 'Searched: ' + c.sources.slice(0, 3).map(function (s) { return s.title; }).filter(Boolean).join(', ');
        if (src.childNodes.length) body.appendChild(src);
        row.appendChild(body); res.appendChild(row);
      });
    }
    if (r.gap_sample && r.gap_sample.length) {
      res.appendChild(el('p', 'mono lsub', 'Questions the page does not answer yet'));
      var gl = el('ul', 'lissues'); r.gap_sample.slice(0, 5).forEach(function (g) { gl.appendChild(el('li', '', g.query)); }); res.appendChild(gl);
    }
    var acts = el('div', 'lacts');
    var pv = el('a', 'btn g', 'Preview generated page \u2197'); pv.href = API + '/api/jobs/' + id + '/page.html'; pv.target = '_blank'; pv.rel = 'noopener'; acts.appendChild(pv);
    var dl = el('a', 'btn p', 'Download site (.zip)'); dl.href = API + '/api/jobs/' + id + '/site.zip'; acts.appendChild(dl);
    res.appendChild(acts);
    res.appendChild(el('p', 'fine', 'Review every fact before publishing. Verdicts are automated and preliminary; passage coverage is a lexical match, not a measure of AI citations.'));
    res.hidden = false; prog.hidden = true;
    try { res.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); } catch (e) {}
  }

  /* ---------- feed real numbers into the rest of the page ---------- */
  function setKpi(i, label, value, sub) {
    var k = document.querySelectorAll('.kpis .kpi')[i]; if (!k) return;
    k.textContent = ''; k.appendChild(document.createTextNode(label)); k.appendChild(el('b', '', value)); k.appendChild(document.createTextNode(sub));
  }
  function applyToPage(r) {
    var m = r.metrics, p = r.page, tot = m.claims_total + m.removed;

    /* Studio: the generated article */
    var bar0 = document.querySelectorAll('.studio .sbar span');
    if (bar0[0]) bar0[0].textContent = 'Source studio / ' + r.topic;
    if (bar0[1]) bar0[1].textContent = 'Live workspace';
    var art = document.querySelector('.studio .art');
    if (art) {
      var eb = art.querySelector('.eyebrow'); if (eb) eb.textContent = 'Generated by CiteForge';
      var h3 = art.querySelector('h3'); if (h3) h3.textContent = p.title;
      var sh = art.querySelector('.short');
      if (sh) { sh.textContent = ''; sh.appendChild(el('span', 'mono', 'The short answer')); sh.appendChild(document.createElement('br')); sh.appendChild(document.createTextNode(p.summary)); sh.firstChild.style.color = 'var(--teal)'; }
      var h4 = art.querySelector('h4'); if (h4) h4.textContent = 'What the page covers';
      var tb = art.querySelector('table');
      if (tb) {
        tb.textContent = '';
        (p.sections || []).slice(0, 3).forEach(function (s) {
          var tr = document.createElement('tr'); tr.appendChild(el('td', '', s.heading));
          var body = String(s.body || ''); tr.appendChild(el('td', '', body.length > 110 ? body.slice(0, 107) + '\u2026' : body)); tb.appendChild(tr);
        });
      }
    }
    var ev = document.querySelector('.studio .ev');
    if (ev) {
      var big = ev.querySelector('.big');
      if (big) { big.textContent = m.supported + ' '; big.appendChild(el('small', '', '/ ' + (m.claims_total || 0))); big.lastChild.style.cssText = 'font-size:13px;color:var(--mut)'; }
      var span0 = ev.querySelector('.box span'); if (span0) span0.textContent = 'Key facts supported by evidence';
      var bars = ev.querySelector('.bar');
      if (bars) { bars.textContent = ''; for (var i = 0; i < Math.max(m.claims_total, 1); i++) bars.appendChild(el('i', i < m.supported ? '' : 'o')); }
      var linked = ev.querySelector('.linked'), c0 = (r.claims || []).filter(function (c) { return c.verdict === 'supported'; })[0];
      if (linked) {
        if (c0) {
          var q = linked.querySelector('p'); if (q) q.textContent = '\u201C' + c0.claim + '\u201D';
          var ss = linked.querySelectorAll('span'); if (ss[1]) ss[1].textContent = ((c0.evidence || [])[0] || {}).source_title || 'Retrieved sources';
        } else linked.hidden = true;
      }
      var warn = ev.querySelector('.warn'), g0 = (r.gap_sample || [])[0];
      if (warn) { warn.textContent = ''; warn.appendChild(el('b', '', 'A stronger source starts here')); warn.appendChild(document.createElement('br')); warn.appendChild(document.createTextNode(g0 ? 'Add a passage that answers: ' + g0.query : 'No coverage gaps found in generated questions.')); }
    }
    var ck = document.querySelector('.studio ~ .checks .mono'); if (ck) ck.textContent = 'Live data from your latest run';

    /* Testing dashboard: real KPIs */
    var cit = m.citations_tested;
    setKpi(0, cit ? 'Citation coverage' : 'Passage coverage', cit ? pct(m.citation_rate) : pct(m.coverage),
      cit ? (m.citation_hits + ' of ' + cit + ' live answers cited your host') : (m.covered + ' of ' + m.queries + ' generated questions have a matching passage'));
    setKpi(1, 'Fact support', m.claims_total ? pct(m.supported / m.claims_total) : 'n/a',
      m.claims_total ? (m.supported + ' of ' + m.claims_total + ' key facts supported by retrieved sources') : 'Needs LIVE mode');
    setKpi(2, 'Questions generated', String(m.queries), 'Across ' + m.intents + ' intents; ' + (cit || 0) + ' sent to live search');

    var panels = document.querySelectorAll('.dash .dgrid .panel');
    if (panels[0]) drawTrend(panels[0], r.history || []);
    if (panels[1]) {
      panels[1].textContent = 'Key facts by verdict';
      var eng = el('div', 'eng');
      [['Supported', m.supported], ['Insufficient evidence', m.insufficient], ['Removed (contradicted)', m.removed]].forEach(function (x) {
        var share = tot ? Math.round(x[1] / tot * 100) : 0, d = el('div'); d.appendChild(el('span', '', x[0])); d.appendChild(el('span', '', x[1] + ' (' + share + '%)')); eng.appendChild(d);
        var i2 = document.createElement('i'), b2 = document.createElement('b'); b2.style.width = share + '%'; i2.appendChild(b2); eng.appendChild(i2);
      });
      panels[1].appendChild(eng);
    }
    var inl = document.querySelector('.dash > .panel[style]'), c1 = (r.claims || [])[0];
    if (inl && c1) {
      var v = VERDICT[c1.verdict] || VERDICT.unverified;
      inl.textContent = '';
      var l = document.createElement('div'); l.appendChild(el('span', 'mono', 'Latest claim check')); l.appendChild(document.createElement('br'));
      var bq = el('b', '', c1.claim); bq.style.cssText = 'color:#fff;font-weight:400'; l.appendChild(bq);
      var rr = document.createElement('div'); rr.style.color = '#ece8ff'; rr.appendChild(document.createTextNode(c1.explanation || 'No explanation returned.')); rr.appendChild(document.createElement('br'));
      var vv = el('span', 'mono', 'Verdict: ' + v[0]); vv.style.color = 'var(--cyan)'; rr.appendChild(vv);
      inl.appendChild(l); inl.appendChild(rr);
    }
    var fine = document.querySelector('.dark .fine');
    if (fine) fine.textContent = 'Live results from your latest run on \u201C' + r.topic + '\u201D. Coverage is a lexical match between generated questions and page passages. Citation results vary by question, model and time.';
  }

  function drawTrend(panel, hist) {
    var svg = panel.querySelector('svg'); if (!svg) return;
    var first = panel.firstChild; if (first && first.nodeType === 3) first.nodeValue = 'Passage coverage by round';
    var pts = hist.map(function (h) { return h.coverage; });
    if (!pts.length) return;
    var n = pts.length, X = function (i) { return n === 1 ? 260 : Math.round(i * 520 / (n - 1)); }, Y = function (v) { return Math.round(150 - Math.max(0, Math.min(1, v)) * 120); };
    var d = pts.map(function (v, i) { return (i ? 'L' : 'M') + X(i) + ' ' + Y(v); }).join(' ');
    if (n === 1) d = 'M0 ' + Y(pts[0]) + ' L520 ' + Y(pts[0]);
    var paths = svg.querySelectorAll('path');            // [grid, area, line, marker]
    if (paths.length >= 4) {
      paths[1].setAttribute('d', d + ' V170 H0 Z'); paths[2].setAttribute('d', d);
      var mx = n > 1 ? X(1) : 300; paths[3].setAttribute('d', 'M' + mx + ' 0V170');
      var t = svg.querySelector('text'); if (t) { t.setAttribute('x', mx + 6); t.textContent = n > 1 ? 'EDITOR ROUND' : 'SINGLE RUN'; }
    }
  }
})();
