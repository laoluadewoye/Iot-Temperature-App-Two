from requests import get
from os import getenv
from tomllib import load
from threading import Thread, Event, Lock, current_thread
from typing import Literal, Union
from time import sleep
from datetime import datetime, timedelta
from copy import deepcopy
from psycopg2 import connect
from psycopg2.extensions import connection, cursor


# API Key
API_KEY: str = open('API_KEY.txt').read()  # API key because no hardcoding

# Retrieve configuration
with open('start_config.toml', 'rb') as config_file:
    config = load(config_file)

# Get API parameters
LOCATION_SET: set[str] = config['location_set']
GET_AIR_QUALITY: Literal['yes', 'no'] = config['get_air_quality']

# Get other parameters
RESET_DATABASE: Literal['yes', 'no'] = config['reset_database']
GET_HISTORICAL_DATA: Literal['yes', 'no'] = config['get_historical_data']
SENSOR_INTERVAL_SECONDS: float = config['sensor_interval_seconds']
UPDATE_INTERVAL_SECONDS: float = config['update_interval_seconds']

# Dynamic parameters
DATABASE_CREATION_PROGRESS: float = 0.0

# Environmental variables
ENV_DB_HOST = "postgres"
ENV_DB_NAME = "postgres"
ENV_DB_USER = "data_generator"
ENV_DB_PASSWORD = open("/run/secrets/iot_temp_data_gen_password").read().strip()
ENV_DB_PORT = 5432


def add_sensor_entry(sensor_conn: connection, sensor_api_link: str, conn_lock: Lock,
                     sensor_name: Union[str, None] = None) -> int:
    # Set sensor name
    if sensor_name is None:
        sensor_name = current_thread().name

    with conn_lock:
        # Check for entry
        sensor_cursor: cursor = sensor_conn.cursor()
        sensor_cursor.execute('SELECT * FROM sensors WHERE sensor_name = %s', (sensor_name,))

        # Add if check returned nothing
        if not sensor_cursor.fetchall():
            sensor_location_info: dict = get(url=sensor_api_link).json()['location']
            insert_params: tuple = (
                sensor_name, sensor_location_info["name"], sensor_location_info["region"],
                sensor_location_info["country"], sensor_location_info["lat"], sensor_location_info["lon"],
                sensor_location_info["tz_id"]
            )
            insert_query: str = (
                "INSERT INTO sensors "
                "(sensor_name, sensor_locale, sensor_region, sensor_country, "
                "sensor_lat, sensor_long, sensor_timezone) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)"
            )
            sensor_cursor.execute(insert_query, insert_params)

            # Commit transaction
            sensor_conn.commit()
            print(f'Added {sensor_name} to database')

        # Get sensor id
        sensor_cursor.execute('SELECT sensor_id FROM sensors WHERE sensor_name = %s', (sensor_name,))
        sensor_id: int = sensor_cursor.fetchone()[0]
        print('Sensor ID:', sensor_id)

    return sensor_id


def add_sensor_data_entry(sensor_conn: connection, sensor_id: int, sensor_current_info: dict, conn_lock: Lock,
                          timestamp: Union[str, None] = None, sensor_name: Union[str, None] = None) -> None:
    # Set sensor name and timestamp
    if sensor_name is None:
        sensor_name = current_thread().name
    if timestamp is None:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    with conn_lock:
        insert_params: tuple = (
            sensor_id, timestamp, sensor_current_info['temp_c'],
            sensor_current_info['temp_f'], sensor_current_info['wind_mph'], sensor_current_info['wind_kph'],
            sensor_current_info['wind_degree'], sensor_current_info['wind_dir'], sensor_current_info['pressure_mb'],
            sensor_current_info['pressure_in'], sensor_current_info['precip_mm'], sensor_current_info['precip_in'],
            sensor_current_info['humidity'], sensor_current_info['uv']
        )
        insert_query: str = (
            "INSERT INTO weather_data "
            "(sensor_id, time_recorded, temp_c, temp_f, wind_mph, wind_kph, wind_degree, wind_dir, "
            "pressure_mb, pressure_in, precip_mm, precip_in, humidity_perc, uv_index_score) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        )
        sensor_cursor: cursor = sensor_conn.cursor()
        sensor_cursor.execute(insert_query, insert_params)

        # Commit transaction
        sensor_conn.commit()
        print(f'Added weather data from {sensor_name} to database at {insert_params[1]}.')


def weather_detection_service(sensor_loc: str, conn_lock: Lock, stop_event: Event) -> None:
    # Connect to the database
    sensor_conn: connection = connect(
        host=ENV_DB_HOST, database=ENV_DB_NAME, user=ENV_DB_USER, password=ENV_DB_PASSWORD, port=ENV_DB_PORT
    )

    # Create api link
    sensor_api_link = f'http://api.weatherapi.com/v1/current.json?key={API_KEY}&q={sensor_loc}&aqi={GET_AIR_QUALITY}'

    # Add sensor to database if not exist
    if not stop_event.is_set():
        sensor_db_id: int = add_sensor_entry(sensor_conn, sensor_api_link, conn_lock)

    # Start data generation loop
    next_update: datetime = datetime.now()
    while not stop_event.is_set():
        if datetime.now() > next_update:
            # Get updated information
            sensor_current_info: dict = get(url=sensor_api_link).json()['current']
            print(f'Weather data from {sensor_loc} was last updated at {sensor_current_info["last_updated"]}.')

            # Add updated information to database
            if not stop_event.is_set():
                add_sensor_data_entry(sensor_conn, sensor_db_id, sensor_current_info, conn_lock)

            # Reset next update
            next_update = datetime.now() + timedelta(seconds=UPDATE_INTERVAL_SECONDS)

        # Sleep for one second until next stop event check
        sleep(1)


def create_historical_data(start_date: Union[datetime, None] = None) -> None:
    global DATABASE_CREATION_PROGRESS

    # Start from one week ago by default
    present_date: datetime = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if start_date is None:
        start_date: datetime = present_date - timedelta(days=7)

    # Wait a few seconds
    sleep(3)

    # Connect to the database
    hist_conn: connection = connect(
        host=ENV_DB_HOST, database=ENV_DB_NAME, user=ENV_DB_USER, password=ENV_DB_PASSWORD, port=ENV_DB_PORT
    )
    hist_conn_lock: Lock = Lock()

    # Start the loop
    num_sensors = len(LOCATION_SET)
    sensors_completed = 0
    for sensor_location in LOCATION_SET:
        # Prepare sensor information
        sensor_api_link: str = (
            f'http://api.weatherapi.com/v1/current.json?key={API_KEY}&q={sensor_location}&aqi={GET_AIR_QUALITY}'
        )
        sensor_name: str = f'sensor_{sensor_location.replace(" ", "_").lower()}'
        sensor_id: int = add_sensor_entry(hist_conn, sensor_api_link, hist_conn_lock, sensor_name)

        # Loop through historical data
        cur_date: datetime = deepcopy(start_date)
        while cur_date <= present_date:
            # Get hourly data
            sensor_api_link: str = (
                f'http://api.weatherapi.com/v1/history.json?'
                f'key={API_KEY}&q={sensor_location}&dt={cur_date.strftime("%Y-%m-%d")}&aqi={GET_AIR_QUALITY}'
            )
            data_by_sensor_hour: list = get(url=sensor_api_link).json()['forecast']['forecastday'][0]['hour']

            # Add hourly data to database
            for sensor_hour_info in data_by_sensor_hour:
                sensor_hour_timestamp = datetime.strptime(sensor_hour_info['time'], '%Y-%m-%d %H:%M')
                add_sensor_data_entry(
                    hist_conn, sensor_id, sensor_hour_info, hist_conn_lock,
                    sensor_hour_timestamp.strftime('%Y-%m-%d %H:%M:%S'), sensor_name
                )

            # Increment date by one day
            cur_date += timedelta(days=1)

            # Calculate progress
            cur_sensor_progress = (present_date - cur_date).total_seconds() / (present_date - start_date).total_seconds()
            DATABASE_CREATION_PROGRESS = sensors_completed / num_sensors + cur_sensor_progress * (1 / num_sensors)

        # Increment sensor completion count
        sensors_completed += 1

    # Finish Database Creation
    DATABASE_CREATION_PROGRESS = 1.0
    hist_conn.close()


def get_db_create_progress() -> float:
    global DATABASE_CREATION_PROGRESS
    return DATABASE_CREATION_PROGRESS


def start_sensor_threads(main_stop_event: Event) -> None:
    # Create threads for sensors
    main_conn_lock: Lock = Lock()
    sensor_threads: dict[str, Thread] = {}
    for sensor_location in LOCATION_SET:
        new_sensor_name: str = f'sensor_{sensor_location.replace(" ", "_").lower()}'
        sensor_threads[new_sensor_name] = Thread(
            name=new_sensor_name,
            target=weather_detection_service,
            args=(sensor_location, main_conn_lock, main_stop_event,)
        )
        sensor_threads[new_sensor_name].start()


def start_database(init_stop_event: Event, sensor_stop_event: Event) -> None:
    # Get Historical Data
    if GET_HISTORICAL_DATA == 'yes' and not init_stop_event.is_set():
        create_historical_data()

    # Start sensor threads
    # start_sensor_threads(sensor_stop_event)

    # Set the init stop event
    init_stop_event.set()


if __name__ == '__main__':
    test_stop_event: Event = Event()
    test_sensor_stop_event: Event = Event()

    init_thread = Thread(target=start_database, args=(test_stop_event, test_sensor_stop_event))
    init_thread.start()

    init_thread.join()
