import folium
import requests
import pandas as pd
from folium import IFrame
from streamlit_folium import folium_static
import streamlit as st
from streamlit_js_eval import streamlit_js_eval

# Set Streamlit layout to wide mode
st.set_page_config(layout="wide", page_title="Hydrocron Data Download", page_icon=":material/cloud_download:") 

# Streamlit Interface
st.title("Hydrocron Data Viz and Download")
image_url = 'https://cef.org.au/wp-content/uploads/2021/10/UoW-logo.png'
st.logo(image_url, link="https://www.uow.edu.au/", size="large", icon_image=None)

screen_width = int((streamlit_js_eval(js_expressions='screen.width', key='SCR')) * 0.85)

# Function to fetch and process data from API
def fetch_data(reach_id, start_time, end_time, fields):
    base_url = "https://soto.podaac.earthdatacloud.nasa.gov/hydrocron/v1/timeseries"
    params = {
        "feature": "Reach",
        "feature_id": reach_id,
        "start_time": start_time,
        "end_time": end_time,
        "output": "geojson",
        "fields": fields
    }

    # Send the GET request
    hydrocron_response = requests.get(base_url, params=params).json()

    # Extract geojson data and process
    geojson_data = hydrocron_response['results']['geojson']
    data_list = []
    for feature in geojson_data['features']:
        properties = feature['properties']
        data_list.append([properties[field] for field in fields.split(',')])

    # Create DataFrame
    df = pd.DataFrame(data_list, columns=fields.split(','))
    df = df[df['time_str'] != 'no_data']
    df['ID'] = range(1, len(df) + 1)
    return geojson_data, df, start_time, end_time

# Function to create map with Folium
def create_map(geojson_data, df, start_time, end_time):
    # Initialize map centered at a given location
    map = folium.Map(zoom_start=4, tiles=None, control_scale=True)

    
    folium.TileLayer(
        tiles='https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
        attr='© OpenStreetMap contributors & CARTO',
        name="Light Map",
        subdomains='abcd'
    ).add_to(map)
    
    # Add basemaps to the map
    folium.TileLayer(
        tiles="https://{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
        attr="© Google",
        name="Satellite Hybrid Imagery",
        subdomains=["mt0", "mt1", "mt2", "mt3"]
    ).add_to(map)

    
    
    # Assuming df is your DataFrame
    df_unique = df.drop_duplicates(subset=['river_name', 'continent_id', 'reach_id'])
    # Extract the top row
    top_row = df_unique.iloc[0]
    # Initialize an empty string to hold the formatted output
    
    formatted_output = f"""
    <div style="font-family: Arial, sans-serif; color: #333; padding: 6px; font-size: 14px;">
        <h3 style="color: #5a2d9c; font-size: 16px;">River Information</h3>
        <p style="margin-bottom: 1px; padding-bottom: 0px;"><strong>River Name:</strong> {top_row['river_name']} - {top_row['reach_id']}</p>
        <p style="margin-bottom: 1px; padding-bottom: 0px;"><strong>Reach ID:</strong> {top_row['reach_id']}</p>
        <p style="margin-bottom: 1px; padding-bottom: 0px;"><strong>Continent ID:</strong> {top_row['continent_id']}</p>
        <p style="margin-bottom: 1px; padding-bottom: 0px;"><strong>Start Time:</strong> {start_time}</p>
        <p style="margin-bottom: 1px; padding-bottom: 0px;"><strong>End Time:</strong> {end_time}</p>
    </div>
    """

    iframe = IFrame(html=formatted_output, width=400, height=215)
    popup = folium.Popup(iframe, max_width=400, min_width=250)

    # Add GeoJSON to the map
    folium.GeoJson(geojson_data, name="Reach Features", popup=popup).add_to(map)
    folium.LayerControl().add_to(map)
    map.fit_bounds(map.get_bounds(), padding=(30, 30))

    return map

with st.expander("$ \\large \\textrm {\color{#F94C10} Help} $", expanded=False, icon=":material/info:"):
    st.markdown("""
    #### About the Tool
    This tool sources data through Hydrocron API calls and enables users to download the results as a CSV file and visualize them on a map, making it easier to handle and analyze the data.
    
    #### How to Use the Tool:
    1. **Find Reach ID**: Identify the Reach ID for the river segment you're interested in. You can find Reach IDs [here](https://shorturl.at/yZzbT).   
    :gray[*Requires ArcGIS Pro or QGIS or similar to open those files.*]
    2. **Input Start and End Times**: Enter the start and end times for the period you want to retrieve data for, in the format `YYYY-MM-DDTHH:MM:SSZ`.

    Once the data is fetched, the tool generates a **downloadable CSV table** and displays the data on an **interactive map** below.
    """)


# Streamlit user input interface
with st.expander("$ \\large \\textrm {\color{#F94C10} Inputs} $", expanded=True, icon=":material/instant_mix:"):
    # User Inputs for Reach ID, Start Time, and End Time
    reach_id = st.text_input(":violet[**River Reach ID**]", "56861000151")
    start_time = st.text_input(":violet[**Start Time**]", "2022-07-01T00:00:00Z", help="YYYY-MM-DDTHH:MM:SSZ")
    end_time = st.text_input(":violet[**End Time**]", "2024-12-05T00:00:00Z", help="YYYY-MM-DDTHH:MM:SSZ")

    compulsory_fields = ['reach_id', 'river_name', 'continent_id']
    # All fields as selectable checkboxes
    fields = [
        'reach_id', 'time', 'time_tai', 'time_str', 'p_lat', 'p_lon', 'river_name',
        'wse', 'wse_u', 'wse_r_u', 'wse_c', 'wse_c_u', 'slope', 'slope_u', 'slope_r_u',
        'slope2', 'slope2_u', 'slope2_r_u', 'width', 'width_u', 'width_c', 'width_c_u',
        'area_total', 'area_tot_u', 'area_detct', 'area_det_u', 'area_wse', 'd_x_area', 
        'd_x_area_u', 'layovr_val', 'node_dist', 'loc_offset', 'xtrk_dist', 'dschg_c', 
        'dschg_c_u', 'dschg_csf', 'dschg_c_q', 'dschg_gc', 'dschg_gc_u', 'dschg_gcsf', 
        'dschg_gc_q', 'dschg_m', 'dschg_m_u', 'dschg_msf', 'dschg_m_q', 'dschg_gm', 
        'dschg_gm_u', 'dschg_gmsf', 'dschg_gm_q', 'dschg_b', 'dschg_b_u', 'dschg_bsf', 
        'dschg_b_q', 'dschg_gb', 'dschg_gb_u', 'dschg_gbsf', 'dschg_gb_q', 'dschg_h', 
        'dschg_h_u', 'dschg_hsf', 'dschg_h_q', 'dschg_gh', 'dschg_gh_u', 'dschg_ghsf', 
        'dschg_gh_q', 'dschg_o', 'dschg_o_u', 'dschg_osf', 'dschg_o_q', 'dschg_go', 
        'dschg_go_u', 'dschg_gosf', 'dschg_go_q', 'dschg_s', 'dschg_s_u', 'dschg_ssf', 
        'dschg_s_q', 'dschg_gs', 'dschg_gs_u', 'dschg_gssf', 'dschg_gs_q', 'dschg_i', 
        'dschg_i_u', 'dschg_isf', 'dschg_i_q', 'dschg_gi', 'dschg_gi_u', 'dschg_gisf', 
        'dschg_gi_q', 'dschg_q_b', 'dschg_gq_b', 'reach_q', 'reach_q_b', 'dark_frac', 
        'ice_clim_f', 'ice_dyn_f', 'partial_f', 'n_good_nod', 'obs_frac_n', 'xovr_cal_q', 
        'geoid_hght', 'geoid_slop', 'solid_tide', 'load_tidef', 'load_tideg', 'pole_tide', 
        'dry_trop_c', 'wet_trop_c', 'iono_c', 'xovr_cal_c', 'n_reach_up', 'n_reach_dn', 
        'rch_id_up', 'rch_id_dn', 'p_wse', 'p_wse_var', 'p_width', 'p_wid_var', 'p_n_nodes', 
        'p_dist_out', 'p_length', 'p_maf', 'p_dam_id', 'p_n_ch_max', 'p_n_ch_mod', 'p_low_slp', 
        'cycle_id', 'pass_id', 'continent_id', 'range_start_time', 'range_end_time', 'crid', 
        'sword_version', 'collection_shortname', 'collection_version', 'granuleUR', 
        'ingest_time'
    ]

    selected_fields = st.multiselect(":violet[**Select Fields to download**]", fields, default=['reach_id', 'time_str', 'wse', 'width', 'river_name', 'continent_id'])

    # Check if compulsory fields are selected
    if not all(field in selected_fields for field in compulsory_fields):
        st.warning(f"Please select all compulsory fields: {compulsory_fields}")

        # After the check, proceed with the process
    if all(field in selected_fields for field in compulsory_fields):
        st.success("All compulsory fields selected. Choose other optional fields and :blue[proceed with the download...]")
    else:
        st.stop()  # Stops further execution until the condition is met


# Button to trigger data fetching and displaying
if st.button("Run", icon=":material/play_circle:"):
    if reach_id and start_time and end_time and selected_fields:
        # Fetch data using user inputs
        geojson_data, df, start_time, end_time = fetch_data(reach_id, start_time, end_time, ','.join(selected_fields))

        # Show Data Table in Streamlit
        st.write("### Data Table", df)

        # Placeholder for dynamic map
        map_placeholder = st.empty()

        # Display Map with initial width
        map = create_map(geojson_data, df, start_time=start_time, end_time=end_time)
        folium_static(map, width=screen_width)
    
    else:
        st.warning("Please enter all fields (Reach ID, Start Time, and End Time) to fetch data.")

