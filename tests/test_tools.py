import energytool.tools as tl


class TestTools:
    def test_select_by_strings(self):
        test_name_list = [
            "Zone_1:control",
            "Zone_2:control",
            "control:Zone_1",
            "control:Zone_2control",
        ]

        to_test = tl.select_in_list(target_list=test_name_list, target="*")

        assert to_test == test_name_list

        to_test = tl.select_in_list(target_list=test_name_list, target="Zone_1")

        assert to_test == ["Zone_1:control", "control:Zone_1"]

        to_test = tl.select_in_list(
            target_list=test_name_list, target=["Zone_1", "Zone_2"]
        )

        assert to_test == [
            "Zone_1:control",
            "control:Zone_1",
            "Zone_2:control",
            "control:Zone_2control",
        ]

    def test_hourly_lst_from_dict(self):
        day_config = {6: 15, 18: 19, 24: 15}

        ref = [
            15,
            15,
            15,
            15,
            15,
            15,
            19,
            19,
            19,
            19,
            19,
            19,
            19,
            19,
            19,
            19,
            19,
            19,
            15,
            15,
            15,
            15,
            15,
            15,
        ]

        to_test = tl.hourly_lst_from_dict(day_config)

        assert ref == to_test

    def test_scheduler(self):
        week_day = {6: 15, 18: 19, 24: 15}
        weekend = {24: 19}
        summer = {24: -50}

        test_scheduler = tl.Scheduler(name="test", year=2009)
        test_scheduler.add_day_in_period(
            start="2009-01-01",
            end="2009-12-31",
            days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            hourly_dict=week_day,
        )

        test_scheduler.add_day_in_period(
            start="2009-01-01",
            end="2009-12-31",
            days=["Saturday", "Sunday"],
            hourly_dict=weekend,
        )

        test_scheduler.add_day_in_period(
            start="2009-04-01",
            end="2009-09-30",
            days=[
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ],
            hourly_dict=summer,
        )

        ref = [
            15.0,
            15.0,
            15.0,
            15.0,
            15.0,
            15.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            15.0,
            15.0,
            15.0,
            15.0,
            15.0,
            15.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
        ]

        assert ref == list(test_scheduler.series.loc["2009-01-02":"2009-01-03"])
