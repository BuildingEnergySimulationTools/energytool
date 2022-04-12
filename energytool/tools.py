def format_input_to_list(f_input):
    """
    Convert a string into a list
    return f_input if f_input is a list
    else raise ValueError

    :param f_input:
    :return: list
    """
    if isinstance(f_input, str):
        return [f_input]
    elif isinstance(f_input, list):
        return f_input
    else:
        raise ValueError("Input must be a string or a list of string")


def value_in_object_fieldnames(idf, idf_object, field_name, values):
    """
    :param values:
    :param idf:
    :param idf_object
    :param field_name:
    :return: list of Boolean.

    For  each instance of the idf_object in the idf.
    Return True if specific field_name as variables value
    """
    idf_object = idf_object.upper()
    values_list = format_input_to_list(values)

    try:
        outputs = idf.idfobjects[idf_object]
    except KeyError:
        outputs = []

    var_in_idf = [out[field_name] for out in outputs]

    return [
        True if elmt in values_list
        else False
        for elmt in var_in_idf]
