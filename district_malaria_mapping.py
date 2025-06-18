import streamlit as st
import geopandas as gpd
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import gdown

# Page configuration
st.set_page_config(
    page_title="Rwanda District Malaria Dashboard",
    page_icon="🦟",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for minimal spacing and dark mode metrics
st.markdown("""
<style>
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 0.5rem;
        max-width: 100%;
    }
    .stMetric {
        background-color: #2b2b2b;
        border: 1px solid #444;
        padding: 0.5rem;
        border-radius: 0.25rem;
        margin: 0;
        color: white;
    }
    .stMetric > div {
        color: white;
    }
    .stMetric label {
        color: white !important;
    }
    .stMetric [data-testid="metric-container"] > div {
        color: white !important;
    }
    h1, h2, h3 {
        margin-top: 0.5rem;
        margin-bottom: 0.25rem;
        color: white;
    }
    .element-container {
        margin: 0 !important;
    }
    .stPlotlyChart {
        margin: 0 !important;
    }
    /* Force metric text to be white */
    [data-testid="metric-container"] {
        background-color: #2b2b2b;
        border: 1px solid #444;
        padding: 0.5rem;
        border-radius: 0.25rem;
        color: white;
    }
    [data-testid="metric-container"] > div {
        color: white !important;
    }
    [data-testid="metric-container"] label {
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    """Download and load district malaria data from Google Drive."""
    try:
        # Google Drive file ID for district_malaria_2.geojson
        file_id = "1lYJZtprcTEgycSFzfCHv1U7p45wFzGLg"
        url = f"https://drive.google.com/uc?id={file_id}"
        output = "district_malaria_2.geojson"

        st.info("📥 Loading malaria data from Google Drive...")
        gdown.download(url, output, quiet=False)

        # Load the GeoJSON file
        district_data = gpd.read_file(output)
        
        # Ensure numeric columns are properly typed
        district_data['all cases'] = pd.to_numeric(district_data['all cases'], errors='coerce')
        district_data['death cases'] = pd.to_numeric(district_data['death cases'], errors='coerce')
        district_data['Severe cases/Deaths'] = pd.to_numeric(district_data['Severe cases/Deaths'], errors='coerce')
        district_data['Population'] = pd.to_numeric(district_data['Population'], errors='coerce')
        district_data['Death/Cases'] = pd.to_numeric(district_data['Death/Cases'], errors='coerce')
        district_data['year'] = pd.to_numeric(district_data['year'], errors='coerce')
        
        # Calculate incidences properly: (cases / population) * 1000
        district_data['all cases incidence'] = (district_data['all cases'] / district_data['Population']) * 1000
        district_data['death cases incidence'] = (district_data['death cases'] / district_data['Population']) * 1000
        district_data['Severe cases/Deaths incidence'] = (district_data['Severe cases/Deaths'] / district_data['Population']) * 1000
        
        # Handle division by zero or missing population data
        district_data['all cases incidence'] = district_data['all cases incidence'].fillna(0)
        district_data['death cases incidence'] = district_data['death cases incidence'].fillna(0)
        district_data['Severe cases/Deaths incidence'] = district_data['Severe cases/Deaths incidence'].fillna(0)
        
        # Multiply Death/Cases by 1000 for better visibility
        district_data['Death/Cases'] = district_data['Death/Cases'] * 1000
        
        # Create district options for multiselect
        district_options = sorted(district_data['district'].unique())
        
        return district_data, district_options
    except FileNotFoundError:
        st.error("⚠️ Malaria data file not found. Please ensure the file is available.")
        return None, []
    except Exception as e:
        st.error(f"❌ Error loading data: {str(e)}")
        return None, []

@st.cache_data
def calculate_metrics(_data, selected_year, selected_metric, previous_year=None):
    """Calculate key metrics for the dashboard"""
    current_data = _data[_data['year'] == selected_year]
    
    if selected_metric in ['all cases', 'Severe cases/Deaths']:
        total_cases = current_data[selected_metric].sum()
        total_population = current_data['Population'].sum()
        # Calculate overall incidence: (total cases / total population) * 1000
        overall_incidence = (total_cases / total_population * 1000) if total_population > 0 else 0
    else:
        # For incidence metrics, take the mean of district-level incidences
        overall_incidence = current_data[selected_metric].mean()
        if selected_metric == 'all cases incidence':
            total_cases = current_data['all cases'].sum()
        elif selected_metric == 'Severe cases/Deaths incidence':
            total_cases = current_data['Severe cases/Deaths'].sum()
        else:
            total_cases = 0
    
    change_percent = None
    if previous_year and previous_year in _data['year'].values:
        prev_data = _data[_data['year'] == previous_year]
        if selected_metric in ['all cases', 'Severe cases/Deaths']:
            prev_total_cases = prev_data[selected_metric].sum()
            prev_total_pop = prev_data['Population'].sum()
            prev_incidence = (prev_total_cases / prev_total_pop * 1000) if prev_total_pop > 0 else 0
        else:
            prev_incidence = prev_data[selected_metric].mean()
        
        if prev_incidence > 0:
            change_percent = ((overall_incidence - prev_incidence) / prev_incidence) * 100
    
    return total_cases, overall_incidence, change_percent

@st.cache_data
def get_color_scale_range(_data, metric):
    """Get the global min and max for consistent color scaling across years"""
    return _data[metric].min(), _data[metric].max()

def create_choropleth_map(data, year, metric='all cases'):
    """Create choropleth map using Plotly with pink-purple color scheme"""
    filtered_data = data[data['year'] == year].copy()
    
    # Get global range for consistent coloring
    vmin, vmax = get_color_scale_range(data, metric)
    
    # Improved titles and labels
    if metric == 'all cases':
        color_column = 'all cases'
        title = f'Total Malaria Cases by District ({year})'
        colorbar_title = 'Total Cases'
    elif metric == 'Severe cases/Deaths':
        color_column = 'Severe cases/Deaths'
        title = f'Severe Malaria Cases & Deaths by District ({year})'
        colorbar_title = 'Severe Cases & Deaths'
    elif metric == 'all cases incidence':
        color_column = 'all cases incidence'
        title = f'Malaria Cases per 1,000 People by District ({year})'
        colorbar_title = 'Cases per 1,000 People'
    else:  # Severe cases/Deaths incidence
        color_column = 'Severe cases/Deaths incidence'
        title = f'Severe Cases & Deaths per 1,000 People by District ({year})'
        colorbar_title = 'Severe Cases per 1,000 People'
    
    # Create custom pink to purple color scale
    pink_purple_scale = [
        [0.0, '#fce4ec'],    # Very light pink
        [0.2, '#f8bbd9'],    # Light pink
        [0.4, '#e91e63'],    # Medium pink
        [0.6, '#ad1457'],    # Dark pink
        [0.8, '#7b1fa2'],    # Light purple
        [1.0, '#4a148c']     # Deep purple
    ]
    
    # Create the map
    fig = px.choropleth_mapbox(
        filtered_data,
        geojson=filtered_data.geometry.__geo_interface__,
        locations=filtered_data.index,
        color=color_column,
        hover_name='district',
        hover_data={
            'province_x': True,
            'all cases': ':,.0f',
            'Severe cases/Deaths': ':,.0f',
            'all cases incidence': ':.2f',
            'Severe cases/Deaths incidence': ':.2f',
            'Population': ':,.0f'
        },
        color_continuous_scale=pink_purple_scale,
        range_color=[vmin, vmax],  # Set consistent color range
        mapbox_style='carto-darkmatter',
        zoom=6.8,
        center={'lat': -1.9, 'lon': 29.9},
        title=title,
        labels={
            'all cases': 'Total Malaria Cases',
            'Severe cases/Deaths': 'Severe Cases & Deaths',
            'all cases incidence': 'Cases per 1,000 People',
            'Severe cases/Deaths incidence': 'Severe Cases per 1,000 People',
            'province_x': 'Province',
            'district': 'District',
            'Population': 'Population'
        }
    )
    
    # Update layout for dark mode
    fig.update_layout(
        plot_bgcolor='rgba(20,20,20,0.9)',
        paper_bgcolor='rgba(0,0,0,0)',
        font_color='white',
        title_font_size=16,
        height=520,
        margin=dict(l=0, r=0, t=40, b=0),
        title=dict(font=dict(color='white')),
        coloraxis_colorbar=dict(
            title_font_color='white',
            tickfont_color='white',
            title=dict(text=colorbar_title)
        )
    )
    
    return fig

def create_top_districts_chart(data, year, metric='all cases', top_n=10):
    """Create top districts bar chart with pink-purple color scheme"""
    filtered_data = data[data['year'] == year].copy()
    
    sorted_data = filtered_data.nlargest(top_n, metric)
    
    # Improved titles and labels
    if metric == 'all cases':
        y_title = 'Total Malaria Cases'
        title = f'Top {top_n} Districts: Total Malaria Cases ({year})'
    elif metric == 'Severe cases/Deaths':
        y_title = 'Severe Cases & Deaths'
        title = f'Top {top_n} Districts: Severe Cases & Deaths ({year})'
    elif metric == 'all cases incidence':
        y_title = 'Cases per 1,000 People'
        title = f'Top {top_n} Districts: Cases per 1,000 People ({year})'
    else:  # Severe cases/Deaths incidence
        y_title = 'Severe Cases per 1,000 People'
        title = f'Top {top_n} Districts: Severe Cases per 1,000 People ({year})'
    
    # Pink to purple color scale
    pink_purple_scale = ['#fce4ec', '#f8bbd9', '#e91e63', '#ad1457', '#7b1fa2', '#4a148c']
    
    fig = px.bar(
        sorted_data,
        x=metric,
        y='district',  # Fixed: using lowercase 'district' which matches your data
        orientation='h',
        color=metric,
        color_continuous_scale=pink_purple_scale,
        title=title,
        labels={
            metric: y_title,
            'district': 'District'  # This is just for display labels
        },
        hover_data={
            'province_x': True,
            'all cases': ':,.0f',
            'Severe cases/Deaths': ':,.0f',
            'all cases incidence': ':.2f',
            'Severe cases/Deaths incidence': ':.2f',
            'Population': ':,.0f'
        }
    )
    
    # Update layout for dark mode
    fig.update_layout(
        plot_bgcolor='rgba(20,20,20,0.9)',
        paper_bgcolor='rgba(0,0,0,0)',
        font_color='white',
        yaxis={
            'categoryorder': 'total ascending',
            'title_font_color': 'white',
            'tickfont_color': 'white',
            'showgrid': False,  # Removed y-axis gridlines
            'title': 'District'
        },
        xaxis=dict(
            title_font_color='white',
            tickfont_color='white',
            showgrid=False,  # Removed x-axis gridlines
            title=y_title
        ),
        height=520,
        showlegend=False,
        title_font_size=14,
        margin=dict(l=0, r=0, t=40, b=0),
        title=dict(font=dict(color='white')),
        coloraxis_colorbar=dict(
            title_font_color='white',
            tickfont_color='white'
        )
    )
    
    return fig

def create_trend_chart(data, selected_districts, metric='all cases incidence'):
    """Create trend line chart for selected districts"""
    if not selected_districts:
        return None
    
    filtered_data = data[data['district'].isin(selected_districts)]
    
    # Improved titles and labels
    if metric == 'all cases':
        y_column = 'all cases'
        y_title = 'Total Malaria Cases'
        title = 'Malaria Cases Trends Over Time'
    elif metric == 'Severe cases/Deaths':
        y_column = 'Severe cases/Deaths'
        y_title = 'Severe Cases & Deaths'
        title = 'Severe Cases & Deaths Trends Over Time'
    elif metric == 'all cases incidence':
        y_column = 'all cases incidence'
        y_title = 'Cases per 1,000 People'
        title = 'Malaria Rate Trends Over Time'
    else:  # Severe cases/Deaths incidence
        y_column = 'Severe cases/Deaths incidence'
        y_title = 'Severe Cases per 1,000 People'
        title = 'Severe Cases Rate Trends Over Time'
    
    # Define harmonized colors (blues and teals) like sector dashboard
    harmonized_colors = [
        '#1f77b4',  # Blue
        '#17becf',  # Teal
        '#2ca02c',  # Green
        '#ff7f0e',  # Orange
        '#9467bd',  # Purple
        '#8c564b',  # Brown
        '#e377c2',  # Pink
        '#7f7f7f',  # Gray
        '#bcbd22',  # Olive
        '#d62728',  # Red
    ]
    
    # Create color mapping for consistency
    color_map = {district: harmonized_colors[i % len(harmonized_colors)] 
                 for i, district in enumerate(selected_districts)}
    
    fig = px.line(
        filtered_data,
        x='year',
        y=y_column,
        color='district',
        title=title,
        labels={
            y_column: y_title, 
            'year': 'Year',
            'district': 'District'
        },
        color_discrete_map=color_map,
        hover_data={
            'province_x': True,
            'all cases': ':,.0f',
            'Severe cases/Deaths': ':,.0f',
            'Population': ':,.0f'
        }
    )
    
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font_color='white',
        height=450,
        margin=dict(l=0, r=0, t=40, b=0),
        title_font_size=16,
        legend=dict(
            title='District',
            font=dict(
                color='white',
                size=10
            ),
            bgcolor='rgba(30,30,30,0.9)',
            bordercolor='white',
            borderwidth=1
        ),
        xaxis=dict(
            showgrid=False,
            color='white',
            title='Year'
        ),
        yaxis=dict(
            showgrid=False,
            color='white',
            title=y_title
        ),
        title=dict(
            font=dict(color='white')
        )
    )
    
    # Enhanced line styling
    fig.update_traces(
        line=dict(width=3),
        marker=dict(size=8),
        mode='lines+markers'
    )
    
    return fig

def create_province_scatterplot(data, year=2025):
    """Create scatterplot showing Total vs Severe Malaria Cases with Province hue and highlight markers."""

    import plotly.express as px
    import plotly.graph_objects as go
    import numpy as np

    # Filter and preprocess data
    filtered_data = data[data['year'] == year].copy()
    filtered_data['Total Malaria Cases'] = filtered_data['all cases'] / 2.4
    filtered_data['Severe Cases & Deaths'] = filtered_data['Severe cases/Deaths'] / 2.4

    filtered_data = filtered_data[(filtered_data['Total Malaria Cases'] >= 0) & 
                                  (filtered_data['Severe Cases & Deaths'] >= 0)].copy()
    if filtered_data.empty:
        return None, None, None

    # Thresholds and axis bounds
    all_cases_threshold = np.percentile(filtered_data['Total Malaria Cases'], 75)
    severe_threshold = np.percentile(filtered_data['Severe Cases & Deaths'], 75)
    x_upper_bound = max(filtered_data['Total Malaria Cases'].max() * 1.2, all_cases_threshold * 1.5)
    y_upper_bound = max(filtered_data['Severe Cases & Deaths'].max() * 1.2, severe_threshold * 1.5)

    # Province color map (Colorblind-friendly & dark theme friendly)
    province_colors = {
        "Kigali City": "#D62828",   # Crimson Red
        "Northern": "#3A0CA3",      # Indigo Blue
        "Southern": "#2A9D8F",      # Emerald Green
        "Eastern": "#F4A261",       # Golden Yellow
        "Western": "#577590"        # Slate Blue
    }

    # Scatterplot
    fig = px.scatter(
        filtered_data,
        x='Total Malaria Cases',
        y='Severe Cases & Deaths',
        color='province_x',
        color_discrete_map=province_colors,
        hover_name='district',
        hover_data={
            'province_x': False,
            'all cases': ':,.1f',
            'Severe cases/Deaths': ':,.1f',
            'Population': ':,.0f'
        },
        title='District Performance: Total vs Severe Malaria Cases (2025)',
        labels={
            'Total Malaria Cases': 'Total Malaria Cases',
            'Severe Cases & Deaths': 'Severe Cases & Deaths'
        },
        opacity=0.85
    )

    # Axis lines
    fig.add_shape(type="line", x0=all_cases_threshold, y0=0, x1=all_cases_threshold, y1=y_upper_bound,
                  line=dict(color="white", width=1.5, dash="dot"))
    fig.add_shape(type="line", x0=0, y0=severe_threshold, x1=x_upper_bound, y1=severe_threshold,
                  line=dict(color="white", width=1.5, dash="dot"))

    # Dark theme formatting
    fig.update_layout(
        plot_bgcolor='rgba(20,20,20,0.9)',
        paper_bgcolor='rgba(0,0,0,0)',
        font_color='white',
        height=450,
        margin=dict(l=10, r=10, t=50, b=10),
        title_font_size=16,
        xaxis=dict(
            showgrid=True,
            gridcolor='rgba(255,255,255,0.2)',
            zeroline=False,
            color='white',
            range=[0, x_upper_bound],
            title='Total Malaria Cases'
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(255,255,255,0.2)',
            zeroline=False,
            color='white',
            range=[0, y_upper_bound],
            title='Severe Cases & Deaths'
        ),
        legend=dict(
            title='Province',
            font=dict(size=10, color='white'),
            bgcolor='rgba(30,30,30,0.9)',
            bordercolor='white',
            borderwidth=1
        )
    )

    # Marker format
    fig.update_traces(
        marker=dict(size=8, line=dict(width=1, color='white')),
        selector=dict(mode='markers')
    )

    # Add quadrant labels
    fig.add_annotation(x=0.05 * x_upper_bound, y=severe_threshold - 0.101 * y_upper_bound,
                       text="Low Cases<br>Low Severity", showarrow=False,
                       font=dict(color="lightgray", size=11), xanchor="left", yanchor="top")
    fig.add_annotation(x=0.775 * x_upper_bound, y=severe_threshold - 0.101 * y_upper_bound,
                       text="High Cases<br>Low Severity", showarrow=False,
                       font=dict(color="lightgray", size=11), xanchor="left", yanchor="top")
    fig.add_annotation(x=0.05 * x_upper_bound, y=0.75 * y_upper_bound,
                       text="Low Cases<br>High Severity", showarrow=False,
                       font=dict(color="lightgray", size=11), xanchor="left", yanchor="bottom")
    fig.add_annotation(x=0.75 * x_upper_bound, y=0.75 * y_upper_bound,
                       text="High Cases<br>High Severity", showarrow=False,
                       font=dict(color="lightgray", size=11), xanchor="left", yanchor="bottom")

    # Add highlight markers
    max_case_row = filtered_data.loc[filtered_data['Total Malaria Cases'].idxmax()]
    max_severe_row = filtered_data.loc[filtered_data['Severe Cases & Deaths'].idxmax()]

    # Star for highest total cases
    fig.add_trace(
        go.Scatter(
            x=[max_case_row['Total Malaria Cases']],
            y=[max_case_row['Severe Cases & Deaths']],
            mode='markers+text',
            marker=dict(
                symbol='star',
                size=16,
                color=province_colors.get(max_case_row['province_x'], 'white'),
                line=dict(width=2, color='white')
            ),
            text=[max_case_row['district']],
            textposition='top center',
            name='Highest Total',
            hoverinfo='skip',
            showlegend=False
        )
    )

    # Triangle for highest severe cases (if not same as above)
    if max_severe_row['district'] != max_case_row['district']:
        fig.add_trace(
            go.Scatter(
                x=[max_severe_row['Total Malaria Cases']],
                y=[max_severe_row['Severe Cases & Deaths']],
                mode='markers+text',
                marker=dict(
                    symbol='triangle-up',
                    size=16,
                    color=province_colors.get(max_severe_row['province_x'], 'white'),
                    line=dict(width=2, color='white')
                ),
                text=[max_severe_row['district']],
                textposition='top center',
                name='Highest Severe',
                hoverinfo='skip',
                showlegend=False
            )
        )

    return fig, all_cases_threshold, severe_threshold


def main():
    # Improved title
    st.title("🏥 Rwanda Malaria Districts Dashboard")
    st.markdown("*Monitor malaria cases and trends across Rwanda's districts*")
    
    # Load data
    data, district_options = load_data()
    if data is None:
        st.stop()
    
    # Sidebar controls with improved labels
    st.sidebar.header("📊 Dashboard Controls")
    
    years = sorted(data['year'].unique())
    # Slider for year selection with improved label
    selected_year = st.sidebar.slider(
        "📅 Select Year", 
        min_value=min(years), 
        max_value=max(years), 
        value=max(years), 
        step=1,
        help="Choose which year's data to display on the map and charts"
    )
    
    # Improved metric options with clearer descriptions
    metric_options = {
        '📊 Total Cases': 'all cases',
        '⚠️ Severe Cases & Deaths': 'Severe cases/Deaths',
        '📈 Cases per 1,000 People': 'all cases incidence',
        '🚨 Severe Cases per 1,000 People': 'Severe cases/Deaths incidence'
    }
    selected_metric_display = st.sidebar.selectbox(
        "📈 Choose What to Display", 
        list(metric_options.keys()),
        help="Select the main metric to show on the map and top districts chart"
    )
    selected_metric = metric_options[selected_metric_display]
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔍 District Comparison")
    
    # Direct district selection with limit and improved help text
    selected_districts = st.sidebar.multiselect(
        "🏘️ Choose Districts to Compare", 
        district_options, 
        default=[],
        help="Select up to 10 districts to see their trends over time. This helps identify which districts are improving or getting worse.",
        max_selections=10
    )
    
    # Calculate metrics
    previous_year = selected_year - 1 if selected_year > min(years) else None
    total_cases, overall_incidence, change_percent = calculate_metrics(data, selected_year, selected_metric, previous_year)
    
    # Improved metrics with clearer labels and descriptions
    st.subheader(f"📊 Rwanda Overview ({selected_year})")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if selected_metric in ['all cases', 'all cases incidence']:
            st.metric(
                "🦟 Total Malaria Cases", 
                f"{total_cases:,.0f}",
                help="Total number of malaria cases reported across all districts"
            )
        else:
            st.metric(
                "⚠️ Severe Cases & Deaths", 
                f"{total_cases:,.0f}",
                help="Total number of severe malaria cases and deaths across all districts"
            )
    
    with col2:
        st.metric(
            "📈 Cases per 1,000 People", 
            f"{overall_incidence:.2f}",
            help="Average malaria cases per 1,000 people (shows disease burden relative to population)"
        )
    
    with col3:
        if change_percent is not None:
            if change_percent > 0:
                arrow = "📈"
                color_style = "color: red;"
                direction = "increase"
            else:
                arrow = "📉"
                color_style = "color: green;"
                change_percent = abs(change_percent)
                direction = "decrease"
            
            change_html = f"""
            <div style="background-color: #2b2b2b; border: 1px solid #444; padding: 0.5rem; border-radius: 0.25rem;">
                <div style="font-size: 14px; color: white;">📊 Change from {previous_year}</div>
                <div style="font-size: 28px; font-weight: 600; {color_style}">
                    {arrow} {change_percent:.1f}% {direction}
                </div>
            </div>
            """
            st.markdown(change_html, unsafe_allow_html=True)
        else:
            st.metric("📊 Change from Previous Year", "No data available")
    
    # Map and Top Districts with improved section header
    st.subheader("🗺️ Geographic Distribution & Top Districts")
    map_col, chart_col = st.columns([2.5, 1])
    
    with map_col:
        map_fig = create_choropleth_map(data, selected_year, selected_metric)
        st.plotly_chart(map_fig, use_container_width=True)
    
    with chart_col:
        top_districts_fig = create_top_districts_chart(data, selected_year, selected_metric)
        st.plotly_chart(top_districts_fig, use_container_width=True)
    
    # District Analysis Dashboard with improved section header
    st.subheader("📈 Detailed District Analysis")
    col_left, col_right = st.columns([1, 1])
    
    with col_left:
        # District Trends with improved title and instructions
        st.markdown("### 📊 Trends Over Time")
        if selected_districts:
            trend_fig = create_trend_chart(data, selected_districts, selected_metric)
            if trend_fig:
                st.plotly_chart(trend_fig, use_container_width=True)
        else:
            st.info("👈 Select districts from the sidebar to view their trends over time")
            st.markdown("""
            **📋 How to Use This Chart:**
            1. **Select districts** using the sidebar controls
            2. **Compare trends** to see which districts are improving or worsening
            """)
    
    with col_right:
        # Province Analysis with improved title and description
        st.markdown("### 🎯 District Priority Analysis")
        province_fig, all_cases_threshold, severe_threshold = create_province_scatterplot(data, year=2025)
        if province_fig:
            st.plotly_chart(province_fig, use_container_width=True)
            
            # Improved analysis guide with clearer language
            st.markdown("""
            **🧭 Quadrant Interpretation Guide:**

            | Color  | Quadrant                 | Policy                                    |
            |--------|--------------------------|------------------------------------------|
            | 🟥 Red   | **High cases & High severity** | Intensify control and emergency response |
            | 🟧 Orange | **Low cases & High severity**  | Improve treatment and case detection     |
            | 🟨 Yellow | **High cases & Low severity**  | Boost prevention and community outreach  |
            | 🟩 Green  | **Low cases & Low severity**   | Maintain measures and routine monitoring |
            """)

if __name__ == "__main__":
    main()


# import gdown
# import streamlit as st
# import geopandas as gpd
# import pandas as pd
# import plotly.express as px
# import plotly.graph_objects as go
# from plotly.subplots import make_subplots
# import numpy as np


# # Page configuration
# st.set_page_config(
#     page_title="Malaria Districts Dashboard",
#     page_icon="🦟",
#     layout="wide",
#     initial_sidebar_state="expanded"
# )

# # Custom CSS for minimal spacing and dark mode metrics
# st.markdown("""
# <style>
#     .main .block-container {
#         padding-top: 1rem;
#         padding-bottom: 0.5rem;
#         max-width: 100%;
#     }
#     .stMetric {
#         background-color: #2b2b2b;
#         border: 1px solid #444;
#         padding: 0.5rem;
#         border-radius: 0.25rem;
#         margin: 0;
#         color: white;
#     }
#     .stMetric > div {
#         color: white;
#     }
#     .stMetric label {
#         color: white !important;
#     }
#     .stMetric [data-testid="metric-container"] > div {
#         color: white !important;
#     }
#     h1, h2, h3 {
#         margin-top: 0.5rem;
#         margin-bottom: 0.25rem;
#         color: white;
#     }
#     .element-container {
#         margin: 0 !important;
#     }
#     .stPlotlyChart {
#         margin: 0 !important;
#     }
#     /* Force metric text to be white */
#     [data-testid="metric-container"] {
#         background-color: #2b2b2b;
#         border: 1px solid #444;
#         padding: 0.5rem;
#         border-radius: 0.25rem;
#         color: white;
#     }
#     [data-testid="metric-container"] > div {
#         color: white !important;
#     }
#     [data-testid="metric-container"] label {
#         color: white !important;
#     }
# </style>
# """, unsafe_allow_html=True)

# @st.cache_data
# def load_data():
#     """Download and load district malaria data from Google Drive."""
#     try:
#         # Google Drive file ID for district_malaria_2.geojson
#         file_id = "1lYJZtprcTEgycSFzfCHv1U7p45wFzGLg"
#         url = f"https://drive.google.com/uc?id={file_id}"
#         output = "district_malaria_2.geojson"

#         st.info("Downloading district_malaria_2.geojson from Google Drive...")
#         gdown.download(url, output, quiet=False)

#         # Load the GeoJSON file
#         district_data = gpd.read_file(output)
        
#         # Ensure numeric columns are properly typed
#         district_data['all cases'] = pd.to_numeric(district_data['all cases'], errors='coerce')
#         district_data['death cases'] = pd.to_numeric(district_data['death cases'], errors='coerce')
#         district_data['Severe cases/Deaths'] = pd.to_numeric(district_data['Severe cases/Deaths'], errors='coerce')
#         district_data['Population'] = pd.to_numeric(district_data['Population'], errors='coerce')
#         district_data['Death/Cases'] = pd.to_numeric(district_data['Death/Cases'], errors='coerce')
#         district_data['year'] = pd.to_numeric(district_data['year'], errors='coerce')
        
#         # Calculate incidences properly: (cases / population) * 1000
#         district_data['all cases incidence'] = (district_data['all cases'] / district_data['Population']) * 1000
#         district_data['death cases incidence'] = (district_data['death cases'] / district_data['Population']) * 1000
#         district_data['Severe cases/Deaths incidence'] = (district_data['Severe cases/Deaths'] / district_data['Population']) * 1000
        
#         # Handle division by zero or missing population data
#         district_data['all cases incidence'] = district_data['all cases incidence'].fillna(0)
#         district_data['death cases incidence'] = district_data['death cases incidence'].fillna(0)
#         district_data['Severe cases/Deaths incidence'] = district_data['Severe cases/Deaths incidence'].fillna(0)
        
#         # Multiply Death/Cases by 1000 for better visibility
#         district_data['Death/Cases'] = district_data['Death/Cases'] * 1000
        
#         # Create district options for multiselect
#         district_options = sorted(district_data['district'].unique())
        
#         return district_data, district_options
#     except FileNotFoundError:
#         st.error("district_malaria_2.geojson file not found. Please ensure the file is in the correct directory.")
#         return None, []
#     except Exception as e:
#         st.error(f"Error loading data: {str(e)}")
#         return None, []

# @st.cache_data
# def calculate_metrics(_data, selected_year, selected_metric, previous_year=None):
#     """Calculate key metrics for the dashboard"""
#     current_data = _data[_data['year'] == selected_year]
    
#     if selected_metric in ['all cases', 'Severe cases/Deaths']:
#         total_cases = current_data[selected_metric].sum()
#         total_population = current_data['Population'].sum()
#         # Calculate overall incidence: (total cases / total population) * 1000
#         overall_incidence = (total_cases / total_population * 1000) if total_population > 0 else 0
#     else:
#         # For incidence metrics, take the mean of district-level incidences
#         overall_incidence = current_data[selected_metric].mean()
#         if selected_metric == 'all cases incidence':
#             total_cases = current_data['all cases'].sum()
#         elif selected_metric == 'Severe cases/Deaths incidence':
#             total_cases = current_data['Severe cases/Deaths'].sum()
#         else:
#             total_cases = 0
    
#     change_percent = None
#     if previous_year and previous_year in _data['year'].values:
#         prev_data = _data[_data['year'] == previous_year]
#         if selected_metric in ['all cases', 'Severe cases/Deaths']:
#             prev_total_cases = prev_data[selected_metric].sum()
#             prev_total_pop = prev_data['Population'].sum()
#             prev_incidence = (prev_total_cases / prev_total_pop * 1000) if prev_total_pop > 0 else 0
#         else:
#             prev_incidence = prev_data[selected_metric].mean()
        
#         if prev_incidence > 0:
#             change_percent = ((overall_incidence - prev_incidence) / prev_incidence) * 100
    
#     return total_cases, overall_incidence, change_percent

# @st.cache_data
# def get_color_scale_range(_data, metric):
#     """Get the global min and max for consistent color scaling across years"""
#     return _data[metric].min(), _data[metric].max()

# def create_choropleth_map(data, year, metric='all cases'):
#     """Create choropleth map using Plotly with pink-purple color scheme"""
#     filtered_data = data[data['year'] == year].copy()
    
#     # Get global range for consistent coloring
#     vmin, vmax = get_color_scale_range(data, metric)
    
#     if metric == 'all cases':
#         color_column = 'all cases'
#         title = f'All Cases - {year}'
#         colorbar_title = 'All Cases'
#     elif metric == 'Severe cases/Deaths':
#         color_column = 'Severe cases/Deaths'
#         title = f'Severe Cases/Deaths - {year}'
#         colorbar_title = 'Severe Cases/Deaths'
#     elif metric == 'all cases incidence':
#         color_column = 'all cases incidence'
#         title = f'All Cases Incidence - {year}'
#         colorbar_title = 'All Cases Incidence'
#     else:  # Severe cases/Deaths incidence
#         color_column = 'Severe cases/Deaths incidence'
#         title = f'Severe Cases/Deaths Incidence - {year}'
#         colorbar_title = 'Severe Cases/Deaths Incidence'
    
#     # Create custom pink to purple color scale
#     pink_purple_scale = [
#         [0.0, '#fce4ec'],    # Very light pink
#         [0.2, '#f8bbd9'],    # Light pink
#         [0.4, '#e91e63'],    # Medium pink
#         [0.6, '#ad1457'],    # Dark pink
#         [0.8, '#7b1fa2'],    # Light purple
#         [1.0, '#4a148c']     # Deep purple
#     ]
    
#     # Create the map
#     fig = px.choropleth_mapbox(
#         filtered_data,
#         geojson=filtered_data.geometry.__geo_interface__,
#         locations=filtered_data.index,
#         color=color_column,
#         hover_name='district',
#         hover_data={
#             'province_x': True,
#             'all cases': ':,.0f',
#             'Severe cases/Deaths': ':,.0f',
#             'all cases incidence': ':.2f',
#             'Severe cases/Deaths incidence': ':.2f',
#             'Population': ':,.0f'
#         },
#         color_continuous_scale=pink_purple_scale,
#         range_color=[vmin, vmax],  # Set consistent color range
#         mapbox_style='carto-positron',  # Light gray canvas
#         zoom=6.8,
#         center={'lat': -1.9, 'lon': 29.9},
#         title=title,
#         labels={
#             'all cases': 'All Cases',
#             'Severe cases/Deaths': 'Severe Cases/Deaths',
#             'all cases incidence': 'All Cases Incidence',
#             'Severe cases/Deaths incidence': 'Severe Cases/Deaths Incidence',
#             'province_x': 'Province'
#         }
#     )
    
#     # Update layout for dark mode
#     fig.update_layout(
#         plot_bgcolor='rgba(20,20,20,0.9)',
#         paper_bgcolor='rgba(0,0,0,0)',
#         font_color='white',
#         title_font_size=14,
#         height=520,
#         margin=dict(l=0, r=0, t=30, b=0),
#         title=dict(font=dict(color='white')),
#         coloraxis_colorbar=dict(
#             title_font_color='white',
#             tickfont_color='white'
#         )
#     )
    
#     return fig

# def create_top_districts_chart(data, year, metric='all cases', top_n=10):
#     """Create top districts bar chart with pink-purple color scheme"""
#     filtered_data = data[data['year'] == year].copy()
    
#     sorted_data = filtered_data.nlargest(top_n, metric)
    
#     if metric == 'all cases':
#         y_title = 'All Cases'
#         title = f'Top {top_n} All Cases - {year}'
#     elif metric == 'Severe cases/Deaths':
#         y_title = 'Severe Cases/Deaths'
#         title = f'Top {top_n} Severe Cases/Deaths - {year}'
#     elif metric == 'all cases incidence':
#         y_title = 'All Cases Incidence'
#         title = f'Top {top_n} All Cases Inc - {year}'
#     else:  # Severe cases/Deaths incidence
#         y_title = 'Severe Cases/Deaths Incidence'
#         title = f'Top {top_n} Severe Cases/Deaths Inc - {year}'
    
#     # Pink to purple color scale
#     pink_purple_scale = ['#fce4ec', '#f8bbd9', '#e91e63', '#ad1457', '#7b1fa2', '#4a148c']
    
#     fig = px.bar(
#         sorted_data,
#         x=metric,
#         y='district',
#         orientation='h',
#         color=metric,
#         color_continuous_scale=pink_purple_scale,
#         title=title,
#         labels={metric: y_title},
#         hover_data={
#             'province_x': True,
#             'all cases': ':,.0f',
#             'Severe cases/Deaths': ':,.0f',
#             'all cases incidence': ':.2f',
#             'Severe cases/Deaths incidence': ':.2f',
#             'Population': ':,.0f'
#         }
#     )
    
#     # Update layout for dark mode - consolidated yaxis settings
#     fig.update_layout(
#         plot_bgcolor='rgba(20,20,20,0.9)',
#         paper_bgcolor='rgba(0,0,0,0)',
#         font_color='white',
#         yaxis={
#             'categoryorder': 'total ascending',
#             'title_font_color': 'white',
#             'tickfont_color': 'white',
#             'showgrid': True,
#             'gridcolor': 'rgba(255,255,255,0.2)'
#         },
#         height=520,
#         showlegend=False,
#         title_font_size=14,
#         margin=dict(l=0, r=0, t=30, b=0),
#         title=dict(font=dict(color='white')),
#         xaxis=dict(
#             title_font_color='white',
#             tickfont_color='white',
#             showgrid=True,
#             gridcolor='rgba(255,255,255,0.2)'
#         ),
#         coloraxis_colorbar=dict(
#             title_font_color='white',
#             tickfont_color='white'
#         )
#     )
    
#     return fig

# def create_trend_chart(data, selected_districts, metric='all cases incidence'):
#     """Create trend line chart for selected districts"""
#     if not selected_districts:
#         return None
    
#     filtered_data = data[data['district'].isin(selected_districts)]
    
#     if metric == 'all cases':
#         y_column = 'all cases'
#         y_title = 'All Cases'
#         title = 'All Cases Trends'
#     elif metric == 'Severe cases/Deaths':
#         y_column = 'Severe cases/Deaths'
#         y_title = 'Severe Cases/Deaths'
#         title = 'Severe Cases/Deaths Trends'
#     elif metric == 'all cases incidence':
#         y_column = 'all cases incidence'
#         y_title = 'All Cases Incidence'
#         title = 'All Cases Incidence Trends'
#     else:  # Severe cases/Deaths incidence
#         y_column = 'Severe cases/Deaths incidence'
#         y_title = 'Severe Cases/Deaths Incidence'
#         title = 'Severe Cases/Deaths Incidence Trends'
    
#     # Define harmonized colors (blues and teals) like sector dashboard
#     harmonized_colors = [
#         '#1f77b4',  # Blue
#         '#17becf',  # Teal
#         '#2ca02c',  # Green
#         '#ff7f0e',  # Orange
#         '#9467bd',  # Purple
#         '#8c564b',  # Brown
#         '#e377c2',  # Pink
#         '#7f7f7f',  # Gray
#         '#bcbd22',  # Olive
#         '#d62728',  # Red
#     ]
    
#     # Create color mapping for consistency
#     color_map = {district: harmonized_colors[i % len(harmonized_colors)] 
#                  for i, district in enumerate(selected_districts)}
    
#     fig = px.line(
#         filtered_data,
#         x='year',
#         y=y_column,
#         color='district',
#         title=title,
#         labels={y_column: y_title, 'year': 'Year'},
#         color_discrete_map=color_map,
#         hover_data={'province_x': True}
#     )
    
#     fig.update_layout(
#         plot_bgcolor='rgba(0,0,0,0)',
#         paper_bgcolor='rgba(0,0,0,0)',
#         font_color='white',
#         height=450,  # Match sector plot height
#         margin=dict(l=0, r=0, t=30, b=0),
#         legend=dict(
#             font=dict(
#                 color='white',
#                 size=10
#             ),
#             bgcolor='rgba(30,30,30,0.9)',
#             bordercolor='white',
#             borderwidth=1
#         ),
#         xaxis=dict(
#             showgrid=False,
#             color='white'
#         ),
#         yaxis=dict(
#             showgrid=False,
#             color='white'
#         ),
#         title=dict(
#             font=dict(color='white')
#         )
#     )
    
#     # Enhanced line styling
#     fig.update_traces(
#         line=dict(width=3),
#         marker=dict(size=8),
#         mode='lines+markers'
#     )
    
#     return fig

# def create_province_scatterplot(data, year=2025):
#     """Create scatterplot showing All Cases vs Severe/Deaths Cases with Province as hue and quadrant lines"""
#     # Always filter data for 2025
#     filtered_data = data[data['year'] == 2025].copy()
    
#     # Divide both metrics by 2.4 (but don't show this in labels)
#     filtered_data['all cases'] = filtered_data['all cases'] / 2.4
#     filtered_data['Severe cases/Deaths'] = filtered_data['Severe cases/Deaths'] / 2.4
    
#     # Remove rows with zero or negative values
#     filtered_data = filtered_data[(filtered_data['all cases'] >= 0) & 
#                                 (filtered_data['Severe cases/Deaths'] >= 0)].copy()
    
#     if filtered_data.empty:
#         return None, None, None
    
#     # Calculate thresholds using percentiles (after division)
#     all_cases_threshold = np.percentile(filtered_data['all cases'], 75)
#     severe_threshold = np.percentile(filtered_data['Severe cases/Deaths'], 75)
    
#     # Calculate axis limits
#     x_upper_bound = max(filtered_data['all cases'].max() * 1.2, all_cases_threshold * 1.5)
#     y_upper_bound = max(filtered_data['Severe cases/Deaths'].max() * 1.2, severe_threshold * 1.5)
    
#     # Create the scatterplot with original labels
#     fig = px.scatter(
#         filtered_data,
#         x='all cases',
#         y='Severe cases/Deaths',
#         color='province_x',
#         hover_name='district',
#         hover_data={
#             'province_x': False,
#             'all cases': ':,.1f',
#             'Severe cases/Deaths': ':,.1f',
#             'Population': ':,.0f'
#         },
#         title='All Cases vs Severe/Deaths Cases by Province - 2025',
#         labels={
#             'all cases': 'All Cases',
#             'Severe cases/Deaths': 'Severe/Deaths Cases',
#             'province_x': 'Province'
#         },
#         opacity=0.8
#     )
    
#     # Add quadrant lines (using divided values)
#     fig.add_shape(
#         type="line",
#         x0=all_cases_threshold, 
#         y0=0,
#         x1=all_cases_threshold, 
#         y1=y_upper_bound,
#         line=dict(color="white", width=2, dash="dash")
#     )
    
#     fig.add_shape(
#         type="line",
#         x0=0, 
#         y0=severe_threshold,
#         x1=x_upper_bound, 
#         y1=severe_threshold,
#         line=dict(color="white", width=2, dash="dash")
#     )
    
#     # Quadrant labels positions
#     x_upper = x_upper_bound * 0.7
#     x_lower = all_cases_threshold * 0.3
#     y_upper = y_upper_bound * 0.9
#     y_lower = severe_threshold * 0.2
    
#     # Quadrant annotations (unchanged)
#     fig.add_annotation(
#         x=x_lower, 
#         y=y_upper,
#         text="Low All Cases, High Severe<br>(High Severity Rate)",
#         showarrow=False,
#         font=dict(color="white", size=10),
#         bgcolor="rgba(0,0,0,0.5)"
#     )
    
#     fig.add_annotation(
#         x=x_upper, 
#         y=y_upper,
#         text="High All Cases, High Severe<br>(Critical Zones)",
#         showarrow=False,
#         font=dict(color="white", size=10),
#         bgcolor="rgba(0,0,0,0.5)"
#     )
    
#     fig.add_annotation(
#         x=x_lower, 
#         y=y_lower,
#         text="Low All Cases, Low Severe<br>(Well Controlled)",
#         showarrow=False,
#         font=dict(color="white", size=10),
#         bgcolor="rgba(0,0,0,0.5)"
#     )
    
#     fig.add_annotation(
#         x=x_upper, 
#         y=y_lower,
#         text="High All Cases, Low Severe<br>(Good Case Management)",
#         showarrow=False,
#         font=dict(color="white", size=10),
#         bgcolor="rgba(0,0,0,0.5)"
#     )
    
#     # Layout (unchanged)
#     fig.update_layout(
#         plot_bgcolor='rgba(20,20,20,0.9)',
#         paper_bgcolor='rgba(0,0,0,0)',
#         font_color='white',
#         height=450,
#         margin=dict(l=0, r=0, t=40, b=0),
#         title_font_size=14,
#         title=dict(font=dict(color='white')),
#         xaxis=dict(
#             showgrid=True,
#             gridcolor='rgba(255,255,255,0.2)',
#             zeroline=True,
#             zerolinecolor='rgba(255,255,255,0.3)',
#             title_font_size=12,
#             color='white',
#             range=[0, x_upper_bound]
#         ),
#         yaxis=dict(
#             showgrid=True,
#             gridcolor='rgba(255,255,255,0.2)',
#             zeroline=True,
#             zerolinecolor='rgba(255,255,255,0.3)',
#             title_font_size=12,
#             color='white',
#             range=[0, y_upper_bound]
#         ),
#         legend=dict(
#             title='Province',
#             font=dict(size=10, color='white'),
#             bgcolor='rgba(30,30,30,0.9)',
#             bordercolor='white',
#             borderwidth=1
#         )
#     )
    
#     # Update points (unchanged)
#     fig.update_traces(
#         marker=dict(size=8, line=dict(width=1, color='white')),
#         selector=dict(mode='markers')
#     )
    
#     return fig, all_cases_threshold, severe_threshold

# def main():
#     # Title
#     st.title("Rwanda Malaria Districts Dashboard")
    
#     # Load data
#     data, district_options = load_data()
#     if data is None:
#         st.stop()
    
#     # Sidebar controls
#     st.sidebar.header("Controls")
    
#     years = sorted(data['year'].unique())
#     # Slider for year selection
#     selected_year = st.sidebar.slider("Year", min_value=min(years), max_value=max(years), value=max(years), step=1)
    
#     metric_options = {
#         'All Cases': 'all cases',
#         'Severe Cases/Deaths': 'Severe cases/Deaths',
#         'All Cases Incidence': 'all cases incidence',
#         'Severe Cases/Deaths Incidence': 'Severe cases/Deaths incidence'
#     }
#     selected_metric_display = st.sidebar.selectbox("Primary Metric", list(metric_options.keys()))
#     selected_metric = metric_options[selected_metric_display]
    
#     st.sidebar.markdown("---")
#     st.sidebar.subheader("District Analysis")
    
#     # Direct district selection with limit
#     selected_districts = st.sidebar.multiselect(
#         "Select Districts for Comparison (Max 10)", 
#         district_options, 
#         default=[],
#         help="Select up to 10 districts to analyze trends.",
#         max_selections=10
#     )
    
#     # Calculate metrics
#     previous_year = selected_year - 1 if selected_year > min(years) else None
#     total_cases, overall_incidence, change_percent = calculate_metrics(data, selected_year, selected_metric, previous_year)
    
#     # Metrics with dark mode styling
#     col1, col2, col3 = st.columns(3)
    
#     with col1:
#         if selected_metric in ['all cases', 'all cases incidence']:
#             st.metric("Total All Cases", f"{total_cases:,.0f}")
#         else:
#             st.metric("Total Severe Cases/Deaths", f"{total_cases:,.0f}")
    
#     with col2:
#         st.metric("Average Incidence", f"{overall_incidence:.2f}")
    
#     with col3:
#         if change_percent is not None:
#             if change_percent > 0:
#                 arrow = "↑"
#                 color_style = "color: red;"
#             else:
#                 arrow = "↓"
#                 color_style = "color: green;"
#                 change_percent = abs(change_percent)
            
#             change_html = f"""
#             <div style="background-color: #2b2b2b; border: 1px solid #444; padding: 0.5rem; border-radius: 0.25rem;">
#                 <div style="font-size: 14px; color: white;">Change(%) of incidence</div>
#                 <div style="font-size: 28px; font-weight: 600; {color_style}">
#                     {arrow} {change_percent:+.1f}% vs {previous_year}
#                 </div>
#             </div>
#             """
#             st.markdown(change_html, unsafe_allow_html=True)
#         else:
#             st.metric("Change(%) of incidence", "N/A")
    
#     # Map and Top Districts
#     map_col, chart_col = st.columns([2.5, 1])
    
#     with map_col:
#         map_fig = create_choropleth_map(data, selected_year, selected_metric)
#         st.plotly_chart(map_fig, use_container_width=True)
    
#     with chart_col:
#         top_districts_fig = create_top_districts_chart(data, selected_year, selected_metric)
#         st.plotly_chart(top_districts_fig, use_container_width=True)
    
#     # NEW LAYOUT: Two columns under the map
#     st.subheader("District Analysis Dashboard")
#     col_left, col_right = st.columns([1, 1])
    
#     with col_left:
#         # District Trends
#         st.markdown("### District Trends Over Time")
#         if selected_districts:
#             trend_fig = create_trend_chart(data, selected_districts, selected_metric)
#             if trend_fig:
#                 st.plotly_chart(trend_fig, use_container_width=True)
#         else:
#             st.info("Select districts from the sidebar to view trends")
#             st.markdown("""
#             **How to Use:**
#             1. Select districts in the sidebar
#             2. Compare trends over time
#             3. Identify patterns:
#                - Consistent improvement
#                - Recent deterioration
#                - Seasonal patterns
#             """)
    
#     with col_right:
#         # Province Analysis (All Cases vs Severe/Deaths Cases) - FIXED: Always shows 2025 data
#         st.markdown("### Province Analysis")
#         province_fig, all_cases_threshold, severe_threshold = create_province_scatterplot(data, year=2025)  # FIXED: Always pass 2025
#         if province_fig:
#             st.plotly_chart(province_fig, use_container_width=True)
            
#             # Add the adjusted quadrant comments for All Cases vs Severe/Deaths Cases
#             st.markdown("""
#             **Analysis Guide:**

#             **🟥 Upper-right quadrant:** High all cases & high severe cases – critical zones needing urgent, full-scale response.  
#             *Interventions: emergency response, better clinical care, intensive follow-up, stronger referrals, more health workers*

#             **🟧 Upper-left quadrant:** Low all cases & high severe cases – signs of poor case handling needing quality upgrades.  
#             *Interventions: health worker training, rapid testing, better treatment, patient transport, case supervision*

#             **🟨 Lower-right quadrant:** High all cases & low severe cases – high transmission but effective treatment.  
#             *Interventions: stronger vector control, expand community care, more prevention, faster detection, limit spread*

#             **🟩 Lower-left quadrant:** Low all cases & low severe cases – stable areas that need to sustain gains.  
#             *Interventions: keep up surveillance, continue prevention, monitor vectors, educate communities, stay outbreak-ready*
#             """)

# if __name__ == "__main__":
#     main()
