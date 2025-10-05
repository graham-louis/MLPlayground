import requests
import pandas as pd


def get_yield_data(state=None, crop=None, year=None):
    params = {}
    if state: params['state'] = state
    if crop: params['crop'] = crop
    if year: params['year'] = year
    resp = requests.get('http://api:8000/yields/', params=params)
    data = resp.json()
    return pd.DataFrame(data)

def get_weather_data(state=None, year=None):
    params = {}
    if state: params['state'] = state
    if year: params['year'] = year
    resp = requests.get('http://api:8000/weather/', params=params)
    data = resp.json()
    return pd.DataFrame(data)

def get_soil_data(state=None):
    params = {}
    if state: params['state'] = state
    resp = requests.get('http://api:8000/soil/', params=params)
    data = resp.json()
    return pd.DataFrame(data)
