# Site Form Dynamic Cascading & Client/Server Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement robust, CSP-compliant form validations and dynamic geographical cascading (Country → State → City → PIN code) for Site creation and editing in both HTMX modal dialogs and standalone pages.

**Architecture:** 
1. Relocate all client-side cascading and validation logic from inline `<script>` blocks in `_site_modal.html` into `src/static/js/app.js`. Bind handlers to both `DOMContentLoaded` and HTMX's `htmx:afterSwap` event on `#siteModalContent`.
2. Restructure the form template layout in `_site_modal.html` from auto-fit grid into a structured Bootstrap grid pairing related fields (Country + State, City + Postal Code) and giving textareas full width.
3. Harden `SiteForm` in `src/apps/sites/forms.py` to ensure server-side dynamic choice rebuilding, strict PIN-to-State circle prefix enforcement, and clean error presentation.
4. Verify with automated tests in `tests/test_site_form_validation.py` covering valid submissions, mismatched PIN codes, invalid characters, and dynamic field validation.

**Tech Stack:** Django 5.2, HTML5 / Bootstrap 5, HTMX, Vanilla JavaScript, Pytest.

**Spec:** User feedback from `media_1793681537131_e83a8d38.png` and `media_1793681556870_05419f41.png`: State selected as Kerala must dynamically populate Kerala cities (e.g., Kochi, Thiruvananthapuram, Kozhikode) instead of general Indian cities, and form must validate PIN codes and required fields cleanly without CSP blockage.

---

## File Structure

- **Modified:**
  - `src/static/js/app.js`: Add `initSiteFormValidation()` with complete geo cascading data (Country -> State -> City -> Postal circle), real-time field validation, error feedback, and listener registration for `DOMContentLoaded` and `htmx:afterSwap`.
  - `src/templates/sites/_site_modal.html`: Remove inline `<script>` block; convert form body to structured Bootstrap rows/columns.
  - `src/apps/sites/forms.py`: Align dynamic choice population on `SiteForm.__init__` and validate PIN code against state postal prefix in `clean_postal_code()`.
- **Created:**
  - `tests/test_site_form_validation.py`: Automated tests testing `SiteForm` validation rules, geo cascading choices, and error handling.

---

## Tasks

### Task 1: Write Automated Tests for SiteForm Validation & Cascading
- [ ] Create `tests/test_site_form_validation.py`.
- [ ] Add test cases:
  - `test_valid_site_creation_kerala`: Valid site in India, Kerala, Kochi with PIN `682001`.
  - `test_invalid_pincode_mismatch`: Site in Kerala with Karnataka PIN `560001` fails validation with descriptive error.
  - `test_invalid_site_code`: Code with invalid characters or leading symbols fails validation.
  - `test_numeric_site_name_rejected`: Name consisting purely of numbers fails validation.
  - `test_dynamic_choices_population`: Verifies `SiteForm` initializes with country and state-specific choices.
- [ ] Run `pytest tests/test_site_form_validation.py` to observe failures (Red).

### Task 2: Harden Server-Side Validation in `src/apps/sites/forms.py`
- [ ] In `SiteForm.__init__`: Ensure that when `country` or `state_region` is provided (via `data` or `initial`), `state_region` and `city` choices are dynamically populated from `CITIES_BY_STATE`.
- [ ] In `SiteForm.clean_postal_code`: Validate Indian PIN codes against `INDIA_STATE_PIN_PREFIXES` based on the cleaned `state_region`.
- [ ] Run `pytest tests/test_site_form_validation.py` to confirm server-side tests pass (Green).

### Task 3: Restructure `_site_modal.html` Layout & Remove Inline Script
- [ ] In `src/templates/sites/_site_modal.html`:
  - Replace the generic `.fx-form-grid` loop with an explicit, clean grid:
    - Row 1: `code` (col-md-6) + `name` (col-md-6)
    - Row 2: `description` (col-12)
    - Row 3: `address` (col-12)
    - Row 4: `country` (col-md-6) + `state_region` (col-md-6)
    - Row 5: `city` (col-md-6) + `postal_code` (col-md-6)
    - Row 6: `timezone` (col-md-6) + `contact_name` (col-md-6)
    - Row 7: `contact_email` (col-md-6) + `contact_phone` (col-md-6)
  - Remove the inline `<script nonce="{{ csp_nonce }}">` tag from `_site_modal.html`.

### Task 4: Implement Client-Side Geo Cascading & Real-Time Validation in `app.js`
- [ ] In `src/static/js/app.js`:
  - Define `initSiteForm(container)`:
    - Complete `geoStates` and `geoCities` datasets (including Kerala: Thiruvananthapuram, Kochi, Kozhikode, Thrissur, Kollam, Kannur, Alappuzha, Palakkad, Kottayam, etc.).
    - Complete `indiaStatePin` dictionary with valid postal prefixes.
    - Wire `change` on `countryEl` -> update states, timezones, phone placeholders.
    - Wire `change` on `stateEl` -> update cities for selected state, update PIN placeholder.
    - Wire `change` on `cityEl` -> auto-fill sample PIN if applicable.
    - Wire `input` / `blur` on `postalEl` -> validate 6-digit PIN and state prefix match.
    - Wire `input` on `codeEl` -> auto-uppercase and regex validation.
    - Wire `submit` on `site-modal-form` -> validate all required fields, display inline errors, prevent submission if invalid, focus first error.
  - Wire `document.body.addEventListener('htmx:afterSwap', ...)` to trigger `initSiteForm` when `#siteModalContent` receives swapped content.
  - Wire `DOMContentLoaded` to initialize if site form is rendered on a standalone page.

### Task 5: End-to-End Verification
- [ ] Run full test suite: `pytest tests/test_site_form_validation.py -v`.
- [ ] Restart web container: `docker compose restart web`.
- [ ] Verify HTTP response of `/app/sites/new/` via curl to ensure valid HTML and no syntax errors.
- [ ] Confirm clean git status.
