        /**
         * Dark Fleet: Music / Comedy toggle (no second page, no DOM rebuild). Both fleets are
         * built once as yard-style tile grids; yard-wall.js hangs the picked one on the rail.
         * Perf: dual prebuilt panels + dual tickers, WAAPI px marquee, no backdrop-filter.
         * Free-agent pass 2026-08-03: no toggle img thrash, resize guard, IO cache, will-change on.
         * Catalog: #videos-data (kind). Refresh: update-dark-fleet-videos
         */
        (() => {
            const BLURBS = {
                music: "Dark AI music videos: Norse metal, dark country and memorial ballads.",
                comedy: "Absurdist comedy videos: Valhalla denials, hell dinners and wasteland parodies."
            };
            const LABELS = { music: "music videos", comedy: "comedy videos" };
            const TITLES = { music: "Music videos", comedy: "Comedy videos" };

            let catalog = [];
            try {
                catalog = JSON.parse(document.getElementById("videos-data").textContent || "[]");
                if (!Array.isArray(catalog)) catalog = [];
            } catch (e) {
                catalog = [];
            }
            /* Full MVs only in Music fleet — promo #Shorts / "Full MV 👇" never bleed in. */
            function isPromoShort(v) {
                if (!v) return false;
                if (v.kind === "short") return true;
                const t = String(v.title || "").toLowerCase();
                if (t.includes("#shorts")) return true;
                if (t.includes("music short")) return true;
                if (t.includes("full mv in description")) return true;
                if (/full\s*mv\s*[👇⬇️↓]/.test(t)) return true;
                return false;
            }
            const byKind = {
                music: catalog.filter(
                    (v) =>
                        v &&
                        (v.kind || "music") === "music" &&
                        !isPromoShort(v) &&
                        /^[\w-]{6,}$/.test(v.id || "")
                ),
                comedy: catalog.filter(
                    (v) => v && v.kind === "comedy" && /^[\w-]{6,}$/.test(v.id || "")
                )
            };

            /* A fleet other than Music gets its own tab only with MIN_FLEET+ videos.
               Smaller fleets stay off the switcher (and #comedy falls back to Music)
               until uploads bring them up to the minimum. */
            const MIN_FLEET = 6;
            const shownKinds = Object.keys(byKind).filter(
                (k) => k === "music" || byKind[k].length >= MIN_FLEET
            );

            const panels = {
                music: document.getElementById("gallery-music"),
                comedy: document.getElementById("gallery-comedy")
            };
            const fleetSwitch = document.getElementById("fleet-switch");
            const heroBlurb = document.getElementById("hero-blurb");
            const fleetLabel = document.getElementById("fleet-label");
            const fleetCount = document.getElementById("fleet-count");
            const fleetTitle = document.getElementById("fleetTitle");
            const tickerEl = document.getElementById("ticker");
            const tickerSlots = {
                music: document.getElementById("ticker-slot-music"),
                comedy: document.getElementById("ticker-slot-comedy")
            };
            const tickerTracks = {
                music: document.getElementById("ticker-track-music"),
                comedy: document.getElementById("ticker-track-comedy")
            };
            const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
            const counts = { music: 0, comedy: 0 };
            let active = "music";
            const bootHash = (location.hash || "").replace(/^#/, "").toLowerCase();
            const bootKind =
                (bootHash === "comedy" || bootHash === "shorts") && shownKinds.includes("comedy")
                    ? "comedy"
                    : "music";

            /* ── Dual WAAPI marquees (prebuilt; fleet switch = show/hide only) ── */
            const tickerState = {
                kind: bootKind,
                anims: { music: null, comedy: null },
                half: { music: 0, comedy: 0 },
                lastWidth: { music: 0, comedy: 0 },
                paused: false,
                onScreen: true,
                speed: 48,
                names: { music: [], comedy: [] }
            };

            function shortTitle(t) {
                return String(t || "")
                    .replace(/\s*[|·•].*$/, "")
                    .replace(/#\w+/g, "")
                    .replace(/\s+/g, " ")
                    .trim()
                    .slice(0, 34);
            }

            function makeSeq(names) {
                const seq = document.createElement("div");
                seq.className = "ticker-seq";
                names.forEach((name) => {
                    const span = document.createElement("span");
                    span.textContent = name;
                    seq.appendChild(span);
                    const sep = document.createElement("span");
                    sep.className = "sep";
                    sep.textContent = "◆";
                    sep.setAttribute("aria-hidden", "true");
                    seq.appendChild(sep);
                });
                return seq;
            }

            function prepareTickerNames() {
                ["music", "comedy"].forEach((kind) => {
                    const pool = byKind[kind].length ? byKind[kind] : catalog;
                    tickerState.names[kind] = (pool.length ? pool : [{ title: "Dark Fleet" }])
                        .slice(0, 12)
                        .map((v) => shortTitle(v.title) || "Dark Fleet");
                });
            }

            function stopTickerAnim(kind) {
                const a = tickerState.anims[kind];
                if (!a) return;
                try {
                    a.cancel();
                } catch (e) { /* ignore */ }
                tickerState.anims[kind] = null;
            }

            function setTrackWillChange(kind, on) {
                const track = tickerTracks[kind];
                if (track) track.classList.toggle("will-change-transform", !!on);
            }

            function restartTickerAnim(kind) {
                const track = tickerTracks[kind];
                if (!track || prefersReduced) return;
                stopTickerAnim(kind);
                void track.offsetWidth;
                const seq = track.firstElementChild;
                const half = seq ? seq.offsetWidth : 0;
                tickerState.half[kind] = half;
                tickerState.lastWidth[kind] = track.scrollWidth || 0;
                if (half < 2) return;

                const ms = Math.max(12000, Math.round((half / tickerState.speed) * 1000));
                tickerState.anims[kind] = track.animate(
                    [
                        { transform: "translate3d(0,0,0)" },
                        { transform: "translate3d(" + -half + "px,0,0)" }
                    ],
                    { duration: ms, iterations: Infinity, easing: "linear" }
                );
                const shouldRun = !tickerState.paused && tickerState.onScreen && kind === tickerState.kind && !document.hidden;
                setTrackWillChange(kind, shouldRun);
                if (!shouldRun) {
                    try {
                        tickerState.anims[kind].pause();
                    } catch (e) { /* ignore */ }
                }
            }

            function applyTickerPauseState() {
                const paused = tickerState.paused || !tickerState.onScreen || document.hidden;
                ["music", "comedy"].forEach((kind) => {
                    const a = tickerState.anims[kind];
                    const activeKind = kind === tickerState.kind;
                    const run = !paused && activeKind;
                    setTrackWillChange(kind, run);
                    if (!a) return;
                    try {
                        if (run) a.play();
                        else a.pause();
                    } catch (e) { /* ignore */ }
                });
            }

            function setTickerPaused(paused) {
                tickerState.paused = !!paused;
                applyTickerPauseState();
            }

            function buildTicker(kind) {
                const track = tickerTracks[kind];
                if (!track || prefersReduced) return;
                const names = tickerState.names[kind] || tickerState.names.music;
                track.replaceChildren(makeSeq(names), makeSeq(names));
                restartTickerAnim(kind);
            }

            function showTicker(kind) {
                if (prefersReduced) return;
                if (kind !== "music" && kind !== "comedy") kind = "music";
                tickerState.kind = kind;
                Object.keys(tickerSlots).forEach((k) => {
                    const slot = tickerSlots[k];
                    if (!slot) return;
                    slot.hidden = k !== kind;
                });
                /* Hidden slots measure as width 0 — (re)start WAAPI only once visible */
                if (!tickerState.anims[kind] || tickerState.half[kind] < 2) {
                    restartTickerAnim(kind);
                }
                applyTickerPauseState();
            }

            function startTickers() {
                if (prefersReduced) {
                    if (tickerEl) tickerEl.classList.add("is-display-none");
                    return;
                }
                buildTicker("music");
                buildTicker("comedy");
                showTicker(tickerState.kind);
            }

            document.addEventListener("visibilitychange", () => {
                applyTickerPauseState();
            });
            if (tickerEl && "IntersectionObserver" in window) {
                const tio = new IntersectionObserver(
                    (entries) => {
                        tickerState.onScreen = !!(entries[0] && entries[0].isIntersecting);
                        applyTickerPauseState();
                    },
                    { threshold: 0.01 }
                );
                tio.observe(tickerEl);
            }
            window.addEventListener(
                "resize",
                (() => {
                    let t = 0;
                    return () => {
                        clearTimeout(t);
                        t = setTimeout(() => {
                            const kind = tickerState.kind;
                            const track = tickerTracks[kind];
                            if (!track || !track.firstElementChild) return;
                            const w = track.scrollWidth;
                            if (w === tickerState.lastWidth[kind]) return;
                            tickerState.lastWidth[kind] = w;
                            restartTickerAnim(kind);
                        }, 150);
                    };
                })(),
                { passive: true }
            );

            /* Same tile as the yard photo grid (styles.css .yard-*), with a 16:9 frame.
               yard-wall.js reads these tiles for the rail and plays them in the page player. */
            const thumb = (id, size) => "https://i.ytimg.com/vi/" + encodeURIComponent(id) + "/" + size + ".jpg";
            const noEmbed = new Set(catalog.filter((v) => v && v.embed === false).map((v) => v.id));

            function makeTile(v, opts) {
                const li = document.createElement("li");
                li.className = "yard-item";
                if (opts.wide) li.classList.add("yard-item--wide");
                const fig = document.createElement("figure");
                fig.className = "yard-figure";

                const a = document.createElement("a");
                a.className = "yard-open";
                /* id already filtered to [\w-] - still encode for URL safety */
                a.href = "https://www.youtube.com/watch?v=" + encodeURIComponent(v.id);
                a.target = "_blank";
                a.rel = "noopener noreferrer";
                a.referrerPolicy = "no-referrer";
                a.dataset.video = v.id;
                a.dataset.title = v.title;
                a.dataset.wallSrc = thumb(v.id, "mqdefault");
                a.dataset.w = "16";
                a.dataset.h = "9";
                a.setAttribute("aria-label", (noEmbed.has(v.id) ? "Watch on YouTube: " : "Play ") + v.title);

                const img = document.createElement("img");
                img.src = thumb(v.id, "hqdefault");
                img.srcset = thumb(v.id, "mqdefault") + " 320w, " + thumb(v.id, "hqdefault") + " 480w";
                img.sizes = opts.big ? "(max-width: 639px) 92vw, 760px" : "(max-width: 639px) 46vw, 380px";
                img.alt = "";
                img.width = 480;
                img.height = 360;
                img.decoding = "async";
                img.loading = opts.eager ? "eager" : "lazy";
                if (opts.eager) img.fetchPriority = "high";
                a.append(img);

                const cap = document.createElement("figcaption");
                const name = document.createElement("span");
                name.className = "yard-cap";
                name.textContent = v.title;
                const when = document.createElement("span");
                when.className = "yard-when";
                when.textContent = (v.published || "") + (noEmbed.has(v.id) ? ", plays on YouTube" : "");
                cap.append(name, when);

                fig.append(a, cap);
                li.append(fig);
                return li;
            }

            /* Rows stay full on the 3-column grid: the lead tile fills 2x2, and one or two
               tiles near the end go wide when the count would leave a short last row. */
            function wideSet(n) {
                const r = n % 3;
                if (n < 5 || r === 0) return new Set();
                return r === 2 ? new Set([n - 1]) : new Set([n - 3, n - 1]);
            }

            /* Fresh order on every visit (shared BucShuffle helper). The static lead tile in the
               HTML is first paint only; it stays when the shuffle lands on it, else the shuffled
               lead takes its 2x2 slot (fixed 16:9 frame, so nothing shifts). */
            const shuffle = (a) => (window.BucShuffle ? window.BucShuffle.shuffle(a) : a.slice());
            function fillPanel(kind) {
                const panel = panels[kind];
                if (!panel) return;
                const pool = byKind[kind] || [];
                const lcpEl = panel.querySelector("[data-lcp]");
                const lcpOpen = lcpEl && lcpEl.querySelector("[data-video]");
                const lcpId = lcpOpen ? lcpOpen.dataset.video : "";
                const picks = shuffle(pool);
                counts[kind] = picks.length;
                if (!picks.length) {
                    const empty = document.createElement("p");
                    empty.className = "hero-description";
                    empty.textContent = "No videos in this fleet yet. Check back after the next upload.";
                    panel.replaceChildren(empty);
                    return;
                }
                let list = panel.querySelector(".yard-grid");
                if (!list) {
                    list = document.createElement("ul");
                    list.className = "yard-grid yard-grid--video";
                    panel.replaceChildren(list);
                }
                const wide = wideSet(picks.length);
                const frag = document.createDocumentFragment();
                picks.forEach((v, i) => {
                    if (lcpEl && i === 0 && v.id === lcpId) return;
                    /* eager only for the boot fleet's lead tile - never thrash on toggle */
                    frag.appendChild(makeTile(v, { eager: kind === bootKind && i === 0, big: i === 0 || wide.has(i), wide: wide.has(i) }));
                });
                const keepLead = lcpEl && picks[0].id === lcpId;
                Array.from(list.children).forEach((c) => {
                    if (!(keepLead && c === lcpEl)) c.remove();
                });
                list.appendChild(frag);
            }

            function showPanel(kind) {
                Object.keys(panels).forEach((k) => {
                    const p = panels[k];
                    if (!p) return;
                    const on = k === kind;
                    p.classList.toggle("is-on", on);
                    p.classList.toggle("is-off", !on);
                    p.hidden = !on;
                });
            }

            function setMeta(kind) {
                fleetLabel.textContent = LABELS[kind] || kind;
                fleetCount.textContent = String(counts[kind] || 0);
                if (fleetTitle) fleetTitle.textContent = TITLES[kind] || TITLES.music;
                heroBlurb.textContent = BLURBS[kind] || BLURBS.music;
                showTicker(kind);
            }

            function setFleet(kind, { pushHash } = { pushHash: true }) {
                if (!shownKinds.includes(kind)) kind = "music";
                active = kind;
                fleetSwitch.dataset.active = kind;
                fleetSwitch.querySelectorAll("button[data-fleet]").forEach((btn) => {
                    const on = btn.dataset.fleet === kind;
                    btn.setAttribute("aria-selected", on ? "true" : "false");
                    btn.tabIndex = on ? 0 : -1;
                });
                showPanel(kind);
                setMeta(kind);
                if (pushHash) {
                    /* pushState so browser Back flips fleets (free-agent UX/SEO note) */
                    const want = kind === "comedy" ? "#comedy" : "#music";
                    if ((location.hash || "#music") !== want) {
                        history.pushState({ fleet: kind }, "", location.pathname + location.search + want);
                    }
                }
            }

            /* Build BOTH fleets + both tickers once; toggle = visibility only */
            fillPanel("music");
            fillPanel("comedy");
            prepareTickerNames();
            const bootTicker = () => {
                startTickers();
            };
            if (document.fonts && document.fonts.ready) {
                document.fonts.ready.then(bootTicker).catch(bootTicker);
            } else {
                bootTicker();
            }

            fleetSwitch.querySelectorAll("button[data-fleet]").forEach((btn) => {
                btn.hidden = !shownKinds.includes(btn.dataset.fleet);
                btn.addEventListener("click", () => setFleet(btn.dataset.fleet));
            });
            /* One fleet left = no switcher at all */
            fleetSwitch.hidden = shownKinds.length < 2;

            fleetSwitch.addEventListener("keydown", (e) => {
                if (e.key !== "ArrowLeft" && e.key !== "ArrowRight" && e.key !== "Home" && e.key !== "End") return;
                e.preventDefault();
                if (e.key === "Home") return setFleet("music");
                if (e.key === "End") return setFleet("comedy");
                setFleet(active === "music" ? "comedy" : "music");
            });

            setFleet(bootKind, { pushHash: false });

            function fleetFromHash() {
                const h = (location.hash || "").replace(/^#/, "").toLowerCase();
                return h === "comedy" || h === "shorts" ? "comedy" : h === "music" ? "music" : null;
            }
            window.addEventListener("popstate", () => {
                const k = fleetFromHash();
                setFleet(k || "music", { pushHash: false });
            });
            window.addEventListener("hashchange", () => {
                const k = fleetFromHash();
                if (k) setFleet(k, { pushHash: false });
            });

            if (prefersReduced) {
                document.documentElement.classList.add("rm");
            }
        })();

