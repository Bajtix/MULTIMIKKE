def is_alphanumeric(value: str):
    return value.replace(" ", "").replace("_", "").replace("-", "").replace("(", "").replace(")", "").isalnum()


def validate_spinbox(a, new_value):
    return new_value.isdigit()
