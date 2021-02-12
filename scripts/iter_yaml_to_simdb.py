import yaml


def get_meta(data):
    meta = {
        'status': data['status'],
        'reference_name': data['reference_name'],
        'responsible_name': data['responsible_name'],
        'replaces': data['database_relations']['replaces'],
        'replaced_by': data['database_relations']['replaced_by'],
        'scenario_key_parameters': data['scenario_key_parameters'],
        'hcd': data['hcd'],
        'plasma_composition': data['plasma_composition'],
    }
    return meta


def main(args):
    if len(args) != 2:
        print('usage: %s file_name' % args[0])
        return
    file_name = args[1]
    with open(file_name) as file:
        text = file.read()
    in_data = yaml.safe_load(text)

    out_data = {
        'workflow': {'name': in_data['characteristics']['workflow']},
        'description': in_data['free_description'],
        'inputs': [{'ids': 'imas://{machine}?shot={shot}&run={run}'.format(**in_data['characteristics'])}],
        'outputs': [],
        'metadata': [{'values': get_meta(in_data)}],
    }

    out_file_name = '../temp.yaml'
    with open(out_file_name, 'w') as file:
        yaml.dump(out_data, file)


if __name__ == '__main__':
    import sys
    main(sys.argv)
