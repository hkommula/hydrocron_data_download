import folium
import requests
import pandas as pd
from folium import IFrame
from folium import plugins
from streamlit_folium import folium_static
import streamlit as st
from streamlit_js_eval import streamlit_js_eval
from shapely.geometry import shape
from streamlit_folium import st_folium
import hashlib
import colorsys
import html
import numpy as np

# NEW: interactive plotting
import plotly.graph_objects as go

try:
    # optional: enables click-to-details
    from streamlit_plotly_events import plotly_events
    PLOTLY_EVENTS_AVAILABLE = True
except Exception:
    PLOTLY_EVENTS_AVAILABLE = False

# ----------------------------
# App setup
# ----------------------------
st.set_page_config(layout="wide", page_title="Hydrocron Data Download", page_icon=":material/cloud_download:")
st.cache_data.clear()

st.title("Hydrocron Data Viz and Download")
image_url = 'https://cef.org.au/wp-content/uploads/2021/10/UoW-logo.png'
st.logo(image_url, link="https://www.uow.edu.au/", size="large", icon_image=None)

screen_width_js = (streamlit_js_eval(js_expressions='screen.width', key='SCR'))
screen_width = 0
if screen_width_js is not None:
    screen_width = round(screen_width_js * 0.9)

# ----------------------------
# Helpers
# ----------------------------
def reach_color_palette():
    """
    A clean, professional, user-friendly palette based on Tableau 20 + Set2.
    Supports ~20 distinct reaches. Deterministic via hashing.
    """
    return [
        "#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F",
        "#EDC948", "#B07AA1", "#FF9DA7", "#9C755F", "#BAB0AC",
        "#1F77B4", "#FF7F0E", "#2CA02C", "#D62728", "#9467BD",
        "#8C564B", "#E377C2", "#7F7F7F", "#BCBD22", "#17BECF"
    ]

def nice_color_for_reach(reach_id: str) -> str:
    """
    Deterministic professional color assignment for each reach ID.
    """
    palette = reach_color_palette()
    h = int(hashlib.md5(str(reach_id).encode()).hexdigest(), 16)
    return palette[h % len(palette)]


def esc(x):
    return html.escape(str(x)) if x is not None else "—"

def parse_reach_ids(text: str) -> list[str]:
    """Parse comma/space/newline separated reach ids into a unique, ordered list."""
    if not text:
        return []
    tokens = []
    for chunk in text.replace(",", " ").split():
        t = chunk.strip()
        if t:
            tokens.append(t)
    # preserve order while ensuring uniqueness
    seen = set()
    uniq = []
    for t in tokens:
        if t not in seen:
            uniq.append(t)
            seen.add(t)
    return uniq

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
    hydrocron_response = requests.get(base_url, params=params).json()
    # Extract geojson and table
    geojson_data = hydrocron_response['results']['geojson']
    data_list = []
    for feature in geojson_data['features']:
        properties = feature['properties']
        data_list.append([properties.get(field, None) for field in fields.split(',')])
    df = pd.DataFrame(data_list, columns=fields.split(','))
    if 'time_str' in df.columns:
        df = df[df['time_str'] != 'no_data']
    df['ID'] = range(1, len(df) + 1)
    return geojson_data, df, start_time, end_time

def fetch_data_multi(reach_ids: list[str], start_time, end_time, fields):
    """Fetch and combine multiple reach ids. Returns (FeatureCollection, combined_df, errors)."""
    all_features = []
    df_list = []
    errors = []

    for rid in reach_ids:
        try:
            gjson, df, _, _ = fetch_data(rid, start_time, end_time, fields)
            feats = gjson.get('features', [])
            if feats:
                all_features.extend(feats)
            if not df.empty:
                df_list.append(df)
        except Exception as e:
            errors.append(f"{rid}: {e}")

    combined_geojson = {"type": "FeatureCollection", "features": all_features}

    if df_list:
        combined_df = pd.concat(df_list, ignore_index=True)
        combined_df['ID'] = range(1, len(combined_df) + 1)
    else:
        combined_df = pd.DataFrame(columns=fields.split(',') + ['ID'])

    return combined_geojson, combined_df, errors

def get_geojson_bounds(geojson_data):
    min_lon, min_lat, max_lon, max_lat = float('inf'), float('inf'), float('-inf'), float('-inf')
    if geojson_data.get('type') == 'FeatureCollection':
        for feature in geojson_data.get('features', []):
            try:
                geom = shape(feature['geometry'])
                bounds = geom.bounds
                min_lon = min(min_lon, bounds[0])
                min_lat = min(min_lat, bounds[1])
                max_lon = max(max_lon, bounds[2])
                max_lat = max(max_lat, bounds[3])
            except Exception as e:
                print(f"Skipping invalid geometry in feature: {e}")
    else:
        try:
            geom = shape(geojson_data)
            min_lon, min_lat, max_lon, max_lat = geom.bounds
        except Exception as e:
            raise ValueError(f"Invalid GeoJSON geometry: {e}")

    if min_lon == float('inf') or max_lon == float('-inf'):
        raise ValueError("No valid geometries found in GeoJSON data")
    return min_lon, min_lat, max_lon, max_lat

def create_map(geojson_data, df, start_time, end_time):
    limits = get_geojson_bounds(geojson_data)
    m = folium.Map(
        zoom_start=4,
        tiles=None,
        control_scale=True,
        min_lat=limits[1], min_lon=limits[0],
        max_lat=limits[3], max_lon=limits[2],
        max_bounds=True
    )

    # folium.TileLayer(
    #     tiles='https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    #     attr='© OpenStreetMap contributors & CARTO',
    #     name="Light Map",
    #     subdomains='abcd',
    #     opacity=0.9
    # ).add_to(m)

    folium.TileLayer(
        tiles="https://{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
        attr="© Google",
        name="Satellite Hybrid Imagery",
        subdomains=["mt0", "mt1", "mt2", "mt3"],
        opacity=0.5
    ).add_to(m)

    # Neon color per reach for consistency with the time series
    def style_fn(feature):
        rid = str(feature.get('properties', {}).get('reach_id', 'na'))
        c = nice_color_for_reach(rid)
        return {"color": c, "weight": 4, "opacity": 0.95, "fill": False}

    def highlight_fn(feature):
        return {"weight": 6, "opacity": 1.0}

    gj = folium.GeoJson(
        geojson_data,
        name="Reach Features",
        style_function=style_fn,
        highlight_function=highlight_fn,
        tooltip=folium.GeoJsonTooltip(
            fields=["reach_id", "river_name"],
            aliases=["Reach ID", "River"],
            labels=True,
            sticky=True
        ),
        popup=folium.GeoJsonPopup(
            fields=["reach_id", "river_name", "continent_id", "time_str", "wse"],
            aliases=["Reach ID", "River", "Continent", "Time", "WSE"],
            localize=True,
            labels=True,
            max_width=420,
            parse_html=False,
            sticky=False,
            show=False
        )
    )
    gj.add_to(m)

    m.fit_bounds(m.get_bounds(), padding=(50, 50))

    folium.plugins.Fullscreen(
        position="topright",
        title="Fullscreen",
        title_cancel="Exit Fullscreen",
        force_separate_button=True,
    ).add_to(m)

    return m

# ----------------------------
# UI: Help / Inputs
# ----------------------------
with st.expander("$ \\large \\textrm {\\color{#F94C10} Help} $", expanded=False, icon=":material/info:"):
    st.markdown("""
    #### :gray[About the Tool]
    This tool sources data through [Hydrocron API calls](https://podaac.github.io/hydrocron/timeseries.html) and enables users to download the results as a CSV file and visualize them on a map.

    #### :gray[How to Use the Tool:]
    1. **Find River Reach IDs**: Identify the Reach ID(s) for the river segments you're interested in. You can include **one or many** (comma/space/newline separated).
       You can find Reach IDs [here](https://drive.google.com/file/d/17uH5RsyvVjM45JupjYTLNFIu2GMHvy3u/view?usp=sharing).  
       :gray[*Requires ArcGIS Pro or QGIS or similar to open those files.*]
    2. **Input Start and End Times**: Use `YYYY-MM-DDTHH:MM:SSZ`.
    3. The tool will fetch all selected reaches, compile a single table, and render all features together on the map.
    """)

with st.expander("$ \\large \\textrm {\\color{#F94C10} Inputs} $", expanded=True, icon=":material/instant_mix:"):
    # Multiple Reach IDs (comma/space/newline separated)
    reach_ids_text = st.text_area(
        ":violet[**River Reach ID(s)**]",
        "56861000151",
        help="Enter one or more Reach IDs separated by commas, spaces, or newlines."
    )

    start_time = st.text_input(":violet[**Start Time**]", "2022-07-01T00:00:00Z", help="YYYY-MM-DDTHH:MM:SSZ")
    end_time = st.text_input(":violet[**End Time**]", "2024-12-05T00:00:00Z", help="YYYY-MM-DDTHH:MM:SSZ")

    compulsory_fields = ['reach_id', 'river_name', 'continent_id', 'wse', 'time_str']
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

    selected_fields = st.multiselect(
        ":violet[**Select Fields to download**]",
        fields,
        default=['reach_id', 'time_str', 'wse', 'width', 'river_name', 'continent_id']
    )

    if not all(field in selected_fields for field in compulsory_fields):
        st.warning(f"Please select all compulsory fields: {compulsory_fields}")
    if all(field in selected_fields for field in compulsory_fields):
        st.success("All compulsory fields selected. Choose other optional fields and :blue[proceed with the download...]")
    else:
        st.stop()

# ----------------------------
# Run
# ----------------------------
if st.button("Run", icon=":material/play_circle:"):
    reach_ids = parse_reach_ids(reach_ids_text)
    if not reach_ids:
        st.warning("Please provide at least one Reach ID.")
    elif start_time and end_time and selected_fields:
        with st.spinner(" Fetching data"):
            combined_geojson, combined_df, errors = fetch_data_multi(
                reach_ids, start_time, end_time, ','.join(selected_fields)
            )

            if errors:
                with st.expander(":material/error: Some requests failed (click to expand)"):
                    for e in errors:
                        st.write(f"- {e}")

            # Show Data Table
            st.write("### Data Table", combined_df)

            # Map
            st.text("")
            st.markdown("""### Map""")
            if combined_geojson.get('features'):
                m = create_map(combined_geojson, combined_df, start_time=start_time, end_time=end_time)
                folium_static(m, width=screen_width)
            else:
                st.info("No valid geometries returned for the provided Reach ID(s).")

            # ----------------------------------------------------------
            # Time Series (WSE vs Date) — ALL reaches on ONE interactive plot
            # ----------------------------------------------------------
            st.text("")
            st.markdown("### Time Series")

            required_cols = {'reach_id', 'time_str', 'wse', 'river_name'}
            if required_cols.issubset(set(combined_df.columns)) and not combined_df.empty:
                # Clean & prepare
                ts = combined_df[['reach_id', 'river_name', 'time_str', 'wse']].copy()
                ts['reach_id'] = ts['reach_id'].astype(str)

                # numeric WSE, drop sentinel + non-finite
                ts['wse'] = pd.to_numeric(ts['wse'], errors='coerce').replace(-999999999999.0, np.nan)
                ts = ts.replace([np.inf, -np.inf], np.nan).dropna(subset=['wse'])

                # tz-aware UTC timestamps
                ts['time'] = pd.to_datetime(ts['time_str'], errors='coerce', utc=True)
                ts = ts.dropna(subset=['time']).sort_values(['reach_id', 'time'])

                if ts.empty:
                    st.info("No valid WSE time series points to plot after cleaning.")
                else:
                    # Build a Plotly figure with dark background + neon lines
                    fig = go.Figure()
                    for rid, sub in ts.groupby('reach_id', sort=False):
                        color = nice_color_for_reach(rid)

                        # Convert time → POSIX milliseconds (tz-aware safe)
                        # Convert tz-aware datetime → tz-naive → POSIX milliseconds (int)
                        epoch_ms = (
                            sub['time']
                            .dt.tz_convert('UTC')         # ensure consistent timezone
                            .dt.tz_localize(None)         # remove timezone safely (not using astype)
                            .astype('int64') // 1_000_000 # convert ns → ms
                        )
                        epoch_ms = epoch_ms.to_numpy(dtype='int64')  # ensure clean 1D array


                        customdata = np.stack([
                            sub['reach_id'].astype(str).values,
                            sub['river_name'].astype(str).values,
                            epoch_ms,
                            sub['wse'].values
                        ], axis=-1)

                        fig.add_trace(go.Scatter(
                            x=sub['time'],
                            y=sub['wse'],
                            mode='lines+markers',
                            name=f"{rid}",
                            line=dict(width=2, color=color),
                            marker=dict(size=6, line=dict(width=0), color=color),
                            hovertemplate="<b>Reach:</b> %{customdata[0]}<br>"
                                        "<b>River:</b> %{customdata[1]}<br>"
                                        "<b>Time (UTC):</b> %{x|%Y-%m-%d %H:%M:%S}<br>"
                                        "<b>WSE (m):</b> %{y:.3f}<extra></extra>",
                            customdata=customdata
                        ))


                    fig.update_layout(
                        template="plotly_dark",
                        height=420,
                        margin=dict(l=40, r=20, t=50, b=40),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                        xaxis=dict(title="Date (UTC)", showgrid=True, gridwidth=0.3),
                        yaxis=dict(title="Water Surface Elevation (m)", showgrid=True, gridwidth=0.3),
                        # paper_bgcolor="#11151a",
                        # plot_bgcolor="#11151a",
                    )

                    # Render with optional click capture
                    if PLOTLY_EVENTS_AVAILABLE:
                        st.caption("Tip: Click a point to see details below.")
                        selected_points = plotly_events(
                            fig,
                            click_event=True,
                            hover_event=False,
                            select_event=False,
                            override_height=420,
                            override_width=screen_width if screen_width else None,
                            key="wse_clicks"
                        )
                    else:
                        st.caption("Hover to inspect values.")
                        # Fallback: no click capture, just show chart
                        selected_points = None
                        st.plotly_chart(fig, use_container_width=True)

                    # If we captured a click, show details for that datapoint
                    if selected_points:
                        pt = selected_points[0]
                        # pt contains point data with customdata indices
                        cd = pt.get("customdata", [])
                        if cd and len(cd) >= 4:
                            rid, river, epoch_ms, wse_val = cd
                            # epoch_ms is numpy int; convert to pandas/py datetime
                            t_utc = pd.to_datetime(int(epoch_ms), unit="ms", utc=True)
                            st.success(
                                f"**Selected Point**  \n"
                                f"- Reach ID: `{rid}`  \n"
                                f"- River: `{river}`  \n"
                                f"- Time (UTC): `{t_utc.strftime('%Y-%m-%d %H:%M:%S')}`  \n"
                                f"- WSE (m): `{wse_val:.3f}`"
                            )

                    # Optional: download cleaned time series
                    csv_bytes = ts[['reach_id', 'river_name', 'time', 'wse']].rename(columns={'time': 'time_utc'}).to_csv(index=False).encode('utf-8')
                    st.download_button(
                        "Download cleaned WSE time series (CSV)",
                        data=csv_bytes,
                        file_name="wse_timeseries_clean_neon.csv",
                        mime="text/csv",
                        icon=":material/download:"
                    )
            else:
                st.info("Time series plotting requires 'reach_id', 'river_name', 'time_str', and 'wse' in the selected fields.")

    else:
        st.warning("Please enter all fields (Reach ID(s), Start Time, and End Time) to fetch data.")
