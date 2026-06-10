"""Custom admin form widgets."""

from __future__ import annotations

from django import forms


class CategoryTreeWidget(forms.Widget):
    """Hierarchical checkbox picker with search for product categories."""

    template_name = "admin/catalog/widgets/category_tree.html"
    allow_multiple_selected = True

    def __init__(self, attrs=None, *, nodes: list[dict] | None = None):
        super().__init__(attrs)
        self.nodes = nodes or []

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        selected = {str(item) for item in (value or [])}
        context["widget"]["nodes"] = [
            {**node, "selected": str(node["pk"]) in selected}
            for node in self.nodes
        ]
        return context

    def value_from_datadict(self, data, files, name):
        return data.getlist(name)

    def value_omitted_from_data(self, data, files, name):
        return name not in data

    class Media:
        js = ("admin/js/category_tree.js",)
