import pandas as pd

 # TODO : to be formatted and integrated into Outputs

def calculate_lighting_deficiency(df, lux_threshold=200, light_schedule_column=None):
    """
    Create columns indicating lighting deficiency per zone.

    This function requires that you loaded Daylighting Reference Point 1
    and Zone People occupant Count in the simulation outputs.

    Parameters:
    - df: DataFrame containing illuminance, occupancy, and light schedule data.
    - lux_threshold: The minimum lux level required for lighting autonomy.
    - light_schedule_column: Column name for the light schedule to determine active hours.

    Returns:
    - DataFrame with additional columns for lighting deficiency per zone.
    """
    illuminance_columns = [col for col in df.columns if 'Daylighting Reference Point' in col and 'Illuminance' in col]
    occupancy_column = [col for col in df.columns if 'Zone People Occupant Count' in col][0]

    is_occupied = df[occupancy_column] > 0
    is_schedule_active = df[light_schedule_column] > 0

    for illum_col in illuminance_columns:
        zone = illum_col.split('_')[0].split(':')[1]
        df[f'no_autonomy_{zone}'] = ((df[illum_col] < lux_threshold) & is_occupied & is_schedule_active).astype(int)

    return df


def aggregate_lighting_deficiency(df, season_mapping=None):
    """
        Aggregates lighting deficiency as a percentage relative to occupied time.

        Parameters:
        - df: DataFrame containing lighting deficiency columns (starting with 'no_autonomy')
          and occupancy columns (containing 'Zone People Occupant Count').
        - season_mapping: Optional dictionary mapping months (1-12) to seasons. If provided,
          the function calculates the deficiency percentage for each season as well as the total.
          If not provided, the function calculates only the total deficiency percentage.
        Example of season_mapping:
          {
              12: 'Winter', 1: 'Winter', 2: 'Winter',
              3: 'Spring', 4: 'Spring', 5: 'Spring',
              6: 'Summer', 7: 'Summer', 8: 'Summer',
              9: 'Fall', 10: 'Fall', 11: 'Fall'
          }
        Returns:
        - A DataFrame with columns:
          - 'Zone': The zone for which the deficiency is calculated.
          - 'Season': The season ('Winter', 'Spring', 'Summer', 'Fall', or 'Total').
          - 'lighting_deficiency_%': The percentage of time without lighting autonomy relative to occupied time.
        """
    deficiency_columns = [col for col in df.columns if col.startswith('no_autonomy')]
    occupancy_columns = [col for col in df.columns if 'Zone People Occupant Count' in col]

    results = []
    if season_mapping:
        df['Season'] = df.index.month.map(season_mapping)
        grouped = df.groupby('Season')

        for deficiency_col, occ_col in zip(deficiency_columns, occupancy_columns):
            zone = deficiency_col.split('_')[2]

            for season, group in grouped:
                total_deficiency = group[deficiency_col].sum()
                total_occupancy = (group[occ_col] > 0).sum()
                percentage = (total_deficiency / total_occupancy) * 100 if total_occupancy > 0 else 0
                results.append({'Zone': zone, 'Season': season, 'lighting_deficiency_%': percentage})

            total_deficiency = df[deficiency_col].sum()
            total_occupancy = (df[occ_col] > 0).sum()
            percentage = (total_deficiency / total_occupancy) * 100 if total_occupancy > 0 else 0
            results.append({'Zone': zone, 'Season': 'Total', 'lighting_deficiency_%': percentage})

    else:
        for deficiency_col, occ_col in zip(deficiency_columns, occupancy_columns):
            zone = deficiency_col.split('_')[2]

            total_deficiency = df[deficiency_col].sum()
            total_occupancy = (df[occ_col] > 0).sum()
            percentage = (total_deficiency / total_occupancy) * 100 if total_occupancy > 0 else 0
            results.append({'Zone': zone, 'Season': 'Total', 'lighting_deficiency_%': percentage})

    return pd.DataFrame(results)


def calculate_discomfort(df, temp_threshold=28):
    """
    Adds columns to the DataFrame to indicate thermal discomfort for each zone.
    This function requires that you loaded DZone Operative Temperatures
    and Zone People occupant Count in the simulation outputs.

    Parameters:
    - df: DataFrame containing columns for operative temperature and occupancy.
    - temp_threshold: The temperature threshold to define thermal discomfort.

    Returns:
    - The input DataFrame with additional columns for each zone indicating thermal discomfort.
    """
    temp_columns = [col for col in df.columns if 'Zone Operative Temperature' in col]
    occupancy_columns = [col for col in df.columns if 'Zone People Occupant Count' in col]

    for temp_col, occ_col in zip(temp_columns, occupancy_columns):
        zone = temp_col.split('_')[0].split(':')[1]
        df[f'discomfort{temp_threshold}_{zone}'] = ((df[temp_col] >= temp_threshold) & (df[occ_col] > 0)).astype(int)

    return df


def aggregate_discomfort_percentage(df, season_mapping=None):
    """
    Aggregates thermal discomfort data as a percentage relative to occupied time.

    Parameters:
    - df: DataFrame containing thermal discomfort columns (e.g., discomfort columns) and occupancy data.
    - season_mapping: A dictionary mapping months to seasons (only needed for seasonal aggregation).
        Otherwise, will calculate throughout the entire dataset

    Returns:
    - A DataFrame with columns: Zone, Season, time_discomfort_%.
    """
    discomfort_columns = [col for col in df.columns if col.startswith('discomfort')]
    occupancy_columns = [col for col in df.columns if 'Zone People Occupant Count' in col]

    if season_mapping:
        df['Season'] = df.index.month.map(season_mapping)
        grouped = df.groupby('Season')

    results = []

    for discomfort_col, occ_col in zip(discomfort_columns, occupancy_columns):
        zone = discomfort_col.split('_')[1].split(':')[0]

        if season_mapping:
            for season, group_data in grouped:
                total_discomfort = group_data[discomfort_col].sum()
                total_occupancy = (group_data[occ_col] > 0).sum()
                percentage = (total_discomfort / total_occupancy) * 100 if total_occupancy > 0 else 0
                results.append({'Zone': zone, 'Season': season, 'Percentage': percentage})

        total_discomfort = df[discomfort_col].sum()
        total_occupancy = (df[occ_col] > 0).sum()
        percentage = (total_discomfort / total_occupancy) * 100 if total_occupancy > 0 else 0
        results.append({'Zone': zone, 'Season': 'Total', 'Percentage': percentage})

    return pd.DataFrame(results)