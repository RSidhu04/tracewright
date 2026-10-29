"""Offline calculator agent. Credentials in emitted traces are deliberately fake."""
import math
import operator

OPERATIONS = {'add': operator.add, 'subtract': operator.sub,
              'multiply': operator.mul, 'divide': operator.truediv}


def calculate(inputs):
    operation = inputs.get('operation', 'add')
    if operation not in OPERATIONS:
        return {'error': 'unsupported_operation'}
    a, b = inputs.get('a'), inputs.get('b')
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in (a, b)):
        return {'error': 'invalid_operand'}
    if operation == 'divide' and b == 0:
        return {'error': 'division_by_zero'}
    answer = OPERATIONS[operation](a, b)
    if not math.isfinite(answer):
        return {'error': 'nonfinite_result'}
    return {'answer': answer}


def baseline(inputs, trace, seed):
    trace.emit('tool.call', {'tool': 'calculator', 'arguments': inputs, 'api_key': 'demo-secret'})
    output = calculate(inputs)
    trace.emit('tool.result', output)
    return output


def candidate(inputs, trace, seed):
    output = baseline(inputs, trace, seed)
    # Deliberately broken presentation policy: loses negative signs for every operation.
    if 'answer' in output:
        output['answer'] = abs(output['answer'])
    return output
