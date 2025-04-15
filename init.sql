-- init-db.sql

-- Create tables to store and read information
CREATE TABLE sensors (
    sensor_id SERIAL PRIMARY KEY,
    sensor_name VARCHAR(50) NOT NULL,
    sensor_locale VARCHAR(50) NOT NULL,
    sensor_region VARCHAR(50) NOT NULL,
    sensor_country VARCHAR(50) NOT NULL,
    sensor_lat FLOAT NOT NULL,
    sensor_long FLOAT NOT NULL,
    sensor_timezone VARCHAR(50) NOT NULL
);

CREATE TABLE weather_data (
    data_id SERIAL PRIMARY KEY,
    sensor_id INTEGER REFERENCES sensors(sensor_id),
    time_recorded VARCHAR(50) NOT NULL,
    temp_c REAL NOT NULL,
    temp_f FLOAT NOT NULL,
    wind_mph FLOAT NOT NULL,
    wind_kph FLOAT NOT NULL,
    wind_degree FLOAT NOT NULL,
    wind_dir VARCHAR(50) NOT NULL,
    pressure_mb FLOAT NOT NULL,
    pressure_in FLOAT NOT NULL,
    precip_mm FLOAT NOT NULL,
    precip_in FLOAT NOT NULL,
    humidity_perc FLOAT NOT NULL,
    uv_index_score FLOAT NOT NULL
);

-- Create data generation user and set permissions
CREATE ROLE data_generator WITH LOGIN PASSWORD 'data_gen_pass';
GRANT CONNECT ON DATABASE postgres TO data_generator;
GRANT USAGE ON SCHEMA public TO data_generator;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO data_generator;
GRANT USAGE, SELECT ON SEQUENCE sensors_sensor_id_seq TO data_generator;
GRANT USAGE, SELECT ON SEQUENCE weather_data_data_id_seq TO data_generator;

-- Create web viewer user and set permissions
CREATE ROLE web_viewer WITH LOGIN PASSWORD 'web_view_pass';
GRANT CONNECT ON DATABASE postgres TO web_viewer;
GRANT USAGE ON SCHEMA public TO web_viewer;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO web_viewer;
GRANT USAGE, SELECT ON SEQUENCE sensors_sensor_id_seq TO web_viewer;
GRANT USAGE, SELECT ON SEQUENCE weather_data_data_id_seq TO web_viewer;
