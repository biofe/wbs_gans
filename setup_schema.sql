/* Create gans */

-- Drop the database if it already exists
DROP DATABASE IF EXISTS gans ;


-- Create the database
CREATE DATABASE gans;


-- Use the database
USE gans;

CREATE TABLE city (
    city_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    country VARCHAR(255) NOT NULL,
    country_code CHAR(2),
    timezone INT,
    population INT,
    latitude DECIMAL(10 , 7 ),
    longitude DECIMAL(10 , 7 )
);

-- drop table city_tmp;
-- Temporary city table for updating using pandas
CREATE TABLE city_tmp (
    city_id INT PRIMARY KEY,
    name VARCHAR(255),
    country VARCHAR(255),
    country_code CHAR(2),
    timezone INT,
    population INT,
    latitude DECIMAL(10 , 7 ),
    longitude DECIMAL(10 , 7 )
);

CREATE TABLE solar_time (
    city_id INT NOT NULL,
    sunrise INT NOT NULL,
    sunset INT NOT NULL,
    sunrise_text TEXT,
    sunset_text TEXT,
    FOREIGN KEY (city_id)
        REFERENCES city (city_id),
	UNIQUE (city_id, sunrise)
);

CREATE TABLE solar_time_tmp (
    city_id INT NOT NULL,
    sunrise INT NOT NULL,
    sunset INT NOT NULL,
    sunrise_text TEXT,
    sunset_text TEXT,
    FOREIGN KEY (city_id)
        REFERENCES city (city_id),
	UNIQUE (city_id, sunrise)
);

CREATE TABLE forecast (
	city_id INT NOT NULL,
    `time` INT NOT NULL,
    time_text TEXT,
    temperature DECIMAL(5, 2),
    temperature_felt DECIMAL(5, 2),
    weather TEXT,
    `description` TEXT,
    weather_id TEXT,
    precipitation_prob INT,
    rain_3h DECIMAL(5, 2),
    clouds INT,
    pressure INT,
    humidity INT,
    icon_id CHAR(3),
    FOREIGN KEY (city_id)
        REFERENCES city (city_id),
	UNIQUE (city_id, `time`)
);

CREATE TABLE forecast_tmp (
	city_id INT NOT NULL,
    `time` INT NOT NULL,
    time_text TEXT,
    temperature DECIMAL(5, 2),
    temperature_felt DECIMAL(5, 2),
    weather TEXT,
    `description` TEXT,
    weather_id TEXT,
    precipitation_prob INT,
    rain_3h DECIMAL(5, 2),
    clouds INT,
    pressure INT,
    humidity INT,
    icon_id CHAR(3),
    FOREIGN KEY (city_id)
        REFERENCES city (city_id),
	UNIQUE (city_id, `time`)
);

CREATE TABLE arrival (
    city_id INT NOT NULL,
    at_iata CHAR(3),
    icao CHAR(4),
    iata CHAR(3) NOT NULL,
    name TEXT,
    country_code CHAR(2),
    lat DECIMAL(10,7),
    lon DECIMAL(10,7),
    arrival VARCHAR(20) NOT NULL,
    FOREIGN KEY (city_id)
        REFERENCES city (city_id),
    UNIQUE (at_iata, iata, arrival)
);

-- drop table arrival;
CREATE TABLE arrival_tmp (
    city_id INT NOT NULL,
    at_iata CHAR(3),
    icao CHAR(4),
    iata CHAR(3) NOT NULL,
    name TEXT,
    country_code CHAR(2),
    lat DECIMAL(10,7),
    lon DECIMAL(10,7),
    arrival VARCHAR(20) NOT NULL,
    FOREIGN KEY (city_id)
        REFERENCES city (city_id),
    UNIQUE (at_iata, iata, arrival)
);

-- drop procedure update_arrival;
DELIMITER $$

CREATE PROCEDURE update_city ()

BEGIN
    UPDATE city AS c,
		city_tmp AS t 
	SET 
		c.country_code = t.country_code,
		c.timezone = t.timezone
	WHERE
		c.city_id = t.city_id;
END $$

CREATE PROCEDURE update_solar_time ()

BEGIN
	INSERT INTO solar_time (city_id, sunrise, sunset, sunrise_text, sunset_text)
    SELECT city_id, sunrise, sunset, sunrise_text, sunset_text FROM solar_time_tmp AS t
		ON DUPLICATE KEY UPDATE
			city_id = t.city_id,
			sunrise = t.sunrise,
			sunset = t.sunset,
			sunrise_text = t.sunrise_text,
			sunset_text = t.sunset_text;

END $$

CREATE PROCEDURE update_forecast ()

BEGIN
	INSERT INTO forecast (city_id, time, time_text, temperature, temperature_felt, weather, description, weather_id, rain_3h, clouds, pressure, humidity, icon_id, precipitation_prob)
    SELECT city_id, time, time_text, temperature, temperature_felt, weather, description, weather_id, rain_3h, clouds, pressure, humidity, icon_id, precipitation_prob FROM forecast_tmp AS t
    ON DUPLICATE KEY UPDATE
		city_id = t.city_id,
		time = t.time,
		time_text = t.time_text,
		temperature = t.temperature,
		temperature_felt = t.temperature_felt,
		weather = t.weather,
		description = t.description,
		weather_id = t.weather_id,
		rain_3h = t.rain_3h,
		clouds = t.clouds,
		pressure = t.pressure,
		humidity = t.humidity,
		icon_id = t.icon_id,
		precipitation_prob = t.precipitation_prob;

END $$

CREATE PROCEDURE update_arrival ()

BEGIN
	INSERT INTO arrival (at_iata, city_id, icao, iata, name, country_code, lat, lon, arrival)
    SELECT at_iata, city_id, icao, iata, name, country_code, lat, lon, arrival FROM arrival_tmp AS t
    ON DUPLICATE KEY UPDATE
        at_iata = t.at_iata,
        city_id = t.city_id,
        icao = t.icao,
        iata = t.iata,
        name = t.name,
        country_code = t.country_code,
        lat = t.lat,
        lon = t.lon,
        arrival = t.arrival;
END $$

DELIMITER ;

/*use gans;
select * from city;
select * from city_tmp;
select * from solar_time;
select * from forecast;
select * from arrival;
call update_city();
drop table `table`;

show processlist;
kill 115;
*/