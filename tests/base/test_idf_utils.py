from io import StringIO
from pathlib import Path

import pytest
import eppy

from eppy.modeleditor import IDF

from energytool.base.idf_utils import (
    get_objects_name_list,
    set_named_objects_field_values,
    get_named_objects,
    get_named_objects_field_values,
    del_named_objects,
)

TEST_RESOURCES_PATH = Path(__file__).parent.parent / "resources"

try:
    IDF.setiddname((TEST_RESOURCES_PATH / "Energy+.idd").as_posix())
except eppy.modeleditor.IDDAlreadySetError:
    pass


@pytest.fixture(scope="session")
def toy_idf(tmp_path_factory):
    empty_idf = ""
    handle = StringIO(empty_idf)
    toy_idf = IDF(handle)

    for toy_zone in range(10):
        toy_idf.newidfobject("Zone", Name=f"Zone_{toy_zone}", Floor_Area=10)

    return toy_idf


class TestIdfObjectUtils:
    def test_get_objects_name_list(self, toy_idf):
        to_test = get_objects_name_list(toy_idf, "Zone")
        assert to_test == [f"Zone_{i}" for i in range(10)]

    def test_set_objects_field_values(self, toy_idf):
        zone_list = toy_idf.idfobjects["Zone"]

        set_named_objects_field_values(
            idf=toy_idf, idf_object="Zone", field_name="Floor_Area", values=42
        )

        to_test = [z.Floor_Area for z in zone_list]

        # Test for all object
        assert to_test == [42] * 10

        # Test by object with a single Name
        set_named_objects_field_values(
            idf=toy_idf,
            idf_object="Zone",
            idf_object_names="Zone_0",
            field_name="Floor_Area",
            values=4.2,
        )

        to_test = [z.Floor_Area for z in zone_list]

        assert to_test == [4.2] + [42] * 9

        # Test by object with multiple Names
        set_named_objects_field_values(
            idf=toy_idf,
            idf_object="Zone",
            idf_object_names=["Zone_0", "Zone_1"],
            field_name="Floor_Area",
            values=4.2,
        )

        to_test = [z.Floor_Area for z in zone_list]

        assert to_test == [4.2, 4.2] + [42] * 8

        # Test by object with multiple Names multiple values
        set_named_objects_field_values(
            idf=toy_idf,
            idf_object="Zone",
            idf_object_names=["Zone_0", "Zone_1"],
            field_name="Floor_Area",
            values=[33, 33],
        )

        to_test = [z.Floor_Area for z in zone_list]

        assert to_test == [33, 33] + [42] * 8

    def test_get_objects_by_names(self, toy_idf):
        res_to_test = get_named_objects(toy_idf, "Zone", ["Zone_0", "Zone_1"])

        ref = toy_idf.idfobjects["Zone"][:2]

        assert res_to_test == ref

    def test_get_named_objects_field_values(self):
        idf = IDF(TEST_RESOURCES_PATH / "test.idf")

        all_materials_test = get_named_objects_field_values(
            idf=idf, idf_object="Material", field_name="Conductivity"
        )

        assert all_materials_test == [
            0.04,
            1.13,
            0.41,
            1.4,
            0.25,
            0.51,
            0.04,
            0.7,
            0.04,
            0.25,
        ]

        three_materials_test = get_named_objects_field_values(
            idf=idf,
            idf_object="Material",
            field_name="Conductivity",
            names=[
                "Floor/Roof Screed_.03",
                "Cast Concrete (Dense)_.1",
                "Gypsum Plasterboard_.025",
            ],
        )

        assert three_materials_test == [0.41, 1.4, 0.25]

    def test_del_obj_by_names(self, toy_idf):
        del_named_objects(toy_idf, "Zone", ["Zone_0", "Zone_1"])
        zone_name_list = get_objects_name_list(toy_idf, "Zone")
        assert zone_name_list == [
            "Zone_2",
            "Zone_3",
            "Zone_4",
            "Zone_5",
            "Zone_6",
            "Zone_7",
            "Zone_8",
            "Zone_9",
        ]

        del_named_objects(toy_idf, "Zone", "*")
        zone_name_list = get_objects_name_list(toy_idf, "Zone")
        assert zone_name_list == []
