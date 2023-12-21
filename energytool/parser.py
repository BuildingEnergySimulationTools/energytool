import pandas as pd
from pathlib import Path


class ExcelParser:
    def __init__(self, excel_file_path, VARIANT_DICT, tab_names=None):
        self.excel_file_path = Path(excel_file_path)
        self.tab_names = tab_names
        self.tables = {}
        self.VARIANT_DICT = VARIANT_DICT

    def load_excel_data(self):
        try:
            # Load Excel file and iterate over each tab
            xl = pd.ExcelFile(self.excel_file_path)

            tabs_to_read = xl.sheet_names if self.tab_names is None else self.tab_names

            for tab_name in tabs_to_read:
                df = xl.parse(tab_name, skiprows=None, header=None)

                # Identify rows where empty lines are present
                empty_line_rows = df.isnull().all(axis=1)
                empty_line_indices = empty_line_rows[empty_line_rows].index

                # Split DataFrame based on empty lines
                start_idx = 0
                for end_idx in empty_line_indices:
                    # Exclude empty lines at the beginning
                    if start_idx != end_idx:
                        # Use the first row as the table name
                        table_name = df.iloc[start_idx, 0]
                        table_name = table_name if pd.notnull(table_name) else f"Table_{start_idx + 1}_{end_idx}"

                        # Extract the table and set the first row as the header
                        table_df = df.iloc[start_idx:end_idx, 1:]
                        table_df.columns = table_df.iloc[0]
                        table_df = table_df.iloc[1:]

                        self.tables[table_name] = table_df
                    start_idx = end_idx + 1

                # Handle the last table if it's not followed by an empty line
                if start_idx < len(df):
                    table_name = df.iloc[start_idx, 0]
                    table_name = table_name if pd.notnull(table_name) else f"Table_{start_idx + 1}_{len(df)}"

                    table_df = df.iloc[start_idx:, 1:]
                    table_df.columns = table_df.iloc[0]
                    table_df = table_df.iloc[1:]

                    self.tables[table_name] = table_df

        except Exception as e:
            print(f"Error loading Excel data: {e}")

    def get_table(self, table_name):
        return self.tables.get(table_name, None)

    def add_existing_building(self):
        try:
            existing_building_df = self.get_table("Existing building")

            for index, row in existing_building_df.iterrows():
                orientation = row["Opaque_orientation"]
                composition = [
                    {"Name": layer}
                    for column_name, layer in row.items()
                    if "layer" in column_name.lower() and pd.notna(layer)
                ]

                # Determine the face filter based on orientation
                if "south" in orientation.lower():
                    face_filter = "Face1"
                elif "west" in orientation.lower():
                    face_filter = "Face2"
                elif "north" in orientation.lower():
                    face_filter = "Face3"
                elif "east" in orientation.lower():
                    face_filter = "Face4"
                else:
                    face_filter = ""

                mat_info_walls = [self.get_material_opaque_info(layer["Name"]) for layer in composition]

                # Build the dictionary entry for each orientation
                variant_key = f"EXISTING_walls_{orientation.lower()}"
                if variant_key not in self.VARIANT_DICT:
                    self.VARIANT_DICT[variant_key] = {
                        "VariantKeys.MODIFIER": f"walls_{orientation.lower()}",
                        "VariantKeys.ARGUMENTS": {
                            "name_filter": face_filter
                        },
                        "VariantKeys.DESCRIPTION": {
                            variant_key: mat_info_walls
                        }
                    }

        except Exception as e:
            print(f"Error adding existing data: {e}")

    def add_existing_windows(self):
        try:
            existing_windows_df = self.get_table("Existing windows")

            for index, row in existing_windows_df.iterrows():
                orientation = row["Window_orientation"]
                presence_window = row["Presence_window"]
                compo_windows = row["compo_windows"]

                if presence_window == 1 and not pd.isna(compo_windows):
                    mat_info_windows = [self.get_material_window_info(compo_windows)]

                    variant_key = f"EXISTING_windows_{orientation.lower()}"
                    if variant_key not in self.VARIANT_DICT:

                        # Build the dictionary entry for each orientation
                        variant_key = f"EXISTING_windows_{orientation.lower()}"
                        if variant_key not in self.VARIANT_DICT:
                            self.VARIANT_DICT[variant_key] = {
                                "VariantKeys.MODIFIER": f"windows_{orientation.lower()}",
                                "VariantKeys.DESCRIPTION": {
                                    variant_key: mat_info_windows
                                }
                            }
        except Exception as e:
            print(f"Error adding existing data: {e}")

    def get_material_opaque_info(self, material_name):
        self.db_mat = self.get_table("db_mat")

        # Check if the material_name exists in the DataFrame
        if material_name in self.db_mat['Full_names'].values:
            material_info = self.db_mat[self.db_mat['Full_names'] == material_name].iloc[0]

            # Extract relevant columns
            mat_info = [
                {
                    "Name": material_info['Full_names'],
                    "Thickness": material_info['Thickness (m)'],
                    "Conductivity": material_info['Conductivity (W/m.K)'],
                    "Density": material_info['Density (kg/m3)'],
                    "Specific_Heat": material_info['Specific Heat (J/kg.K)'],
                }
            ]
        else:
            print(f"Material '{material_name}' not found in db_mat DataFrame.")
            mat_info = []

        return mat_info

    def get_material_window_info(self, material_name):
        self.db_mat_w = self.get_table("list_compo_window")

        # Check if the material_name exists in the DataFrame
        if material_name in self.db_mat_w['compo_windows'].values:
            material_info = self.db_mat_w[self.db_mat_w['compo_windows'] == material_name].iloc[0]
            # Extract relevant columns
            mat_info_w = [
                {
                    "Name": material_info['compo_windows'],
                    "UFactor": material_info['U'],
                    "Solar_Heat_Gain_Coefficient": material_info['tl'],
                    "Visible_Transmittance": material_info['fs'],
                }
            ]
        else:
            print(f"Material '{material_name}' not found in list_compo_window DataFrame.")
            mat_info_w = []

        return mat_info_w

    def add_variant_building(self):
        try:
            variant_building_df = self.get_table("Renovation config_wall")

            for index, row in variant_building_df.iterrows():
                orientation = row["Opaque_orientation"]
                composition = [
                    {"Name": layer}
                    for column_name, layer in row.items()
                    if "layer" in column_name.lower() and pd.notna(layer)
                ]

                # Determine the face filter based on orientation
                if "south" in orientation.lower():
                    face_filter = "Face1"
                elif "west" in orientation.lower():
                    face_filter = "Face2"
                elif "north" in orientation.lower():
                    face_filter = "Face3"
                elif "east" in orientation.lower():
                    face_filter = "Face4"
                else:
                    face_filter = ""

                mat_info_walls = [self.get_material_opaque_info(layer["Name"]) for layer in composition]

                # Build the dictionary entry for each orientation
                variant_key = f"RENOVATION_walls_{orientation.lower()}"
                if variant_key not in self.VARIANT_DICT:
                    self.VARIANT_DICT[variant_key] = {
                        "VariantKeys.MODIFIER": f"walls_{orientation.lower()}",
                        "VariantKeys.ARGUMENTS": {
                            "name_filter": face_filter
                        },
                        "VariantKeys.DESCRIPTION": {
                            variant_key: mat_info_walls
                        }
                    }
        except Exception as e:
            print(f"Error adding existing data: {e}")
