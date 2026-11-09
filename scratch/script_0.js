
(function () {
  'use strict';

  var overlay  = document.getElementById('fx-article-modal-overlay');
  var modal    = document.getElementById('fx-article-modal');
  var closeBtn = document.getElementById('fx-modal-close');
  var categoryEl = document.getElementById('fx-modal-category-text');
  var titleEl    = document.getElementById('fx-modal-title');
  var dateEl     = document.getElementById('fx-modal-date');
  var readtimeEl = document.getElementById('fx-modal-readtime');
  var imageEl    = document.getElementById('fx-modal-image');
  var descEl     = document.getElementById('fx-modal-desc');
  var bodyEl     = document.getElementById('fx-modal-body');

  function openModal(btn) {
    var d = btn.dataset;
    categoryEl.textContent = d.category    || '';
    titleEl.textContent    = d.title       || '';
    dateEl.textContent     = d.date        || '';
    readtimeEl.textContent = d.readTime    || '';
    imageEl.src            = d.image       || '';
    imageEl.alt            = d.title       || '';
    descEl.textContent     = d.description || '';
    bodyEl.textContent     = d.body        || '';

    overlay.removeAttribute('hidden');
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        overlay.classList.add('is-open');
      });
    });
    document.body.style.overflow = 'hidden';
    closeBtn.focus();
  }

  function closeModal() {
    overlay.classList.remove('is-open');
    overlay.addEventListener('transitionend', function handler() {
      overlay.setAttribute('hidden', '');
      overlay.removeEventListener('transitionend', handler);
    });
    document.body.style.overflow = '';
  }

  document.querySelectorAll('.fx-article-modal-trigger').forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      openModal(btn);
    });
  });

  closeBtn.addEventListener('click', closeModal);

  overlay.addEventListener('click', function (e) {
    if (!modal.contains(e.target)) {
      closeModal();
    }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && !overlay.hasAttribute('hidden')) {
      closeModal();
    }
  });
})();
