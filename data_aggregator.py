"""
Data Aggregation Utility for Health Monitoring System
=====================================================

This module calculates statistical metrics for vital signs data to reduce token usage
when sending data to OpenAI for analysis.

Aggregation Strategy:
- < 1 week: Send all raw data (no aggregation)
- 1 week to 1 month: Aggregate to daily averages
- > 1 month: Calculate comprehensive statistical metrics

Author: REMONI Health Monitoring System
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from scipy import stats
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


class VitalsDataAggregator:
    """
    Aggregates vital signs data into statistical metrics to reduce token usage
    while maintaining analytical capability.
    """
    
    # Define normal ranges for vital signs
    NORMAL_RANGES = {
        'heart_rate': (40, 130),
        'systolic_pressure': (90, 190),
        'diastolic_pressure': (60, 120),
        'respiratory_rate': (10, 25),
        'body_temperature': (27, 38),
        'oxygen_saturation': (88, 100),
        'spo2': (88, 100),
        'glucose': (70, 180)
    }
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def determine_aggregation_level(self, df: pd.DataFrame) -> str:
        """
        Determine the appropriate aggregation level based on time span.
        
        Returns:
            'raw': < 1 week - send all data
            'daily': 1 week to 1 month - daily aggregation
            'metrics': > 1 month - full statistical metrics
        """
        if df.empty or 'time_stamp' not in df.columns:
            return 'raw'
        
        # Ensure time_stamp is datetime
        if not pd.api.types.is_datetime64_any_dtype(df['time_stamp']):
            df['time_stamp'] = pd.to_datetime(df['time_stamp'], errors='coerce')
            df = df.dropna(subset=['time_stamp'])
        
        if df.empty:
            return 'raw'
        
        time_span = (df['time_stamp'].max() - df['time_stamp'].min())
        time_span_days = time_span.total_seconds() / 86400  # Convert to days
        
        if time_span_days < 7:
            return 'raw'
        elif time_span_days <= 31:
            return 'daily'
        else:
            return 'metrics'
    
    def calculate_baseline_metrics(self, data: pd.Series) -> Dict:
        """Calculate baseline statistical metrics."""
        data_clean = data.dropna()
        
        if len(data_clean) == 0:
            return {}
        
        # Calculate trimmed mean (remove top and bottom 10%)
        trimmed_mean = stats.trim_mean(data_clean, 0.1)
        
        return {
            'mean': round(float(data_clean.mean()), 2),
            'median': round(float(data_clean.median()), 2),
            'trimmed_mean': round(float(trimmed_mean), 2)
        }
    
    def calculate_variability_metrics(self, data: pd.Series) -> Dict:
        """Calculate variability metrics."""
        data_clean = data.dropna()
        
        if len(data_clean) == 0:
            return {}
        
        mean = data_clean.mean()
        std = data_clean.std()
        
        # Coefficient of Variation (CV)
        cv = (std / mean * 100) if mean != 0 else 0
        
        # Interquartile Range
        q75, q25 = data_clean.quantile([0.75, 0.25])
        iqr = q75 - q25
        
        return {
            'std': round(float(std), 2),
            'iqr': round(float(iqr), 2),
            'coefficient_of_variation': round(float(cv), 2)
        }
    
    def calculate_extreme_value_metrics(self, data: pd.Series) -> Dict:
        """Calculate extreme value metrics."""
        data_clean = data.dropna()
        
        if len(data_clean) == 0:
            return {}
        
        # Percentile range
        p5 = data_clean.quantile(0.05)
        p95 = data_clean.quantile(0.95)
        
        return {
            'min': round(float(data_clean.min()), 2),
            'max': round(float(data_clean.max()), 2),
            'range': round(float(data_clean.max() - data_clean.min()), 2),
            'p5': round(float(p5), 2),
            'p95': round(float(p95), 2),
            'p5_p95_range': round(float(p95 - p5), 2)
        }
    
    def calculate_abnormal_burden_metrics(self, data: pd.Series, vital_sign: str) -> Dict:
        """Calculate abnormal burden metrics."""
        data_clean = data.dropna()
        
        if len(data_clean) == 0 or vital_sign not in self.NORMAL_RANGES:
            return {}
        
        normal_range = self.NORMAL_RANGES[vital_sign]
        low_threshold, high_threshold = normal_range
        
        # Identify abnormal values
        below_normal = data_clean < low_threshold
        above_normal = data_clean > high_threshold
        abnormal = below_normal | above_normal
        
        # Calculate percentage of time outside normal range
        pct_abnormal = (abnormal.sum() / len(data_clean) * 100)
        
        # Count episodes (consecutive abnormal readings)
        abnormal_episodes = 0
        episode_durations = []
        in_episode = False
        episode_duration = 0
        
        for is_abnormal in abnormal:
            if is_abnormal:
                if not in_episode:
                    abnormal_episodes += 1
                    in_episode = True
                    episode_duration = 1
                else:
                    episode_duration += 1
            else:
                if in_episode:
                    episode_durations.append(episode_duration)
                    in_episode = False
                    episode_duration = 0
        
        # Close last episode if still ongoing
        if in_episode:
            episode_durations.append(episode_duration)
        
        mean_episode_duration = np.mean(episode_durations) if episode_durations else 0
        
        return {
            'pct_outside_normal': round(float(pct_abnormal), 2),
            'num_abnormal_episodes': int(abnormal_episodes),
            'mean_episode_duration': round(float(mean_episode_duration), 2),
            'pct_below_normal': round(float(below_normal.sum() / len(data_clean) * 100), 2),
            'pct_above_normal': round(float(above_normal.sum() / len(data_clean) * 100), 2)
        }
    
    def calculate_trend_metrics(self, df: pd.DataFrame, vital_sign: str) -> Dict:
        """Calculate trend metrics."""
        if df.empty or vital_sign not in df.columns:
            return {}
        
        data_clean = df[[vital_sign, 'time_stamp']].dropna()
        
        if len(data_clean) < 2:
            return {}
        
        # Convert timestamps to numeric (days since first reading)
        first_time = data_clean['time_stamp'].min()
        data_clean['days'] = (data_clean['time_stamp'] - first_time).dt.total_seconds() / 86400
        
        # Linear regression for trend
        try:
            slope, intercept, r_value, p_value, std_err = stats.linregress(
                data_clean['days'], 
                data_clean[vital_sign]
            )
            
            # Calculate month-to-month change
            df_monthly = data_clean.set_index('time_stamp').resample('M')[vital_sign].mean()
            monthly_changes = df_monthly.diff().dropna()
            mean_monthly_change = monthly_changes.mean() if len(monthly_changes) > 0 else 0
            
            return {
                'linear_slope': round(float(slope), 4),
                'trend_direction': 'increasing' if slope > 0 else 'decreasing' if slope < 0 else 'stable',
                'r_squared': round(float(r_value ** 2), 4),
                'trend_significance': 'significant' if p_value < 0.05 else 'not_significant',
                'mean_monthly_change': round(float(mean_monthly_change), 2)
            }
        except Exception as e:
            self.logger.warning(f"Could not calculate trend metrics: {e}")
            return {}
    
    def calculate_circadian_metrics(self, df: pd.DataFrame, vital_sign: str) -> Dict:
        """Calculate circadian (day vs night) metrics."""
        if df.empty or vital_sign not in df.columns:
            return {}
        
        data_clean = df[[vital_sign, 'time_stamp']].dropna()
        
        if len(data_clean) < 2:
            return {}
        
        # Extract hour of day
        data_clean['hour'] = data_clean['time_stamp'].dt.hour
        
        # Define day (6am-6pm) and night (6pm-6am)
        day_data = data_clean[(data_clean['hour'] >= 6) & (data_clean['hour'] < 18)][vital_sign]
        night_data = data_clean[(data_clean['hour'] < 6) | (data_clean['hour'] >= 18)][vital_sign]
        
        if len(day_data) == 0 or len(night_data) == 0:
            return {}
        
        day_mean = day_data.mean()
        night_mean = night_data.mean()
        
        # Diurnal amplitude (difference between day and night)
        amplitude = abs(day_mean - night_mean)
        
        # Circadian consistency (inverse of coefficient of variation across hours)
        hourly_means = data_clean.groupby('hour')[vital_sign].mean()
        hourly_cv = hourly_means.std() / hourly_means.mean() if hourly_means.mean() != 0 else 0
        consistency_index = 1 / (1 + hourly_cv)  # Normalized to 0-1
        
        return {
            'day_mean': round(float(day_mean), 2),
            'night_mean': round(float(night_mean), 2),
            'diurnal_amplitude': round(float(amplitude), 2),
            'circadian_consistency_index': round(float(consistency_index), 4),
            'day_night_difference': round(float(day_mean - night_mean), 2)
        }
    
    def calculate_comprehensive_metrics(self, df: pd.DataFrame, vital_sign: str) -> Dict:
        """
        Calculate all metrics for a vital sign.
        This is used for time spans > 1 month.
        """
        if df.empty or vital_sign not in df.columns:
            return {}
        
        data = df[vital_sign]
        
        metrics = {
            'vital_sign': vital_sign,
            'sample_count': int(data.notna().sum()),
            'time_span_days': float((df['time_stamp'].max() - df['time_stamp'].min()).total_seconds() / 86400)
        }
        
        # Add all metric categories
        metrics.update(self.calculate_baseline_metrics(data))
        metrics.update(self.calculate_variability_metrics(data))
        metrics.update(self.calculate_extreme_value_metrics(data))
        metrics.update(self.calculate_abnormal_burden_metrics(data, vital_sign))
        metrics.update(self.calculate_trend_metrics(df, vital_sign))
        metrics.update(self.calculate_circadian_metrics(df, vital_sign))
        
        return metrics
    
    def aggregate_to_daily(self, df: pd.DataFrame, vital_signs: List[str]) -> pd.DataFrame:
        """
        Aggregate data to daily averages.
        This is used for time spans between 1 week and 1 month.
        """
        if df.empty:
            return df
        
        # Ensure time_stamp is datetime
        if not pd.api.types.is_datetime64_any_dtype(df['time_stamp']):
            df['time_stamp'] = pd.to_datetime(df['time_stamp'], errors='coerce')
            df = df.dropna(subset=['time_stamp'])
        
        # Extract date (without time)
        df['date'] = df['time_stamp'].dt.date
        
        # Aggregate by date
        daily_agg = df.groupby('date')[vital_signs].agg(['mean', 'min', 'max', 'std', 'count']).reset_index()
        
        # Flatten multi-level column names
        daily_agg.columns = ['_'.join(col).strip('_') if col[1] else col[0] 
                             for col in daily_agg.columns.values]
        
        return daily_agg
    
    def format_metrics_for_llm(self, metrics_dict: Dict, vital_sign: str) -> str:
        """
        Format metrics dictionary into human-readable text for LLM.
        """
        from config_nlp_engine import vital_sign_var_to_text, SIMULATED_VITALS
        
        vital_label = vital_sign_var_to_text.get(vital_sign, vital_sign.replace('_', ' ').title())
        is_simulated = vital_sign in SIMULATED_VITALS
        
        # Add simulated marker if needed
        header = f"{vital_label}"
        if is_simulated:
            header += " (*)"
        
        text = f"\n{'=' * 60}\n"
        text += f"{header}\n"
        text += f"{'=' * 60}\n"
        
        # Data overview
        text += f"\nData Overview:\n"
        text += f"  Sample Count: {metrics_dict.get('sample_count', 'N/A')}\n"
        text += f"  Time Span: {metrics_dict.get('time_span_days', 'N/A'):.1f} days\n"
        
        # Baseline metrics
        if 'mean' in metrics_dict:
            text += f"\nBaseline Metrics:\n"
            text += f"  Mean: {metrics_dict.get('mean', 'N/A')}\n"
            text += f"  Median: {metrics_dict.get('median', 'N/A')}\n"
            text += f"  Trimmed Mean (10%): {metrics_dict.get('trimmed_mean', 'N/A')}\n"
        
        # Variability
        if 'std' in metrics_dict:
            text += f"\nVariability Metrics:\n"
            text += f"  Standard Deviation: {metrics_dict.get('std', 'N/A')}\n"
            text += f"  Interquartile Range: {metrics_dict.get('iqr', 'N/A')}\n"
            text += f"  Coefficient of Variation: {metrics_dict.get('coefficient_of_variation', 'N/A')}%\n"
        
        # Extremes
        if 'min' in metrics_dict:
            text += f"\nExtreme Values:\n"
            text += f"  Minimum: {metrics_dict.get('min', 'N/A')}\n"
            text += f"  Maximum: {metrics_dict.get('max', 'N/A')}\n"
            text += f"  Range: {metrics_dict.get('range', 'N/A')}\n"
            text += f"  5th Percentile: {metrics_dict.get('p5', 'N/A')}\n"
            text += f"  95th Percentile: {metrics_dict.get('p95', 'N/A')}\n"
        
        # Abnormal burden
        if 'pct_outside_normal' in metrics_dict:
            text += f"\nAbnormal Burden Metrics:\n"
            text += f"  % Time Outside Normal Range: {metrics_dict.get('pct_outside_normal', 'N/A')}%\n"
            text += f"  % Below Normal: {metrics_dict.get('pct_below_normal', 'N/A')}%\n"
            text += f"  % Above Normal: {metrics_dict.get('pct_above_normal', 'N/A')}%\n"
            text += f"  Number of Abnormal Episodes: {metrics_dict.get('num_abnormal_episodes', 'N/A')}\n"
            text += f"  Mean Episode Duration: {metrics_dict.get('mean_episode_duration', 'N/A')} readings\n"
        
        # Trends
        if 'linear_slope' in metrics_dict:
            text += f"\nTrend Metrics:\n"
            text += f"  Trend Direction: {metrics_dict.get('trend_direction', 'N/A')}\n"
            text += f"  Linear Slope: {metrics_dict.get('linear_slope', 'N/A')} per day\n"
            text += f"  R-squared: {metrics_dict.get('r_squared', 'N/A')}\n"
            text += f"  Statistical Significance: {metrics_dict.get('trend_significance', 'N/A')}\n"
            text += f"  Mean Monthly Change: {metrics_dict.get('mean_monthly_change', 'N/A')}\n"
        
        # Circadian
        if 'day_mean' in metrics_dict:
            text += f"\nCircadian Metrics:\n"
            text += f"  Day Mean (6am-6pm): {metrics_dict.get('day_mean', 'N/A')}\n"
            text += f"  Night Mean (6pm-6am): {metrics_dict.get('night_mean', 'N/A')}\n"
            text += f"  Day-Night Difference: {metrics_dict.get('day_night_difference', 'N/A')}\n"
            text += f"  Diurnal Amplitude: {metrics_dict.get('diurnal_amplitude', 'N/A')}\n"
            text += f"  Circadian Consistency Index: {metrics_dict.get('circadian_consistency_index', 'N/A')}\n"
        
        return text
    
    def format_daily_data_for_llm(self, daily_df: pd.DataFrame, vital_signs: List[str]) -> str:
        """
        Format daily aggregated data for LLM.
        """
        from config_nlp_engine import vital_sign_var_to_text, SIMULATED_VITALS
        
        text = "\n" + "=" * 60 + "\n"
        text += "DAILY AGGREGATED VITAL SIGNS DATA\n"
        text += "=" * 60 + "\n\n"
        
        # Check if any vitals are simulated
        has_simulated = any(v in SIMULATED_VITALS for v in vital_signs)
        
        # Header
        text += "Date"
        for vital in vital_signs:
            vital_label = vital_sign_var_to_text.get(vital, vital.replace('_', ' ').title())
            if vital in SIMULATED_VITALS:
                text += f" | {vital_label} (*) (Mean/Min/Max/Std)"
            else:
                text += f" | {vital_label} (Mean/Min/Max/Std)"
        text += "\n"
        text += "-" * 60 + "\n"
        
        # Data rows
        for _, row in daily_df.iterrows():
            date = row['date']
            text += f"{date}"
            
            for vital in vital_signs:
                mean_val = row.get(f'{vital}_mean', 'N/A')
                min_val = row.get(f'{vital}_min', 'N/A')
                max_val = row.get(f'{vital}_max', 'N/A')
                std_val = row.get(f'{vital}_std', 'N/A')
                
                if mean_val != 'N/A':
                    text += f" | {mean_val:.1f}/{min_val:.1f}/{max_val:.1f}/{std_val:.1f}"
                else:
                    text += " | N/A"
            
            text += "\n"
        
        # Add disclaimer if needed
        if has_simulated:
            text += f"\n(*) - These values are simulated due to Samsung Galaxy Watch hardware limitations.\n"
        
        return text
    
    def process_data_for_llm(self, df: pd.DataFrame, vital_signs: List[str]) -> Tuple[str, str]:
        """
        Main entry point: Process data and return formatted text for LLM.
        
        Returns:
            Tuple of (formatted_text, aggregation_level)
        """
        if df.empty:
            return "No data available.", "raw"
        
        aggregation_level = self.determine_aggregation_level(df)
        
        self.logger.info(f"📊 Data aggregation level: {aggregation_level}")
        self.logger.info(f"   Total samples: {len(df)}")
        self.logger.info(f"   Vital signs: {vital_signs}")
        
        if aggregation_level == 'raw':
            # Send all raw data (< 1 week)
            from utils import df_to_text
            return df_to_text(df, {'vital_sign': vital_signs}), 'raw'
        
        elif aggregation_level == 'daily':
            # Aggregate to daily averages (1 week - 1 month)
            daily_df = self.aggregate_to_daily(df, vital_signs)
            text = self.format_daily_data_for_llm(daily_df, vital_signs)
            self.logger.info(f"   Aggregated to {len(daily_df)} daily summaries")
            return text, 'daily'
        
        else:  # aggregation_level == 'metrics'
            # Calculate comprehensive metrics (> 1 month)
            all_metrics_text = ""
            
            for vital in vital_signs:
                if vital in df.columns:
                    metrics = self.calculate_comprehensive_metrics(df, vital)
                    metrics_text = self.format_metrics_for_llm(metrics, vital)
                    all_metrics_text += metrics_text + "\n"
            
            # Add simulated disclaimer at the end
            from config_nlp_engine import SIMULATED_VITALS
            has_simulated = any(v in SIMULATED_VITALS for v in vital_signs)
            if has_simulated:
                all_metrics_text += f"\n(*) - These values are simulated due to Samsung Galaxy Watch hardware limitations.\n"
            
            self.logger.info(f"   Calculated comprehensive metrics for {len(vital_signs)} vitals")
            return all_metrics_text, 'metrics'


# Global instance
vitals_aggregator = VitalsDataAggregator()