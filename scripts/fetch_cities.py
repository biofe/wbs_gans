"""
fetch_cities.py
===============

Scrape Wikipedia articles for the geographic location, country and
population of a list of cities and fill this data into a MySQL database.
"""

import os
import requests
import re
from dotenv import load_dotenv
import pandas as pd
from bs4 import BeautifulSoup

load_dotenv()


def scrape_city(city):
    """Get the Wikipedia article"""
    url = "https://en.wikipedia.org/wiki/" + city
    headers = {'User-Agent': 'Chrome/134.0.0.0'}
    return BeautifulSoup(
        requests.get(url, headers=headers).content,
        "html.parser"
    )

def extract_data(soup):
    """Parse the Wikipedia article and return the desired data"""
    city = soup.select("h1.firstHeading span.mw-page-title-main")[0].get_text()
    country = soup.find(string="Country").find_next().get_text().strip()
    population = soup.find(string="Population").parent.find_next("td").get_text()
    latitude = soup.select("td.infobox-full-data span.latitude")[0].get_text()
    longitude = soup.select("td.infobox-full-data span.longitude")[0].get_text()
    return {
        "city": city,
        "country": country,
        "population": population,
        "latitude": latitude,
        "longitude": longitude,
    }

def coord_to_float(coord_str: str) -> float:
    """Transform lat / lon from xx°xx"xx' to decimal degrees"""
    coord_str = coord_str.replace(" ", "")
    coord_split = re.split(r"[°′″]", coord_str)
    sign = 1 if coord_split.pop(-1) in ("N", "E") else -1
    coord_dec = float(coord_split.pop(0))
    for i, c in enumerate(coord_split):
        coord_dec += float(c) * 10 / 6 / 100**(1 + i)
    return sign * coord_dec

def df_cleanup(df):
    """Apply clean format to the dataframe"""
    df2 = df.copy()
    df2["population"] = df.loc[:, "population"].str.replace(",", "").astype(int)
    df2["latitude"] = df.loc[:, "latitude"].apply(coord_to_float)
    df2["longitude"] = df.loc[:, "longitude"].apply(coord_to_float)
    return df2

def create_df(cities):
    """Create the clean DataFrame"""
    dat = []
    for city in cities:
        soup = scrape_city(city)
        dat.append(extract_data(soup))
    return df_cleanup(pd.DataFrame(dat).set_index("city"))

if __name__ == "__main__":
    connection_string = f'mysql+pymysql://{os.environ["MYSQL_USER"]}:{os.environ["MYSQL_ROOT_PASSWORD"]}@{os.environ["MYSQL_HOST"]}:{os.environ["MYSQL_PORT"]}' #/{schema}'

    cities = [
        "Berlin",
        "Hamburg",
        "Munich",
#    "London",
#    "Paris",
#    "Prague",
#    "New_York_City"
    ]

    df = create_df(cities)
    city_df = (df
        .reset_index()
        .rename({"city": "name"}, axis="columns")
               )
    city_df.to_sql(
        'city',
        schema="gans",
        if_exists='append',
        con=connection_string,
        index=False,
    )
