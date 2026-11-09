import json

with open(r"FieldOps_Nexus_Internal\src\templates\public\resources.html", "r", encoding="utf-8") as f:
    orig = f.read()

with open(r"FieldOps_Nexus_Internal\scratch\extracted_cards.json", "r", encoding="utf-8") as f:
    cards = json.load(f)

# Find prefix (up to <div class="fx-resources-grid">)
grid_start_idx = orig.find('<div class="fx-resources-grid">')
prefix = orig[:grid_start_idx + len('<div class="fx-resources-grid">\n')]

# Find suffix (from </section> after the cards grid)
faq_idx = orig.find('<!-- Frequently Asked Questions (FAQ) Section -->')
if faq_idx == -1:
    faq_idx = orig.find('<section class="fx-faq-section"')

# Generate new cards HTML
cards_html_parts = []
for i, c in enumerate(cards, 1):
    card_html = f'''      <!-- Card {i}: {c['title']} -->
      <div class="fx-resource-card-col" data-category="{c['category_slug']}">
        <article class="fx-resource-card" tabindex="0" role="region" aria-label="{c['title']}">
          <div class="fx-resource-thumb-wrap">
            <img src="{c['img_src']}" alt="{c['img_alt']}" class="fx-resource-thumb" loading="lazy">
          </div>
          <div class="fx-resource-card-body">
            <div class="fx-card-top-meta">
              <span class="fx-card-category">{c['cat_badge']}</span>
              <span class="fx-card-read-time">{c['read_time']}</span>
            </div>
            <h3 class="fx-card-title">{c['title']}</h3>
            <p class="fx-card-desc">{c['desc']}</p>
            <div class="fx-card-footer">
              <span class="fx-card-date">{c['date']}</span>
              <button type="button" class="fx-read-more-link fx-article-modal-trigger"
                data-category="{c['cat_badge']}"
                data-title="{c['title']}"
                data-date="{c['date']}"
                data-read-time="{c['read_time']}"
                data-image="{c['img_src']}"
                data-description="{c['desc']}"
                aria-label="Read article: {c['title']}">
                <span>Read Article</span>
                <span class="fx-read-more-arrow">&gt;</span>
              </button>
            </div>
          </div>

          <!-- Rich Article Content Payload for Modal -->
          <div class="fx-card-modal-payload" hidden aria-hidden="true">
            <div class="fx-payload-extended">{c['extended']}</div>
            <div class="fx-payload-takeaways">
              {c['takeaways_html']}
            </div>
            <div class="fx-payload-badge">{c['badge']}</div>
          </div>
        </article>
      </div>
'''
    cards_html_parts.append(card_html)

cards_html = "\n".join(cards_html_parts) + "\n    </div>\n  </div>\n</section>\n\n"

# Suffix includes FAQ, Modal, and Script
faq_section_text = orig[faq_idx:orig.find('<!-- Article Reading Modal -->')]

modal_and_script = '''<!-- Article Reading Modal -->
<div id="fx-article-modal-overlay" class="fx-article-overlay" role="dialog" aria-modal="true" aria-labelledby="fx-modal-title" hidden>
  <div class="fx-article-modal" id="fx-article-modal">
    <button type="button" class="fx-modal-close" id="fx-modal-close" aria-label="Close article modal">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <line x1="18" y1="6" x2="6" y2="18"></line>
        <line x1="6" y1="6" x2="18" y2="18"></line>
      </svg>
    </button>
    <div class="fx-modal-scroll-inner">
      <div class="fx-modal-category-badge" id="fx-modal-category">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
        <span id="fx-modal-category-text"></span>
      </div>
      <h2 class="fx-modal-title" id="fx-modal-title"></h2>
      <div class="fx-modal-meta">
        <span class="d-inline-flex align-items-center gap-1">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
          <span id="fx-modal-date"></span>
        </span>
        <span class="fx-modal-meta-dot">&bull;</span>
        <span class="d-inline-flex align-items-center gap-1">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          <span id="fx-modal-readtime"></span>
        </span>
      </div>
      <img id="fx-modal-image" class="fx-modal-cover-img" src="" alt="">
      
      <!-- Article Lead Description -->
      <p class="fx-modal-desc" id="fx-modal-desc"></p>

      <!-- Complete Extended Article Content -->
      <div class="fx-modal-extended-text" id="fx-modal-extended"></div>

      <!-- Key Takeaways Box with Icons & Badges -->
      <div class="fx-modal-takeaways-box" id="fx-modal-takeaways"></div>

      <!-- Footer Tag / Badge -->
      <div class="fx-modal-footer-meta" id="fx-modal-footer-meta">
        <span class="fx-modal-badge" id="fx-modal-badge"></span>
      </div>
    </div>
  </div>
</div>
{% endblock %}

{% block scripts %}{{ block.super }}
<script nonce="{{ csp_nonce }}">
(function () {
  'use strict';

  var overlay     = document.getElementById('fx-article-modal-overlay');
  var modal       = document.getElementById('fx-article-modal');
  var closeBtn    = document.getElementById('fx-modal-close');
  var categoryEl  = document.getElementById('fx-modal-category-text');
  var titleEl     = document.getElementById('fx-modal-title');
  var dateEl      = document.getElementById('fx-modal-date');
  var readtimeEl  = document.getElementById('fx-modal-readtime');
  var imageEl     = document.getElementById('fx-modal-image');
  var descEl      = document.getElementById('fx-modal-desc');
  var extendedEl  = document.getElementById('fx-modal-extended');
  var takeawaysEl = document.getElementById('fx-modal-takeaways');
  var badgeEl     = document.getElementById('fx-modal-badge');
  var footerMetaEl= document.getElementById('fx-modal-footer-meta');

  function openModal(btn, card) {
    if (!overlay) return;
    var c = card || (btn ? btn.closest('.fx-resource-card') : null);
    if (!c) return;

    var catText   = (btn && btn.dataset && btn.dataset.category) || c.querySelector('.fx-card-category')?.textContent?.trim() || '';
    var titleText = (btn && btn.dataset && btn.dataset.title)    || c.querySelector('.fx-card-title')?.textContent?.trim() || '';
    var dateText  = (btn && btn.dataset && btn.dataset.date)     || c.querySelector('.fx-card-date')?.textContent?.trim() || '';
    var readText  = (btn && btn.dataset && btn.dataset.readTime) || c.querySelector('.fx-card-read-time')?.textContent?.trim() || '';
    var imgSrc    = (btn && btn.dataset && btn.dataset.image)    || c.querySelector('.fx-resource-thumb')?.getAttribute('src') || '';
    var descText  = (btn && btn.dataset && btn.dataset.description) || c.querySelector('.fx-card-desc')?.textContent?.trim() || '';

    var payload = c.querySelector('.fx-card-modal-payload');
    var extendedHtml  = payload ? (payload.querySelector('.fx-payload-extended')?.innerHTML || '') : '';
    var takeawaysHtml = payload ? (payload.querySelector('.fx-payload-takeaways')?.innerHTML || '') : '';
    var badgeText     = payload ? (payload.querySelector('.fx-payload-badge')?.textContent?.trim() || '') : '';

    if (categoryEl) categoryEl.textContent = catText;
    if (titleEl)    titleEl.textContent    = titleText;
    if (dateEl)     dateEl.textContent     = dateText;
    if (readtimeEl) readtimeEl.textContent = readText;
    if (imageEl) {
      imageEl.src = imgSrc;
      imageEl.alt = titleText;
    }
    if (descEl) descEl.textContent = descText;

    if (extendedEl) {
      extendedEl.innerHTML = extendedHtml;
      extendedEl.style.display = extendedHtml ? 'block' : 'none';
    }

    if (takeawaysEl) {
      takeawaysEl.innerHTML = takeawaysHtml;
      takeawaysEl.style.display = takeawaysHtml ? 'block' : 'none';
    }

    if (badgeEl && footerMetaEl) {
      badgeEl.textContent = badgeText;
      footerMetaEl.style.display = badgeText ? 'block' : 'none';
    }

    var scrollInner = modal ? modal.querySelector('.fx-modal-scroll-inner') : null;
    if (scrollInner) scrollInner.scrollTop = 0;

    overlay.removeAttribute('hidden');
    void overlay.offsetWidth;
    overlay.classList.add('is-open');
    document.body.style.overflow = 'hidden';
    if (closeBtn) closeBtn.focus();
  }

  function closeModal() {
    if (!overlay) return;
    overlay.classList.remove('is-open');
    document.body.style.overflow = '';
    setTimeout(function () {
      if (!overlay.classList.contains('is-open')) {
        overlay.setAttribute('hidden', '');
      }
    }, 250);
  }

  window.fxOpenArticleModal = openModal;
  window.fxCloseArticleModal = closeModal;

  document.querySelectorAll('.fx-article-modal-trigger, .fx-read-more-link').forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      openModal(btn, btn.closest('.fx-resource-card'));
    });
  });

  document.querySelectorAll('.fx-resource-card').forEach(function (card) {
    card.addEventListener('click', function (e) {
      if (e.target.closest('a') || e.target.closest('button')) return;
      openModal(null, card);
    });
  });

  if (closeBtn) closeBtn.addEventListener('click', closeModal);

  if (overlay) {
    overlay.addEventListener('click', function (e) {
      if (modal && !modal.contains(e.target)) {
        closeModal();
      }
    });
  }

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && overlay && !overlay.hasAttribute('hidden')) {
      closeModal();
    }
  });
})();
</script>
'''

full_new_content = prefix + cards_html + faq_section_text + modal_and_script

with open(r"FieldOps_Nexus_Internal\src\templates\public\resources.html", "w", encoding="utf-8") as f:
    f.write(full_new_content)

print("Updated resources.html successfully!")

