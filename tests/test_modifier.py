from io import StringIO
from pathlib import Path

import energytool.epluspreprocess as pr

import pytest
import eppy

from eppy.modeleditor import IDF
from energytool.building import Building
from energytool.modifier import OpaqueSurfaceModifier

RESOURCES_PATH = Path(__file__).parent / "resources"

try:
    IDF.setiddname(RESOURCES_PATH / 'Energy+.idd')
except eppy.modeleditor.IDDAlreadySetError:
    pass

Building.set_idd(RESOURCES_PATH)


@pytest.fixture(scope="session")
def toy_building(tmp_path_factory):
    empty_idf = ""
    handle = StringIO(empty_idf)
    toy_idf = IDF(handle)

    for toy_surf in range(5):
        toy_idf.newidfobject(
            "BuildingSurface:Detailed",
            Name=f"Surface_{toy_surf}",
        )

    pr.set_objects_field_values(
        idf=toy_idf,
        idf_object="BuildingSurface:Detailed",
        field_name="Surface_Type",
        values=["Wall", "Wall", "Floor", "Ceiling", "Roof"]
    )

    pr.set_objects_field_values(
        idf=toy_idf,
        idf_object="BuildingSurface:Detailed",
        field_name="Outside_Boundary_Condition",
        values=["Outdoors", "Surface", "Ground", "Surface", "Outdoors"]
    )

    # Very dirty, instantiate a Building with and idf file
    # Replace it wih toy_idf
    toy_building = Building(idf_path=RESOURCES_PATH / "test.idf")
    toy_building.idf = toy_idf

    return toy_building


class TestModifier:
    def test_opaque_surface_modifier(self, toy_building):
        construction_variant_dict = {
            "test_base": [
                {
                    "Name": "Coating",
                    "Thickness": 0.01,
                    "Conductivity": 0.1,
                    "Density": 400,
                    "Specific_Heat": 1200,
                },
                {
                    "Name": "Laine_15cm",
                    "Thickness": 0.15,
                    "Conductivity": 0.032,
                    "Density": 40,
                    "Specific_Heat": 1000,
                },
            ],
            "test_1_layer": [
                {
                    "Name": "Coating_2",
                    "Thickness": 0.01,
                    "Conductivity": 0.1,
                    "Density": 400,
                    "Specific_Heat": 1200,
                },
            ]
        }

        ext_walls_mod = OpaqueSurfaceModifier(
            building=toy_building,
            name="Ext_wall_modification",
            surface_type="Wall",
            outside_boundary_condition="Outdoors",
            construction_variant_dict=construction_variant_dict
        )

        # Test general case
        ext_walls_mod.set_variant("test_base")
        material_list = toy_building.idf.idfobjects["Material"]
        assert material_list[0]['obj'] == [
            'MATERIAL', 'Coating', 'Rough', 0.01, 0.1, 400, 1200, 0.9, 0.7, 0.7]
        assert pr.get_objects_name_list(toy_building.idf, "Material") == [
            'Coating', 'Laine_15cm']

        construction_list = toy_building.idf.idfobjects["Construction"]
        assert construction_list[0]['obj'] == [
            'CONSTRUCTION', 'test_base', 'Coating', 'Laine_15cm']

        to_test = pr.get_objects_field_values(
            idf=toy_building.idf,
            idf_object="BuildingSurface:Detailed",
            field_name="Construction_Name"
        )
        assert to_test == ['test_base', '', '', '', '']

        # Test single layer construction
        ext_walls_mod.set_variant("test_1_layer")
        assert construction_list[-1]['obj'] == [
            'CONSTRUCTION', 'test_1_layer', 'Coating_2']

        # No duplication
        ext_walls_mod.set_variant("test_1_layer")
        assert pr.get_objects_name_list(toy_building.idf, "Material") == [
            'Coating', 'Laine_15cm', 'Coating_2']