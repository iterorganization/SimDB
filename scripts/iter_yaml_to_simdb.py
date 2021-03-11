import yaml


def get_meta(data):
    meta = {
        'device': 'ITER',
        'workflow': {'name': data['characteristics']['workflow']},
        'description': Literal(data['free_description']),
        'status': data['status'],
        'reference_name': data['reference_name'],
        'responsible_name': data['responsible_name'],
        'scenario_key_parameters': data['scenario_key_parameters'],
        'hcd': data['hcd'],
        'plasma_composition': data['plasma_composition'],
    }
    if 'database_relations' in data:
        meta['replaces'] = data['database_relations']['replaces']
        meta['replaced_by'] = data['database_relations']['replaces']
    return meta


class Literal(str):
    pass


def literal_presenter(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')


yaml.add_representer(Literal, literal_presenter)


def to_uri(**kwargs):
    return 'imas:?machine={machine}&user=public&shot={shot}&run={run}'.format(**kwargs)


def main(args):
    if len(args) != 3:
        print('usage: %s iter_yaml out_file' % args[0])
        return

    in_file = args[1]
    out_file = args[2]

    with open(in_file) as file:
        text = file.read()
    in_data = yaml.safe_load(text)

    out_data = {
        'alias': in_data['reference_name'],
        'outputs': [{'uri': to_uri(**in_data['characteristics'])}],
        'inputs': [],
        'metadata': [{'values': get_meta(in_data)}],
    }

    with open(out_file, 'w') as file:
        yaml.dump(out_data, file, default_flow_style=False)


if __name__ == '__main__':
    import sys
    main(sys.argv)
