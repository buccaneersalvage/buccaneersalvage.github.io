    const reveals = document.querySelectorAll('.reveal');
    const io = new IntersectionObserver((entries) => {
      entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('visible'); io.unobserve(e.target); } });
    }, { threshold: 0.08 });
    reveals.forEach(el => io.observe(el));

    const toggleBtn = document.getElementById('navToggle');
    const drawer = document.getElementById('drawer');
    toggleBtn.addEventListener('click', () => {
      const open = drawer.classList.toggle('open');
      toggleBtn.setAttribute('aria-expanded', String(open));
    });

    const nav = document.getElementById('nav');
    const onScroll = () => nav.classList.toggle('is-solid', window.scrollY > 40);
    window.addEventListener('scroll', onScroll, { passive: true }); onScroll();

    document.getElementById('f-send').addEventListener('click', () => {
      const email = document.getElementById('f-email').value.trim();
      const store = document.getElementById('f-store').value.trim();
      const count = document.getElementById('f-count').value;
      const plan = document.getElementById('f-plan').value;
      const photos = document.getElementById('f-photos').value.trim();
      const body =
        `Email: ${email}\nStore URL: ${store}\nSKU count: ${count}\nPlan: ${plan}\nPhotos: ${photos}\n\nNotes:\n`;
      const subject = encodeURIComponent(`Listing services - ${plan} (${count})`);
      window.location.href = `mailto:jollyroger1480@gmail.com?subject=${subject}&body=${encodeURIComponent(body)}`;
    });
