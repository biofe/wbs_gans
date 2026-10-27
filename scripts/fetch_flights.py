"""
fetch_flights.py
================

Fetch arrivals for all airports nearby the cities in the database and
populate the corresponding table.
"""

import pandas as pd
import requests
import os
from dotenv import load_dotenv
import datetime
import pymysql

load_dotenv()

api_key = os.environ["API_KEY_OPENAEROBOX"]
connection_string = f'mysql+pymysql://{os.environ["MYSQL_USER"]}:{os.environ["MYSQL_ROOT_PASSWORD"]}@{os.environ["MYSQL_HOST"]}:{os.environ["MYSQL_PORT"]}/gans' #/{schema}'

def get_airports(latitudes, longitudes):
    '''Retrieves airports nearby (50km) of the positions.

    latittudes, longitudes: lists containing the respective coordinates. Both must be equally long.

    Returns: pd.DataFrame
    '''
    # API headers
    headers = {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": "aerodatabox.p.rapidapi.com",
        "Content-Type": "application/json"
    }

    # DataFrame to store results
    all_airports = []

    for lat, lon in zip(latitudes, longitudes):
    # Construct the URL with the latitude and longitude
        url = url = "https://aerodatabox.p.rapidapi.com/airports/search/location"
        querystring = {
            "lat":lat,
            "lon":lon,
            "radiusKm":"50",
            "limit":"10",
            "withFlightInfoOnly":"true",
        }

        # Make the API request
        response = requests.get(url, headers=headers, params=querystring)

        if response.status_code == 200:
            data = response.json()
            airports = pd.json_normalize(data.get('items', []))
            all_airports.append(airports)

    return pd.concat(all_airports, ignore_index=True)

def fetch_airports():
    '''Loads the city table from MySQL and returns the airports DataFrame, including the corresponding city_id.'''
    cities = pd.read_sql(
        "SELECT * FROM city",
        con = connection_string,
    )
    airports = get_airports(*cities.loc[:, ["latitude", "longitude"]].T.values.tolist())
    airports["city_id"] = cities["city_id"]
    return airports

def get_url(iata):
    '''Returns tuple of 12h URL for a given iata.'''
    t0 = datetime.date.today() + datetime.timedelta(days=1)
    t1 = datetime.datetime.today().replace(hour=23, minute=59) + datetime.timedelta(days=0, hours=12)
    t2 = t1 + datetime.timedelta(days=0, hours=0, minutes=1)
    t3 = t1 + datetime.timedelta(days=0, hours=12)
    fmt = lambda x: x.strftime("%Y-%m-%dT%H%%3A%M")
    return (
        f"https://aerodatabox.p.rapidapi.com/flights/airports/iata/{iata}/{fmt(t0)}/{fmt(t1)}",
        f"https://aerodatabox.p.rapidapi.com/flights/airports/iata/{iata}/{fmt(t2)}/{fmt(t3)}",
    )

def get_flights_airport(url):
    """Query the flights for one airport given the API URL"""
    querystring = {
        "withLeg":"true",
        "direction":"Arrival",
        "withCancelled":"true",
        "withCodeshared":"true",
        "withCargo":"false",
        "withPrivate":"false",
        "withLocation":"false",
    }

    headers = {
    	"x-rapidapi-key": api_key,
    	"x-rapidapi-host": "aerodatabox.p.rapidapi.com"
    }

    response = requests.get(url, headers=headers, params=querystring)
    df = pd.json_normalize(response.json()["arrivals"])
    if "arrival.runwayTime.local" in df.columns:
        revised_times = df.loc[:, "arrival.revisedTime.local"].fillna(df.loc[:, "arrival.runwayTime.local"])
        df = df.drop(["arrival.runwayTime.local", "arrival.runwayTime.utc"], axis=1)
    else:
        revised_times = df.loc[:, "arrival.revisedTime.local"]
    df["arrival"] = (
        df.loc[:, "arrival.scheduledTime.local"]
            .where(df.loc[:, "arrival.revisedTime.local"].isnull(), revised_times)
            .str.split("+").apply(lambda x: x[0])
    )
    return df

def get_flights(airports):
    '''Returns flights from the airports DataFrame querying the respective API.'''
    flights = []
    for iata in airports.loc[:, "iata"]:
        url1, url2 = get_url(iata)
        flights += [pd.concat([
            get_flights_airport(url1),
            get_flights_airport(url2),
        ])]
        flights[-1]["at_iata"] = iata
        flights[-1]["city_id"] = airports.loc[airports.loc[:, "iata"] == iata, "city_id"].values[0]

    return pd.concat(flights, ignore_index=True)

def flights_to_arrivals(df):
    """Extract the desired arrival data from the flights DataFrame"""
    df = df.drop_duplicates(subset=["callSign", "arrival"])
    arr = (
        df.loc[:, [
            'at_iata',
            'city_id',
            'departure.airport.icao',
            'departure.airport.iata',
            'departure.airport.name',
            'departure.airport.countryCode',
            'departure.airport.location.lat',
            'departure.airport.location.lon',
            'arrival',
        ]]
        .rename({
            'departure.airport.icao': 'icao',
            'departure.airport.iata': 'iata',
            'departure.airport.name': 'name',
            'departure.airport.countryCode': 'country_code',
            'departure.airport.location.lat': 'lat',
            'departure.airport.location.lon': 'lon',
        }, axis=1)
        .drop_duplicates([
            'iata',
            'arrival'
        ])
    )
    return arr

def get_arrivals():
    """Execute the pipeline"""
    airports = fetch_airports()
    flights = get_flights(airports)
    return flights_to_arrivals(flights)

def write_arrivals(arrivals):
    """Write arrivals to the database table"""
    arrivals.to_sql(
        'arrival_tmp',
        schema="gans",
        if_exists='replace',
        con=connection_string,
        index=False,
    )
    conn = pymysql.connect(
        host=os.environ["MYSQL_HOST"],
        port=int(os.environ["MYSQL_PORT"]),
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_ROOT_PASSWORD"],
        database="gans",
    )

    with conn.cursor() as c:
        c.callproc("update_arrival")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    write_arrivals(get_arrivals())
