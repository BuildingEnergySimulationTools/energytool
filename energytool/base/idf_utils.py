import eppy
from eppy.modeleditor import IDF
import eppy.json_functions as json_functions

from energytool.tools import is_items_in_list, to_list


def getidfvalue(idf, param_key: str):
    """
    Get value from IDF object using a dotted key string, compatible with Eppy.
    Supports wildcard '*' for object name.
    """
    idftag, obj_type, obj_name, field = json_functions.key2elements(param_key)

    if idftag != "idf":
        raise ValueError(f"Unsupported prefix '{idftag}' in key: {param_key}")

    if obj_name == "*":
        idfobjs = idf.idfobjects[obj_type.upper()]
        return [obj[field] for obj in idfobjs if field in obj.fieldnames]
    else:
        obj = idf.getobject(obj_type.upper(), obj_name)
        if obj is None:
            raise KeyError(
                f"Object '{obj_name}' of type '{obj_type}' not found in IDF."
            )
        if field not in obj.fieldnames:
            raise KeyError(f"Field '{field}' not found in object '{obj_name}'.")
        return obj[field]


def get_objects_name_list(idf: IDF, idf_object: str):
    """
    Get a list of names of objects of a specified type in an EnergyPlus IDF file.

    :param idf: An EnergyPlus IDF object.
    :param idf_object: The name of the EnergyPlus object type for which to retrieve
        names.
    :return: A list of names of objects of the specified type in the IDF file.

    The function accesses objects of the given `idf_object` type in the IDF file and
    returns a list of their names.
    """
    return [obj.Name for obj in idf.idfobjects[idf_object]]


def get_named_objects(idf: IDF, idf_object: str, names: str | list):
    """
    Get specific named objects of a given type from an EnergyPlus IDF file.

    This function retrieves specific named objects of the specified EnergyPlus object
    type from an IDF file.

    :param idf: An EnergyPlus IDF object.
    :param idf_object: The name of the EnergyPlus object type from which to retrieve
        objects.
    :param names: The names of the specific objects to retrieve, either as a string
        or a list of strings.
    :return: A list of EnergyPlus objects that match the specified names.

    The function searches for objects of the given `idf_object` type in the IDF file and
    returns a list of objects whose names match the names provided in the `names`
    parameter.
    """
    names_list = to_list(names)
    objects_list = idf.idfobjects[idf_object]
    return [obj for obj in objects_list if obj.Name in names_list]


def get_building_surface_area(idf: IDF, outside_boundary_condition: str):
    """
    Return specific outside_boundary_condition building surface area
    """

    return sum(
        [
            o.area
            for o in idf.idfobjects["BuildingSurface:Detailed"]
            if o.Outside_Boundary_Condition == outside_boundary_condition
        ]
    )


def get_building_volume(idf: IDF):
    """Return volume based on zones volumes"""
    return sum(
        [
            eppy.modeleditor.zonevolume(idf, zname)
            for zname in get_objects_name_list(idf, "Zone")
        ]
    )


def is_value_in_objects_fieldname(
    idf: IDF,
    idf_object: str,
    field_name: str,
    values: float | int | str | list[float | int | str],
):
    """
    This function checks whether the specified values are present in the specified field
    of each instance of the specified EnergyPlus object type in the IDF file.

    :param idf: An EnergyPlus IDF object.
    :param idf_object: The name of the EnergyPlus object type to check.
    :param field_name: The name of the field within the object to check for values.
    :param values: The values to check for in the field.
    :return: A list of Boolean values, where each element corresponds to an instance
        of the specified EnergyPlus object type. True indicates that the value was found
        in the field, and False indicates that it was not found.

    For each instance of the `idf_object` in the IDF, this function checks if the
    specified `field_name` has the specified `values` as its variable value.

    Example:
    ```
    idf = IDF("example.idf")
    result = is_value_in_objects_fieldname(idf, "Zone", "ZoneName", ["Zone1", "Zone2"])
    # Returns [True, False] if "Zone1" is found in the "ZoneName" field of the first
    # instance and "Zone2" is not found in the field of the second instance.
    ```
    """
    values_list = to_list(values)
    obj_list = idf.idfobjects[idf_object]
    var_in_idf = [obj[field_name] for obj in obj_list]

    return is_items_in_list(var_in_idf, values_list)


def set_named_objects_field_values(
    idf: IDF,
    idf_object: str,
    field_name: str,
    values: str | float | list[str | float],
    idf_object_names: str | list = "*",
):
    """
    Set field values for one or more objects in an EnergyPlus IDF file.

    This function allows you to set the values of a specific field for multiple objects
    in an EnergyPlus IDF file. You can specify the objects and their names, the field
    name, and the values to set.

    :param idf: An EnergyPlus IDF object.
    :param idf_object: The name of the EnergyPlus object type for which to set values.
    :param field_name: The name of the field within the object to set.
    :param values: The value or list of values to set for the field.
    :param idf_object_names: (Optional) The names of the specific objects to update.
        By default, "*" is used to update all objects of the specified type.
    :return: None

    :raises ValueError: If the length of `values` and `idf_object_names` lists
        is not the same when updating multiple objects.
    """
    if idf_object_names == "*":
        idf_object_names_list = get_objects_name_list(idf, idf_object)
    else:
        idf_object_names_list = to_list(idf_object_names)

    values_list = to_list(values)
    if len(values_list) == 1:
        values_list = values_list * len(idf_object_names_list)

    if len(idf_object_names_list) != len(values_list):
        raise ValueError(
            "values and idf_object_names list must be of the "
            "same length. Or values must be a single object"
        )

    for obj_name, value in zip(idf_object_names_list, values_list):
        _set_named_object_field_value(idf, idf_object, obj_name, field_name, value)


def _set_named_object_field_value(
    idf, idf_object: IDF, name: str, field_name: str, value
):
    """
    Set the value of a field for a specific object in an EnergyPlus IDF file.

    This function allows you to set the value of a specific field for a particular
    object in an EnergyPlus IDF file. You need to specify the IDF object type, the
    object's name, the field name, and the value to set.

    :param idf: An EnergyPlus IDF object.
    :param idf_object: The name of the EnergyPlus object type to which the object belongs.
    :param name: The name of the specific object you want to update.
    :param field_name: The name of the field within the object to set.
    :param value: The value to set for the specified field.
    :return: None

    :raises ValueError: If the specified IDF object type is not found in the IDF file.
    """
    obj_list = idf.idfobjects[idf_object]
    if not obj_list:
        raise ValueError(f"{idf_object} not found in idf file")

    for obj in obj_list:
        if obj["Name"] == name:
            obj[field_name] = value


def get_named_objects_field_values(
    idf: IDF, idf_object: str, field_name: str, names: str | list = "*"
):
    """
    This function allows you to retrieve the values of a specific field for one or more
    named objects of a particular EnergyPlus object type in an IDF file.

    :param idf: An EnergyPlus IDF object.
    :param idf_object: The name of the EnergyPlus object type for which to retrieve values.
    :param field_name: The name of the field within the object from which to retrieve values.
    :param names: (Optional) The names of the specific objects for which to retrieve values.
        By default, "*" is used to retrieve values for all objects of the specified type.
    :return: A list of field values corresponding to the specified named objects.

    :raises ValueError: If the specified IDF object type is not found in the IDF file.
    """
    if names == "*":
        idf_object_names_list = get_objects_name_list(idf, idf_object)
    else:
        idf_object_names_list = to_list(names)

    return [
        _get_named_object_field_value(idf, idf_object, obj_name, field_name)
        for obj_name in idf_object_names_list
    ]


def _get_named_object_field_value(
    idf: IDF, idf_object: str, name: str, field_name: str
):
    obj_list = idf.idfobjects[idf_object]
    if not obj_list:
        raise ValueError(f"{idf_object} not found in idf file")

    for obj in obj_list:
        if obj.Name == name:
            return obj[field_name]


def del_named_objects(idf: IDF, idf_object: str, names: str | list = "*"):
    """
    Delete specific named objects of a given type from an EnergyPlus IDF file.

    This function allows you to remove one or more named objects of a specified
    EnergyPlus object type from an IDF file.

    :param idf: An EnergyPlus IDF object.
    :param idf_object: The name of the EnergyPlus object type from which to delete
        objects.
    :param names: (Optional) The names of the specific objects to delete.
        By default, "*"
        is used to delete all objects of the specified type.
    :return: None

    If the `names` parameter is set to "*", all objects of the specified type are
    deleted. Otherwise, the function removes only the named objects specified in
    the `names` list.
    """
    if names == "*":
        idf.idfobjects[idf_object] = []
    else:
        name_list = to_list(names)
        obj_to_remove = [idf.getobject(idf_object, name) for name in name_list]
        obj_list = idf.idfobjects[idf_object]

        idf.idfobjects[idf_object] = [o for o in obj_list if o not in obj_to_remove]


def copy_named_object_from_idf(
    source_idf: IDF, destination_idf: IDF, idf_object: str, name: str
):
    """
    This function allows you to copy a specific named object of a specified EnergyPlus
    object type from a source IDF file to a destination IDF file.

    :param source_idf: The source EnergyPlus IDF object from which to copy the object.
    :param destination_idf: The destination EnergyPlus IDF object to which the object
        should be copied.
    :param idf_object: The name of the EnergyPlus object type to which the object belongs.
    :param name: The name of the specific object to copy.
    :return: None

    The function retrieves the named object from the source IDF and copies it to the
    destination IDF if it is not already present in the destination IDF.

    Note: The function assumes that the object name is unique within the specified
    EnergyPlus object type.
    """
    # Get schedule in resources file
    obj_to_copy = source_idf.getobject(idf_object, name)

    # Copy in building idf if not already present
    destination_obj_list = destination_idf.idfobjects[idf_object]

    if obj_to_copy.Name not in get_objects_name_list(destination_idf, idf_object):
        destination_obj_list.append(obj_to_copy)
