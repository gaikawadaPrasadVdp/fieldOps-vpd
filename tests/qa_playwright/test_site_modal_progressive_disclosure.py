import pytest
from playwright.sync_api import Page, expect


def test_site_modal_progressive_disclosure(page: Page, base_url: str, login_as):
    """
    Verify progressive disclosure of Country -> State / Region -> City hierarchy:
    - Country unselected: State and City fields are hidden.
    - Country selected: State field appears with country's states; City is hidden.
    - State selected: City field appears with state's cities ONLY.
    - State changed: City field dynamically updates to new state's cities.
    - State unselected: City field hides.
    - Country unselected: State and City fields hide.
    """
    login_as(page)

    page.goto(f"{base_url}/app/sites/")
    page.wait_for_load_state("networkidle")

    # Click 'New site' button
    new_site_btn = page.locator("a:has-text('New site'), button:has-text('New site')").first
    expect(new_site_btn).to_be_visible()
    new_site_btn.click()

    # Wait for modal and form to be loaded via HTMX
    page.wait_for_selector("#siteModal.show", timeout=5000)
    form = page.locator("#site-modal-form")
    expect(form).to_be_visible()

    country_select = form.locator("#id_country")
    state_select = form.locator("#id_state_region")
    city_select = form.locator("#id_city")
    state_wrapper = form.locator("#field-wrapper-state")
    city_wrapper = form.locator("#field-wrapper-city")

    # 1. Initially, no Country is selected
    expect(country_select).to_be_visible()
    expect(country_select).to_have_value("")

    # 2. State and City must be hidden initially
    expect(state_wrapper).to_have_class(re_pattern("d-none"))
    expect(city_wrapper).to_have_class(re_pattern("d-none"))

    # 3. Select Country: India
    country_select.select_option("IN")
    country_select.dispatch_event("change")

    # State should now be VISIBLE, City still HIDDEN
    expect(state_wrapper).not_to_have_class(re_pattern("d-none"))
    expect(city_wrapper).to_have_class(re_pattern("d-none"))

    # Verify State options contain Indian states
    state_options = state_select.locator("option").all_text_contents()
    assert "Andhra Pradesh" in state_options
    assert "Karnataka" in state_options
    assert "Kerala" in state_options

    # 4. Select State: Andhra Pradesh
    state_select.select_option("Andhra Pradesh")
    state_select.dispatch_event("change")

    # City should now be VISIBLE
    expect(city_wrapper).not_to_have_class(re_pattern("d-none"))

    # City options MUST contain ONLY Andhra Pradesh cities
    city_options = city_select.locator("option").all_text_contents()
    assert "Visakhapatnam" in city_options
    assert "Vijayawada" in city_options
    assert "Guntur" in city_options
    assert "Nellore" in city_options
    assert "Tirupati" in city_options

    # Must NOT contain cities of other states
    assert "Bengaluru" not in city_options
    assert "Mumbai" not in city_options
    assert "New Delhi" not in city_options
    assert "Chennai" not in city_options

    # 5. Change State: Karnataka
    state_select.select_option("Karnataka")
    state_select.dispatch_event("change")

    expect(city_wrapper).not_to_have_class(re_pattern("d-none"))
    karnataka_cities = city_select.locator("option").all_text_contents()
    assert "Bengaluru" in karnataka_cities
    assert "Mysuru" in karnataka_cities
    assert "Visakhapatnam" not in karnataka_cities

    # 6. Deselect State (set back to empty)
    state_select.select_option("")
    state_select.dispatch_event("change")

    # City should now be HIDDEN again
    expect(city_wrapper).to_have_class(re_pattern("d-none"))

    # 7. Select State: Andhra Pradesh again, then deselect Country
    state_select.select_option("Andhra Pradesh")
    state_select.dispatch_event("change")
    expect(city_wrapper).not_to_have_class(re_pattern("d-none"))

    # Deselect Country
    country_select.select_option("")
    country_select.dispatch_event("change")

    # Both State and City must be HIDDEN
    expect(state_wrapper).to_have_class(re_pattern("d-none"))
    expect(city_wrapper).to_have_class(re_pattern("d-none"))


def re_pattern(cls_name: str):
    import re
    return re.compile(rf"(^|\s){cls_name}(\s|$)")
