def is_alphanumeric(value: str):
    return value.replace(" ", "").replace("_", "").replace("-", "").replace("(", "").replace(")", "").isalnum()
