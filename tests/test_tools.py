import energytool.tools as tl


class TestTools:
    def test_select_by_strings(self):
        test_name_list = [
            "Zone_1:control",
            "Zone_2:control",
            "control:Zone_1",
            "control:Zone_2control"
        ]

        to_test = tl.select_by_strings(
            items_list=test_name_list, select_by="*")

        assert to_test == test_name_list

        to_test = tl.select_by_strings(
            items_list=test_name_list, select_by="Zone_1")

        assert to_test == ["Zone_1:control", "control:Zone_1"]

        to_test = tl.select_by_strings(
            items_list=test_name_list, select_by=["Zone_1", "Zone_2"])

        assert to_test == ['Zone_1:control', 'control:Zone_1',
                           'Zone_2:control', 'control:Zone_2control']