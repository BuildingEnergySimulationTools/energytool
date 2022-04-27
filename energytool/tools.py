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
