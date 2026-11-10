/**

 * FieldOps Nexus — Public Marketing Interactivity (Vanilla JS)

 * High-performance 60fps animations, mega-menu interactions, and scroll telemetry.

 * Fully compliant with strict CSP (No inline scripts or handlers).

 */



document.addEventListener('DOMContentLoaded', () => {

  // =========================================================================

  // 1. Top Edge Gold Scroll Signal & Navbar Scrolled State

  // =========================================================================

  const navScrollSignal = document.getElementById('nexus-nav-scroll-signal');

  const pubHeader = document.querySelector('.fx-pub-header');



  const updateScrollSignals = () => {

    const scrollY = window.scrollY || window.pageYOffset || document.documentElement.scrollTop || 0;

    const scrollHeight = Math.max(

      document.documentElement.scrollHeight,

      document.body.scrollHeight,

      0

    );

    const clientHeight = window.innerHeight || document.documentElement.clientHeight || 0;

    const maxScroll = scrollHeight - clientHeight;

    const progress = maxScroll > 0 ? Math.min(Math.max(scrollY / maxScroll, 0), 1) : 0;



    // Top navbar indicator & scroll class toggle

    if (pubHeader) {

      if (scrollY > 50) {

        pubHeader.classList.add('is-scrolled');

      } else {

        pubHeader.classList.remove('is-scrolled');

      }

    }

    if (navScrollSignal) {

      navScrollSignal.style.transform = `scaleX(${progress})`;

    }

  };



  window.addEventListener('scroll', updateScrollSignals, { passive: true });

  window.addEventListener('resize', updateScrollSignals, { passive: true });

  updateScrollSignals();



  // =========================================================================

  // 2. Desktop Mega-Menu Hover & Click Handling

  // =========================================================================

  const megaTriggers = document.querySelectorAll('[data-fx-mega-trigger]');

  const megaPanels = document.querySelectorAll('.fx-mega-menu');

  let closeTimer = null;

  let activeMenu = null;



  const cancelClose = () => {

    if (closeTimer) {

      clearTimeout(closeTimer);

      closeTimer = null;

    }

  };



  const openMega = (menuId) => {

    cancelClose();

    activeMenu = menuId;

    if (pubHeader) pubHeader.classList.add('has-mega-open');

    megaPanels.forEach(panel => {

      if (panel.id === `mega-${menuId}`) {

        panel.classList.add('is-active');

      } else {

        panel.classList.remove('is-active');

      }

    });

    megaTriggers.forEach(btn => {

      if (btn.getAttribute('data-fx-mega-trigger') === menuId) {

        btn.classList.add('is-open');

        btn.setAttribute('aria-expanded', 'true');

      } else {

        btn.classList.remove('is-open');

        btn.setAttribute('aria-expanded', 'false');

      }

    });

  };



  const scheduleClose = () => {

    cancelClose();

    closeTimer = setTimeout(() => {

      closeMega();

    }, 220);

  };



  const closeMega = () => {

    cancelClose();

    activeMenu = null;

    if (pubHeader) pubHeader.classList.remove('has-mega-open');

    megaPanels.forEach(panel => panel.classList.remove('is-active'));

    megaTriggers.forEach(btn => {

      btn.classList.remove('is-open');

      btn.setAttribute('aria-expanded', 'false');

    });

  };



  megaTriggers.forEach(btn => {

    const menuId = btn.getAttribute('data-fx-mega-trigger');



    btn.addEventListener('mouseenter', () => openMega(menuId));

    btn.addEventListener('mouseleave', scheduleClose);



    btn.addEventListener('click', (e) => {

      e.preventDefault();

      e.stopPropagation();

      cancelClose();

      if (activeMenu === menuId) {

        closeMega();

      } else {

        openMega(menuId);

      }

    });

  });



  megaPanels.forEach(panel => {

    panel.addEventListener('mouseenter', cancelClose);

    panel.addEventListener('mouseleave', scheduleClose);

  });



  // Close on outside click

  document.addEventListener('click', (e) => {

    if (!e.target.closest('.fx-pub-header') && !e.target.closest('.fx-mega-menu')) {

      closeMega();

    }

  });



  // Close on Escape key

  document.addEventListener('keydown', (e) => {

    if (e.key === 'Escape') {

      closeMega();

      closeMobileNav();

    }

  });



  // =========================================================================

  // 3. Mobile Navigation Drawer & Accordions

  // =========================================================================

  const mobileToggle = document.querySelector('[data-fx-pub-toggle]');

  const mobileDrawer = document.querySelector('[data-fx-pub-drawer]');



  const closeMobileNav = () => {

    if (mobileDrawer && mobileToggle) {

      mobileDrawer.classList.remove('is-open');

      mobileToggle.setAttribute('aria-expanded', 'false');

    }

  };



  if (mobileToggle && mobileDrawer) {

    mobileToggle.addEventListener('click', () => {

      const isOpen = mobileDrawer.classList.contains('is-open');

      if (isOpen) {

        closeMobileNav();

      } else {

        mobileDrawer.classList.add('is-open');

        mobileToggle.setAttribute('aria-expanded', 'true');

      }

    });

  }



  // Mobile Accordion Triggers

  document.querySelectorAll('[data-fx-mobile-accordion]').forEach(accBtn => {

    accBtn.addEventListener('click', () => {

      const targetId = accBtn.getAttribute('data-fx-mobile-accordion');

      const content = document.getElementById(targetId);

      if (content) {

        const isOpen = content.classList.contains('is-open');

        // Close siblings

        document.querySelectorAll('.fx-mobile-accordion-content').forEach(c => c.classList.remove('is-open'));

        document.querySelectorAll('[data-fx-mobile-accordion]').forEach(b => b.classList.remove('is-active'));

        if (!isOpen) {

          content.classList.add('is-open');

          accBtn.classList.add('is-active');

        }

      }

    });

  });



  // =========================================================================

  // 4. 7-Step Interactive Workflow Timeline (Step-Locked Section Experience)

  // =========================================================================

  const workflowSection = document.getElementById('workflow');

  const workflowLineFill = document.getElementById('workflow-line-fill');

  const workflowSteps = document.querySelectorAll('.fx-timeline-step');

  const workflowDescText = document.getElementById('workflow-desc-text');

  const workflowDescPill = document.getElementById('workflow-step-desc');



  if (workflowSection && workflowSteps.length > 0) {

    const STEP_DESCRIPTIONS = [

      "01. Service Request Raised — Instant omnichannel incident logging & customer confirmation",

      "02. Triage — AI & dispatcher assess urgency, severity, and contract SLA",

      "03. Service Work Order — Structured work order generated with BOM parts and safety checklists",

      "04. Technician Allocation — Geo-smart dispatch assigns certified technicians based on availability",

      "05. Execution of Service — On-site mobile checklist completion, live telemetry & parts logging",

      "06. Supervisor Approval — Digital QA verification, photo evidence & quality audit",

      "07. Closure — Automated SLA reporting, inventory deduction, and customer satisfaction survey"

    ];



    let currentStep = 0;

    const maxStep = workflowSteps.length - 1; // 6 (Step 07 Closure)

    let isTransitioning = false;

    let accumulatedDelta = 0;

    const WHEEL_THRESHOLD = 45;



    const updateStepUI = (stepIdx) => {

      currentStep = Math.min(Math.max(stepIdx, 0), maxStep);



      // 1. Move connecting line: 0% at step 0, 100% at step 6

      const progress = currentStep / maxStep;

      if (workflowLineFill) {

        workflowLineFill.style.transform = `scaleX(${progress})`;

      }



      // 2. Update step classes: completed, active, upcoming

      workflowSteps.forEach((step, idx) => {

        step.classList.remove('active', 'completed', 'upcoming');

        if (idx === currentStep) {

          step.classList.add('active');

          step.setAttribute('aria-selected', 'true');

          // scrollIntoView removed: caused page to scroll far down on mobile load

        } else if (idx < currentStep) {

          step.classList.add('completed');

          step.setAttribute('aria-selected', 'false');

        } else {

          step.classList.add('upcoming');

          step.setAttribute('aria-selected', 'false');

        }

      });



      // 3. Update description pill

      if (workflowDescText && STEP_DESCRIPTIONS[currentStep]) {

        if (workflowDescPill) {

          workflowDescPill.classList.add('is-updating');

          setTimeout(() => {

            workflowDescText.textContent = STEP_DESCRIPTIONS[currentStep];

            workflowDescPill.classList.remove('is-updating');

          }, 100);

        } else {

          workflowDescText.textContent = STEP_DESCRIPTIONS[currentStep];

        }

      }

    };



    const goToStep = (targetIdx) => {

      if (isTransitioning) return;

      const nextIdx = Math.min(Math.max(targetIdx, 0), maxStep);

      if (nextIdx === currentStep) return;



      isTransitioning = true;

      updateStepUI(nextIdx);

      setTimeout(() => {

        isTransitioning = false;

        accumulatedDelta = 0;

      }, 240);

    };



    // Make steps clickable & accessible

    workflowSteps.forEach((step, idx) => {

      step.setAttribute('tabindex', '0');

      step.setAttribute('role', 'button');

      const title = step.querySelector('.fx-timeline-title')?.textContent?.trim() || '';

      step.setAttribute('aria-label', `Step ${idx + 1}: ${title}`);



      step.addEventListener('click', () => {

        goToStep(idx);

      });

      step.addEventListener('keydown', (e) => {

        if (e.key === 'Enter' || e.key === ' ') {

          e.preventDefault();

          goToStep(idx);

        }

      });

    });



    const isUserInWorkflowSection = () => {

      const rect = workflowSection.getBoundingClientRect();

      const header = document.querySelector('.fx-pub-header');

      const headerH = header ? header.offsetHeight : 68;

      // Active reading viewport: section top is within header zone and bottom is still visible

      return (rect.top <= headerH + 60 && rect.bottom >= headerH + 180);

    };



    const lockSectionInView = () => {

      const header = document.querySelector('.fx-pub-header');

      const headerH = header ? header.offsetHeight : 68;

      const targetTop = workflowSection.getBoundingClientRect().top + window.scrollY - headerH;

      if (Math.abs(window.scrollY - targetTop) > 10) {

        window.scrollTo({ top: targetTop, behavior: 'smooth' });

      }

    };



    // Wheel Scroll Interceptor:

    // If in section: page does NOT scroll, only bar moves.

    // When bar reaches Step 07 Closure (or Step 01 when scrolling up), page scrolls normally!

    window.addEventListener('wheel', (e) => {

      if (!isUserInWorkflowSection()) {

        accumulatedDelta = 0;

        return;

      }



      if (e.deltaY > 0) {

        // Scrolling DOWN

        if (currentStep < maxStep) {

          // Keep page pinned on this section, only the bar moves!

          e.preventDefault();

          lockSectionInView();

          accumulatedDelta += e.deltaY;

          if (accumulatedDelta >= WHEEL_THRESHOLD && !isTransitioning) {

            goToStep(currentStep + 1);

          }

        }

        // When currentStep === maxStep (at Step 07 Closure), NO preventDefault:

        // page continues scrolling normally down!

      } else if (e.deltaY < 0) {

        // Scrolling UP

        if (currentStep > 0) {

          // Keep page pinned on this section, move bar backward!

          e.preventDefault();

          lockSectionInView();

          accumulatedDelta += e.deltaY;

          if (accumulatedDelta <= -WHEEL_THRESHOLD && !isTransitioning) {

            goToStep(currentStep - 1);

          }

        }

        // When currentStep === 0 (at Step 01), NO preventDefault:

        // page continues scrolling normally up!

      }

    }, { passive: false });



    // Touch Support for Mobile / Tablet

    let touchStartY = 0;

    window.addEventListener('touchstart', (e) => {

      if (e.touches && e.touches.length > 0) {

        touchStartY = e.touches[0].clientY;

      }

    }, { passive: true });



    window.addEventListener('touchmove', (e) => {

      if (window.innerWidth < 768) return; // Allow natural vertical scrolling through vertical timeline on mobile

      if (!isUserInWorkflowSection()) return;

      if (!e.touches || e.touches.length === 0) return;



      const currentY = e.touches[0].clientY;

      const diffY = touchStartY - currentY; // > 0 = swipe up = scroll down



      if (Math.abs(diffY) > 35) {

        if (diffY > 0 && currentStep < maxStep) {

          if (e.cancelable) e.preventDefault();

          touchStartY = currentY;

          goToStep(currentStep + 1);

        } else if (diffY < 0 && currentStep > 0) {

          if (e.cancelable) e.preventDefault();

          touchStartY = currentY;

          goToStep(currentStep - 1);

        }

      }

    }, { passive: false });



    // Keyboard Arrow Navigation

    window.addEventListener('keydown', (e) => {

      if (!isUserInWorkflowSection()) return;

      if (e.key === 'ArrowDown' || e.key === 'PageDown') {

        if (currentStep < maxStep) {

          e.preventDefault();

          goToStep(currentStep + 1);

        }

      } else if (e.key === 'ArrowUp' || e.key === 'PageUp') {

        if (currentStep > 0) {

          e.preventDefault();

          goToStep(currentStep - 1);

        }

      }

    });



    // Initialize initial state at Step 01

    updateStepUI(0);

  }



  // =========================================================================

  // 5. Reveal On Scroll Observer

  // =========================================================================

  const revealElements = document.querySelectorAll('.landing-reveal, .fx-reveal');

  if ('IntersectionObserver' in window) {

    const observer = new IntersectionObserver((entries) => {

      entries.forEach(entry => {

        if (entry.isIntersecting) {

          entry.target.classList.add('is-visible');

          observer.unobserve(entry.target);

        }

      });

    }, { threshold: 0.08, rootMargin: '0px 0px -20px 0px' });



    revealElements.forEach(el => observer.observe(el));

  } else {

    revealElements.forEach(el => el.classList.add('is-visible'));

  }



  // =========================================================================

  // 7. Video Autoplay Fallback Verification

  // =========================================================================

  const showcaseVideo = document.querySelector('.fx-showcase-video');

  if (showcaseVideo) {

    const playPromise = showcaseVideo.play();

    if (playPromise !== undefined) {

      playPromise.catch(() => {

        // Autoplay muted was prevented or user preferred reduced data

      });

    }

  }



  // =========================================================================

  // 8. Smooth Anchor Scrolling with 76px Header Offset

  // =========================================================================

  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {

    anchor.addEventListener('click', function (e) {

      const targetId = this.getAttribute('href');

      if (targetId && targetId !== '#') {

        const targetEl = document.querySelector(targetId);

        if (targetEl) {

          e.preventDefault();

          closeMega();

          closeMobileNav();

          const navH = 76;

          const top = targetEl.getBoundingClientRect().top + window.scrollY - navH;

          window.scrollTo({ top, behavior: 'smooth' });

        }

      }

    });

  });



  // =========================================================================

  // 8.1 Detail Page: Interactive Hero Image Depth & Capability Cards

  // =========================================================================

  const heroImageCards = document.querySelectorAll('[data-hero-interactive-image]');

  const isReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;



  if (heroImageCards.length > 0 && !isReducedMotion) {

    heroImageCards.forEach((card) => {

      card.addEventListener('mousemove', (e) => {

        const rect = card.getBoundingClientRect();

        const x = (e.clientX - rect.left) / rect.width - 0.5;

        const y = (e.clientY - rect.top) / rect.height - 0.5;

        card.style.transform = `perspective(1000px) rotateY(${x * 5}deg) rotateX(${-y * 5}deg) translateY(-3px)`;

      });

      card.addEventListener('mouseleave', () => {

        card.style.transform = 'perspective(1000px) rotateY(0deg) rotateX(0deg) translateY(0px)';

      });

    });

  }



  const interactiveCards = document.querySelectorAll('[data-fx-interactive-card]');

  if (interactiveCards.length > 0) {

    interactiveCards.forEach((card) => {

      card.addEventListener('mouseenter', () => {

        interactiveCards.forEach(c => c.classList.remove('fx-capability-active'));

        card.classList.add('fx-capability-active');

      });

    });

  }



  // =========================================================================

  // 9. About Page: Five Core Principles Interactive Feature Cards

  // =========================================================================

  const principleCards = document.querySelectorAll('.fx-principle-card');

  if (principleCards.length > 0) {

    principleCards.forEach((card) => {

      // Remove is-pulsing after animation ends so it doesn't clash with hover/selected styles

      card.addEventListener('animationend', (e) => {

        if (e.animationName === 'fx-card-gold-pulse') {

          card.classList.remove('is-pulsing');

        }

      });



      const activateCard = (e) => {

        if (e && e.type === 'keydown') {

          e.preventDefault();

        }



        // Unset other cards

        principleCards.forEach((other) => {

          if (other !== card) {

            other.classList.remove('is-selected', 'is-pulsing');

            other.setAttribute('aria-pressed', 'false');

          }

        });



        // Set selected state

        card.classList.add('is-selected');

        card.setAttribute('aria-pressed', 'true');



        // Replay click pulse animation cleanly

        card.classList.remove('is-pulsing');

        void card.offsetWidth; // Force reflow

        card.classList.add('is-pulsing');

      };



      card.addEventListener('click', activateCard);

      card.addEventListener('keydown', (e) => {

        if (e.key === 'Enter' || e.key === ' ') {

          activateCard(e);

        }

      });

    });

  }



  // =========================================================================

  // 10. About Page: Hero Image Interaction (Click Zoom Animation)

  // =========================================================================

  const aboutHeroCard = document.querySelector('.fx-about-hero-card');

  const aboutHeroImg = document.querySelector('.fx-about-hero-img');



  if (aboutHeroCard && aboutHeroImg) {

    const triggerHeroZoomPulse = () => {

      // Re-trigger animation cleanly

      aboutHeroImg.classList.remove('is-clicked');

      void aboutHeroImg.offsetWidth; // Force DOM reflow to restart CSS animation

      aboutHeroImg.classList.add('is-clicked');

    };



    aboutHeroCard.addEventListener('click', triggerHeroZoomPulse);



    aboutHeroCard.addEventListener('keydown', (e) => {

      if (e.key === 'Enter' || e.key === ' ') {

        e.preventDefault();

        triggerHeroZoomPulse();

      }

    });



    aboutHeroImg.addEventListener('animationend', (e) => {

      if (e.animationName && e.animationName.indexOf('fx-hero-img-click') !== -1) {

        aboutHeroImg.classList.remove('is-clicked');

      }

    });

  }



  // =========================================================================

  // 11. About Page: Dual-Row Ecosystem Architecture Carousel

  // =========================================================================

  const ecosystemRows = document.querySelectorAll('.fx-ecosystem-row-wrapper');

  if (ecosystemRows.length > 0) {

    const isReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    const activeRows = [];



    ecosystemRows.forEach((rowEl) => {

      const rowId = parseInt(rowEl.getAttribute('data-fx-row'), 10) || 1;

      const direction = rowEl.getAttribute('data-direction') === 'right' ? 1 : -1;

      const track = rowEl.querySelector('.fx-carousel-track');

      const container = rowEl.querySelector('.fx-carousel-track-container');

      const prevBtn = rowEl.querySelector('.fx-nav-prev');

      const nextBtn = rowEl.querySelector('.fx-nav-next');

      const dots = Array.from(rowEl.querySelectorAll('.fx-dot'));



      if (!track || !container) return;



      const origCards = Array.from(track.children);

      const cardCount = origCards.length;



      // Duplicate cards for seamless continuous wrap

      origCards.forEach((c) => {

        const clone = c.cloneNode(true);

        clone.setAttribute('aria-hidden', 'true');

        clone.setAttribute('tabindex', '-1');

        clone.classList.add('is-clone');

        track.appendChild(clone);

      });



      // Find initial active index

      const initialActive = rowEl.querySelector('.fx-ecosystem-card.is-selected');

      const initialIndex = initialActive ? parseInt(initialActive.getAttribute('data-card-index'), 10) : 0;



      const rowState = {

        rowId,

        rowEl,

        track,

        container,

        direction, // -1: left (scrollPos increases), 1: right (scrollPos decreases)

        speed: 30, // px per second

        scrollPos: 0,

        singleSetWidth: 0,

        cardStep: 315,

        isPausedByUser: false,

        isHovered: false,

        selectedIndex: isNaN(initialIndex) ? 0 : initialIndex,

        isAnimatingStep: false,

        dots,

        allCards: Array.from(track.children)

      };



      // Measure dimensions

      const calculateDimensions = () => {

        if (track.children.length > cardCount) {

          const firstCard = track.children[0];

          const firstClone = track.children[cardCount];

          const dist = firstClone.getBoundingClientRect().left - firstCard.getBoundingClientRect().left;

          if (dist > 0) {

            rowState.singleSetWidth = dist;

            rowState.cardStep = dist / cardCount;

          }

        }

      };



      calculateDimensions();

      window.addEventListener('resize', calculateDimensions, { passive: true });



      // Start position for row 2 (moving right): start at singleSetWidth so it scrolls backwards cleanly

      if (direction === 1 && rowState.singleSetWidth > 0) {

        rowState.scrollPos = rowState.singleSetWidth;

      }



      // Synchronize selection state across original cards and clones

      const syncActiveCard = (index) => {

        rowState.selectedIndex = index;

        rowState.allCards.forEach((card) => {

          const cIdx = parseInt(card.getAttribute('data-card-index'), 10);

          if (cIdx === index) {

            card.classList.add('is-selected');

          } else {

            card.classList.remove('is-selected');

          }

        });

        rowState.dots.forEach((dot, dIdx) => {

          if (dIdx === index) {

            dot.classList.add('is-active');

            dot.setAttribute('aria-current', 'true');

          } else {

            dot.classList.remove('is-active');

            dot.removeAttribute('aria-current');

          }

        });

      };



      syncActiveCard(rowState.selectedIndex);



      // Card click interaction (Toggle pause/resume & card selection)

      rowState.allCards.forEach((card) => {

        card.addEventListener('click', (e) => {

          e.preventDefault();

          const clickedIndex = parseInt(card.getAttribute('data-card-index'), 10);

          if (isNaN(clickedIndex)) return;



          if (rowState.selectedIndex === clickedIndex && rowState.isPausedByUser) {

            // Clicking the same card again resumes scrolling

            rowState.isPausedByUser = false;

            rowEl.classList.remove('is-paused');

          } else {

            // Pauses the row and selects this card

            rowState.isPausedByUser = true;

            rowEl.classList.add('is-paused');

            syncActiveCard(clickedIndex);

          }

        });



        // Keyboard accessibility

        card.addEventListener('keydown', (e) => {

          if (e.key === 'Enter' || e.key === ' ') {

            e.preventDefault();

            card.click();

          }

        });

      });



      // Hover pause & resume

      rowEl.addEventListener('mouseenter', () => {

        rowState.isHovered = true;

      });



      rowEl.addEventListener('mouseleave', () => {

        rowState.isHovered = false;

      });



      // Smooth step navigation for arrows and dots

      const smoothScrollBy = (offset) => {

        if (rowState.singleSetWidth <= 0) return;

        const startPos = rowState.scrollPos;

        const duration = 380;

        const startTime = performance.now();

        rowState.isAnimatingStep = true;



        const animateStep = (now) => {

          const elapsed = now - startTime;

          const progress = Math.min(elapsed / duration, 1);

          // Ease-out cubic

          const ease = 1 - Math.pow(1 - progress, 3);

          let currentPos = startPos + offset * ease;



          while (currentPos < 0) currentPos += rowState.singleSetWidth;

          while (currentPos >= rowState.singleSetWidth) currentPos -= rowState.singleSetWidth;



          rowState.scrollPos = currentPos;

          track.style.transform = `translate3d(${-rowState.scrollPos}px, 0, 0)`;



          if (progress < 1) {

            requestAnimationFrame(animateStep);

          } else {

            rowState.isAnimatingStep = false;

          }

        };



        requestAnimationFrame(animateStep);

      };



      if (prevBtn) {

        prevBtn.addEventListener('click', (e) => {

          e.preventDefault();

          const stepDist = rowState.cardStep || 315;

          smoothScrollBy(-stepDist);

        });

      }



      if (nextBtn) {

        nextBtn.addEventListener('click', (e) => {

          e.preventDefault();

          const stepDist = rowState.cardStep || 315;

          smoothScrollBy(stepDist);

        });

      }



      // Dot click navigation

      dots.forEach((dot, dotIdx) => {

        dot.addEventListener('click', (e) => {

          e.preventDefault();

          syncActiveCard(dotIdx);

          const currentModuloIndex = Math.round(rowState.scrollPos / (rowState.cardStep || 315)) % cardCount;

          let diff = dotIdx - currentModuloIndex;

          if (diff > cardCount / 2) diff -= cardCount;

          if (diff < -cardCount / 2) diff += cardCount;

          smoothScrollBy(diff * (rowState.cardStep || 315));

        });

      });



      // Touch / Swipe support for mobile devices

      let touchStartX = 0;

      let touchStartScroll = 0;

      let isTouching = false;



      container.addEventListener('touchstart', (e) => {

        if (e.touches.length === 1) {

          isTouching = true;

          rowState.isHovered = true;

          touchStartX = e.touches[0].clientX;

          touchStartScroll = rowState.scrollPos;

        }

      }, { passive: true });



      container.addEventListener('touchmove', (e) => {

        if (!isTouching || e.touches.length !== 1) return;

        const deltaX = e.touches[0].clientX - touchStartX;

        let newPos = touchStartScroll - deltaX;

        while (newPos < 0 && rowState.singleSetWidth > 0) newPos += rowState.singleSetWidth;

        while (newPos >= rowState.singleSetWidth && rowState.singleSetWidth > 0) newPos -= rowState.singleSetWidth;

        rowState.scrollPos = newPos;

        track.style.transform = `translate3d(${-rowState.scrollPos}px, 0, 0)`;

      }, { passive: true });



      const finishTouch = () => {

        if (isTouching) {

          isTouching = false;

          rowState.isHovered = false;

        }

      };



      container.addEventListener('touchend', finishTouch, { passive: true });

      container.addEventListener('touchcancel', finishTouch, { passive: true });



      activeRows.push(rowState);

    });



    // Global RAF loop for continuous smooth auto-scrolling

    let lastTime = performance.now();



    const loop = (currentTime) => {

      const delta = Math.min((currentTime - lastTime) / 1000, 0.1);

      lastTime = currentTime;



      if (!isReducedMotion) {

        activeRows.forEach((row) => {

          if (!row.isPausedByUser && !row.isHovered && !row.isAnimatingStep && row.singleSetWidth > 0) {

            if (row.direction === -1) {

              // Scrolls to the left

              row.scrollPos += row.speed * delta;

              if (row.scrollPos >= row.singleSetWidth) {

                row.scrollPos -= row.singleSetWidth;

              }

            } else {

              // Scrolls to the right

              row.scrollPos -= row.speed * delta;

              if (row.scrollPos <= 0) {

                row.scrollPos += row.singleSetWidth;

              }

            }

            row.track.style.transform = `translate3d(${-row.scrollPos}px, 0, 0)`;

          }

        });

      }



      requestAnimationFrame(loop);

    };



    requestAnimationFrame(loop);

  }



  // =========================================================================

  // 12. Resources Page: Category Filter Logic

  // =========================================================================

  const resourceFilterButtons = document.querySelectorAll('.fx-resources-filter-bar .fx-filter-btn');

  const resourceCards = document.querySelectorAll('.fx-resource-card-col');

  const quickFilterTriggers = document.querySelectorAll('[data-filter-trigger]');



  if (resourceFilterButtons.length > 0 && resourceCards.length > 0) {

    const applyFilter = (filterKey) => {

      // Update filter button states

      resourceFilterButtons.forEach((btn) => {

        const isMatch = btn.getAttribute('data-filter') === filterKey;

        btn.classList.toggle('active', isMatch);

        btn.setAttribute('aria-selected', isMatch ? 'true' : 'false');

      });



      // Filter card columns

      resourceCards.forEach((cardCol) => {

        const cardCategory = cardCol.getAttribute('data-category');

        if (filterKey === 'all' || cardCategory === filterKey) {

          cardCol.style.display = '';

          cardCol.style.opacity = '0';

          cardCol.style.transform = 'translateY(12px)';

          requestAnimationFrame(() => {

            cardCol.style.transition = 'opacity 0.3s ease, transform 0.3s ease';

            cardCol.style.opacity = '1';

            cardCol.style.transform = 'translateY(0)';

          });

        } else {

          cardCol.style.display = 'none';

        }

      });

    };



    resourceFilterButtons.forEach((btn) => {

      btn.addEventListener('click', () => {

        const filter = btn.getAttribute('data-filter');

        applyFilter(filter);

      });

    });



    // Quick links in hero overlay

    quickFilterTriggers.forEach((trigger) => {

      trigger.addEventListener('click', (e) => {

        e.preventDefault();

        const category = trigger.getAttribute('data-filter-trigger');

        applyFilter(category);



        // Smooth scroll to catalog section

        const catalogSec = document.getElementById('resources-grid');

        if (catalogSec) {

          catalogSec.scrollIntoView({ behavior: 'smooth', block: 'start' });

        }

      });

    });

  }



  // =========================================================================
  // 13. Resources Page: Clean Article Modal Triggering (No Inline Expansion)
  // =========================================================================
  const resourceCardsList = document.querySelectorAll('.fx-resource-card');

  if (resourceCardsList.length > 0) {
    resourceCardsList.forEach((card) => {
      const readMoreLink = card.querySelector('.fx-read-more-link');

      const triggerModal = () => {
        if (typeof window.fxOpenArticleModal === 'function') {
          window.fxOpenArticleModal(readMoreLink, card);
        }
      };

      if (readMoreLink) {
        readMoreLink.addEventListener('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          e.stopImmediatePropagation();
          triggerModal();
        });
      }

      // Clicking anywhere on the card surface opens the modal
      card.addEventListener('click', (e) => {
        if (e.target.closest('a') || e.target.closest('button')) {
          return;
        }
        triggerModal();
      });

      // Keyboard accessibility (Enter or Space)
      card.addEventListener('keydown', (e) => {
        if ((e.key === 'Enter' || e.key === ' ') && !e.target.closest('a')) {
          if (e.target === card) {
            e.preventDefault();
            triggerModal();
          }
        }
      });
    });
  }



  // =========================================================================

  // 14. Features Page: 8-Stage Interactive Connected Service Flow Explanation

  // =========================================================================

  const featuresFlowRoot = document.getElementById('fx-features-workflow-section') || document.getElementById('fx-workflow-flow-section');

  if (featuresFlowRoot && !featuresFlowRoot.dataset.flowActive) {
    featuresFlowRoot.dataset.flowActive = 'true';

    const FLOW_STAGES = [

      {

        step: '01',

        title: 'Asset Monitored',

        category: 'Asset Telemetry & Monitoring',

        role: 'Telemetry Sensors & Asset Operators',

        desc: 'Continuous real-time tracking of operational vibration, temperature, pressure, and cycle counts to detect abnormal variances in baseline operating levels before equipment failure.',

        actionsBadge: 'IoT Telemetry & Sensing',

        actions: [

          'Gather automated telemetry streams from IoT sensors and plant SCADA systems.',

          'Conduct edge threshold analysis and continuous anomalous operations detection.',

          'Verify abnormal operational variance against historical baseline health models.',

          'Generate condition-based maintenance alerts when operating parameters exceed tolerance.'

        ],

        outcome: 'Abnormal operation identified and logged with comprehensive diagnostic telemetry.',

        handoff: 'Handoff \u2192 Stage 02: Service Request Logged',

        images: [

          { src: '/static/images/workflow-field-operations.jpg', caption: 'Real-time asset telemetry and condition monitoring' },

          { src: '/static/images/workflow-asset-management.jpg', caption: 'Asset health diagnostics and predictive condition tracking' },

          { src: '/static/images/operational-visibility.jpg', caption: 'Plant-wide equipment telemetry overview' }

        ]

      },

      {

        step: '02',

        title: 'Service Request Logged',

        category: 'Service Request & Triage',

        role: 'Service Desk Agent & Operations Dispatcher',

        desc: 'Incoming service requests triggered automatically by telemetry threshold breaches or submitted via customer portal are validated against SLA contract tiers and prioritized for resolution.',

        actionsBadge: 'Intake & SLA Triage',

        actions: [

          'Ingest automated telemetry alerts and customer portal service inquiries into unified ticket queue.',

          'Validate customer contract entitlements, SLA response windows, and warranty coverage.',

          'Perform initial triage, asset verification, and severity-level classification.',

          'Issue automated dispatch notifications and tracking IDs to requesters.'

        ],

        outcome: 'Qualified, SLA-classified service request logged with complete asset history and priority rating.',

        handoff: 'Handoff \u2192 Stage 03: Work Order Formulated',

        images: [

          { src: '/static/images/workflow-service-requests.jpg', caption: 'Automated service request intake and SLA contract triage' },

          { src: '/static/images/connected-data.jpg', caption: 'Centralized incident ticket management and priority queue' },

          { src: '/static/images/smarter-workflows.jpg', caption: 'Intelligent ticket routing and customer notification tracking' }

        ]

      },

      {

        step: '03',

        title: 'Work Order Formulated',

        category: 'Work Order Formulation',

        role: 'Maintenance Planner & Job Coordinator',

        desc: 'Maintenance planners convert approved service requests into structured work orders complete with task checklists, safety permits, tooling specifications, and estimated labor hours.',

        actionsBadge: 'Planning & SOP Scoping',

        actions: [

          'Convert verified service tickets into structured work orders with standard operating procedures.',

          'Attach mandatory job safety protocols, PPE requirements, and lockout/tagout (LOTO) steps.',

          'Estimate labor hours and match required technician skill certifications.',

          'Generate preliminary bill of materials and reserve components in inventory.'

        ],

        outcome: 'Comprehensive work package formulated with attached digital compliance checklists and resource plans.',

        handoff: 'Handoff \u2192 Stage 04: Technician Dispatched',

        images: [

          { src: '/static/images/module-work-orders.jpg', caption: 'Detailed work order formulation and procedural checklist design' },

          { src: '/static/images/module-maintenance.jpg', caption: 'Preventive and corrective maintenance job planning' },

          { src: '/static/images/fieldops-workflow-visual.jpg', caption: 'End-to-end maintenance workflow orchestration' }

        ]

      },

      {

        step: '04',

        title: 'Technician Dispatched',

        category: 'Technician Dispatch & Routing',

        role: 'Dispatch Controller & Mobile Field Technician',

        desc: 'Intelligent dispatch schedules certified technicians based on skill certifications and GPS proximity, syncing full job packets, schematics, and routing to mobile devices.',

        actionsBadge: 'Mobile Scheduling & Dispatch',

        actions: [

          'Match certified field engineers based on skills, tooling availability, and GPS proximity.',

          'Transmit digital work packets, schematics, and safety instructions directly to mobile devices.',

          'Track en-route travel milestones, estimated arrival times, and real-time transit status.',

          'Enable offline mobile execution and safety permit sign-off at the work site.'

        ],

        outcome: 'Certified technician arrives on-site equipped with full job schematics, parts, and safety clearance.',

        handoff: 'Handoff \u2192 Stage 05: Spare Parts Allocated',

        images: [

          { src: '/static/images/module-workforce.jpg', caption: 'Intelligent technician scheduling and GPS-enabled dispatch' },

          { src: '/static/images/workflow-field-operations.jpg', caption: 'Mobile field engineer dispatch and work order synchronization' },

          { src: '/static/images/module-organization.jpg', caption: 'Field workforce management and real-time resource tracking' }

        ]

      },

      {

        step: '05',

        title: 'Spare Parts Allocated',

        category: 'Spare Parts & Inventory Staging',

        role: 'Warehouse Manager & Inventory Controller',

        desc: 'All required replacement parts, tools, and consumables are staged from central depots or service vans and scanned to establish end-to-end serialized traceability.',

        actionsBadge: 'Inventory Allocation & Staging',

        actions: [

          'Verify stock availability across central warehouses, local depots, and service van inventories.',

          'Stage and kit required OEM replacement components and calibrated specialty tools.',

          'Scan 2D barcodes and RFID tags to link serial-tracked parts directly to the work order.',

          'Trigger automated reorder replenishment requests when inventory hits reorder thresholds.'

        ],

        outcome: 'All required components and tooling verified, scanned, and issued with serial-level audit tracking.',

        handoff: 'Handoff \u2192 Stage 06: Supervisor Verification',

        images: [

          { src: '/static/images/workflow-inventory-management.jpg', caption: 'Depot parts staging and serialized barcode inventory checkout' },

          { src: '/static/images/module-inventory.jpg', caption: 'Real-time stock level monitoring and component reservation' },

          { src: '/static/images/module-assets.jpg', caption: 'Asset-linked parts consumption and inventory traceability' }

        ]

      },

      {

        step: '06',

        title: 'Supervisor Verification',

        category: 'Supervisor Verification & QA',

        role: 'Field Supervisor & Quality Assurance Inspector',

        desc: 'Field supervisors conduct on-site or digital reviews of completed work orders, validating before-and-after photo evidence, diagnostic test logs, and technician labor timesheets.',

        actionsBadge: 'Quality Audit & Sign-Off',

        actions: [

          'Audit completed procedural checklists and review mandatory before/after photo documentation.',

          'Validate technical readings, vibration levels, and post-repair operational tolerances.',

          'Verify technician logged hours, travel time, and billable material consumption.',

          'Authorize formal technical sign-off and release work order for client acceptance.'

        ],

        outcome: 'Completed maintenance verified against engineering tolerances, safety standards, and QA protocols.',

        handoff: 'Handoff \u2192 Stage 07: Client Confirmation',

        images: [

          { src: '/static/images/workflow-approval.jpg', caption: 'Quality assurance verification and photographic proof review' },

          { src: '/static/images/workflow-insights.jpg', caption: 'Field supervisor inspection metrics and job performance review' },

          { src: '/static/images/smarter-workflows.jpg', caption: 'Engineering compliance validation and checklist sign-off' }

        ]

      },

      {

        step: '07',

        title: 'Client Confirmation',

        category: 'Client Confirmation & Sign-Off',

        role: 'Client Representative & Facility Manager',

        desc: 'Client representatives inspect completed repairs, observe equipment operational test runs, and provide legally binding on-glass digital signatures and satisfaction ratings.',

        actionsBadge: 'Client Acceptance & Sign-Off',

        actions: [

          'Present digital service summary, replaced components list, and test results to client.',

          'Witness live operational equipment run-up and confirm normal baseline operation.',

          'Capture cryptographic on-glass digital client signature and sign-off timestamp.',

          'Record immediate customer satisfaction (CSAT) rating and customer feedback.'

        ],

        outcome: 'Formal customer sign-off secured with digital signature and customer satisfaction feedback.',

        handoff: 'Handoff \u2192 Stage 08: Closure & Audit Trace',

        images: [

          { src: '/static/images/resources_hero.jpg', caption: 'On-site client sign-off and cryptographic digital signature capture' },

          { src: '/static/images/module-service.jpg', caption: 'Client service verification and satisfaction tracking' },

          { src: '/static/images/connected-data.jpg', caption: 'Client portal service history and completion confirmation' }

        ]

      },

      {

        step: '08',

        title: 'Closure & Audit Trace',

        category: 'Closure & Audit Trace',

        role: 'Compliance Auditor & Financial Controller',

        desc: 'The service lifecycle concludes with automated ledger postings into the ERP, asset master history updates, warranty tracking, and immutable SHA-256 audit trail compilation.',

        actionsBadge: 'ERP Settlement & Audit Seal',

        actions: [

          'Compile immutable chronological audit package with SHA-256 cryptographic hash.',

          'Post labor costs, consumed parts values, and travel expenses to ERP finance ledgers.',

          'Update asset maintenance logs, cumulative run-hours, and warranty records.',

          'Benchmark MTTR, first-time fix rate, and contractual SLA metrics for continuous improvement.'

        ],

        outcome: 'Tamper-proof audit record archived, ERP financials settled, and equipment returned to active service.',

        handoff: 'Loop Complete \u2192 Equipment returned to Stage 01: Asset Monitored',

        images: [

          { src: '/static/images/audit-traceability.jpg', caption: 'Cryptographic audit package archive and ERP financial reconciliation' },

          { src: '/static/images/module-analytics.jpg', caption: 'SLA compliance analytics and operational KPI reporting' },

          { src: '/static/images/workflow-insights.jpg', caption: 'Post-closure operational insights and reliability benchmarking' }

        ]

      }

    ];



    let currentStageIndex = 0;

    let currentGalleryIndex = 0;



    const stageCards = featuresFlowRoot.querySelectorAll('.fx-flow-stage-card');

    const flowPanel = document.getElementById('fx-flow-panel');

    const pillEl = document.getElementById('fx-flow-pill');

    const titleEl = document.getElementById('fx-flow-title');

    const descEl = document.getElementById('fx-flow-desc');

    const roleValEl = document.getElementById('fx-flow-role-val');

    const sectionBadgeEl = document.getElementById('fx-flow-section-badge');

    const actionsListEl = document.getElementById('fx-flow-actions-list');

    const outcomeTextEl = document.getElementById('fx-flow-outcome-text');

    const handoffNextEl = document.getElementById('fx-flow-handoff-next');

    const mainImgEl = document.getElementById('fx-flow-main-img');

    const mediaStepEl = document.getElementById('fx-flow-media-step');

    const mediaTitleEl = document.getElementById('fx-flow-media-title');

    const mediaCaptionEl = document.getElementById('fx-flow-media-caption');

    const prevBtn = document.getElementById('fx-flow-btn-prev');

    const nextBtn = document.getElementById('fx-flow-btn-next');



    // Gallery controls

    const galleryPrevBtn = document.getElementById('fx-gallery-prev');

    const galleryNextBtn = document.getElementById('fx-gallery-next');

    const thumbStripEl = document.getElementById('fx-gallery-thumb-strip');



    // -----------------------------------------------------------------------

    // Gallery: render image at galleryIdx for the currently active stage

    // -----------------------------------------------------------------------

    const renderGalleryImage = (galleryIdx, animate = true) => {

      const stage = FLOW_STAGES[currentStageIndex];

      if (!stage || !stage.images) return;



      const total = stage.images.length;

      currentGalleryIndex = (galleryIdx + total) % total; // wrap

      const imgData = stage.images[currentGalleryIndex];



      // Update main image

      if (mainImgEl) {

        if (animate) {

          mainImgEl.style.opacity = '0.45';

          setTimeout(() => {

            mainImgEl.src = imgData.src;

            mainImgEl.alt = `${stage.title} — image ${currentGalleryIndex + 1}`;

            mainImgEl.style.opacity = '1';

          }, 120);

        } else {

          mainImgEl.src = imgData.src;

          mainImgEl.alt = `${stage.title} — image ${currentGalleryIndex + 1}`;

        }

      }



      // Update caption

      if (mediaCaptionEl) mediaCaptionEl.textContent = imgData.caption;



      // Update arrow disabled states — keep enabled (wrap-around)

      if (galleryPrevBtn) galleryPrevBtn.disabled = false;

      if (galleryNextBtn) galleryNextBtn.disabled = false;



      // Highlight active thumbnail

      if (thumbStripEl) {

        thumbStripEl.querySelectorAll('.fx-gallery-thumb').forEach((th, i) => {

          th.classList.toggle('is-active', i === currentGalleryIndex);

        });

      }

    };



    // -----------------------------------------------------------------------

    // Gallery: rebuild thumbnail strip for the active stage

    // -----------------------------------------------------------------------

    const buildThumbStrip = (stageIdx) => {

      if (!thumbStripEl) return;

      const stage = FLOW_STAGES[stageIdx];

      if (!stage || !stage.images) { thumbStripEl.innerHTML = ''; return; }



      thumbStripEl.innerHTML = stage.images.map((img, i) => `

        <button type="button"

                class="fx-gallery-thumb${i === currentGalleryIndex ? ' is-active' : ''}"

                data-gallery-idx="${i}"

                aria-label="View image ${i + 1}: ${img.caption}">

          <img src="${img.src}" alt="" loading="lazy">

        </button>

      `).join('');



      thumbStripEl.querySelectorAll('.fx-gallery-thumb').forEach((btn) => {

        btn.addEventListener('click', () => {

          renderGalleryImage(parseInt(btn.dataset.galleryIdx, 10));

        });

      });

    };



    // -----------------------------------------------------------------------

    // Main stage renderer — wires columns 1 & 2 and resets gallery

    // -----------------------------------------------------------------------

    const renderStage = (index, animate = true) => {

      if (index < 0 || index >= FLOW_STAGES.length) return;

      currentStageIndex = index;

      currentGalleryIndex = 0;

      const stage = FLOW_STAGES[currentStageIndex];



      // Update stage cards active state

      stageCards.forEach((c, idx) => {

        const isActive = idx === currentStageIndex;

        c.classList.toggle('is-active', isActive);

        c.setAttribute('aria-selected', isActive ? 'true' : 'false');

        c.setAttribute('tabindex', isActive ? '0' : '-1');

      });



      // Subtle panel transition

      if (animate && flowPanel) {

        flowPanel.classList.add('is-switching');

        setTimeout(() => flowPanel.classList.remove('is-switching'), 200);

      }



      // Column 1: Stage Overview & Narrative

      if (pillEl) pillEl.textContent = `Stage ${stage.step} • ${stage.category}`;

      if (titleEl) titleEl.textContent = stage.title;

      if (roleValEl) roleValEl.textContent = stage.role;

      if (descEl) descEl.textContent = stage.desc;



      // Stage nav buttons (Previous Step / Next Workflow Step)

      if (prevBtn) {

        prevBtn.disabled = currentStageIndex === 0;

      }

      if (nextBtn) {

        if (currentStageIndex === FLOW_STAGES.length - 1) {

          nextBtn.innerHTML = '<span>Restart Flow</span> ↺';

        } else {

          nextBtn.innerHTML = '<span>Next Workflow Step</span> &rarr;';

        }

      }



      // Column 2: Key Actions & Handoff

      if (sectionBadgeEl) sectionBadgeEl.textContent = stage.actionsBadge || 'Stage Execution';

      if (actionsListEl) {

        actionsListEl.innerHTML = stage.actions.map((act, i) => `

          <div class="fx-flow-action-item">

            <span class="fx-flow-action-num">${i + 1}</span>

            <span>${act}</span>

          </div>

        `).join('');

      }



      if (outcomeTextEl) outcomeTextEl.textContent = stage.outcome;

      if (handoffNextEl) handoffNextEl.innerHTML = `<span>${stage.handoff}</span>`;



      // Column 3: Stage tag

      if (mediaStepEl) mediaStepEl.textContent = `STAGE ${stage.step}`;

      if (mediaTitleEl) mediaTitleEl.textContent = stage.title;



      // Rebuild thumbnails and show first image (no cross-fade on stage switch)

      buildThumbStrip(currentStageIndex);

      renderGalleryImage(0, animate);

    };



    // -----------------------------------------------------------------------

    // Gallery arrow event listeners

    // -----------------------------------------------------------------------

    if (galleryPrevBtn) {

      galleryPrevBtn.addEventListener('click', () => {

        renderGalleryImage(currentGalleryIndex - 1);

      });

    }

    if (galleryNextBtn) {

      galleryNextBtn.addEventListener('click', () => {

        renderGalleryImage(currentGalleryIndex + 1);

      });

    }



    // -----------------------------------------------------------------------

    // Stage timeline card events (click + keyboard)

    // -----------------------------------------------------------------------

    stageCards.forEach((card, idx) => {

      card.addEventListener('click', () => {

        renderStage(idx);

      });



      card.addEventListener('keydown', (e) => {

        if (e.key === 'Enter' || e.key === ' ') {

          e.preventDefault();

          renderStage(idx);

        } else if (e.key === 'ArrowRight') {

          e.preventDefault();

          const nextIdx = (idx + 1) % FLOW_STAGES.length;

          stageCards[nextIdx].focus();

          renderStage(nextIdx);

        } else if (e.key === 'ArrowLeft') {

          e.preventDefault();

          const prevIdx = (idx - 1 + FLOW_STAGES.length) % FLOW_STAGES.length;

          stageCards[prevIdx].focus();

          renderStage(prevIdx);

        }

      });

    });



    // Stage Prev / Next navigation buttons

    if (prevBtn) {

      prevBtn.addEventListener('click', () => {

        if (currentStageIndex > 0) {

          renderStage(currentStageIndex - 1);

        }

      });

    }



    if (nextBtn) {

      nextBtn.addEventListener('click', () => {

        if (currentStageIndex < FLOW_STAGES.length - 1) {

          renderStage(currentStageIndex + 1);

        } else {

          renderStage(0);

        }

      });

    }



    // Initial render

    renderStage(0, false);

  }


  // =========================================================================
  // 14. Anime.js Metric Counter Tweening
  // =========================================================================
  const initMetricCounters = () => {
    const counterElements = document.querySelectorAll('[data-fx-counter]');
    if (!counterElements.length) return;

    const prefersReducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (prefersReducedMotion || typeof window.anime !== 'function') {
      counterElements.forEach(el => {
        const target = el.getAttribute('data-fx-counter');
        const prefix = el.getAttribute('data-fx-prefix') || '';
        const suffix = el.getAttribute('data-fx-suffix') || '';
        el.textContent = prefix + target + suffix;
      });
      return;
    }

    if (!('IntersectionObserver' in window)) {
      counterElements.forEach(el => {
        const target = el.getAttribute('data-fx-counter');
        const prefix = el.getAttribute('data-fx-prefix') || '';
        const suffix = el.getAttribute('data-fx-suffix') || '';
        el.textContent = prefix + target + suffix;
      });
      return;
    }

    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        const el = entry.target;
        observer.unobserve(el);

        const rawTarget = parseFloat(el.getAttribute('data-fx-counter') || '0');
        const decimals = parseInt(el.getAttribute('data-fx-decimals') || '0', 10);
        const prefix = el.getAttribute('data-fx-prefix') || '';
        const suffix = el.getAttribute('data-fx-suffix') || '';

        const animObj = { val: 0 };
        window.anime({
          targets: animObj,
          val: rawTarget,
          duration: 1400,
          easing: 'easeOutExpo',
          update: () => {
            const formatted = decimals > 0 ? animObj.val.toFixed(decimals) : Math.round(animObj.val);
            el.textContent = prefix + formatted + suffix;
          },
          complete: () => {
            const finalVal = decimals > 0 ? rawTarget.toFixed(decimals) : Math.round(rawTarget);
            el.textContent = prefix + finalVal + suffix;
          }
        });
      });
    }, { threshold: 0.15, rootMargin: '0px 0px -40px 0px' });

    counterElements.forEach(el => observer.observe(el));
  };

  // =========================================================================
  // 15. Anime.js Staggered Card Entrance & Button Micro-Glow
  // =========================================================================
  const initStaggeredCards = () => {
    const cardContainers = document.querySelectorAll('.fx-module-grid, .fx-advantage-section .row.g-3');
    if (!cardContainers.length) return;

    const prefersReducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (prefersReducedMotion || typeof window.anime !== 'function') {
      cardContainers.forEach(container => {
        container.querySelectorAll('.module-card, .fx-pill-card, .landing-reveal').forEach(card => {
          card.classList.add('is-visible');
        });
      });
      return;
    }

    if (!('IntersectionObserver' in window)) {
      cardContainers.forEach(container => {
        container.querySelectorAll('.module-card, .fx-pill-card, .landing-reveal').forEach(card => {
          card.classList.add('is-visible');
        });
      });
      return;
    }

    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        const container = entry.target;
        observer.unobserve(container);

        const cards = container.querySelectorAll('.module-card, .fx-pill-card, .landing-reveal');
        if (!cards.length) return;

        window.anime({
          targets: cards,
          opacity: [0, 1],
          translateY: [24, 0],
          delay: window.anime.stagger(65, { start: 100 }),
          duration: 700,
          easing: 'easeOutCubic',
          complete: () => {
            cards.forEach(c => c.classList.add('is-visible'));
          }
        });
      });
    }, { threshold: 0.1, rootMargin: '0px 0px -30px 0px' });

    cardContainers.forEach(c => observer.observe(c));
  };

  const initCtaMicroGlow = () => {
    const rings = document.querySelectorAll('.fx-cta-rings, .fx-cta-rings-2');
    if (!rings.length) return;

    const prefersReducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReducedMotion || typeof window.anime !== 'function') return;

    window.anime({
      targets: rings,
      scale: [1, 1.05],
      opacity: [0.15, 0.3],
      direction: 'alternate',
      loop: true,
      easing: 'easeInOutQuad',
      duration: 3200
    });
  };

  initMetricCounters();
  initStaggeredCards();
  initCtaMicroGlow();
});
