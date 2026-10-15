def infer(model_input, configuration):
    import math
    if configuration['mode'] != 'offline-only':
        raise ValueError('Only offline replay is supported')
    if configuration['action_definition_id'] != 'g1-brainco26-position-v001':
        raise ValueError('Unexpected action definition')
    if model_input.get('diagnostic_only') is not True:
        raise ValueError('Expected diagnostic-only input')
    names = list(configuration['joint_names'])
    if len(names) != 26 or len(set(names)) != 26 or configuration['value_dimension'] != 26:
        raise ValueError('Invalid action contract')
    if model_input['joint_names'] != names:
        raise ValueError('Joint order does not match the contract')
    timestamp = model_input['timestamp_ns']
    if type(timestamp) is not int or timestamp < 0:
        raise ValueError('Invalid observation timestamp')
    positions = model_input['positions']
    if len(positions) != 26:
        raise ValueError('Incomplete joint positions')
    values = []
    for position in positions:
        if isinstance(position, bool) or not isinstance(position, (int, float)):
            raise ValueError('Joint positions must be numeric')
        value = float(position)
        if not math.isfinite(value):
            raise ValueError('Joint positions must be finite')
        values.append(value)
    return {
        'action_definition_id': configuration['action_definition_id'],
        'timestamp_ns': timestamp,
        'joint_names': names,
        'values': values,
    }
