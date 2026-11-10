from apps.checklists.forms import TemplateForm, ItemForm
import pytest
from apps.inventory.forms import PartForm, RequestPartForm
from apps.portal.forms import PortalServiceRequestForm
from django.utils import timezone


def test_part_form_name_alphabetical_validation():
    # Number in name must be rejected (image scenario: 231115656665654 / `14324)
    form_bad = PartForm(data={
        "part_number": "123456",
        "name": "231115656665654",
        "unit": "1",
    })
    assert not form_bad.is_valid()
    assert "name" in form_bad.errors
    assert "Name must contain only alphabetical characters and cannot contain numbers." in str(form_bad.errors["name"])

    # Valid alphabetical name with standard punctuation accepted
    form_good = PartForm(data={
        "part_number": "123456",
        "name": "Heavy Duty Mechanical Seal",
        "unit": "1",
        "min_stock": 2,
        "max_stock": 10,
        "reorder_quantity": 5,
    })
    assert form_good.is_valid(), form_good.errors


def test_part_form_part_number_validation():
    # Symbols without letters or digits rejected
    form_bad_sym = PartForm(data={
        "part_number": "--- ...",
        "name": "Mechanical Seal",
        "unit": "EA",
    })
    assert not form_bad_sym.is_valid()
    assert "part_number" in form_bad_sym.errors
    assert "Part number must contain letters or numbers." in str(form_bad_sym.errors["part_number"])

    # Invalid characters rejected
    form_bad_char = PartForm(data={
        "part_number": "SEAL@100",
        "name": "Mechanical Seal",
        "unit": "EA",
    })
    assert not form_bad_char.is_valid()
    assert "part_number" in form_bad_char.errors

    # Digits, letters (alphanumeric), and valid separators accepted
    for valid_pn in ["231115656665654", "123456", "100-20", "500/2", "99.1", "FT-UI-100", "FLT-9"]:
        form_valid = PartForm(data={
            "part_number": valid_pn,
            "name": "Mechanical Seal",
            "unit": "EA",
        })
        assert form_valid.is_valid(), f"Failed on {valid_pn}: {form_valid.errors}"


def test_part_form_stock_levels_validation():
    # Negative min stock rejected
    form_neg_min = PartForm(data={
        "part_number": "12345",
        "name": "Mechanical Seal",
        "unit": "1",
        "min_stock": -5,
    })
    assert not form_neg_min.is_valid()
    assert "min_stock" in form_neg_min.errors

    # Max stock less than min stock rejected
    form_max_lt_min = PartForm(data={
        "part_number": "12345",
        "name": "Mechanical Seal",
        "unit": "1",
        "min_stock": 20,
        "max_stock": 10,
    })
    assert not form_max_lt_min.is_valid()
    assert "max_stock" in form_max_lt_min.errors
    assert "Maximum stock cannot be less than minimum stock." in str(form_max_lt_min.errors["max_stock"])

    # Negative reorder quantity rejected
    form_neg_reorder = PartForm(data={
        "part_number": "12345",
        "name": "Mechanical Seal",
        "unit": "1",
        "reorder_quantity": -2,
    })
    assert not form_neg_reorder.is_valid()
    assert "reorder_quantity" in form_neg_reorder.errors


def test_part_form_unit_and_description_validation():
    # Valid alphanumeric units (e.g. EA, pcs, 1) accepted
    for valid_unit in ["EA", "pcs", "1", "box-10"]:
        form_good_unit = PartForm(data={
            "part_number": "FT-UI-100",
            "name": "Mechanical Seal",
            "unit": valid_unit,
        })
        assert form_good_unit.is_valid(), f"Failed on {valid_unit}: {form_good_unit.errors}"

    # Symbols without letters/digits or invalid characters in unit rejected
    for bad_unit in ["---", "EA@"]:
        form_bad_unit = PartForm(data={
            "part_number": "12345",
            "name": "Mechanical Seal",
            "unit": bad_unit,
        })
        assert not form_bad_unit.is_valid()
        assert "unit" in form_bad_unit.errors

    # Digits in description rejected
    form_bad_desc = PartForm(data={
        "part_number": "12345",
        "name": "Mechanical Seal",
        "unit": "1",
        "description": "Installed 12 items yesterday",
    })
    assert not form_bad_desc.is_valid()
    assert "description" in form_bad_desc.errors


def test_portal_service_request_form_title_validation():
    # Number in title must be rejected (image scenario: 6555557)
    form_bad = PortalServiceRequestForm(data={
        "title": "6555557",
        "description": "Clean description text without numbers",
    })
    assert not form_bad.is_valid()
    assert "title" in form_bad.errors
    assert "Request Title / Subject must contain only alphabetical characters and cannot contain numbers." in str(form_bad.errors["title"])

    # Numbers in description rejected
    form_bad_desc = PortalServiceRequestForm(data={
        "title": "Motor failure on main conveyor",
        "description": "Error code 404 happened at 1200 rpm",
    })
    assert not form_bad_desc.is_valid()
    assert "description" in form_bad_desc.errors
    assert "Problem Description must contain only alphabetical characters and cannot contain numbers." in str(form_bad_desc.errors["description"])

    # Numbers in impact notes rejected
    form_bad_impact = PortalServiceRequestForm(data={
        "title": "Motor failure on main conveyor",
        "description": "Motor overheating and vibrating loudly",
        "impact_notes": "Assembly line slowed down by 50 percent",
    })
    assert not form_bad_impact.is_valid()
    assert "impact_notes" in form_bad_impact.errors
    assert "Impact Notes must contain only alphabetical characters and cannot contain numbers." in str(form_bad_impact.errors["impact_notes"])


def test_request_part_form_quantity_and_notes_validation():
    # Letters in quantity rejected
    form_qty_letters = RequestPartForm(data={
        "quantity": "abc",
        "notes": "Emergency replacement needed",
    })
    assert not form_qty_letters.is_valid()
    assert "quantity" in form_qty_letters.errors
    assert "Quantity must contain only numbers" in str(form_qty_letters.errors["quantity"])

    # Non-digit in quantity rejected
    form_qty_symbol = RequestPartForm(data={
        "quantity": "12.5",
        "notes": "Emergency replacement needed",
    })
    assert not form_qty_symbol.is_valid()
    assert "quantity" in form_qty_symbol.errors

    # Zero or negative quantity rejected
    form_qty_zero = RequestPartForm(data={
        "quantity": "0",
        "notes": "Emergency replacement needed",
    })
    assert not form_qty_zero.is_valid()
    assert "quantity" in form_qty_zero.errors

    # Numbers in notes rejected
    form_notes_numbers = RequestPartForm(data={
        "quantity": "5",
        "notes": "Replace 2 seals on line 3",
    })
    assert not form_notes_numbers.is_valid()
    assert "notes" in form_notes_numbers.errors
    assert "Notes must contain only alphabetical characters and cannot contain numbers." in str(form_notes_numbers.errors["notes"])

    # Clean alphabetical notes accepted
    form_notes_good = RequestPartForm(data={
        "quantity": "5",
        "notes": "Emergency replacement needed immediately",
    })
    assert "quantity" not in form_notes_good.errors
    assert "notes" not in form_notes_good.errors

def test_checklist_template_and_item_form_alphabetical_validation():
    # Number in template name rejected
    t_bad = TemplateForm(data={
        "name": "Checklist 12345",
        "description": "Standard inspection routine",
    })
    assert not t_bad.is_valid()
    assert "name" in t_bad.errors
    assert "Name must contain only alphabetical characters and cannot contain numbers." in str(t_bad.errors["name"])

    # Number in template description rejected
    t_bad_desc = TemplateForm(data={
        "name": "Standard HVAC Verification",
        "description": "Inspect 4 compressors on roof",
    })
    assert not t_bad_desc.is_valid()
    assert "description" in t_bad_desc.errors
    assert "Description must contain only alphabetical characters and cannot contain numbers." in str(t_bad_desc.errors["description"])

    # Valid template form passes
    t_good = TemplateForm(data={
        "name": "Standard HVAC Verification",
        "description": "Routine quarterly inspection protocol",
    })
    assert t_good.is_valid(), t_good.errors

    # Number in item prompt rejected
    it_bad_prompt = ItemForm(data={
        "prompt": "Verify 3 phase power voltage",
        "item_type": "BOOLEAN",
    })
    assert not it_bad_prompt.is_valid()
    assert "prompt" in it_bad_prompt.errors
    assert "Question must contain only alphabetical characters and cannot contain numbers." in str(it_bad_prompt.errors["prompt"])

    # Number in guidance rejected
    it_bad_guide = ItemForm(data={
        "prompt": "Inspect main drive belt tension",
        "item_type": "BOOLEAN",
        "guidance": "Deflection should not exceed 5 millimeters",
    })
    assert not it_bad_guide.is_valid()
    assert "guidance" in it_bad_guide.errors
    assert "Guidance must contain only alphabetical characters and cannot contain numbers." in str(it_bad_guide.errors["guidance"])

    # Valid item form passes
    it_good = ItemForm(data={
        "prompt": "Inspect main drive belt tension",
        "item_type": "BOOLEAN",
        "guidance": "Check for visual cracks and appropriate tension",
    })
    assert it_good.is_valid(), it_good.errors
