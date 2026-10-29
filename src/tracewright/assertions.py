from .models import Assertion


def check(output, assertion: Assertion) -> bool:
    try:
        value = output
        for part in assertion.path:
            if isinstance(value, list) and (type(part) is not int or part < 0):
                return False
            value = value[part]
        if assertion.kind == "equals":
            return type(value) is type(assertion.expected) and value == assertion.expected
        if assertion.kind == "contains":
            return isinstance(value, (str, list, dict)) and assertion.expected in value
        types = {"string": str, "number": (int, float), "boolean": bool,
                 "object": dict, "array": list, "null": type(None)}
        return type(value) in (types[assertion.expected] if isinstance(types[assertion.expected], tuple)
                               else (types[assertion.expected],))
    except (KeyError, IndexError, TypeError):
        return False
