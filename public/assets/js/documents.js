// Documents : filtres (liste) et lecteur de pages (document)
document.querySelectorAll('.yt-chip').forEach(b => b.addEventListener('click', () => {
  document.querySelectorAll('.yt-chip').forEach(x => x.classList.toggle('on', x === b));
  const f = b.dataset.f;
  document.querySelectorAll('.yt-carte,.yt-une').forEach(c => { c.style.display = (!f || c.dataset.cat === f) ? '' : 'none'; });
}));

// lecteur : flèches, miniatures, clavier
(() => {
  const l = document.querySelector('.lecteur');
  if (!l) return;
  const pages = [...l.querySelectorAll('.lecteur-page')], minis = [...l.querySelectorAll('.mini')], total = pages.length;
  const compte = l.querySelector('.lecteur-compte b');
  let n = 1;
  const va = (k) => {
    n = Math.min(total, Math.max(1, k));
    pages.forEach(p => p.classList.toggle('on', +p.dataset.n === n));
    minis.forEach(m => m.classList.toggle('on', +m.dataset.n === n));
    compte.textContent = n;
    const m = minis[n - 1]; if (m) m.scrollIntoView({ block: 'nearest', inline: 'center', behavior: 'smooth' });
  };
  l.querySelector('.prec').addEventListener('click', () => va(n - 1));
  l.querySelector('.suiv').addEventListener('click', () => va(n + 1));
  minis.forEach(m => m.addEventListener('click', (e) => { e.preventDefault(); va(+m.dataset.n); }));
  document.addEventListener('keydown', (e) => { if (e.key === 'ArrowRight') va(n + 1); if (e.key === 'ArrowLeft') va(n - 1); });
  const b = document.querySelector('[data-partage]');
  if (b) b.addEventListener('click', async () => {
    const u = b.dataset.partage;
    try { if (navigator.share) await navigator.share({ url: u, title: document.title }); else { await navigator.clipboard.writeText(u); b.querySelector('span').textContent = 'Lien copié'; } } catch (_) {}
  });
})();
