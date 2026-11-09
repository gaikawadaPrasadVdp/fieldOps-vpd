with open(r"FieldOps_Nexus_Internal\src\static\js\public.js", "r", encoding="utf-8") as f:
    js_content = f.read()

target = '''  // =========================================================================

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
          e.preventDefault();
          e.stopPropagation();
          e.stopImmediatePropagation();

          if (typeof window.fxOpenArticleModal === 'function') {
            window.fxOpenArticleModal(readMoreLink, card);
          } else {
            // Fallback if modal handler not yet loaded
            const overlay = document.getElementById('fx-article-modal-overlay');
            if (overlay) {
              const d = readMoreLink.dataset;
              const cat = document.getElementById('fx-modal-category-text');
              const title = document.getElementById('fx-modal-title');
              const date = document.getElementById('fx-modal-date');
              const readtime = document.getElementById('fx-modal-readtime');
              const img = document.getElementById('fx-modal-image');
              const desc = document.getElementById('fx-modal-desc');

              if (cat) cat.textContent = d.category || card.querySelector('.fx-card-category')?.textContent?.trim() || '';
              if (title) title.textContent = d.title || card.querySelector('.fx-card-title')?.textContent?.trim() || '';
              if (date) date.textContent = d.date || card.querySelector('.fx-card-date')?.textContent?.trim() || '';
              if (readtime) readtime.textContent = d.readTime || card.querySelector('.fx-card-read-time')?.textContent?.trim() || '';
              if (img) {
                img.src = d.image || card.querySelector('.fx-resource-thumb')?.getAttribute('src') || '';
                img.alt = d.title || '';
              }
              if (desc) desc.textContent = d.description || card.querySelector('.fx-card-desc')?.textContent?.trim() || '';

              overlay.removeAttribute('hidden');
              void overlay.offsetWidth;
              overlay.classList.add('is-open');
              document.body.style.overflow = 'hidden';
            }
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

  }'''

replacement = '''  // =========================================================================
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
  }'''

# Normalize line endings before replace
js_normalized = js_content.replace('\r\n', '\n')
target_normalized = target.replace('\r\n', '\n')

if target_normalized in js_normalized:
    js_updated = js_normalized.replace(target_normalized, replacement)
    with open(r"FieldOps_Nexus_Internal\src\static\js\public.js", "w", encoding="utf-8") as f:
        f.write(js_updated)
    print("public.js updated successfully!")
else:
    print("Target block not found in public.js!")

