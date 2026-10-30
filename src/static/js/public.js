/**
 * FieldOps Nexus — Public Marketing Interactivity (Vanilla JS)
 * High-performance 60fps animations, mega-menu interactions, and scroll telemetry.
 * Fully compliant with strict CSP (No inline scripts or handlers).
 */

document.addEventListener('DOMContentLoaded', () => {
  // =========================================================================
  // 1. Top Edge Gold Scroll Signal & NexusScrollFlow Telemetry 
  // =========================================================================
  const navScrollSignal = document.getElementById('nexus-nav-scroll-signal');
  const railLine = document.getElementById('nexus-rail-line');
  const signalHead = document.getElementById('nexus-signal-head');
  const stageTag = document.getElementById('nexus-stage-tag');

  const GLOBAL_STAGES = [
    { p: 0.00, label: "SIGNAL INITIATED" },
    { p: 0.20, label: "CONNECTED OPERATIONS" },
    { p: 0.45, label: "MODULE ECOSYSTEM" },
    { p: 0.70, label: "INTELLIGENCE & CONTROL" },
    { p: 0.92, label: "NETWORK SYNCHRONIZED" }
  ];

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

    // Top navbar indicator
    if (navScrollSignal) {
      navScrollSignal.style.transform = `scaleX(${progress})`;
    }

    // Right-rail telemetry
    if (railLine) {
      railLine.style.transform = `scaleY(${progress})`;
    }
    if (signalHead) {
      const y = progress * 220; // 220px track height
      signalHead.style.transform = `translate(-50%, -50%) translateY(${y}px)`;
    }
    if (stageTag) {
      let currentStage = GLOBAL_STAGES[0].label;
      for (let i = 0; i < GLOBAL_STAGES.length; i++) {
        if (progress >= GLOBAL_STAGES[i].p) {
          currentStage = GLOBAL_STAGES[i].label;
        }
      }
      stageTag.textContent = currentStage;
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
  // 4. 7-Step Interactive Workflow Timeline (Scroll-Synchronized)
  // =========================================================================
  const workflowSection = document.getElementById('workflow');
  const workflowLineFill = document.getElementById('workflow-line-fill');
  const workflowSteps = document.querySelectorAll('.fx-timeline-step');

  if (workflowSection && workflowLineFill && workflowSteps.length > 0) {
    let ticking = false;

    const handleWorkflowScroll = () => {
      if (!ticking) {
        requestAnimationFrame(() => {
          const rect = workflowSection.getBoundingClientRect();
          const vh = window.innerHeight;

          const startOffset = vh * 0.70;
          const endOffset = vh * 0.25;
          const totalDistance = rect.height + (startOffset - endOffset);
          const currentDistance = startOffset - rect.top;

          const rawProgress = currentDistance / totalDistance;
          const clamped = Math.min(Math.max(rawProgress, 0), 1);

          const isDesktop = window.innerWidth >= 768;
          if (isDesktop) {
            workflowLineFill.style.transform = `scaleX(${clamped})`;
          } else {
            workflowLineFill.style.transform = `scaleY(${clamped})`;
          }

          // Active step index (0 to 6)
          const activeIndex = Math.min(Math.max(Math.floor(clamped * 6 + 0.5), 0), 6);

          workflowSteps.forEach((step, idx) => {
            if (idx === activeIndex) {
              step.classList.add('active');
              step.classList.remove('completed');
            } else if (idx < activeIndex) {
              step.classList.remove('active');
              step.classList.add('completed');
            } else {
              step.classList.remove('active', 'completed');
            }
          });

          ticking = false;
        });
        ticking = true;
      }
    };

    window.addEventListener('scroll', handleWorkflowScroll, { passive: true });
    window.addEventListener('resize', handleWorkflowScroll, { passive: true });
    handleWorkflowScroll();
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
  // 13. Resources Page: Expandable Article Cards (Inline Expansion)
  // =========================================================================
  const resourceCardsList = document.querySelectorAll('.fx-resource-card');

  if (resourceCardsList.length > 0) {
    resourceCardsList.forEach((card) => {
      const expandBtn = card.querySelector('.fx-card-expand-btn');
      const collapseBtn = card.querySelector('.fx-collapse-trigger');
      const readMoreLink = card.querySelector('.fx-read-more-link');

      const toggleCard = (forceState) => {
        const isExpanded = card.classList.contains('is-expanded');
        const nextState = typeof forceState === 'boolean' ? forceState : !isExpanded;
        card.classList.toggle('is-expanded', nextState);
        if (expandBtn) {
          expandBtn.setAttribute('aria-expanded', nextState ? 'true' : 'false');
          expandBtn.setAttribute('title', nextState ? 'Collapse article' : 'Expand article');
        }
      };

      // Expand button or expand link ("Read Article")
      if (expandBtn) {
        expandBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          e.preventDefault();
          toggleCard();
        });
      }

      // Collapse button in footer
      if (collapseBtn) {
        collapseBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          e.preventDefault();
          toggleCard(false);
        });
      }

      // Read Article control (button or link)
      if (readMoreLink) {
        readMoreLink.addEventListener('click', (e) => {
          e.stopPropagation();
          if (readMoreLink.classList.contains('fx-card-expand-link') || readMoreLink.tagName.toLowerCase() === 'button') {
            e.preventDefault();
            toggleCard();
          }
        });
      }

      // Clicking anywhere on the card surface toggles expansion (except links/buttons)
      card.addEventListener('click', (e) => {
        if (e.target.closest('a') || e.target.closest('button')) {
          return;
        }
        toggleCard();
      });

      // Keyboard accessibility (Enter or Space)
      card.addEventListener('keydown', (e) => {
        if ((e.key === 'Enter' || e.key === ' ') && !e.target.closest('a')) {
          if (e.target === card || e.target === expandBtn || e.target === collapseBtn) {
            e.preventDefault();
            toggleCard();
          }
        }
      });
    });
  }

  // =========================================================================
  // 14. Features Page: 8-Stage Interactive Connected Service Flow Explanation
  // =========================================================================
  const featuresFlowRoot = document.getElementById('fx-workflow-flow-section');
  if (featuresFlowRoot) {
    const FLOW_STAGES = [
      {
        step: '01',
        title: 'Asset Monitored',
        category: 'Telemetry / Sensor',
        role: 'Telemetry Sensors & Asset Operators',
        desc: 'Continuous real-time monitoring tracks operational vibration, temperature, pressure, and cycle counts to detect early deviations from normal operating baselines before failure occurs.',
        actions: [
          'Capture automated telemetry feeds from IoT sensors and plant SCADA systems.',
          'Run edge threshold checks and continuous anomaly detection algorithms.',
          'Validate abnormal operational variances against historical performance baselines.',
          'Trigger condition-based maintenance alert when safety tolerances exceed thresholds.'
        ],
        outcome: 'Operational anomaly verified and logged with complete diagnostic telemetry payload.',
        handoff: 'Handoff \u2192 Stage 02: Service Request Logged',
        images: [
          { src: '/static/images/workflow-field-operations.jpg', caption: 'Real-time asset telemetry & condition monitoring capture' },
          { src: '/static/images/workflow-asset-management.jpg', caption: 'Asset lifecycle & health status tracking' },
          { src: '/static/images/operational-visibility.jpg', caption: 'Operational visibility across field assets' }
        ]
      },
      {
        step: '02',
        title: 'Service Request Logged',
        category: 'Client / Requester',
        role: 'Client Representative & Service Desk',
        desc: 'Maintenance requests\u2014whether auto-triggered by telemetry or submitted via customer portal\u2014are validated, prioritized by SLA tier, and prepared for planning.',
        actions: [
          'Ingest automated telemetry tickets and customer-submitted service inquiries.',
          'Verify client contract coverage, SLA response deadlines, and priority tier.',
          'Perform initial triage, asset verification, and severity categorization.',
          'Issue confirmation to requester with ticket tracking and expected arrival window.'
        ],
        outcome: 'Qualified, SLA-tagged service ticket generated with asset history and urgency tier.',
        handoff: 'Handoff \u2192 Stage 03: Work Order Formulated',
        images: [
          { src: '/static/images/workflow-service-requests.jpg', caption: 'Customer request intake & automated SLA contract triage' },
          { src: '/static/images/connected-data.jpg', caption: 'Centralised service request management dashboard' },
          { src: '/static/images/smarter-workflows.jpg', caption: 'Intelligent workflow routing & SLA prioritisation' }
        ]
      },
      {
        step: '03',
        title: 'Work Order Formulated',
        category: 'Maintenance Planner',
        role: 'Maintenance Planner & Operations Coordinator',
        desc: 'Planners transform raw service requests into structured work orders with procedural task checklists, required tooling, safety guidelines, and labor requirements.',
        actions: [
          'Define detailed operational scope, task steps, and standard operating procedures.',
          'Attach mandatory safety protocols, hazard mitigation steps, and PPE requirements.',
          'Estimate job duration and match required technician certifications and skills.',
          'Link bill of materials and reserve preliminary spare parts from inventory.'
        ],
        outcome: 'Comprehensive work package generated with attached digital compliance checklists.',
        handoff: 'Handoff \u2192 Stage 04: Technician Dispatched',
        images: [
          { src: '/static/images/module-work-orders.jpg', caption: 'Detailed work package formulation & task checklist design' },
          { src: '/static/images/module-maintenance.jpg', caption: 'Preventive & corrective maintenance planning' },
          { src: '/static/images/fieldops-workflow-visual.jpg', caption: 'End-to-end workflow orchestration' }
        ]
      },
      {
        step: '04',
        title: 'Technician Dispatched',
        category: 'Field Technician',
        role: 'Dispatch Controller & Mobile Field Technician',
        desc: 'The work order is assigned using skill-based and location-aware scheduling, transmitting full job context, schematics, and route navigation to the technician mobile device.',
        actions: [
          'Match qualified technicians based on skills, certifications, and real-time proximity.',
          'Sync complete work order packet, asset history, and safety instructions to mobile app.',
          'Track en-route status, travel duration, and GPS arrival at the physical job site.',
          'Enable offline task execution and safety checklist sign-off at point of work.'
        ],
        outcome: 'Certified technician arrives on site fully equipped with job context and safety clearance.',
        handoff: 'Handoff \u2192 Stage 05: Spare Parts Allocated',
        images: [
          { src: '/static/images/module-workforce.jpg', caption: 'Skill-based mobile dispatch & technician geolocation' },
          { src: '/static/images/workflow-field-operations.jpg', caption: 'Field technician mobile job execution' },
          { src: '/static/images/module-organization.jpg', caption: 'Team scheduling & workforce management' }
        ]
      },
      {
        step: '05',
        title: 'Spare Parts Allocated',
        category: 'Warehouse / Stock',
        role: 'Warehouse Manager & Inventory Controller',
        desc: 'Every part, tool, and consumable required for the work order is verified, staged from depot stock or van inventory, and scanned to guarantee traceability.',
        actions: [
          'Check real-time stock levels across central depots, local staging, and technician vans.',
          'Reserve and stage required replacement components and specialized tooling.',
          'Scan barcodes and serial numbers to link consumed parts directly to the work order.',
          'Auto-trigger min-max inventory replenishment orders for consumed stock items.'
        ],
        outcome: 'All required components are verified and physically issued with serial-level audit tracking.',
        handoff: 'Handoff \u2192 Stage 06: Supervisor Verification',
        images: [
          { src: '/static/images/workflow-inventory-management.jpg', caption: 'Depot & van stock staging with barcode serialization' },
          { src: '/static/images/module-inventory.jpg', caption: 'Real-time inventory levels & reserve management' },
          { src: '/static/images/module-assets.jpg', caption: 'Parts traceability & asset-linked consumption' }
        ]
      },
      {
        step: '06',
        title: 'Supervisor Verification',
        category: 'Field Supervisor',
        role: 'Field Operations Supervisor & Quality Inspector',
        desc: 'Field supervisors inspect completed maintenance work, review before-and-after photo evidence, check test measurements, and approve labor timesheets.',
        actions: [
          'Audit digital checklist completion and mandatory before/after photo documentation.',
          'Verify technical measurements and operational test runs against tolerance specs.',
          'Review recorded technician labor hours, travel time, and material consumption.',
          'Authorize formal technical sign-off and mark job as ready for customer handover.'
        ],
        outcome: 'Work order validated for engineering quality, regulatory compliance, and safety standards.',
        handoff: 'Handoff \u2192 Stage 07: Client Confirmation',
        images: [
          { src: '/static/images/workflow-approval.jpg', caption: 'Quality assurance verification & photographic evidence review' },
          { src: '/static/images/workflow-insights.jpg', caption: 'Supervisor dashboard & field team performance insights' },
          { src: '/static/images/smarter-workflows.jpg', caption: 'Compliance sign-off & checklist audit trail' }
        ]
      },
      {
        step: '07',
        title: 'Client Confirmation',
        category: 'Client Representative',
        role: 'Client Representative & Facility Manager',
        desc: 'The client inspects the completed work, witnesses equipment run-up and testing, and provides cryptographic on-glass digital signature confirmation.',
        actions: [
          'Review service executive summary and resolution documentation on-site or via portal.',
          'Perform equipment test run-up and verify restored operational conditions.',
          'Capture client digital signature and timestamp on mobile device glass.',
          'Collect instant customer satisfaction rating (CSAT) and service feedback.'
        ],
        outcome: 'Formal client acceptance signed and immutable customer satisfaction recorded.',
        handoff: 'Handoff \u2192 Stage 08: Closure & Audit Trace',
        images: [
          { src: '/static/images/resources_hero.jpg', caption: 'Client acceptance sign-off & on-glass digital signature' },
          { src: '/static/images/module-service.jpg', caption: 'Service delivery & client satisfaction management' },
          { src: '/static/images/connected-data.jpg', caption: 'Client portal & real-time service status' }
        ]
      },
      {
        step: '08',
        title: 'Closure & Audit Trace',
        category: 'Compliance & Finance',
        role: 'Compliance Auditor & Finance Controller',
        desc: 'The workflow terminates with complete tamper-proof audit trails, automated ledger journal postings into the ERP, warranty updates, and SLA performance calculations.',
        actions: [
          'Compile full chronological activity history with cryptographic SHA-256 integrity hash.',
          'Post labor hours, consumed material costs, and invoice details to ERP finance ledger.',
          'Update asset master record with new service history, run hours, and warranty expiration.',
          'Calculate final MTTR, first-time fix rate, and contractual SLA compliance metrics.'
        ],
        outcome: 'Legally binding, permanent audit record generated; asset record updated; financials settled.',
        handoff: 'Loop Complete \u2192 Equipment returned to Stage 01 Monitoring',
        images: [
          { src: '/static/images/audit-traceability.jpg', caption: 'Immutable audit package & ERP financial reconciliation' },
          { src: '/static/images/module-analytics.jpg', caption: 'SLA performance analytics & compliance reporting' },
          { src: '/static/images/workflow-insights.jpg', caption: 'Post-closure insights & KPI benchmarking' }
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
    const actionsListEl = document.getElementById('fx-flow-actions-list');
    const outcomeTextEl = document.getElementById('fx-flow-outcome-text');
    const handoffNextEl = document.getElementById('fx-flow-handoff-next');
    const mainImgEl = document.getElementById('fx-flow-main-img');
    const mediaStepEl = document.getElementById('fx-flow-media-step');
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
      if (actionsListEl) {
        actionsListEl.innerHTML = stage.actions.map((act, i) => `
          <div class="fx-flow-action-item">
            <span class="fx-flow-action-num">${i + 1}</span>
            <span>${act}</span>
          </div>
        `).join('');
      }

      if (outcomeTextEl) outcomeTextEl.textContent = stage.outcome;
      if (handoffNextEl) handoffNextEl.textContent = stage.handoff;

      // Column 3: Stage tag
      if (mediaStepEl) mediaStepEl.textContent = `STAGE ${stage.step}`;

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
});