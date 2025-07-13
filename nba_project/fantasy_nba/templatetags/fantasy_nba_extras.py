# fantasy_nba/templatetags/fantasy_nba_extras.py
from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Template filter to allow accessing dictionary keys with a variable.
    Usage: {{ my_dictionary|get_item:my_variable }}
    """
    return dictionary.get(key)