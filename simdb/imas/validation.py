import numpy as np

from ..database.database import get_local_db
from .utils import is_missing, remove_methods


def ignore_entity(name):
    ignore_list = ('base_path', 'idx')
    return name in ignore_list


def log_failed_verification(path, msg):
    pass


class Results:
    range: bool = False
    mean: bool = False
    median: bool = False
    stdev: bool = False
    not_missing: bool = False
    mandatory: bool = False

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __getitem__(self, item):
        return getattr(self, item)


class Stats:
    max: float = 0
    min: float = 0
    mean: float = 0
    median: float = 0
    stdev: float = 0
    not_missing: bool = False

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def to_dict(self) -> dict:
        return dict(
            max=self.max,
            min=self.min,
            mean=self.mean,
            median=self.median,
            stdev=self.stdev,
            not_missing=self.not_missing,
        )


def float_scalar_validation_tests(uuid, path, obj, stats_test_count, stats_test_failure_count, test_mode) -> (bool, int, int):
    # tests are for data compliance within expected norms
    # query the database for values appropriate for this data entity

    stats = [obj, obj, obj, obj, 0.0, not is_missing(obj)]

    db = get_local_db()

    if test_mode == 'startup':
        db.insert_validation_parameters('', '', '', path, stats)
        return True

    tests = db.get_validation_parameters(path)
    if len(tests) == 0:
        return True

    test_quality = tests['quality']
    test_mean = tests['mean']
    test_range = tests['range']
    test_median = tests['median']
    test_mandatory = tests['mandatory']

    results = Results(stdev=True)
    stats = Stats()

    if not is_missing(obj):
        if test_range[1] >= obj <= test_range[0]:
            results.range = True
        if test_mean[1] >= obj <= test_mean[0]:
            results.mean = True
        if test_median[1] >= obj <= test_median[0]:
            results.median = True
        if test_quality[0]: results.not_missing = True
        results.mandatory = True
    else:
        if not test_quality[0]:
            results.not_missing = True
        if test_quality[1]:
            results.mandatory = False
        else:
            results.mandatory = False

    # test outcome

    test_pass = True
    for test in test_mandatory:
        stats_test_count += 1
        test_pass = test_pass and results[test]
        if test == 0 and not results.range:
            log_failed_verification(path, 'Value is outside validation range')
            stats_test_failure_count += 1
        if test == 1 and not results.mean:
            log_failed_verification(path, 'Mean value is outside validation range')
            stats_test_failure_count += 1
        if test == 2 and not results.median:
            log_failed_verification(path, 'Median value is outside validation range')
            stats_test_failure_count += 1

        if test == 4 and results.not_missing:
            log_failed_verification(path, 'Missing Scalar Float Data detected')
            stats_test_failure_count += 1
        if test == 5 and results.mandatory:
            log_failed_verification(path, 'Missing Mandatory Scalar Float Data')
            stats_test_failure_count += 1

    print('Pass or Fail? ' + str(test_pass))

    # write results to the validation database

    db.put_validation_result(uuid, path, test_pass, tests, results, stats)

    return (test_pass, stats_test_count, stats_test_failure_count)


def float_array_validation_tests(uuid, path, obj, stats_test_count, stats_test_failure_count, test_mode) -> (bool, int, int):
    # tests are for data compliance within expected norms
    # query the database for values appropriate for this data entity

    db = get_local_db()

    tests = db.get_validation_parameters(path)
    if not tests:
        # Not testable
        return True

    test_quality = tests['quality']
    test_mean = tests['mean']
    test_range = tests['range']
    test_median = tests['median']
    test_stdev = tests['stdev']
    test_mandatory = tests['mandatory']

    results = Results()
    stats = Stats()

    if obj.size > 0:
        not_missing = True

        for el in obj:
            not_missing = not_missing and not is_missing(el)

        mean = np.mean(obj)
        median = np.median(obj)
        dmax = np.max(obj)
        dmin = np.min(obj)
        dstd = np.std(obj)

        stats = Stats(max=dmax, min=dmin, mean=mean, median=median, stdev=dstd, not_missing=not_missing)

        if test_mode == 'startup':
            db.insert_validation_parameters(path, stats.to_dict())
            return True

        if test_range[1] <= dmax <= test_range[0]:
            results.range = True
        if test_mean[1] <= dmax <= test_mean[0]:
            results.mean = True
        if test_median[1] <= dmax <= test_median[0]:
            results.median = True
        if test_stdev[1] <= dmax <= test_stdev[0]:
            results.stdev = True
        if not_missing:
            if test_quality[0]:
                results.not_missing = True
            results.mandatory = True
        else:
            if not test_quality[0]:
                results.not_missing = True
            if test_quality[1]:
                results.mandatory = False
            else:
                results.mandatory = True

    else:
        if not test_quality[0]:
            results.not_missing = True
        if test_quality[1]:
            results.mandatory = False
        else:
            results.mandatory = True

    # test outcome

    test_pass = True
    for test in test_mandatory:
        if not test:
            continue
        stats_test_count += 1
        test_pass = test_pass and results[test]
        if test == 0 and not results.range:
            log_failed_verification(path, 'Value is outside validation range')
            stats_test_failure_count += 1
        if test == 1 and not results.mean:
            log_failed_verification(path, 'Mean value is outside validation range')
            stats_test_failure_count += 1
        if test == 2 and not results.median:
            log_failed_verification(path, 'Median value is outside validation range')
            stats_test_failure_count += 1
        if test == 3 and not results.stdev:
            log_failed_verification(path, 'Standard Deviation value is outside validation range')
            stats_test_failure_count += 1

        if test == 4 and results.not_missing:
            log_failed_verification(path, 'Missing Float Data detected')
            stats_test_failure_count += 1
        if test == 5 and results.mandatory:
            log_failed_verification(path, 'Missing Mandatory Float Data')
            stats_test_failure_count += 1

    print('Pass or Fail? ' + str(test_pass))

    # write results to the validation database

    db.put_validation_result(uuid, path, test_pass, tests, results, stats)

    return (test_pass, stats_test_count, stats_test_failure_count)


def string_scalar_validation_tests(uuid, path, obj, stats_test_count, stats_test_failure_count, test_mode) -> (bool, int, int):
    # tests are for data compliance within expected norms
    # query the database for values appropriate for this data entity

    if test_mode == 'startup':
        return True

    db = get_local_db()

    tests = db.get_validation_parameters(path)
    if not tests:
        # Not testable
        return True

    print(type(tests))
    print(str(tests))

    test_quality = tests['quality']
    test_mandatory = [i.strip() for i in tests['mandatory'].split(",")]

    results = Results(range=True, mean=True, median=True, stdev=True)
    stats = Stats()

    if not is_missing(obj):
        results.not_missing = 1
        results.mandatory = 1
        stats.not_missing = True
    else:
        stats.not_missing = False
        if not test_quality[0]:
            results.not_missing = 1
        if test_quality[1]:
            results.mandatory = 0  # missing data so fail
        else:
            results.mandatory = 1  # not important for test so don't fail the test

    # test outcome

    test_pass = True
    for test in test_mandatory:
        stats_test_count += 1
        test_pass = test_pass and results[test]
        if test == 4 and not results.not_missing:
            log_failed_verification(path, 'Missing String Data detected!')
            stats_test_failure_count += 1
        if test == 5 and results.mandatory:
            log_failed_verification(path, 'Missing Mandatory String Data detected!')
            stats_test_failure_count += 1

    print('Pass or Fail? ' + str(test_pass))

    # write results to the validation database

    db.put_validation_result(uuid, path, test_pass, tests, results, stats)

    return (test_pass, stats_test_count, stats_test_failure_count)


def int_scalar_validation_tests(uuid, path, obj, stats_test_count, stats_test_failure_count, test_mode) -> (bool, int, int):
    return (True, stats_test_count, stats_test_failure_count)


def int_array_validation_tests(uuid, path, obj, stats_test_count, stats_test_failure_count, test_mode) -> (bool, int, int):
    return (True, stats_test_count, stats_test_failure_count)


def drilldown(parent_path, obj_name, uuid, obj, test_mode):
    if ignore_entity(obj_name):
        return

    if obj_name.startswith('array['):  # strip out the array index value
        path = parent_path + '/' + obj_name[6:]
    else:
        path = parent_path + '/' + obj_name

    stats_test_count = 0
    stats_test_failure_count = 0

    print('========')
    print('DRILLDOWN:' + path)

    dtype = type(obj).__name__
    print('Type: [' + str(dtype) + '][' + str(type(obj)) + ']')

    if dtype.startswith('int'):
        print('Integer Object: ' + obj_name + ' = ' + str(obj))
        int_scalar_validation_tests(uuid, path, obj, stats_test_count, stats_test_failure_count, test_mode)
        return

    if dtype.startswith('float'):
        print('Float Object: ' + obj_name + ' = ' + str(obj))
        if not not is_missing(obj): print('Missing Value!')
        float_scalar_validation_tests(uuid, path, obj, stats_test_count, stats_test_failure_count, test_mode)
        return

    if dtype.startswith('str'):
        print('String Object: ' + obj_name + ' = ' + str(obj))
        string_scalar_validation_tests(uuid, path, obj, stats_test_count, stats_test_failure_count, test_mode)
        return

    if dtype == 'ndarray':
        rank = obj.ndim
        shape = obj.shape
        size = obj.size

        if dtype.startswith('int') or dtype.startswith('float'):
            print('Atomic NUMPY Array Object: ' + obj_name)
            print('Rank = ' + str(rank))  # Rank
            print('Shape = ' + str(shape))  # Shape
            print('Size = ' + str(size))  # Number of elements
            print('Type = ' + str(dtype))  # Type

            if size > 0:

                print(str(obj))
                print('Maximum Value: ' + str(np.max(obj)))
                print('Minimum Value: ' + str(np.min(obj)))
                print('Sum Value: ' + str(np.sum(obj)))
                print('Std Value: ' + str(np.std(obj)))
                print('Var Value: ' + str(np.var(obj)))
                print('Mean Value: ' + str(np.mean(obj)))
                if dtype[0:5] == 'float':
                    missing = False
                    for item in obj:
                        missing = is_missing(item)
                        if missing:
                            break
                    if missing:
                        print('Missing Data in Float Array detected!')

                    float_array_validation_tests(uuid, path, obj, stats_test_count, stats_test_failure_count, test_mode)
                else:
                    int_array_validation_tests(uuid, path, obj, stats_test_count, stats_test_failure_count, test_mode)
            return

        print('Array of NUMPY Structured Type: (' + obj_name + ') ' + str(dtype))
        return

    print('Other Structured Type: (' + obj_name + ')  ' + str(dtype))

    s_mems = remove_methods(obj)
    s_count = len(s_mems)

    s_list = []
    for s_index in range(s_count): s_list.append(s_mems[s_index][0])

    print('Structure Data Entity Count: ' + str(s_count))
    print(str(s_list))

    base_path = ''
    for s_index in range(s_count):
        if s_mems[s_index][0] == 'base_path':
            base_path = getattr(obj, 'base_path')  # the name of the parent object for drill down
            print('Base Path = ' + base_path)
            break

    if base_path == '':
        print('ERROR: BASE PATH NOT FOUND!')

    print('Parent = ' + parent_path + '   Base_Path = ' + base_path + '  Name = ' + obj_name)

    if '__structure' in dtype or '__structArrayElement' in dtype or 'instance' in dtype:
        print('Structure Object')
        for s_index in range(s_count):
            name = s_mems[s_index][0]  # target this data entity
            child = getattr(obj, name)
            print(name)
            print(type(child).__name__)
            drilldown(path, name, uuid, child, test_mode)

    elif '__structArray' in dtype:
        print('Structure Array Object')

        obj_count = len(obj)
        print('Array Count: ' + str(obj_count))

        for s_index in range(s_count):
            name = s_mems[s_index][0]  # target this data entity
            children = getattr(obj, name)
            print(name)
            print(type(children).__name__)

            ctype = type(children).__name__
            if ctype in ['str', 'int', 'float', 'int32', 'float32', 'int64', 'float64']:
                child_count = 0
                drilldown(path, name, uuid, children, test_mode)
            else:
                child_count = len(children)
                print('Child Count: ' + str(child_count))

                child_index = 0
                for child in children:
                    print('child[' + str(child_index) + ']: ' + name)
                    print(type(child).__name__)
                    a_name = name + '[' + str(child_index) + ']'
                    drilldown(path, a_name, uuid, child, test_mode)
                    child_index += 1

    else:
        print('Unknown Object')

    return
