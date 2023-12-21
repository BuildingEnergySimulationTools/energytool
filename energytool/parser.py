import pandas as pd
from pathlib import Path
from corrai.variant import VariantKeys


class ExcelVariantFiller:
    def __init__(self, excel_file_path, tab_name, variant_dict):
        self.excel_file_path = Path(excel_file_path)
        self.tab_name = tab_name
        self.variant_dict = variant_dict
        self.result_dict = None

    def load_excel_data(self):
        try:
            # Load the Excel file
            xl = pd.ExcelFile(self.excel_file_path)

            # Parse the specified tab
            df = xl.parse(self.tab_name)

            # Create a dictionary with material information
            self.result_dict = {}
            for index, row in df.iterrows():
                name = row['Name']
                thickness = row.get('Thickness (m)', None)
                conductivity = row.get('Conductivity (W/m.K)', None)
                density = row.get('Density (kg/m3)', None)
                specific_heat = row.get('Specific Heat (J/kg.K)', None)

                info = {
                    "Name": name,
                    "Thickness": thickness,
                    "Conductivity": conductivity,
                    "Density": density,
                    "Specific_Heat": specific_heat,
                }

                self.result_dict[name] = info

        except Exception as e:
            print(f"An error occurred while loading Excel data: {e}")

    def fill_variant_dict(self):
        try:
            # Check if result_dict is loaded
            if self.result_dict is None:
                print("Please call load_excel_data() before fill_variant_dict().")
                return

            # Iterate through VARIANT_DICT and update with missing information
            for variant_key, variant_info in self.variant_dict.items():
                description = variant_info.get(VariantKeys.DESCRIPTION, {})
                for sub_key, sub_info in description.items():
                    if isinstance(sub_info, list):
                        for item in sub_info:
                            material_name = item.get("Name")
                            if material_name in self.result_dict:
                                material_info = self.result_dict[material_name]
                                item.update(material_info)
                            else:
                                print(f"Material {material_name} not found in result_dict.")

        except Exception as e:
            print(f"An error occurred while filling VARIANT_DICT: {e}")
