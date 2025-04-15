import streamlit as st
import pandas as pd
from DataGen import UPDATE_INTERVAL_SECONDS
from streamlit_autorefresh import st_autorefresh
from collections import Counter
from datetime import datetime, timedelta
from threading import Thread, Event
from time import sleep


def get_avg_metric(conn_string: str, timestamps_by_sensor: pd.DataFrame, col_n, selected_unit: str,
                   selected_unit_modifier: str, metric_title: str, delta=None) -> None:
    timestamps_by_sensor = timestamps_by_sensor.values.tolist()

    results = []
    for sensor_id, max_timestamp in timestamps_by_sensor:
        # cursor.execute(query, (sensor_id, max_timestamp))
        # results.append(cursor.fetchone()[0])
        query = (f"SELECT {selected_unit} FROM weather_data "
                 f"WHERE sensor_id = {sensor_id} AND time_recorded = '{max_timestamp}'")
        df = pd.read_sql_query(query, conn_string)
        if not df.empty:
            results.append(df.iloc[0, 0])

    col_n.metric(metric_title, f'{round(sum(results) / len(results), 2)}{selected_unit_modifier}', delta)


def get_hist_section(conn_string: str, start_date_time: datetime, end_date_time: datetime, just_id_choices: list[int],
                     id_to_locale_map: dict[int, str], measured_unit: str, measured_unit_modifier: str,
                     title: str, y_label_base: str) -> None:
    # Create title for plot
    st.subheader(title)

    # Get data using ids
    if len(just_id_choices) == 1:
        query = (f"SELECT sensor_id, time_recorded, {measured_unit} FROM weather_data "
                 f"WHERE sensor_id = {just_id_choices[0]}")
    else:
        query = (f"SELECT sensor_id, time_recorded, {measured_unit} FROM weather_data "
                 f"WHERE sensor_id IN {tuple(just_id_choices)}")
    df = pd.read_sql_query(query, conn_string)

    # Filter the table
    df['time_recorded'] = pd.to_datetime(df['time_recorded'])
    df = df[(df['time_recorded'] >= start_date_time) & (df['time_recorded'] <= end_date_time)]

    # Format the table
    df['locale'] = df['sensor_id'].map(lambda x: id_to_locale_map[x])
    pivot_df = df.pivot(index="time_recorded", columns="locale", values=measured_unit)

    # Create line chart
    st.line_chart(pivot_df, x_label='Date & Time', y_label=f'{y_label_base} ({measured_unit_modifier})')


def create_sensor_info_tab(conn_string: str) -> None:
    # Sensor information
    st.header("Sensor Information")
    st.write("This dashboard shows information about the sensors and their locations.")

    # Table
    st.subheader("Sensor Information Table")
    df = pd.read_sql_query("SELECT * FROM sensors", conn_string)
    st.dataframe(df)

    # Map
    st.subheader("Sensor Locations")
    df = pd.read_sql_query('SELECT sensor_lat, sensor_long FROM sensors', conn_string)
    st.map(df, latitude='sensor_lat', longitude='sensor_long', color='#2A9CFF', size=2000)


def create_latest_weather_tab(conn_string: str) -> None:
    # Real-time weather
    st.header("Real-Time Weather")
    st.write("This dashboard shows real-time weather data from the sensors.")

    # Selection for which sensors to view
    st.subheader("Select Locations to View")
    all_or_selected_latest = st.radio(
        "What locations would you like the average of?",
        ["All", "Selected Options"],
        horizontal=True,
        key="all_or_selected_latest"
    )

    # cursor.execute('SELECT sensor_locale, sensor_region, sensor_country FROM sensors')
    # all_locations_query = cursor.fetchall()
    df = pd.read_sql_query("SELECT sensor_locale, sensor_region, sensor_country FROM sensors", conn_string)
    all_locations_query = df.values.tolist()
    all_locations = [', '.join(location) for location in all_locations_query]

    if all_or_selected_latest == "All":
        st.empty()
        just_locale_choices = [location.split(', ')[0] for location in all_locations]
        locale_string = 'all locations'
    else:
        location_options_latest = st.multiselect(
            "Select locations to view:", all_locations, default=None, key="location_options_latest"
        )
        just_locale_choices = [location.split(', ')[0] for location in location_options_latest]
        if len(location_options_latest) == len(all_locations):
            locale_string = 'all locations'
        else:
            if len(just_locale_choices) > 2:
                locale_string = (', '.join(just_locale_choices[:2]) +
                                 f', and {len(just_locale_choices) - 2} more location(s).')
            else:
                locale_string = ', '.join(just_locale_choices)

    if len(just_locale_choices) == 0:
        st.write('No locations selected. Defaulting to All. **Please select at least one location.**')
        locale_string = 'all locations'

    # Selection for metric or customary
    st.subheader("Select Unit of Measurement")
    metric_or_customary_latest = st.radio(
        "What measurement system would you like to use?",
        ["Metric", "Customary"],
        horizontal=True,
        captions=["For international use.", "Used in North America and UK."],
        key="metric_or_customary_latest"
    )

    generic_units = {
        'Wind_Degree': 'wind_degree', 'Wind_Direction': 'wind_dir', 'Humidity': 'humidity_perc',
        'UV': 'uv_index_score'
    }
    generic_unit_modifiers = {'Wind_Degree': '°', 'Wind_Direction': '', 'Humidity': '%', 'UV': ' uvi'}
    if metric_or_customary_latest == "Metric":
        selected_units = {
            'Temperature': 'temp_c', 'Wind': 'wind_kph', 'Pressure': 'pressure_mb', 'Precipitation': 'precip_mm'
        }
        selected_unit_modifiers = {'Temperature': '°C', 'Wind': ' kph', 'Pressure': ' mb', 'Precipitation': ' mm'}
    else:
        selected_units = {
            'Temperature': 'temp_f', 'Wind': 'wind_mph', 'Pressure': 'pressure_in', 'Precipitation': 'precip_in'
        }
        selected_unit_modifiers = {'Temperature': '°F', 'Wind': ' mph', 'Pressure': ' in', 'Precipitation': ' in'}

    st.header(f'Current averages for {locale_string}.')
    st.write("This section shows the averages of several of the latest metrics over Maryland.")

    # Columns
    col1, col2, col3 = st.columns(3, border=True, gap="medium")
    col4, col5, col6 = st.columns(3, border=True, gap="medium")
    col7, col8, col9 = st.columns(3, border=True, gap="medium")

    # Get only the sensors wanted when getting the latest timestamps
    if locale_string == 'All Locations' or len(just_locale_choices) == 0:
        # cursor.execute('SELECT sensor_id, MAX(timestamp) AS max_timestamp FROM weather_data GROUP BY sensor_id')
        timestamps_by_sensor = pd.read_sql_query(
            'SELECT sensor_id, MAX(time_recorded) AS max_timestamp FROM weather_data GROUP BY sensor_id',
            conn_string
        )
    else:
        # Get only the ids wanted
        if len(just_locale_choices) == 1:
            # cursor.execute(f"SELECT sensor_id FROM sensors WHERE sensor_locale = '{just_locale_choices[0]}'")
            # just_id_choices = cursor.fetchone()[0]
            df = pd.read_sql_query(
                f"SELECT sensor_id FROM sensors WHERE sensor_locale = '{just_locale_choices[0]}'",
                conn_string
            )
            just_id_choices = df.iloc[0, 0]

            # Use the ids to get the latest timestamps
            # cursor.execute(f"""
            #     SELECT sensor_id, MAX(timestamp) AS max_timestamp FROM weather_data
            #     WHERE sensor_id = {just_id_choices} GROUP BY sensor_id
            # """)
            query = f"""
                SELECT sensor_id, MAX(time_recorded) AS max_timestamp FROM weather_data
                WHERE sensor_id = {just_id_choices} GROUP BY sensor_id
            """
            timestamps_by_sensor = pd.read_sql_query(query, conn_string)
        else:
            # cursor.execute(f'SELECT sensor_id FROM sensors WHERE sensor_locale IN {tuple(just_locale_choices)}')
            # just_id_choices = [sensor_id[0] for sensor_id in cursor.fetchall()]
            df_ids = pd.read_sql_query(
                f"SELECT sensor_id FROM sensors WHERE sensor_locale IN {tuple(just_locale_choices)}", conn_string
            )
            just_id_choices = df_ids['sensor_id'].tolist()

            # Use the ids to get the latest timestamps
            # cursor.execute(f"""
            #     SELECT sensor_id, MAX(timestamp) AS max_timestamp FROM weather_data
            #     WHERE sensor_id IN {tuple(just_id_choices)} GROUP BY sensor_id
            # """)
            query = f"""
                SELECT sensor_id, MAX(time_recorded) AS max_timestamp FROM weather_data
                WHERE sensor_id IN {tuple(just_id_choices)} GROUP BY sensor_id
            """
            timestamps_by_sensor = pd.read_sql_query(query, conn_string)

    # Average Temperature
    get_avg_metric(
        conn_string, timestamps_by_sensor, col1, selected_units["Temperature"], selected_unit_modifiers["Temperature"],
        "Avg Temperature"
    )

    # Average Wind Speed
    get_avg_metric(
        conn_string, timestamps_by_sensor, col2, selected_units["Wind"], selected_unit_modifiers["Wind"],
        "Avg Wind Speed"
    )

    # Average Wind Degree/Direction
    wind_dir_results = []
    for sid, mt in timestamps_by_sensor.values.tolist():
        # cursor.execute(wind_dir_query, (sid, mt))
        # wind_dir_results.append(cursor.fetchone()[0])
        query = (f"SELECT {generic_units['Wind_Direction']} FROM weather_data "
                 f"WHERE sensor_id = {sid} AND time_recorded = '{mt}'")
        df = pd.read_sql_query(query, conn_string)
        if not df.empty:
            wind_dir_results.append(df.iloc[0, 0])

    get_avg_metric(
        conn_string, timestamps_by_sensor, col3, generic_units["Wind_Degree"],
        generic_unit_modifiers["Wind_Degree"],
        "Avg Wind Direction",
        Counter(wind_dir_results).most_common(1)[0][0]
    )

    # Average Air Pressure
    get_avg_metric(
        conn_string, timestamps_by_sensor, col4, selected_units["Pressure"], selected_unit_modifiers["Pressure"],
        "Avg Air Pressure"
    )

    # Average Precipitation
    get_avg_metric(
        conn_string, timestamps_by_sensor, col5, selected_units["Precipitation"],
        selected_unit_modifiers["Precipitation"], "Avg Precipitation"
    )

    # Average Humidity
    get_avg_metric(
        conn_string, timestamps_by_sensor, col6, generic_units["Humidity"], generic_unit_modifiers["Humidity"],
        "Avg Humidity"
    )

    # Average UV Index Score
    get_avg_metric(
        conn_string, timestamps_by_sensor, col8, generic_units["UV"], generic_unit_modifiers["UV"],
        "Avg UV Index Score"
    )


def create_historical_tab(conn_string: str) -> None:
    # Real-time weather
    st.header("Historical Weather Trends")
    st.write("This dashboard shows historical weather data from the sensors given a specific range.")

    # Selection for which sensors to view
    st.subheader("Select Locations to View")
    all_or_selected_hist = st.radio(
        "What locations would you like the average of?",
        ["All", "Selected Options"],
        horizontal=True,
        key="all_or_selected_hist"
    )

    df = pd.read_sql_query("SELECT sensor_locale, sensor_region, sensor_country FROM sensors", conn_string)
    all_locations_query = df.values.tolist()
    all_locations = [', '.join(location) for location in all_locations_query]

    if all_or_selected_hist == "All":
        st.empty()
        just_locale_choices = [location.split(', ')[0] for location in all_locations]
        locale_string = 'all locations'
    else:
        location_options_hist = st.multiselect(
            "Select locations to view:", all_locations, default=None, key="location_options_hist"
        )
        just_locale_choices = [location.split(', ')[0] for location in location_options_hist]
        if len(location_options_hist) == len(all_locations):
            locale_string = 'all locations'
        else:
            if len(just_locale_choices) > 3:
                locale_string = (', '.join(just_locale_choices[:3]) +
                                 f', and {len(just_locale_choices) - 3} more location(s)')
            else:
                locale_string = ', '.join(just_locale_choices)

    if len(just_locale_choices) == 0:
        st.write('No locations selected. Defaulting to All. **Please select at least one location.**')
        locale_string = 'all locations'

    # Selection for metric or customary
    st.subheader("Select Unit of Measurement")
    metric_or_customary_hist = st.radio(
        "What measurement system would you like to use?",
        ["Metric", "Customary"],
        horizontal=True,
        captions=["For international use.", "Used in North America and UK."],
        key="metric_or_customary_hist"
    )

    generic_units = {
        'Wind_Degree': 'wind_degree', 'Wind_Direction': 'wind_dir', 'Humidity': 'humidity_perc',
        'UV': 'uv_index_score'
    }
    generic_unit_modifiers = {'Wind_Degree': '°', 'Wind_Direction': '', 'Humidity': '%', 'UV': ' uvi'}
    if metric_or_customary_hist == "Metric":
        selected_units = {
            'Temperature': 'temp_c', 'Wind': 'wind_kph', 'Pressure': 'pressure_mb', 'Precipitation': 'precip_mm'
        }
        selected_unit_modifiers = {'Temperature': '°C', 'Wind': ' kph', 'Pressure': ' mb', 'Precipitation': ' mm'}
    else:
        selected_units = {
            'Temperature': 'temp_f', 'Wind': 'wind_mph', 'Pressure': 'pressure_in', 'Precipitation': 'precip_in'
        }
        selected_unit_modifiers = {'Temperature': '°F', 'Wind': ' mph', 'Pressure': ' in', 'Precipitation': ' in'}

    # Selection for date range
    st.subheader("Select Date Range")
    date_range_choice_hist = st.radio(
        "Select the range of data you want to view:",
        ['Last 24 hours', 'Last 7 days', 'Last 30 days', 'Custom Range'],
        horizontal=True,
        key="date_range_choice_hist"
    )

    end_date = datetime.now()
    if date_range_choice_hist == 'Last 24 hours':
        st.empty()
        start_date = end_date - timedelta(hours=24)
    elif date_range_choice_hist == 'Last 7 days':
        st.empty()
        start_date = end_date - timedelta(days=7)
    elif date_range_choice_hist == 'Last 30 days':
        st.empty()
        start_date = end_date - timedelta(days=30)
    else:
        col1, col2 = st.columns(2)
        with col1:
            custom_start_date_hist = st.date_input('Select start date:', 'today')
            custom_start_time_hist = st.time_input('Select start time:', '00:00')
        with col2:
            custom_end_date_hist = st.date_input('Select end date:', 'today')
            custom_end_time_hist = st.time_input('Select end time:', '23:59')

        # Convert to datetime objects
        start_date = datetime.combine(custom_start_date_hist, custom_start_time_hist)
        end_date = datetime.combine(custom_end_date_hist, custom_end_time_hist)

    # Create string versions of dates
    start_date_str = start_date.strftime("%d %b %Y, %I:%M%p")
    end_date_str = end_date.strftime("%d %b %Y, %I:%M%p")

    # Get the ids necessary for the query
    if locale_string == 'all locations' or len(just_locale_choices) == 0:
        # cursor.execute('SELECT sensor_id, sensor_locale FROM sensors')
        # query_result = cursor.fetchall()
        # just_id_choices = [sensor_id[0] for sensor_id in query_result]
        # id_locale_map = {sensor_id[0]: sensor_id[1] for sensor_id in query_result}
        df = pd.read_sql_query("SELECT sensor_id, sensor_locale FROM sensors", conn_string)
        just_id_choices = df['sensor_id'].tolist()
        id_locale_map = dict(zip(df['sensor_id'], df['sensor_locale']))
    elif len(just_locale_choices) == 1:
        # cursor.execute(
        #     f"SELECT sensor_id, sensor_locale FROM sensors WHERE sensor_locale = '{just_locale_choices[0]}'"
        # )
        # query_result = cursor.fetchone()
        # just_id_choices = [query_result[0]]
        # id_locale_map = {query_result[0]: query_result[1]}
        df = pd.read_sql_query(
            f"SELECT sensor_id, sensor_locale FROM sensors WHERE sensor_locale = '{just_locale_choices[0]}'",
            conn_string
        )
        just_id_choices = df['sensor_id'].tolist()
        id_locale_map = dict(zip(df['sensor_id'], df['sensor_locale']))
    else:
        # cursor.execute(
        #     f'SELECT sensor_id, sensor_locale FROM sensors WHERE sensor_locale IN {tuple(just_locale_choices)}'
        # )
        # query_result = cursor.fetchall()
        # just_id_choices = [sensor_id[0] for sensor_id in query_result]
        # id_locale_map = {sensor_id[0]: sensor_id[1] for sensor_id in query_result}
        df = pd.read_sql_query(
            f'SELECT sensor_id, sensor_locale FROM sensors WHERE sensor_locale IN {tuple(just_locale_choices)}',
            conn_string
        )
        just_id_choices = df['sensor_id'].tolist()
        id_locale_map = dict(zip(df['sensor_id'], df['sensor_locale']))

    # Section for line plots
    st.header('Historical Trends by Topic')
    st.write(f'This dashboard shows historical weather data from {locale_string}.')

    # Historical Temperature Data
    get_hist_section(
        conn_string, start_date, end_date, just_id_choices, id_locale_map, selected_units['Temperature'],
        selected_unit_modifiers['Temperature'],
        f'Historical Temperature Data from {start_date_str} to {end_date_str}.', 'Degrees'
    )

    # Historical Wind Speed Data
    get_hist_section(
        conn_string, start_date, end_date, just_id_choices, id_locale_map, selected_units['Wind'],
        selected_unit_modifiers['Wind'],
        f'Historical Wind Speed Data from {start_date_str} to {end_date_str}.', 'Wind Speed'
    )

    # Historical Wind Direction Data
    st.subheader(f'Historical Wind Direction Data from {start_date_str} to {end_date_str}.')

    if len(just_id_choices) == 1:
        query = (f"SELECT sensor_id, time_recorded, {generic_units['Wind_Direction']} FROM weather_data "
                 f"WHERE sensor_id = {just_id_choices[0]}")
    else:
        query = (f"SELECT sensor_id, time_recorded, {generic_units['Wind_Direction']} FROM weather_data "
                 f"WHERE sensor_id IN {tuple(just_id_choices)}")
    wind_dir_df = pd.read_sql_query(query, conn_string)

    wind_dir_df['time_recorded'] = pd.to_datetime(wind_dir_df['time_recorded'])
    wind_dir_df = wind_dir_df[(wind_dir_df['time_recorded'] >= start_date) & (wind_dir_df['time_recorded'] <= end_date)]
    wind_dir_df = wind_dir_df[['time_recorded', generic_units['Wind_Direction']]]
    wind_dir_df_groups = wind_dir_df.groupby(['time_recorded', generic_units['Wind_Direction']])
    wind_dir_df_size = wind_dir_df_groups.size().unstack(fill_value=0)

    st.area_chart(wind_dir_df_size, stack=True, x_label='Date & Time', y_label=f'Wind Direction')

    # Historical Air Pressure Data
    get_hist_section(
        conn_string, start_date, end_date, just_id_choices, id_locale_map, selected_units['Pressure'],
        selected_unit_modifiers['Pressure'],
        f'Historical Air Pressure Data from {start_date_str} to {end_date_str}.', 'Air Pressure'
    )

    # Historical Precipitation Data
    get_hist_section(
        conn_string, start_date, end_date, just_id_choices, id_locale_map, selected_units['Precipitation'],
        selected_unit_modifiers['Precipitation'],
        f'Historical Precipitation Data from {start_date_str} to {end_date_str}.', 'Rainfall'
    )

    # Historical Humidity Data
    get_hist_section(
        conn_string, start_date, end_date, just_id_choices, id_locale_map, generic_units['Humidity'],
        generic_unit_modifiers['Humidity'],
        f'Historical Humidity Percentage Data from {start_date_str} to {end_date_str}.', 'Humidity'
    )

    # Historical UV Index Data
    get_hist_section(
        conn_string, start_date, end_date, just_id_choices, id_locale_map, generic_units['UV'], generic_unit_modifiers['UV'],
        f'Historical UV Index Data from {start_date_str} to {end_date_str}.', 'UV Index Score'
    )


def set_cooldown(e: Event) -> None:
    e.set()
    sleep(UPDATE_INTERVAL_SECONDS)
    e.clear()


def set_cooldown_thread(e: Event) -> None:
    cooldown_thread = Thread(target=set_cooldown, args=(e,))
    cooldown_thread.start()


def create_web_page():
    # Automatically refresh at a specific rate
    refresh_rate: int = int(UPDATE_INTERVAL_SECONDS) * 1000
    st_autorefresh(interval=refresh_rate, key="auto_refresh")

    # Create connection and cursor
    ENV_DB_HOST = "postgres"
    ENV_DB_NAME = "postgres"
    ENV_DB_USER = "web_viewer"
    ENV_DB_PASSWORD = open("secrets/iot_temp_web_view_password.txt").read().strip()
    ENV_DB_PORT = 5432

    web_string = f'postgresql+pg8000://{ENV_DB_USER}:{ENV_DB_PASSWORD}@{ENV_DB_HOST}:{ENV_DB_PORT}/{ENV_DB_NAME}'

    # Title of dashboard
    st.title("IoT Weather Sensor Data Dashboard")

    # Tabs
    tab1, tab2, tab3 = st.tabs(["Sensor Info", "Historical Trends Info", "Latest Weather Info"])

    with tab1:
        create_sensor_info_tab(web_string)
    with tab2:
        create_historical_tab(web_string)
    with tab3:
        create_latest_weather_tab(web_string)

    # # Create events for sidebar
    # web_event: Event = Event()
    # init_data_event: Event = Event()
    # cooldown_event: Event = Event()

    # # Start creating the database
    # init_thread = Thread(target=start_database, args=(init_data_event, web_event))
    # init_thread.start()

    # # Sidebar with toggling
    # with st.sidebar:
    #     st.header("Sidebar Menu")
    #     # if init_data_event.is_set():
    #     if True:
    #         data_gen_on = st.toggle(
    #             "Turn on active sensor data retrival", value=False, on_change=set_cooldown_thread,
    #             args=(cooldown_event,)
    #         )
    #         if data_gen_on:
    #             if cooldown_event.is_set():
    #                 st.write(f'Data Generation is already being started/stopped. '
    #                          f'Please wait {UPDATE_INTERVAL_SECONDS} before trying again.')
    #             else:
    #                 st.write('Data Generation has been started.')
    #                 if web_event.is_set():
    #                     web_event.clear()
    #                 start_sensor_threads(web_event)
    #         else:
    #             if cooldown_event.is_set():
    #                 st.write(f'Data Generation is already being started/stopped. '
    #                          f'Please wait {UPDATE_INTERVAL_SECONDS} before trying again.')
    #             else:
    #                 st.write('Data Generation has been stopped.')
    #                 if not web_event.is_set():
    #                     web_event.set()
    #     else:
    #         cur_progress_value: float = 0.0
    #         database_init_progress_bar = st.progress(
    #             value=cur_progress_value, text='Currently adding historical data to database. Please wait until done.'
    #         )
    #         while cur_progress_value < 1.0:
    #             sleep(0.1)
    #             cur_progress_value = get_db_create_progress()
    #             database_init_progress_bar.progress(cur_progress_value)


if __name__ == '__main__':
    st.set_page_config(layout='wide')
    create_web_page()
