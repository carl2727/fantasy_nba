import pandas as pd

def normalize(series):
    max_value = series.max()
    if max_value == 0:
        return series
    return (series / max_value) * 100