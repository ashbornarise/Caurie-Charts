// Documents : filtres (liste), lecteur de pages, sommaire cliquable, partage (15/11/2026)
document.querySelectorAll('.yt-chip').forEach(b => b.addEventListener('click', () => {
  document.querySelectorAll('.yt-chip').forEach(x => x.classList.toggle('on', x === b));
  const f = b.dataset.f;
  document.querySelectorAll('[data-cat]').forEach(c => { c.hidden = !!f && c.dataset.cat !== f; });
}));

(() => {
  const l = document.querySelector('.lecteur');
  if (l) {
    const pages = [...l.querySelectorAll('.lecteur-page')], minis = [...l.querySelectorAll('.mini')], total = pages.length;
    const num = l.querySelector('.lecteur-n'), sec = l.querySelector('.lecteur-sec');
    let reperes = [];
    try { reperes = JSON.parse((document.getElementById('dc-sections') || {}).textContent || '[]'); } catch (_) {}
    let n = 1;
    const va = (k) => {
      n = Math.min(total, Math.max(1, k));
      pages.forEach(p => p.classList.toggle('on', +p.dataset.n === n));
      minis.forEach(m => m.classList.toggle('on', +m.dataset.n === n));
      if (num) num.textContent = n;
      const r = reperes.find(x => n >= x[0] && n <= x[1]);
      if (sec && r) sec.textContent = r[2];
      const m = minis[n - 1]; if (m) m.scrollIntoView({ block: 'nearest', inline: 'center', behavior: 'smooth' });
    };
    l.querySelector('.prec').addEventListener('click', () => va(n - 1));
    l.querySelector('.suiv').addEventListener('click', () => va(n + 1));
    minis.forEach(m => m.addEventListener('click', (e) => { e.preventDefault(); va(+m.dataset.n); }));
    document.addEventListener('keydown', (e) => { if (e.key === 'ArrowRight') va(n + 1); if (e.key === 'ArrowLeft') va(n - 1); });
    document.querySelectorAll('[data-page]').forEach(a => a.addEventListener('click', (e) => {
      e.preventDefault(); va(+a.dataset.page); l.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }));
  }
  document.querySelectorAll('[data-partage]').forEach(b => b.addEventListener('click', async () => {
    const u = b.dataset.partage;
    try {
      if (navigator.share) await navigator.share({ url: u, title: document.title });
      else { await navigator.clipboard.writeText(u); const s = b.querySelector('span'); if (s) s.textContent = 'Lien copié'; }
    } catch (_) {}
  }));
})();
