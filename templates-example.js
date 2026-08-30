// ── Filter ──────────────────────────────────────────────
const filterBtns = document.querySelectorAll('.filter-btn');
const cards = document.querySelectorAll('.template-card');
filterBtns.forEach(btn => {
  btn.addEventListener('click', () => {
    const filter = btn.dataset.filter;
    filterBtns.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    cards.forEach(card => {
      const cats = (card.dataset.categories || '').split(/\s+/);
      const show = filter === 'all' || cats.includes(filter);
      card.classList.toggle('hidden', !show);
    });
  });
});

// ── Scroll reveal ──────────────────────────────────────
const reveals = document.querySelectorAll('.reveal');
const io = new IntersectionObserver((entries) => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      e.target.classList.add('visible');
      io.unobserve(e.target);
    }
  });
}, { threshold: 0.05 });
reveals.forEach(el => io.observe(el));

// ── Nav solid on scroll ────────────────────────────────
const nav = document.getElementById('nav');
const onScroll = () => nav.classList.toggle('is-solid', window.scrollY > 40);
window.addEventListener('scroll', onScroll, { passive: true });
onScroll();
