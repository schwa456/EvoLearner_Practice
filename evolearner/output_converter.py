import re

# output file의 text를 DL 표현으로 변환
def parse_expression(expr):
    """
    Parse the expression into a nested structure
    expr : string, expression to be parsed
    """
    stack = []
    current = []
    token = ""

    for char in expr:
        if char == '(':
            if token:
                current.append(token.strip())
                token = ""
            stack.append(current)
            current = []
        elif char == ')':
            if token:
                current.append(token.strip())
                token = ""
            last = current
            current = stack.pop()
            current.append(last)
        elif char == ',':
            if token:
                current.append(token.strip())
                token = ""
        elif char == ' ':
            pass
        else:
            token += char
    if token:
        current.append(token.strip())

    return current[0] if not current else current


def transform_expression(parsed):
    """
    Transform the parsed expression into DL representation
    parsed : nested structure, parsed expression
    """
    if isinstance(parsed, str):
        return parsed
    if len(parsed) == 1:
        return parsed[0]

    operator_map = {
        "intersection": "⊓",
        "union": "⊔",
        "in": "in",
        "hasValue": "=",
    }

    restriction_map = {
        "exists": "∃",
        "someValuesG": ".≥",
        "cargeq": "≥",
        "negation": "¬"
    }
    """
    if isinstance(parsed[0], list):
        left = transform_expression(parsed[0])
        print('left', left)
        right = transform_expression(parsed[1])
        print('right', right)
        return '.'.join([left, right])
    """

    if parsed[0] in operator_map:
        operator = parsed[0]
        if operator in operator_map:
            if operator == "intersection" or operator == "union":
                # intersection (A ⊓ B)
                if isinstance(parsed[1], list):
                    if len(parsed[1]) == 3:
                        left = transform_expression(parsed[1][0])
                        right = transform_expression(parsed[1])
                        return f"({f' {operator_map[operator]} '.join([left, right])})"
                    elif len(parsed[1]) == 4:
                        left = transform_expression(parsed[1][0:2])
                        right = transform_expression(parsed[1][2:4])
                        return f"({f' {operator_map[operator]} '.join([left, right])})"
                else:
                    return parsed
        else:
            raise ValueError(f"Unknown operator: {operator} or Invalid Structure : {parsed}")

    elif parsed[0].startswith('exists'):
        restriction = 'exists'
        if restriction == "exists":
            # exists relationships are binary: ∃relation.(concept)
            if len(parsed) >= 2:
                return f"{restriction_map[restriction]}{parsed[0][6:]}.{transform_expression(parsed[1])}"
            else:
                raise ValueError(f"Invalid 'exists' structure : {parsed}")

    else:
        return transform_expression(parsed[1:])

def convert_into_DL_format(expression):
    """
    Convert the expression into DL representation
    expression : string, expression to be converted
    """
    parsed = parse_expression(expression)[:-1]
    return transform_expression(parsed)

def final_converter(text):
    operator_map = {
        "intersection": "⊓",
        "union": "⊔",
        "exists": "∃",
        "someValuesG": ".≥",
        "cargeq": "≥",
        "in": "in",
        "hasValue": "=",
        "negation": "¬"
    }

    # Recursive function to apply replacement
    def apply_transform(expr):
        """
        Handle the outermost operation
        :param expr: expression
        """

        for op, symbol in operator_map.items():
            expr = re.sub(op, symbol, expr)

        return expr

    # Apply transformations
    transformed = apply_transform(text)

    # Additional fixes for nested parenthesis and spacing
    transformed = re.sub(r'\s+', ' ', transformed)  # Remove extra spaces
    transformed = re.sub(r'\(\s+', '(', transformed)  # Remove space after '('
    transformed = re.sub(r'\s+\)', ')', transformed)  # Remove space before ')'

    return transformed

def converting_into_DL_formula(data_name):
    file_path_for_colab = f"/content/EvoLearner_Practice/evolearner/workdir/output_{data_name}.txt"
    file_path_for_local = f"./workdir/output_{data_name}.txt"

    with open(file_path_for_local, "r") as f:
        text = f.read()
        converting = convert_into_DL_format(text)
        result = final_converter(converting)
        return result

def __main__():
    print(converting_into_DL_formula("family"))

if __name__ == "__main__":
    __main__()
