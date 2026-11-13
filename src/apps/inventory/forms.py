from django import forms

from apps.ui.forms import (
    BootstrapFormMixin,
    validate_alphabetical_description,
    validate_business_name,
    validate_safe_text,
)

from .models import Part, Warehouse

QTY = {"max_digits": 14, "decimal_places": 3}


class _PartChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.part_number} · {obj.name} ({obj.unit})"


class _WarehouseChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.code} · {obj.name} ({obj.site.code})"


class WholeNumberField(forms.IntegerField):
    """Integer field for whole numbers without decimals.
    Prepares Decimal/float values from model instances without trailing decimals (e.g. 10 instead of 10.000).
    """
    default_error_messages = {
        "invalid": "Value must contain only numbers.",
    }

    def __init__(self, *args, min_value=1, **kwargs):
        attrs = {"step": "1"}
        if min_value is not None:
            attrs["min"] = str(min_value)
        widget = kwargs.pop("widget", None) or forms.NumberInput(attrs=attrs)
        super().__init__(*args, min_value=min_value, widget=widget, **kwargs)

    def prepare_value(self, value):
        if value is not None and value != "":
            try:
                from decimal import Decimal, InvalidOperation
                return int(Decimal(str(value)))
            except (ValueError, TypeError, InvalidOperation):
                pass
        return value

    def to_python(self, value):
        if value in self.empty_values:
            return None
        raw = str(value).strip()
        label_prefix = f"{self.label} " if self.label else "Value "
        if any(c.isalpha() for c in raw):
            raise forms.ValidationError(f"{label_prefix}must contain only numbers and cannot contain letters.")
        try:
            return super().to_python(value)
        except forms.ValidationError:
            raise forms.ValidationError(f"{label_prefix}must contain only numbers.")


def _level(label):
    return WholeNumberField(
        required=False,
        min_value=0,
        label=label,
        widget=forms.NumberInput(attrs={"step": "1", "min": "0"}),
    )


class PartForm(BootstrapFormMixin, forms.Form):
    part_number = forms.CharField(max_length=60)
    name = forms.CharField(max_length=200)
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    unit = forms.CharField(max_length=20)
    min_stock = _level("Minimum stock")
    max_stock = _level("Maximum stock")
    reorder_quantity = _level("Reorder quantity")

    def clean_part_number(self):
        part_number = (self.cleaned_data.get("part_number") or "").strip()
        if not part_number:
            raise forms.ValidationError("Part number is required.")
        if not any(c.isalnum() for c in part_number):
            raise forms.ValidationError("Part number must contain letters or numbers.")
        allowed_separators = set("-./#_ ")
        if any(not (c.isalnum() or c.isspace() or c in allowed_separators) for c in part_number):
            raise forms.ValidationError("Part number can contain only letters, numbers, and standard separators (-, ., /, #, _).")
        return part_number

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if not name:
            raise forms.ValidationError("Name is required.")
        return validate_alphabetical_description(name, field_label="Name")

    def clean_description(self):
        desc = (self.cleaned_data.get("description") or "").strip()
        if desc:
            return validate_alphabetical_description(desc, field_label="Description")
        return desc

    def clean_unit(self):
        unit = (self.cleaned_data.get("unit") or "").strip()
        if not unit:
            raise forms.ValidationError("Unit is required.")
        if not any(c.isalnum() for c in unit):
            raise forms.ValidationError("Unit must contain letters or numbers.")
        allowed_separators = set("-./#_ ")
        if any(not (c.isalnum() or c.isspace() or c in allowed_separators) for c in unit):
            raise forms.ValidationError("Unit can contain only letters, numbers, and standard separators (-, ., /, #, _).")
        return unit

    def clean_min_stock(self):
        val = self.cleaned_data.get("min_stock")
        if val is not None and val < 0:
            raise forms.ValidationError("Minimum stock must be a non-negative number (0 or greater).")
        return val

    def clean_max_stock(self):
        val = self.cleaned_data.get("max_stock")
        if val is not None and val < 0:
            raise forms.ValidationError("Maximum stock must be a non-negative number (0 or greater).")
        return val

    def clean_reorder_quantity(self):
        val = self.cleaned_data.get("reorder_quantity")
        if val is not None and val < 0:
            raise forms.ValidationError("Reorder quantity must be a non-negative number (0 or greater).")
        return val

    def clean(self):
        cleaned_data = super().clean()
        min_stock = cleaned_data.get("min_stock")
        max_stock = cleaned_data.get("max_stock")
        if min_stock is not None and max_stock is not None and max_stock < min_stock:
            self.add_error("max_stock", "Maximum stock cannot be less than minimum stock.")
        return cleaned_data


class WarehouseForm(BootstrapFormMixin, forms.Form):
    site = forms.ModelChoiceField(queryset=None, empty_label="Choose a site")
    code = forms.CharField(max_length=20)
    name = forms.CharField(max_length=120)
    description = forms.CharField(max_length=300, required=False)

    def __init__(self, *args, sites=None, editing=False, **kwargs):
        super().__init__(*args, **kwargs)
        if editing:
            del self.fields["site"]
        else:
            self.fields["site"].queryset = sites

    @property
    def model(self):
        return Warehouse


class ReceiveForm(BootstrapFormMixin, forms.Form):
    warehouse = _WarehouseChoice(queryset=Warehouse.objects.none(), empty_label="Choose a warehouse")
    part = _PartChoice(queryset=Part.objects.none(), empty_label="Choose a part")
    quantity = WholeNumberField(min_value=1, label="Quantity")
    reference = forms.CharField(max_length=100, required=False, label="Reference (PO / delivery note)")
    reason = forms.CharField(max_length=300, required=False)

    def __init__(self, *args, warehouses=None, parts=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["warehouse"].queryset = warehouses
        self.fields["part"].queryset = parts


class AdjustForm(BootstrapFormMixin, forms.Form):
    delta = WholeNumberField(min_value=None, label="Adjustment (+ / -)", widget=forms.NumberInput(attrs={"step": "1"}))
    reason = forms.CharField(max_length=300)

    def clean_delta(self):
        delta = self.cleaned_data.get("delta")
        if delta == 0:
            raise forms.ValidationError("Adjustment delta must be non-zero.")
        return delta

    def clean_reason(self):
        reason = (self.cleaned_data.get("reason") or "").strip()
        if len(reason) < 3:
            raise forms.ValidationError("A detailed reason of at least 3 characters is required.")
        return reason


class LevelsForm(BootstrapFormMixin, forms.Form):
    min_level = _level("Minimum level")
    max_level = _level("Maximum level")
    reorder_quantity = _level("Reorder quantity")

    def clean(self):
        cleaned_data = super().clean()
        min_level = cleaned_data.get("min_level")
        max_level = cleaned_data.get("max_level")
        if min_level is not None and max_level is not None and max_level < min_level:
            self.add_error("max_level", "Maximum level cannot be less than minimum level.")
        return cleaned_data


class TransferForm(BootstrapFormMixin, forms.Form):
    source = _WarehouseChoice(queryset=Warehouse.objects.none(), empty_label="From warehouse")
    target = _WarehouseChoice(queryset=Warehouse.objects.none(), empty_label="To warehouse")
    part = _PartChoice(queryset=Part.objects.none(), empty_label="Choose a part")
    quantity = WholeNumberField(min_value=1, label="Quantity")
    reason = forms.CharField(max_length=300, required=False)

    def __init__(self, *args, warehouses=None, parts=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["source"].queryset = warehouses
        self.fields["target"].queryset = warehouses
        self.fields["part"].queryset = parts

    def clean(self):
        cleaned_data = super().clean()
        source = cleaned_data.get("source")
        target = cleaned_data.get("target")
        if source and target and source == target:
            self.add_error("target", "Target warehouse must be different from source warehouse.")
        return cleaned_data


class RequestPartForm(BootstrapFormMixin, forms.Form):
    part = _PartChoice(queryset=Part.objects.none(), empty_label="Choose a part")
    quantity = WholeNumberField(min_value=1, label="Quantity")
    notes = forms.CharField(max_length=300, required=False)

    def __init__(self, *args, parts=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["part"].queryset = parts

    def clean_quantity(self):
        raw_val = str(self.data.get("quantity") or "").strip()
        if not raw_val:
            raise forms.ValidationError("Quantity is required.")
        if any(c.isalpha() for c in raw_val):
            raise forms.ValidationError("Quantity must contain only numbers and cannot contain letters.")
        if not raw_val.isdigit():
            raise forms.ValidationError("Quantity must contain only numbers.")
        val = int(raw_val)
        if val <= 0:
            raise forms.ValidationError("Quantity must be greater than zero.")
        return val

    def clean_notes(self):
        notes = (self.cleaned_data.get("notes") or "").strip()
        if notes:
            validate_alphabetical_description(notes, field_label="Notes")
        return notes


class ReserveForm(BootstrapFormMixin, forms.Form):
    warehouse = _WarehouseChoice(queryset=Warehouse.objects.none(), empty_label="Warehouse")
    quantity = WholeNumberField(min_value=1, required=False, help_text="Blank = everything still uncovered", label="Quantity")

    def __init__(self, *args, warehouses=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["warehouse"].queryset = warehouses


class IssueForm(BootstrapFormMixin, forms.Form):
    warehouse = _WarehouseChoice(queryset=Warehouse.objects.none(), empty_label="Warehouse")
    quantity = WholeNumberField(min_value=1, label="Quantity")

    def __init__(self, *args, warehouses=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["warehouse"].queryset = warehouses


class QuantityForm(BootstrapFormMixin, forms.Form):
    quantity = WholeNumberField(min_value=1, required=False, label="Quantity")
    reason = forms.CharField(max_length=300, required=False)


class ScrapForm(BootstrapFormMixin, forms.Form):
    quantity = WholeNumberField(min_value=1, label="Quantity")
    reason = forms.CharField(max_length=300, label="Reason (scrap / damage / expiration)")

    def clean_reason(self):
        reason = (self.cleaned_data.get("reason") or "").strip()
        if len(reason) < 3:
            raise forms.ValidationError("A detailed reason of at least 3 characters is required.")
        return reason
