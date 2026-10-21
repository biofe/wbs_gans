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

drop table city_tmp;
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
select * from city_tmp;

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

DELIMITER ;

use gans;
select * from city;
select * from solar_time;
select * from forecast;
drop table `table`;

UPDATE city AS c,
    city_tmp AS t 
SET 
    c.country_code = t.country_code,
    c.timezone = t.timezone
WHERE
    c.city_id = t.city_id;
