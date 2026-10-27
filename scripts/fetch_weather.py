"""
fetch_weather.py
================

Fetch 3-hourly weather forcast for the next five days using OpenWeatherMap
for all cities in the database and write it to the respective table.
"""

import os
from dotenv import load_dotenv
import pandas as pd
from bs4 import BeautifulSoup
import requests
import re
import pymysql

load_dotenv()

api_key = os.environ["API_KEY_OPENWEATHER"]

def get_weather(lat, lon):
    """Fetch the raw data."""
    return requests.get(f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={api_key}&units=metric")

def city_loc(city_df):
    """Fetch and compile the forecast for all cities in city_df"""
    forecast = {
        "city": [],
        "weather": [],
        "short": [],
    }
    for _, i in city_df.iterrows():
        weather = get_weather(i["latitude"], i["longitude"]).json()

        forecast["city"].append(pd.json_normalize(weather["city"]))
        forecast["city"][-1]["city_name"] = i["name"]
        forecast["city"][-1]["city_id"] = i["city_id"]
        forecast["city"][-1]["country_name"] = i["country"]

        fc = pd.json_normalize(weather["list"]).drop("weather", axis=1)
        fc["city_id"] = weather["city"]["id"]
        fc["city_id_sql"] = i["city_id"]
        forecast["weather"].append(fc)

        short = pd.json_normalize(
            weather["list"],
            record_path="weather",   # explode each row's list of dicts
            meta=["dt"],             # parent fields to attach to every exploded row
        )
        short["city_id"] = weather["city"]["id"]
        forecast["short"].append(short)

    for k, i in forecast.items():
        forecast[k] = pd.concat(i, ignore_index=True)

    return forecast


if __name__ == "__main__":
    # Get the cities from the database
    connection_string = f'mysql+pymysql://{os.environ["MYSQL_USER"]}:{os.environ["MYSQL_ROOT_PASSWORD"]}@{os.environ["MYSQL_HOST"]}:{os.environ["MYSQL_PORT"]}/gans' #/{schema}'
    df = pd.read_sql(
        "SELECT * FROM city",
        con = connection_string,
    )
    # Create the forcecast DataFrame
    forecast = city_loc(df)

    # If there's no rain column, add it
    if not "rain.3h" in forecast["weather"].columns:
        forecast["weather"]["rain.3h"] = 0

    # Devide the data into the tables of the schema
    city_update = forecast["city"].loc[:, ["city_id", "country", "timezone"]]
    city_update = city_update.rename({"country": "country_code"}, axis=1)
    solar_time = forecast["city"].loc[:, ["city_id", "sunrise", "sunset"]]
    solar_time["sunrise_text"] = pd.to_datetime(solar_time.loc[:, "sunrise"] + forecast["city"].loc[:, "timezone"], unit="s").dt.strftime("%Y-%m-%d %H-%M-%S")
    solar_time["sunset_text"] = pd.to_datetime(solar_time.loc[:, "sunset"] + forecast["city"].loc[:, "timezone"], unit="s").dt.strftime("%Y-%m-%d %H-%M-%S")

    forecast_table = (
        forecast["weather"]
            .set_index(["dt", "city_id"])
            .join(
                forecast["short"].set_index(["dt", "city_id"]),
                how="inner"
            )
            .reset_index()
            .drop_duplicates(["dt", "city_id"])
            .loc[:, [
                "city_id_sql",
                "dt",
                "dt_txt",
                "main.temp",
                "main.feels_like",
                "main",
                "description",
                "id",
                "rain.3h",
                "clouds.all",
                "main.pressure",
                "main.humidity",
                "icon",
            ]]
            .rename({
                "dt": "time",
                "dt_txt": "time_text",
                "main.temp": "temperature",
                "main.feels_like": "temperature_felt",
                "main": "weather",
                "id": "weather_id",
                "rain.3h": "rain_3h",
                "clouds.all": "clouds",
                "main.pressure": "pressure",
                "main.humidity": "humidity",
                "icon": "icon_id",
                "city_id_sql": "city_id",
            }, axis=1)
    )
    forecast_table["precipitation_prob"] = (forecast["weather"].loc[:, "pop"] * 100).astype(int)

    # Write / Update the tables
    city_update.to_sql(
        'city_tmp',
        schema="gans",
        if_exists='replace',
        con=connection_string,
        index=False,
    )
    solar_time.to_sql(
        'solar_time',
        schema="gans",
        if_exists='append',
        con=connection_string,
        index=False,
    )
    forecast_table.to_sql(
        'forecast',
        schema="gans",
        if_exists='append',
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
        c.callproc("update_city")

    conn.commit()
    conn.close()
