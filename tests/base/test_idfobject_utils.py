import datetime as dt

import pytest
from io import StringIO
from eppy.modeleditor import IDF

import energytool.base
from energytool.base.idf_utils import get_named_objects_field_values
from energytool.base.idfobject_utils import (
    set_timestep,
    set_run_period,
    get_number_of_people,
    add_hourly_schedules_from_df,
    add_output_variable,
    add_natural_ventilation,
)


@pytest.fixture(scope="session")
def toy_idf(tmp_path_factory):
    empty_idf = ""
    handle = StringIO(empty_idf)
    toy_idf = IDF(handle)

    for toy_zone in range(10):
        toy_idf.newidfobject("Zone", Name=f"Zone_{toy_zone}", Floor_Area=10)

    return toy_idf


class TestIdfObjectUtils:
    def test_add_output_zone_variable(self, toy_idf):
        add_output_variable(toy_idf, key_values="Zone_1", variables="Conso")

        to_test = [elmt["obj"] for elmt in toy_idf.idfobjects["Output:Variable"]]
        ref = [["OUTPUT:VARIABLE", "Zone_1", "Conso", "Hourly"]]
        assert to_test == ref

        add_output_variable(toy_idf, key_values=["Zone_1", "Zone_2"], variables="Conso")

        to_test = [elmt["obj"] for elmt in toy_idf.idfobjects["Output:Variable"]]
        ref = [
            ["OUTPUT:VARIABLE", "Zone_1", "Conso", "Hourly"],
            ["OUTPUT:VARIABLE", "Zone_2", "Conso", "Hourly"],
        ]
        assert to_test == ref

        add_output_variable(toy_idf, key_values="Zone_3", variables=["Conso", "Elec"])

        to_test = [elmt["obj"] for elmt in toy_idf.idfobjects["Output:Variable"]]
        ref = [
            ["OUTPUT:VARIABLE", "Zone_1", "Conso", "Hourly"],
            ["OUTPUT:VARIABLE", "Zone_2", "Conso", "Hourly"],
            ["OUTPUT:VARIABLE", "Zone_3", "Conso", "Hourly"],
            ["OUTPUT:VARIABLE", "Zone_3", "Elec", "Hourly"],
        ]
        assert to_test == ref

        add_output_variable(toy_idf, key_values="*", variables="Conso")

        to_test = [elmt["obj"] for elmt in toy_idf.idfobjects["Output:Variable"]]
        ref = [
            ["OUTPUT:VARIABLE", "Zone_3", "Elec", "Hourly"],
            ["OUTPUT:VARIABLE", "*", "Conso", "Hourly"],
        ]
        assert to_test == ref

    def test_set_run_period(self, toy_idf):
        toy_idf.newidfobject("RunPeriod")

        ref = [
            "RUNPERIOD",
            "run_period",
            1,
            1,
            2009,
            12,
            31,
            2009,
            "Thursday",
            "No",
            "No",
            "Yes",
            "Yes",
            "Yes",
            "No",
        ]

        set_run_period(
            toy_idf,
            simulation_start=dt.datetime(2009, 1, 1, 0, 0, 0),
            simulation_stop=dt.datetime(2009, 12, 31, 23, 0, 0),
        )

        to_test = toy_idf.idfobjects["RunPeriod"][0]

        assert to_test.fieldvalues == ref

    def test_set_timestep(self, toy_idf):
        ref = ["TIMESTEP", 6]

        set_timestep(toy_idf, nb_timestep_per_hour=6)
        to_test = toy_idf.idfobjects["Timestep"][0].fieldvalues

        assert to_test == ref

    def test_get_number_of_people(self, toy_idf):
        configurations = [
            [
                ("Number_of_People_Calculation_Method", "People/Area"),
                ("People_per_Zone_Floor_Area", 0.5),
            ],
            [
                (
                    "Number_of_People_Calculation_Method",
                    "People",
                ),
                ("Number_of_People", 2),
            ],
            [
                ("Number_of_People_Calculation_Method", "Area/Person"),
                ("Zone_Floor_Area_per_Person", 2),
            ],
        ]

        for z in toy_idf.idfobjects["Zone"]:
            z.Floor_Area = 10

        zone_name_iterator = (z.Name for z in toy_idf.idfobjects["Zone"])

        for config in configurations:
            zne = next(zone_name_iterator)
            new_people = toy_idf.newidfobject(
                "People",
                Name=f"People_{zne}",
                Zone_or_ZoneList_Name=zne,
            )
            new_people[config[0][0]] = config[0][1]
            new_people[config[1][0]] = config[1][1]

        assert get_number_of_people(toy_idf) == 12.0

        assert get_number_of_people(toy_idf, zones=["Zone_1", "Zone_2"]) == 7.0

    def test_add_add_natural_ventilation(self):
        empty_idf = ""
        handle = StringIO(empty_idf)
        toy_idf = IDF(handle)

        for toy_zone in range(5):
            toy_idf.newidfobject("Zone", Name=f"Zone_{toy_zone}", Floor_Area=10)

        for _, z_name in zip(range(3), toy_idf.idfobjects["Zone"]):
            toy_idf.newidfobject(
                "People",
                Zone_or_ZoneList_Name=z_name.Name,
                Number_of_People_Schedule_Name="people_sched",
            )

        add_natural_ventilation(toy_idf, ach=0.7)

        # Test only occupied zone have ventilation
        assert len(toy_idf.idfobjects["ZoneVentilation:DesignFlowrate"]) == 3
        assert toy_idf.idfobjects["ZoneVentilation:DesignFlowrate"][0].obj == [
            "ZONEVENTILATION:DESIGNFLOWRATE",
            "Natvent_Zone_0",
            "Zone_0",
            "people_sched",
            "AirChanges/Hour",
            0.7,
            "",
            "",
            "",
            "Natural",
            0.0,
            1.0,
            1.0,
            0.0,
            0.0,
            0.0,
            22,
            "",
            100.0,
            "",
            0,
            "",
            -100.0,
            "",
            100.0,
            "",
            40.0,
        ]

        # Test constant ACH addition for all zones
        add_natural_ventilation(toy_idf, ach=0.7, occupancy_schedule=False)
        assert len(toy_idf.idfobjects["ZoneVentilation:DesignFlowrate"]) == 5
        assert toy_idf.idfobjects["Schedule:Compact"][0].obj == [
            "SCHEDULE:COMPACT",
            "On 24/7",
            "Any Number",
            "Through: 12/31",
            "For: AllDays",
            "Until: 24:00",
            1,
        ]

        # Check ventilation and schedule do not duplicate
        add_natural_ventilation(toy_idf, ach=0.7, occupancy_schedule=False)
        assert len(toy_idf.idfobjects["ZoneVentilation:DesignFlowrate"]) == 5
        assert toy_idf.idfobjects["Schedule:Compact"][0].obj == [
            "SCHEDULE:COMPACT",
            "On 24/7",
            "Any Number",
            "Through: 12/31",
            "For: AllDays",
            "Until: 24:00",
            1,
        ]

        # Check kwargs
        add_natural_ventilation(
            toy_idf, ach=0.7, occupancy_schedule=False, kwargs={"Fan_Pressure_Rise": 10}
        )

        assert (
            get_named_objects_field_values(
                toy_idf, "ZoneVentilation:DesignFlowrate", "Fan_Pressure_Rise"
            )
            == [10] * 5
        )

        # Check one zone modification
        add_natural_ventilation(
            toy_idf, zones="zone_0", ach=0.8, occupancy_schedule=False
        )

        assert (
            toy_idf.idfobjects["ZoneVentilation:DesignFlowrate"][-1].Design_Flow_Rate
            == 0.8
        )
