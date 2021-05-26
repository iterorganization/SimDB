import yaml
import re


def map_status(status):
    return {
        'draft': 'invalidated',
        'active': 'accepted',
        'obsolete': 'deprecated',
    }[status]


replaces_re1 = re.compile(r'\d+/\d+')
replaces_re2 = re.compile(r'\((\d+),(\d+)\)(\s*-.*)?')


def get_meta(data):
    meta = {
        'device': 'ITER',
        'workflow': {'name': data['characteristics']['workflow'], 'type': data['characteristics']['type']},
        'description': Literal(data['free_description']),
        'status': map_status(data['status']),
        'reference_name': data['reference_name'],
        'responsible_name': data['responsible_name'],
        'scenario_key_parameters': data['scenario_key_parameters'],
        'hcd': data['hcd'],
        'plasma_composition': data['plasma_composition'],
        'shot': data['characteristics']['shot'],
        'run': data['characteristics']['run'],
        'database': data['characteristics']['machine'],
    }
    if 'database_relations' in data:
        replaces = data['database_relations']['replaces']
        if not replaces:
            return meta
        if replaces_re1.match(replaces):
            meta['replaces'] = replaces
        else:
            m = replaces_re2.match(replaces)
            if m:
                meta['replaces'] = f'{m[1]}/{m[2]}'
                if m[3]:
                    reason = m[3].strip()
                    if reason.startswith('-'):
                        reason = reason[1:]
                    meta['replaces_reason'] = reason.strip()
        #meta['replaced_by'] = data['database_relations']['replaced_by']
    return meta


class Literal(str):
    pass


def literal_presenter(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')


yaml.add_representer(Literal, literal_presenter)


def to_uri(**kwargs):
    return 'imas:?database={machine}&user=public&shot={shot}&run={run}'.format(**kwargs)


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
        'version': 1,
        'alias': in_data['reference_name'].replace(' ', '-'),
        'outputs': [{'uri': to_uri(**in_data['characteristics'])}],
        'inputs': [],
        'metadata': [{'values': get_meta(in_data)}],
    }

    with open(out_file, 'w') as file:
        yaml.dump(out_data, file, default_flow_style=False)


if __name__ == '__main__':
    import sys
    main(sys.argv)
