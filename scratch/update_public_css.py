with open(r"FieldOps_Nexus_Internal\src\static\css\public.css", "r", encoding="utf-8") as f:
    css_content = f.read()

# Normalize
css_norm = css_content.replace('\r\n', '\n')

# Find where .fx-article-overlay starts
overlay_idx = css_norm.find('.fx-article-overlay {')
if overlay_idx == -1:
    overlay_idx = css_norm.find('/* Article Reading Modal */')
print(f"overlay_idx: {overlay_idx}")

prefix = css_norm[:overlay_idx]

new_modal_css = '''/* =========================================================================
   Article Reading Modal Styles (Premium Enterprise Layout)
   ========================================================================= */
.fx-article-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(11, 31, 59, 0.78);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.25s ease;
}

.fx-article-overlay.is-open {
  opacity: 1;
  pointer-events: auto;
}

.fx-article-overlay[hidden] {
  display: none !important;
}

/* Modal box - White background, large rounded corners, centered */
.fx-article-modal {
  background: #FFFFFF;
  border-radius: 28px;
  max-width: 860px;
  width: 100%;
  max-height: 88vh;
  overflow: hidden;
  box-shadow: 0 28px 80px rgba(11, 31, 59, 0.35), 0 4px 16px rgba(11, 31, 59, 0.12);
  position: relative;
  display: flex;
  flex-direction: column;
  transform: translateY(14px);
  transition: transform 0.28s cubic-bezier(0.16, 1, 0.3, 1);
}

.fx-article-overlay.is-open .fx-article-modal {
  transform: translateY(0);
}

/* Scrollable inner area */
.fx-modal-scroll-inner {
  overflow-y: auto;
  padding: 38px 44px 44px;
  flex: 1;
  scroll-behavior: smooth;
}

.fx-modal-scroll-inner::-webkit-scrollbar {
  width: 6px;
}

.fx-modal-scroll-inner::-webkit-scrollbar-track {
  background: #F1F5F9;
  border-radius: 10px;
}

.fx-modal-scroll-inner::-webkit-scrollbar-thumb {
  background: #CBD5E1;
  border-radius: 10px;
}

/* Close button - Top right minimal X button */
.fx-modal-close {
  position: absolute;
  top: 22px;
  right: 24px;
  background: #F8FAFC;
  border: 1px solid #E2E8F0;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748B;
  z-index: 20;
  transition: all 0.2s ease;
  padding: 0;
}

.fx-modal-close:hover {
  background: #0B1F3B;
  border-color: #0B1F3B;
  color: #FFFFFF;
  transform: scale(1.08);
}

.fx-modal-close:focus-visible {
  outline: 2px solid #F5C451;
  outline-offset: 2px;
}

/* Category badge */
.fx-modal-category-badge {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  background: #FEF3C7;
  color: #92400E;
  font-size: 11.5px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  padding: 5px 14px;
  border-radius: 999px;
  margin-bottom: 14px;
}

.fx-modal-category-badge svg {
  color: #92400E;
}

/* Article title in dark navy */
.fx-modal-title {
  font-size: clamp(1.45rem, 2.6vw, 1.95rem);
  font-weight: 800;
  color: #0B1F3B;
  line-height: 1.28;
  margin: 0 0 14px;
  padding-right: 48px;
}

/* Metadata row */
.fx-modal-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #64748B;
  font-size: 13.5px;
  font-weight: 500;
  margin-bottom: 22px;
}

.fx-modal-meta svg {
  flex-shrink: 0;
  opacity: 0.8;
}

.fx-modal-meta-dot {
  color: #CBD5E1;
  font-size: 14px;
}

/* Large article cover image */
.fx-modal-cover-img {
  display: block;
  width: 100%;
  height: 310px;
  object-fit: cover;
  border-radius: 18px;
  margin-bottom: 22px;
  background: #0B1F3B;
}

/* Article Lead Description */
.fx-modal-desc {
  font-size: 16px;
  font-weight: 600;
  line-height: 1.65;
  color: #1E293B;
  margin-bottom: 18px;
}

/* Extended Article Body */
.fx-modal-extended-text {
  font-size: 14.5px;
  line-height: 1.75;
  color: #475569;
  margin-bottom: 22px;
}

/* Key Takeaways Box inside Modal */
.fx-modal-takeaways-box {
  background-color: #F8FAFC;
  border: 1px solid #E2E8F0;
  border-left: 4px solid #F5C451;
  border-radius: 12px;
  padding: 1.25rem 1.4rem;
  margin-bottom: 22px;
}

.fx-modal-takeaways-box .fx-takeaways-heading {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #0B1F3B;
  margin-bottom: 0.85rem;
}

.fx-modal-takeaways-box .fx-takeaways-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.fx-modal-takeaways-box .fx-takeaways-list li {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  font-size: 13.5px;
  line-height: 1.5;
  color: #334155;
}

.fx-modal-footer-meta {
  margin-top: 10px;
  padding-top: 14px;
  border-top: 1px solid #F1F5F9;
}

.fx-modal-badge {
  display: inline-block;
  background-color: #0B1F3B;
  color: #FFFFFF;
  font-size: 11.5px;
  font-weight: 700;
  padding: 4px 12px;
  border-radius: 999px;
  letter-spacing: 0.02em;
}

/* ── Resource Card Clean Reset ────────────────────────────────────────── */
.fx-card-expand-btn {
  display: none !important;
}

.fx-collapse-trigger {
  display: none !important;
}

.fx-card-expanded-content {
  display: none !important;
}

.fx-resource-card {
  display: flex !important;
  flex-direction: column !important;
  height: 100% !important;
  cursor: pointer !important;
  border-radius: 16px !important;
  border: 1px solid #E2E8F0 !important;
  background: #FFFFFF !important;
  transition: all 0.25s ease !important;
}

.fx-resource-card:hover {
  transform: translateY(-3px) !important;
  box-shadow: 0 16px 36px rgba(11, 31, 59, 0.09), 0 4px 12px rgba(11, 31, 59, 0.04) !important;
  border-color: #CBD5E1 !important;
}

.fx-resource-card-body {
  padding: 1.5rem !important;
  display: flex !important;
  flex-direction: column !important;
  flex-grow: 1 !important;
}

.fx-card-footer {
  margin-top: auto !important;
  padding-top: 1.1rem !important;
  border-top: 1px solid #F1F5F9 !important;
  display: flex !important;
  justify-content: space-between !important;
  align-items: center !important;
}

/* Responsive Modal adjustments */
@media (max-width: 768px) {
  .fx-modal-scroll-inner {
    padding: 28px 24px 32px;
  }
  .fx-modal-cover-img {
    height: 220px;
  }
  .fx-modal-title {
    padding-right: 36px;
  }
}

@media (max-width: 480px) {
  .fx-article-overlay {
    padding: 0;
    align-items: flex-end;
  }
  .fx-article-modal {
    border-radius: 24px 24px 0 0;
    max-height: 95vh;
  }
  .fx-modal-scroll-inner {
    padding: 24px 18px 28px;
  }
  .fx-modal-cover-img {
    height: 190px;
    border-radius: 14px;
  }
  .fx-modal-title {
    font-size: 1.3rem;
    padding-right: 32px;
  }
}
'''

with open(r"FieldOps_Nexus_Internal\src\static\css\public.css", "w", encoding="utf-8") as f:
    f.write(prefix + new_modal_css)

print("public.css updated successfully!")

