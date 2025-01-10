import folium
import requests
import pandas as pd
from folium import IFrame
from streamlit_folium import folium_static
import streamlit as st

# Set Streamlit layout to wide mode
st.set_page_config(layout="wide", page_title="Hydrocron Data Download", page_icon=":material/cloud_download:") 
# Streamlit Interface
st.title("Hydrocron Data Viz and Download")
image_url = 'https://cef.org.au/wp-content/uploads/2021/10/UoW-logo.png'
st.logo(image_url, link="https://www.uow.edu.au/", size="large", icon_image=None)


# Function to fetch and process data from API
def fetch_data(reach_id, start_time, end_time):
    base_url = "https://soto.podaac.earthdatacloud.nasa.gov/hydrocron/v1/timeseries"
    params = {
        "feature": "Reach",
        "feature_id": reach_id,
        "start_time": start_time,
        "end_time": end_time,
        "output": "geojson",
        "fields": "reach_id,time_str,wse,width,geometry,river_name,cycle_id,pass_id,continent_id,collection_shortname"
    }

    # Send the GET request
    hydrocron_response = requests.get(base_url, params=params).json()

    # Extract geojson data and process
    geojson_data = hydrocron_response['results']['geojson']
    data_list = []
    for feature in geojson_data['features']:
        reachID = feature['properties']['reach_id']
        riverName = feature['properties']['river_name']
        wse = feature['properties']['wse']
        time_str = feature['properties']['time_str']

        cycle_id = feature['properties']['cycle_id']
        continent_id = feature['properties']['continent_id']
        collection_shortname = feature['properties']['collection_shortname']

        data_list.append([reachID, riverName, wse, time_str])

    # Create DataFrame
    df = pd.DataFrame(data_list, columns=['Reach_ID', 'River Name', 'WSE (m)', 'Time (UTC)'])
    df = df[df['Time (UTC)'] != 'no_data']
    df['ID'] = range(1, len(df) + 1)
    df = df[['ID', 'Reach_ID', 'River Name', 'WSE (m)', 'Time (UTC)']]
    
    return geojson_data, df, cycle_id, continent_id, collection_shortname

# Function to create map with Folium
def create_map(geojson_data, df, cycle_id, continent_id, collection_shortname):
    # Initialize map centered at a given location
    map = folium.Map(zoom_start=4, tiles=None, control_scale=True)

    # Add basemaps to the map
    folium.TileLayer(
        tiles="https://{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
        attr="© Google",
        name="Satellite Hybrid Imagery",
        subdomains=["mt0", "mt1", "mt2", "mt3"]
    ).add_to(map)

    folium.TileLayer(
        tiles='https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
        attr='© OpenStreetMap contributors & CARTO',
        name="Light Map",
        subdomains='abcd'
    ).add_to(map)

    # Create the HTML table and other information for the popup
    table_html = df.to_html(index=False, border=1, classes="table table-striped", escape=False)
    other_info = f"<br><b>Cycle ID:</b> {cycle_id}<br><b>Continent ID:</b> {continent_id}<br><b>Collection:</b> {collection_shortname}"

    table_html = f"""
    <style>
        .popup-content {{
            height: 200px;
            width: auto;
            overflow-y: auto;
            text-align: center;
        }}
        .table {{
            width: 100%;
            table-layout: auto;
            font-size: 11px;
            margin: 0;
            border-collapse: collapse;
            text-align: center;
        }}
        .table td, .table th {{
            padding: 6px;
            text-align: center;
            word-wrap: break-word;
        }}
        .table th {{
            background-color: #4CAF50;
            color: white;
            font-weight: bold;
        }}
        .table tr:nth-child(even) {{
        background-color: #f2f2f2;
        }}
        .table tr:hover {{
            background-color: #ddd;
        }}
        .other-info {{
            font-size: 12px;
            color: #555;
            margin-top: 15px;
            font-family: 'Arial', sans-serif;
        }}
    </style>
    <div class="popup-content">
        {table_html}
    </div>
    <div class="other-info">
        {other_info}
    </div>
    """
    
    # Create popup with IFrame
    iframe = IFrame(html=table_html, width=400, height=300)
    popup = folium.Popup(iframe, max_width=400, min_width=250)

    # Add GeoJSON to the map
    folium.GeoJson(geojson_data, name="Reach Features", popup=popup).add_to(map)
    folium.LayerControl().add_to(map)
    # zoom to the river feature we added
    map.fit_bounds(map.get_bounds(), padding=(30, 30))
    
    return map



with st.expander("$ \\large \\textrm {\color{#F94C10} Inputs} $", expanded=True, icon=":material/instant_mix:"):
    
    st.markdown("")
    downloadFields = '''$ \small Click \; on\;  the\; link \;get \; River \;Reach \;ID.  \;Requires \;ArcGIS \;Pro \;or \;QGIS \;or \;similar \;to \;open \;those \;files\; - $ 
    [SWORD - SWOT River Database](https://shorturl.at/yZzbT)  
    $ \small Following\; fields\; will\; be\; downloaded -$    
      
    
    reach_id, time_str, wse, width, geometry, river_name, cycle_id, pass_id, continent_id, collection_shortname'''
    st.markdown(downloadFields)
    st.markdown("")


    rcol1, rcol2 = st.columns([1, 5])
    with rcol1: reach_id = st.text_input(":red[**River Reach ID**]", "56861000151")

    # Create columns for input fields
    col1, col2, col3 = st.columns([1, 0.02, 1])
    # User Inputs for Reach ID, Start Time, and End Time
    with col1: start_time = st.text_input(":red[**Start Time**]", "2022-07-01T00:00:00Z", help="YYYY-MM-DDTHH:MM:SSZ",)
    with col3: end_time = st.text_input(":red[**End Time**]", "2024-12-05T00:00:00Z", help="YYYY-MM-DDTHH:MM:SSZ")

# Button to trigger data fetching and displaying
if st.button("Run", icon=":material/settings:"):
    if reach_id and start_time and end_time:
        
        # Fetch data using user inputs
        geojson_data, df, cycle_id, continent_id, collection_shortname = fetch_data(reach_id, start_time, end_time)

        # Show Data Table in Streamlit
        st.write("### Data Table", df)

        # Placeholder for dynamic map
        map_placeholder = st.empty()

        # Display Map with initial width
        map = create_map(geojson_data, df, cycle_id=cycle_id, continent_id=continent_id, collection_shortname=collection_shortname)
        folium_static(map, width=1000)

    else:
        st.warning("Please enter all fields (Reach ID, Start Time, and End Time) to fetch data.")



