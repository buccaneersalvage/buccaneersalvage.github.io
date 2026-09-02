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

    const sendBtn = document.getElementById('f-send');
    if (sendBtn) {
      sendBtn.addEventListener('click', async () => {
        const email = document.getElementById('f-email').value.trim();
        const store = document.getElementById('f-store').value.trim();
        const count = document.getElementById('f-count').value;
        const plan = document.getElementById('f-plan').value;
        const photos = document.getElementById('f-photos').value.trim();
        const status = document.getElementById('f-status');
        const endpoint = (window.BUC_FORMSPREE && window.BUC_FORMSPREE.endpoint) || '';

        function setStatus(kind, text) {
          if (!status) return;
          status.hidden = !text;
          status.className = 'contact-status' + (kind ? ' contact-status--' + kind : '');
          status.textContent = text || '';
        }

        if (!email) {
          setStatus('err', 'Email is required.');
          return;
        }
        if (!endpoint) {
          setStatus('warn', 'Form backend not configured yet. Open contact.html setup notes, or email after Square pay.');
          window.location.href = 'contact.html?topic=' + encodeURIComponent('Listing services - ' + plan);
          return;
        }

        sendBtn.disabled = true;
        setStatus('pending', 'Sending…');
        const payload = {
          email,
          store_url: store,
          sku_count: count,
          plan,
          photos,
          topic: 'Listing services',
          message: `Listing services intake\nPlan: ${plan}\nSKU count: ${count}\nStore: ${store}\nPhotos: ${photos}`,
          _subject: `BuccaneerSalvage services - ${plan} (${count})`,
          source: "hub-services",
          page: location.href,
        };
        try {
          const res = await fetch(endpoint, {
            method: 'POST',
            headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
          });
          if (res.ok) {
            setStatus('ok', 'Sent. I’ll reply at ' + email + '.');
          } else {
            const body = await res.json().catch(() => ({}));
            setStatus('err', (body && body.error) || 'Send failed — try the contact page.');
          }
        } catch (e) {
          setStatus('err', 'Network error. Try the contact page.');
        } finally {
          sendBtn.disabled = false;
        }
      });
    }
