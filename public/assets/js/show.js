// Monthly Show : compte à rebours jusqu'au direct (data-start en UTC).
(function () {
  var box = document.querySelector('.show-cd'); if (!box) return;
  var start = Date.parse(box.getAttribute('data-start'));
  function pad(n) { return n < 10 ? '0' + n : '' + n; }
  function tick() {
    var s = Math.max(0, Math.floor((start - Date.now()) / 1000));
    var v = { d: Math.floor(s / 86400), h: Math.floor(s % 86400 / 3600), m: Math.floor(s % 3600 / 60), s: s % 60 };
    for (var k in v) { var el = box.querySelector('[data-u="' + k + '"]'); if (el) el.textContent = k === 'd' ? v[k] : pad(v[k]); }
  }
  tick(); setInterval(tick, 1000);
})();
