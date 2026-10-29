/**
 * FieldOps Nexus — Product, Solutions & Modules Detail Pages Interactivity
 * High-performance 60fps animations, 3D card tilts, and staggered scroll reveals.
 * Fully compliant with strict CSP (No inline scripts or handlers).
 */

document.addEventListener('DOMContentLoaded', () => {
  const isReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // =========================================================================
  // 1. Scroll-Reveal Observer for Detail Sections & Cards
  // =========================================================================
  const revealElements = document.querySelectorAll('.fx-reveal');

  if (revealElements.length > 0) {
    if ('IntersectionObserver' in window && !isReducedMotion) {
      const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible');
            observer.unobserve(entry.target);
          }
        });
      }, {
        threshold: 0.08,
        rootMargin: '0px 0px -25px 0px',
      });

      revealElements.forEach((el) => observer.observe(el));
    } else {
      // Fallback or reduced-motion: make visible immediately
      revealElements.forEach((el) => el.classList.add('is-visible'));
    }
  }

  // =========================================================================
  // 2. Interactive Hero Image Depth & Gentle Parallax
  // =========================================================================
  const heroImageCards = document.querySelectorAll('[data-hero-interactive-image]');

  if (heroImageCards.length > 0 && !isReducedMotion) {
    heroImageCards.forEach((card) => {
      let isHovering = false;

      card.addEventListener('mouseenter', () => {
        isHovering = true;
      });

      card.addEventListener('mousemove', (e) => {
        if (!isHovering) return;
        const rect = card.getBoundingClientRect();
        const x = (e.clientX - rect.left) / rect.width - 0.5;
        const y = (e.clientY - rect.top) / rect.height - 0.5;
        card.style.transform = `perspective(1000px) rotateY(${x * 5}deg) rotateX(${-y * 5}deg) translateY(-3px)`;
      });

      card.addEventListener('mouseleave', () => {
        isHovering = false;
        card.style.transform = 'perspective(1000px) rotateY(0deg) rotateX(0deg) translateY(0px)';
      });
    });
  }

  // =========================================================================
  // 3. Interactive Capabilities Card Synchronization
  // =========================================================================
  const interactiveCards = document.querySelectorAll('[data-fx-interactive-card]');

  if (interactiveCards.length > 0) {
    interactiveCards.forEach((card) => {
      card.addEventListener('mouseenter', () => {
        interactiveCards.forEach((c) => c.classList.remove('fx-capability-active'));
        card.classList.add('fx-capability-active');
      });
    });
  }

  // =========================================================================
  // 4. Smooth Anchor Scrolling for Page Actions (e.g. #capabilities)
  // =========================================================================
  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener('click', function (e) {
      const targetId = this.getAttribute('href');
      if (targetId && targetId !== '#') {
        const targetEl = document.querySelector(targetId);
        if (targetEl) {
          e.preventDefault();
          const navH = 80;
          const top = targetEl.getBoundingClientRect().top + window.scrollY - navH;
          window.scrollTo({ top, behavior: 'smooth' });
        }
      }
    });
  });
});

