# courses/templatetags/custom_filters.py
from django import template

register = template.Library()

@register.filter
def split_lines(value):
    """Matnni qatorlarga ajratish"""
    if value:
        lines = value.split('\n')
        return [line.strip() for line in lines if line.strip()]
    return []

@register.filter
def get_index_letter(index):
    """Indexni harfga aylantirish (0->A, 1->B, ...)"""
    try:
        return chr(65 + int(index))
    except:
        return index

@register.filter(name='range')
def range_filter(value):
    """Range filter"""
    try:
        return range(int(value))
    except:
        return range(0)

@register.filter
def split_string(value, delimiter):
    """Stringni delimiter bo'yicha bo'lib listga aylantiradi"""
    if value:
        # Bo'sh qatorlarni olib tashlash
        result = [item.strip() for item in value.split(delimiter) if item.strip()]
        print(f"split_string called: '{value}' -> {result}")  # DEBUG
        return result
    return []

@register.filter
def int_to_char(value):
    """Raqamni harfga aylantiradi (1->A, 2->B, ...)"""
    try:
        return chr(64 + int(value))  # 65='A', 66='B', ...
    except (ValueError, TypeError):
        return value
@register.filter
def trim(value):
    """Stringni trim qilish"""
    return value.strip() if value else value

@register.filter
def get_letter(index):
    """0-based indexni harfga aylantiradi"""
    return chr(65 + int(index))  # 0->A, 1->B, ...