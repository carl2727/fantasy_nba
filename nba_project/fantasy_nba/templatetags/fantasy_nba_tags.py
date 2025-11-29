from django import template

register = template.Library()

@register.filter(name='is_rating_column')
def is_rating_column(column_name):
    """
    Checks if a given column name corresponds to a rating column.
    """
    if not isinstance(column_name, str):
        return False
    return column_name.endswith(('_Rating', '_Available_Rating', '_Combined_Rating'))