"""Modeltranslation registration for catalog models."""

from modeltranslation.translator import TranslationOptions, register

from .models import Attribute, AttributeGroup, Brand, Category, Filter, FilterGroup, Product


@register(Brand)
class BrandTranslationOptions(TranslationOptions):
    fields = ("description",)


@register(Category)
class CategoryTranslationOptions(TranslationOptions):
    fields = ("name", "description", "seo_title", "seo_description")


@register(AttributeGroup)
class AttributeGroupTranslationOptions(TranslationOptions):
    fields = ("name",)


@register(Attribute)
class AttributeTranslationOptions(TranslationOptions):
    fields = ("name",)


@register(FilterGroup)
class FilterGroupTranslationOptions(TranslationOptions):
    fields = ("name",)


@register(Filter)
class FilterTranslationOptions(TranslationOptions):
    fields = ("name",)


@register(Product)
class ProductTranslationOptions(TranslationOptions):
    fields = ("name", "description", "short_description", "seo_title", "seo_description")
