from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Allows accessing dictionary items with a variable key in Django templates.
    Example: {{ my_dict|get_item:my_key_variable }}
    """
    if hasattr(dictionary, 'get'):
        return dictionary.get(key)
    return None

@register.filter
def is_styled_cell(cell_data):
    """Checks if cell_data is the styled dictionary {'value': ..., 'css_class': ...}"""
    return isinstance(cell_data, dict) and 'value' in cell_data and 'css_class' in cell_data