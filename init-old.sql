-- init-db.sql

-- Create tables to store and read information
CREATE TABLE temperature_data (
    time_recorded TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    value_fahr FLOAT NOT NULL,
    PRIMARY KEY (time_recorded)
);

CREATE TABLE humidity_data (
    time_recorded TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    value_svp_perc FLOAT NOT NULL,
    PRIMARY KEY (time_recorded)
);

CREATE TABLE air_pressure_data (
    time_recorded TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    value_hpa FLOAT NOT NULL,
    PRIMARY KEY (time_recorded)
);

CREATE TABLE wind_speed_data (
    time_recorded TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    value_mph FLOAT NOT NULL,
    PRIMARY KEY (time_recorded)
);

CREATE TABLE wind_direction_data (
    time_recorded TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    value_deg FLOAT NOT NULL,
    PRIMARY KEY (time_recorded)
);

CREATE TABLE solar_radiation_data (
    time_recorded TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    value_w_m2 FLOAT NOT NULL,
    PRIMARY KEY (time_recorded)
);

CREATE TABLE uv_index_data (
    time_recorded TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    value_uvi FLOAT NOT NULL,
    PRIMARY KEY (time_recorded)
);

CREATE TABLE precipitation_data (
    time_recorded TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    value_nm_s FLOAT NOT NULL,
    PRIMARY KEY (time_recorded)
);

-- Create data generation user and set permissions
CREATE ROLE data_generator WITH LOGIN PASSWORD 'data_gen_pass';
GRANT CONNECT ON DATABASE postgres TO data_generator;
GRANT USAGE ON SCHEMA public TO data_generator;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO data_generator;

-- Create web viewer user and set permissions
CREATE ROLE web_viewer WITH LOGIN PASSWORD 'web_view_pass';
GRANT CONNECT ON DATABASE postgres TO web_viewer;
GRANT USAGE ON SCHEMA public TO web_viewer;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO web_viewer;
