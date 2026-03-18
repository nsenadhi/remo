import re
from config_nlp_engine import vital_sign_var_to_text, SIMULATED_VITALS
import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
from collections import defaultdict
import os
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def combine_data_and_time(list_date, list_time):
    """Combine dates and times into full timestamps"""
    time_stamp_list = []
    for date in list_date:
        for time in list_time:
            time_stamp = f'{date} {time}'
            time_stamp_list.append(time_stamp)
    return time_stamp_list


def filter_raw_df(df, intent_dict, is_current):
    """
    ✅ FIXED LOGIC: 
    
    1. EXACT TIMESTAMP MATCHING - When user asks for specific date without time details:
       - Uses 4 daily snapshots: 01:00, 07:00, 13:00, 19:00
       - Matches EXACT times only (within 30-min tolerance for data availability)
       
    2. TIME RANGE MATCHING - When user specifies a time range (e.g., "2 PM to 8 PM"):
       - Filters ALL data within that range
       - Includes every timestamp between start and end
       
    How to detect:
    - If list_time has exactly 4 elements ['01:00:00', '07:00:00', '13:00:00', '19:00:00'] → EXACT mode
    - If list_time has many consecutive times (like every 30 min) → RANGE mode
    """
    if is_current:
        # Current data - just return latest row
        return df.tail(1).copy()

    # Historical data
    list_date = intent_dict.get('list_date', [])
    list_time = intent_dict.get('list_time', [])

    if not list_date:
        logger.warning("No dates specified for historical query")
        return pd.DataFrame()

    # Filter columns to include timestamp + requested vital signs
    vital_signs = intent_dict.get('vital_sign', [])
    columns = ['time_stamp'] + vital_signs

    # Make sure all columns exist
    available_columns = ['time_stamp'] + [col for col in vital_signs if col in df.columns]
    filtered_df = df[available_columns].copy()

    # Convert timestamp column to datetime
    filtered_df['time_stamp'] = pd.to_datetime(filtered_df['time_stamp'], errors='coerce')
    filtered_df = filtered_df.dropna(subset=['time_stamp'])

    # ============================================================================
    # ✅ CRITICAL: Detect query type
    # ============================================================================
    
    # Default daily snapshots (set by process_special_historical_data_retrieval)
    DAILY_SNAPSHOTS = ['01:00:00', '07:00:00', '13:00:00', '19:00:00']
    
    # ✅ Check if this is an EXACT timestamp query (daily snapshots)
    is_exact_timestamps = (
        list_time == DAILY_SNAPSHOTS or 
        len(list_time) == 4 and set(list_time) == set(DAILY_SNAPSHOTS)
    )
    
    if not list_time or len(list_time) == 0:
        # ✅ NO TIMES SPECIFIED - Get ALL data for those dates
        logger.info(f"📅 Date-only query (all data): {list_date}")
        
        all_matching_rows = []
        for date_str in list_date:
            date_obj = pd.to_datetime(date_str).date()
            date_mask = filtered_df['time_stamp'].dt.date == date_obj
            matching_rows = filtered_df[date_mask]
            
            if not matching_rows.empty:
                all_matching_rows.append(matching_rows)
                logger.info(f"   ✅ {date_str}: Found {len(matching_rows)} rows")
            else:
                logger.warning(f"   ⚠️ {date_str}: No data found")
        
        if all_matching_rows:
            filtered_df = pd.concat(all_matching_rows, ignore_index=True)
            logger.info(f"📊 Total rows: {len(filtered_df)}")
        else:
            filtered_df = pd.DataFrame()
    
    elif is_exact_timestamps:
        # ✅ EXACT TIMESTAMPS MODE - Match 4 daily snapshots only
        logger.info(f"🎯 EXACT timestamp matching: {list_date} at times {list_time}")
        logger.info(f"   Using 4 daily snapshots (1AM, 7AM, 1PM, 7PM)")
        
        all_matching_rows = []
        
        for date_str in list_date:
            date_obj = pd.to_datetime(date_str).date()
            
            # Filter to this specific date
            date_mask = filtered_df['time_stamp'].dt.date == date_obj
            date_df = filtered_df[date_mask].copy()
            
            if date_df.empty:
                logger.warning(f"   ⚠️ {date_str}: No data found")
                continue
            
            # For each snapshot time, find closest match (within 30 min tolerance)
            date_matches = []
            for target_time_str in list_time:
                target_time = pd.to_datetime(target_time_str, format='%H:%M:%S').time()
                
                # Find rows within ±30 minutes of target time
                target_hour = target_time.hour
                target_minute = target_time.minute
                
                # Create target datetime for comparison
                target_dt = pd.Timestamp.combine(date_obj, target_time)
                
                # Find closest match within 30-minute window
                time_diffs = abs((date_df['time_stamp'] - target_dt).dt.total_seconds())
                
                # Only accept matches within 30 minutes (1800 seconds)
                valid_matches = date_df[time_diffs <= 1800]
                
                if not valid_matches.empty:
                    # Take the closest match
                    closest_idx = time_diffs[time_diffs <= 1800].idxmin()
                    closest_match = date_df.loc[[closest_idx]]
                    date_matches.append(closest_match)
                    actual_time = closest_match['time_stamp'].iloc[0].strftime('%H:%M:%S')
                    logger.debug(f"      {target_time_str} → matched {actual_time}")
                else:
                    logger.debug(f"      {target_time_str} → no match found")
            
            if date_matches:
                day_data = pd.concat(date_matches, ignore_index=True)
                all_matching_rows.append(day_data)
                logger.info(f"   ✅ {date_str}: Found {len(day_data)}/4 snapshots")
            else:
                logger.warning(f"   ⚠️ {date_str}: No snapshots found")
        
        if all_matching_rows:
            filtered_df = pd.concat(all_matching_rows, ignore_index=True)
            logger.info(f"📊 Total snapshots: {len(filtered_df)} (expected: {len(list_date) * 4})")
        else:
            logger.warning(f"⚠️ No snapshot data found")
            filtered_df = pd.DataFrame()
    
    else:
        # ✅ TIME RANGE MODE - User specified specific time range
        logger.info(f"📍 TIME RANGE filtering: {list_date} with times {list_time[0]} to {list_time[-1]}")
        
        # Parse start and end times
        start_time = pd.to_datetime(list_time[0], format='%H:%M:%S').time()
        end_time = pd.to_datetime(list_time[-1], format='%H:%M:%S').time()
        
        logger.info(f"   Time range: {start_time} to {end_time}")
        
        # Apply filters for each date
        all_matching_rows = []
        
        for date_str in list_date:
            date_obj = pd.to_datetime(date_str).date()
            
            # Filter to this specific date
            date_mask = filtered_df['time_stamp'].dt.date == date_obj
            date_df = filtered_df[date_mask].copy()
            
            if date_df.empty:
                logger.warning(f"   ⚠️ {date_str}: No data found")
                continue
            
            # Apply time range filter
            time_mask = (
                (date_df['time_stamp'].dt.time >= start_time) & 
                (date_df['time_stamp'].dt.time <= end_time)
            )
            
            matching_rows = date_df[time_mask]
            
            if not matching_rows.empty:
                all_matching_rows.append(matching_rows)
                logger.info(f"   ✅ {date_str}: Found {len(matching_rows)} rows in time range")
            else:
                logger.warning(f"   ⚠️ {date_str}: No data in time range {start_time}-{end_time}")
        
        if all_matching_rows:
            filtered_df = pd.concat(all_matching_rows, ignore_index=True)
            logger.info(f"📊 Total rows after time filtering: {len(filtered_df)}")
        else:
            logger.warning(f"⚠️ No data found in specified time range")
            filtered_df = pd.DataFrame()

    return filtered_df.reset_index(drop=True)


def df_to_text(df, intent_dict):
    """
    ✅ MODIFIED: Convert dataframe to text with simulated value markers
    """
    if df.empty:
        return "No data available for the specified time period."

    vital_signs = intent_dict.get('vital_sign', [])
    
    # ✅ Track if any simulated vitals are present
    has_simulated = any(v in SIMULATED_VITALS for v in vital_signs)

    # Build header
    text = 'Timestamp (Year-Month-Day Hour:Minute:Second)'
    for vital_sign in vital_signs:
        if vital_sign in vital_sign_var_to_text:
            label = vital_sign_var_to_text[vital_sign]
            # ✅ Add (*) marker for simulated vitals in header
            if vital_sign in SIMULATED_VITALS:
                text += f', {label} (*)'
            else:
                text += f', {label}'
        else:
            text += f', {vital_sign}'
    text += '\n'

    # Add data rows
    for i in range(len(df)):
        row_text = str(df.iloc[i]['time_stamp'])
        for vital_sign in vital_signs:
            if vital_sign in df.columns:
                value = df.iloc[i][vital_sign]
                row_text += f', {value}'
            else:
                row_text += ', N/A'
        text += f'{row_text}\n'
    
    # ✅ Add disclaimer if any simulated vitals were included
    if has_simulated:
        text += f"\n(*) - These values are simulated due to Samsung Galaxy Watch hardware limitations.\n"
        logger.info(f"📝 Generated text data with simulated values disclaimer: {len(df)} rows")
    else:
        logger.info(f"📝 Generated text data (all real values): {len(df)} rows")

    return text


def plot_vital_sign(df, vital_sign):
    """✅ FIXED: Returns dict with path and simulated status"""
    try:
        if df.empty or vital_sign not in df.columns:
            logger.warning(f"Cannot plot {vital_sign}: no data")
            return None

        # Remove any NaN values
        plot_df = df[['time_stamp', vital_sign]].dropna()

        if len(plot_df) == 0:
            logger.warning(f"No valid data for {vital_sign}")
            return None

        original_count = len(plot_df)
        
        # ✅ Smart sampling for large datasets
        MAX_PLOT_POINTS = 200
        if len(plot_df) > MAX_PLOT_POINTS:
            sample_rate = max(1, len(plot_df) // MAX_PLOT_POINTS)
            plot_df = plot_df.iloc[::sample_rate].copy()
            logger.info(f"Sampled {len(plot_df)} from {original_count} points")

        is_simulated = vital_sign in SIMULATED_VITALS

        # ✅ Define thresholds
        THRESHOLDS = {
            "heart_rate": {"low": 40, "high": 130},
            "body_temperature": {"low": 27, "high": 38},
            "glucose": {"low": 70, "high": 180},
            "oxygen_saturation": {"low": 88, "high": 100},
            "systolic_pressure": {"low": 90, "high": 180},
            "respiratory_rate": {"low": 10, "high": 25},
            "diastolic_pressure": {"low": 60, "high": 120}
        }

        # ✅ AUTO-SCALING: Calculate optimal figure size based on data points
        if original_count <= 50:
            figwidth = 10
            figheight = 6
        elif original_count <= 200:
            figwidth = 12
            figheight = 6
        elif original_count <= 500:
            figwidth = 15
            figheight = 6
        elif original_count <= 1000:
            figwidth = 18
            figheight = 6
        else:
            figwidth = 24
            figheight = 6

        logger.info(f"📏 Plot dimensions: {figwidth}x{figheight} for {original_count} datapoints")

        # ✅ Create plot with calculated dimensions
        figure, ax = plt.subplots(figsize=(figwidth, figheight))
        figure.patch.set_facecolor('white')
        ax.set_facecolor('white')

        x = plot_df['time_stamp']
        y = plot_df[vital_sign]

        # ✅ Conditional styling: no markers for large datasets
        if original_count > 50:
            ax.plot(x, y, linestyle='-', linewidth=1.5, color='black', zorder=3)
        else:
            ax.plot(x, y, marker='o', linestyle='-', linewidth=1.5, 
                   markersize=4, color='black', zorder=3)

        # ✅ Add threshold lines
        if vital_sign in THRESHOLDS:
            thresholds = THRESHOLDS[vital_sign]
            
            if 'high' in thresholds:
                ax.axhline(y=thresholds['high'], color='red', linestyle='--', 
                          linewidth=1.5, label=f'High ({thresholds["high"]})', 
                          alpha=0.7, zorder=2)
            
            if 'low' in thresholds:
                ax.axhline(y=thresholds['low'], color='orange', linestyle='--', 
                          linewidth=1.5, label=f'Low ({thresholds["low"]})', 
                          alpha=0.7, zorder=2)

        # ✅ Labels - NO ASTERISK in plot itself
        ax.set_xlabel('Time', fontsize=11, color='black')
        
        y_label = vital_sign_var_to_text.get(vital_sign, vital_sign)
        ax.set_ylabel(y_label, fontsize=11, color='black')

        title = f'{vital_sign_var_to_text.get(vital_sign, vital_sign)} Over Time'
        ax.set_title(title, fontsize=12, color='black')

        # ✅ Simple grid
        ax.grid(True, alpha=0.2, color='gray', zorder=1)
        ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1.0), fontsize=9, frameon=True, borderaxespad=0.0)
        
        # ✅ AUTO-SCALING: Adjust number of x-axis ticks based on width
        if figwidth <= 10:
            max_ticks = 8
        elif figwidth <= 15:
            max_ticks = 12
        elif figwidth <= 20:
            max_ticks = 16
        else:
            max_ticks = 20
        
        ax.xaxis.set_major_locator(plt.MaxNLocator(max_ticks))
        
        plt.xticks(rotation=45, ha='right', fontsize=9)
        plt.yticks(fontsize=9)

        os.makedirs('./static/local_data/show_data/', exist_ok=True)

        import time
        timestamp = int(time.time() * 1000)
        save_path = f'./static/local_data/show_data/plot_{vital_sign}_{timestamp}.png'
        web_path = f'/static/local_data/show_data/plot_{vital_sign}_{timestamp}.png'

        # ✅ Reduced DPI for faster rendering
        figure.savefig(save_path, bbox_inches='tight', dpi=80, facecolor='white')
        plt.close(figure)

        logger.info(f"✅ Plot saved: {save_path} ({original_count} → {len(plot_df)} points, {figwidth}x{figheight})")
        
        # ✅ RETURN DICT: path and simulated flag
        return {
            'path': web_path,
            'is_simulated': is_simulated,
            'vital_sign': vital_sign
        }

    except Exception as e:
        logger.error(f"Error plotting {vital_sign}: {e}")
        return None

def extract_patient_id_from_text(text):
    """Extract 5-digit patient ID from text"""
    pattern = r"\d{5}"
    match = re.search(pattern, text)
    if match:
        return match.group(0)
    else:
        return 'unknown'


def get_serial_path(data_folder_path):
    """Get next serial number for image files"""
    files = os.listdir(data_folder_path)
    image_files = [f for f in files if f.endswith('.jpg') and f[:-4].isdigit()]
    indices = [int(f.split('.')[0]) for f in image_files]
    max_index = max(indices) if indices else 0
    new_index = max_index + 1
    new_filename = f"{new_index:02d}.jpg"
    new_filepath = os.path.join(data_folder_path, new_filename)
    return new_filepath


def extract_unique_year_month(date_list, format=str):
    """Extract unique YYYY-MM from date list"""
    year_month_set = {date[:7].replace('-', '_') for date in date_list}
    year_month_list = sorted(list(year_month_set))
    return year_month_list


def process_key_to_retrieve_image(timestamp_list):
    """Group timestamps for image retrieval"""
    grouped_timestamps = defaultdict(list)
    for timestamp in timestamp_list:
        date, time = timestamp.split(' ')
        year, month, day = date.split('-')
        year_month = f'{year}_{month}'
        day_time = f'{day}_{time.replace(":", "_")}'
        day_time = day_time[:-3]
        grouped_timestamps[year_month].append(day_time)
    return dict(grouped_timestamps)
