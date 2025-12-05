import requests
import pandas as pd


def get_yield_data(state=None, crop=None, start_year=None, end_year=None):
    params = {}
    if state: params['state'] = str.upper(state)
    if crop: params['crop'] = str.upper(crop)
    if start_year: params['start_year'] = start_year
    if end_year: params['end_year'] = end_year
    resp = requests.get('http://api:8000/yields/', params=params)
    data = resp.json()
    return pd.DataFrame(data)

def get_weather_data(state=None, year=None):
    params = {}
    if state: params['state'] = str.upper(state)
    if year: params['year'] = year
    resp = requests.get('http://api:8000/weather/', params=params)
    data = resp.json()
    return pd.DataFrame(data)

def get_soil_data(state=None):
    params = {}
    if state: params['state'] = str.upper(state)
    resp = requests.get('http://api:8000/soil/', params=params)
    data = resp.json()
    return pd.DataFrame(data)
