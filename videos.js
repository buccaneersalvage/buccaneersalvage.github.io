        /**
         * Dark Fleet — Music ↔ Comedy toggle (no second page, no DOM rebuild).
         * Perf: dual prebuilt panels + dual tickers, WAAPI px marquee, no backdrop-filter.
         * Free-agent pass 2026-08-03: no toggle img thrash, resize guard, IO cache, will-change on.
         * Catalog: #videos-data (kind). Refresh: update-dark-fleet-videos
         */
        (() => {
            const PICK = 9;
            const BLURBS = {
                music: "Dark AI music videos — Norse metal, dark country, memorial ballads, and ritual heat. Forged with industrial fire. Haul these bounties aboard.",
                comedy: "Absurdist / raunchy comedy shorts — Valhalla denials, hell spit-roast dinners, jumpstyle wasteland parodies. You died wrong. Bureaucracy said no."
            };
            const LABELS = { music: "Music Videos", comedy: "Comedy Shorts" };

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

            const panels = {
                music: document.getElementById("gallery-music"),
                comedy: document.getElementById("gallery-comedy")
            };
            const fleetSwitch = document.getElementById("fleet-switch");
            const heroBlurb = document.getElementById("hero-blurb");
            const fleetLabel = document.getElementById("fleet-label");
            const fleetCount = document.getElementById("fleet-count");
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
            const bootKind = bootHash === "comedy" || bootHash === "shorts" ? "comedy" : "music";

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

            function shuffle(arr) {
                const a = arr.slice();
                for (let i = a.length - 1; i > 0; i--) {
                    const j = Math.floor(Math.random() * (i + 1));
                    [a[i], a[j]] = [a[j], a[i]];
                }
                return a;
            }

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
                if (track) track.style.willChange = on ? "transform" : "auto";
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
                    if (tickerEl) tickerEl.style.display = "none";
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

            function makeCard(v, eager) {
                const kind = v.kind || "music";
                const card = document.createElement("article");
                card.className = "video-card is-in";
                card.dataset.kind = kind;

                const thumb = document.createElement("div");
                thumb.className = "video-thumbnail";

                const badge = document.createElement("span");
                badge.className = "kind-badge";
                badge.textContent =
                    kind === "comedy" ? "Comedy" : kind === "short" ? "Short" : "Music";

                const a = document.createElement("a");
                /* id already filtered to [\w-] — still encode for URL safety */
                a.href = "https://www.youtube.com/watch?v=" + encodeURIComponent(v.id);
                a.target = "_blank";
                a.rel = "noopener noreferrer";
                a.referrerPolicy = "no-referrer";
                a.setAttribute("aria-label", "Watch " + v.title + " on YouTube");

                const img = document.createElement("img");
                img.src = "https://img.youtube.com/vi/" + encodeURIComponent(v.id) + "/hqdefault.jpg";
                img.alt = v.title || "YouTube video";
                img.decoding = "async";
                img.loading = eager ? "eager" : "lazy";
                if (eager) img.fetchPriority = "high";
                img.width = 480;
                img.height = 360;
                img.referrerPolicy = "no-referrer-when-downgrade";

                const play = document.createElement("div");
                play.className = "play-button";
                play.setAttribute("aria-hidden", "true");
                play.textContent = "\u25B6";

                a.append(img, play);
                thumb.append(badge, a);

                const info = document.createElement("div");
                info.className = "video-info";
                const h3 = document.createElement("h2");
                h3.className = "video-title";
                h3.textContent = v.title;
                const desc = document.createElement("p");
                desc.className = "video-description";
                desc.textContent = "Watch on YouTube · " + (v.published || "");
                info.append(h3, desc);

                card.append(thumb, info);
                return card;
            }

            function fillPanel(kind) {
                const panel = panels[kind];
                if (!panel) return;
                const pool = byKind[kind] || [];
                const picks = shuffle(pool).slice(0, Math.min(PICK, pool.length));
                counts[kind] = { shown: picks.length, total: pool.length };
                const frag = document.createDocumentFragment();
                if (!picks.length) {
                    const empty = document.createElement("p");
                    empty.className = "hero-description";
                    empty.style.gridColumn = "1 / -1";
                    empty.textContent = "No vessels in this fleet yet — check back after the next haul.";
                    frag.appendChild(empty);
                } else {
                    /* eager only for boot-visible fleet's first row — never thrash on toggle */
                    picks.forEach((v, i) => frag.appendChild(makeCard(v, kind === bootKind && i < 3)));
                }
                panel.replaceChildren(frag);
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
                const c = counts[kind] || { shown: 0, total: 0 };
                fleetLabel.textContent = LABELS[kind] || kind;
                fleetCount.textContent = c.shown + " of " + c.total;
                heroBlurb.textContent = BLURBS[kind] || BLURBS.music;
                showTicker(kind);
            }

            function setFleet(kind, { pushHash } = { pushHash: true }) {
                if (kind !== "music" && kind !== "comedy") kind = "music";
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
                btn.addEventListener("click", () => setFleet(btn.dataset.fleet));
            });

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
