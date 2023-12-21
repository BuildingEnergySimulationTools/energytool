import pandas as pd
from pathlib import Path

class ExcelParser:
    def __init__(self, excel_file_path, tab_name):
        self.excel_file_path = Path(excel_file_path)
        self.tab_name = tab_name
        self.tables = {}

    def load_excel_data(self):
        try:
            # Load Excel file and tab
            xl = pd.ExcelFile(self.excel_file_path)
            df = xl.parse(self.tab_name, skiprows=None, header=None)

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

