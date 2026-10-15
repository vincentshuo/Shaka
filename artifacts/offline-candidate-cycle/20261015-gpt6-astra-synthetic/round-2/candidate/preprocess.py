def preprocess(observation, configuration):
    import math
    if configuration['mode'] != 'offline-only':
        raise ValueError('Only offline replay is supported')
    if configuration['action_definition_id'] != 'g1-brainco26-position-v001':
        raise ValueError('Unexpected action definition')
    timestamp = observation['captured_at_ns']
    if type(timestamp) is not int or timestamp < 0:
        raise ValueError('Invalid observation timestamp')
    state = observation['robot_state']
    names = list(state['joint_names'])
    positions = list(state['positions'])
    expected = list(configuration['joint_names'])
    if len(expected) != 26 or len(set(expected)) != 26 or configuration['value_dimension'] != 26:
        raise ValueError('Invalid action contract')
    if len(names) != len(positions) or len(set(names)) != len(names):
        raise ValueError('Invalid observed joint mapping')
    if set(names) != set(expected):
        raise ValueError('Observed joints do not match the contract')
    mapped = {}
    for name, position in zip(names, positions):
        if isinstance(position, bool) or not isinstance(position, (int, float)):
            raise ValueError('Joint positions must be numeric')
        value = float(position)
        if not math.isfinite(value):
            raise ValueError('Joint positions must be finite')
        mapped[name] = value
    return {
        'timestamp_ns': timestamp,
        'joint_names': expected,
        'positions': [mapped[name] for name in expected],
        'diagnostic_only': True,
        'diagnostic_reason': 'Observed-position echo only; no target localization, contact planning, withdrawal planning, or foot-support verification is implemented.',
    }
