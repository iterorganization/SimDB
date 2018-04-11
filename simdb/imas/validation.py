import numpy as np
from typing import Tuple, Dict, List, Any
from collections import defaultdict

from ..database.database import get_local_db
from .utils import is_missing, remove_methods
from ..validation import TestParameters


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

    def __getitem__(self, item: str):
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


def between(number: float, range: Tuple[float, float], closed: bool=True):
    if closed:
        return range[0] <= number <= range[1]
    else:
        return range[0] < number < range[1]


class TestReport:
    tests_run: int
    failures: Dict[str, List[str]]

    def __init__(self):
        self.tests_run = 0
        self.failures = defaultdict(lambda: [])


def float_scalar_validation_tests(device: str, scenario: str, path: str, obj: Any, test_report: TestReport) -> None:
    db = get_local_db()

    params = db.get_validation_parameters(device, scenario, path)
    if params is None:
        return

    test_params = TestParameters.from_db_parameters(params)

    results = Results(stdev=True)

    if not is_missing(obj):
        if between(obj, test_params.range):
            results.range = True
        if between(obj, test_params.mean):
            results.mean = True
        if between(obj, test_params.median):
            results.median = True
        results.mandatory = True
    else:
        if test_params.mandatory:
            results.mandatory = False
        else:
            results.mandatory = True

    for test in test_params.mandatory_tests:
        test_report.tests_run += 1
        if not results[test]:
            test_report.failures[path].append("{} validation failed".format(test))

    return


def float_array_validation_tests(device: str, scenario: str, path: str, obj: Any, test_report: TestReport) -> None:
    db = get_local_db()

    params = db.get_validation_parameters(device, scenario, path)
    if params is None:
        return

    test_params = TestParameters.from_db_parameters(params)

    results = Results()

    if len(obj):
        not_missing = True

        for el in obj:
            not_missing = not_missing and not is_missing(el)

        mean: float = np.mean(obj)
        median: float = np.median(obj)
        dmax: float = np.max(obj)
        dstd: float = np.std(obj)

        if between(dmax, test_params.range):
            results.range = True
        if between(mean, test_params.range):
            results.mean = True
        if between(median, test_params.range):
            results.median = True
        if between(dstd, test_params.range):
            results.stdev = True
        if not_missing:
            results.mandatory = True
        else:
            if test_params.mandatory:
                results.mandatory = False
            else:
                results.mandatory = True
    else:
        if test_params.mandatory:
            results.mandatory = False
        else:
            results.mandatory = True

    for test in test_params.mandatory_tests:
        test_report.tests_run += 1
        if not results[test]:
            test_report.failures[path].append("{} validation failed".format(test))

    return


def string_scalar_validation_tests(device: str, scenario: str, path: str, obj: Any, test_report: TestReport) -> None:
    db = get_local_db()

    params = db.get_validation_parameters(device, scenario, path)
    if params is None:
        return

    test_params = TestParameters.from_db_parameters(params)

    results = Results(range=True, mean=True, median=True, stdev=True)

    if not is_missing(obj):
        results.mandatory = True
    else:
        if results.mandatory:
            results.mandatory = False
        else:
            results.mandatory = True

    for test in test_params.mandatory_tests:
        test_report.tests_run += 1
        if not results[test]:
            test_report.failures[path].append("{} validation failed".format(test))

    return


def int_scalar_validation_tests(device: str, scenario: str, path: str, obj: Any, test_report: TestReport) -> None:
    return


def int_array_validation_tests(device: str, scenario: str, path: str, obj: Any, test_report: TestReport) -> None:
    return


def drilldown(device: str, scenario: str, parent_path: str, obj_name: str, obj: Any, test_report: TestReport):
    if ignore_entity(obj_name):
        return

    if obj_name.startswith('array['):  # strip out the array index value
        path = parent_path + '/' + obj_name[6:]
    else:
        path = parent_path + '/' + obj_name

    print('========')
    print('DRILLDOWN:' + path)

    dtype = type(obj).__name__
    print('Type: [' + str(dtype) + '][' + str(type(obj)) + ']')

    if dtype.startswith('int'):
        print('Integer Object: ' + obj_name + ' = ' + str(obj))
        int_scalar_validation_tests(device, scenario, path, obj, test_report)
        return

    if dtype.startswith('float'):
        print('Float Object: ' + obj_name + ' = ' + str(obj))
        if not not is_missing(obj): print('Missing Value!')
        float_scalar_validation_tests(device, scenario, path, obj, test_report)
        return

    if dtype.startswith('str'):
        print('String Object: ' + obj_name + ' = ' + str(obj))
        string_scalar_validation_tests(device, scenario, path, obj, test_report)
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

                    float_array_validation_tests(device, scenario, path, obj, test_report)
                else:
                    int_array_validation_tests(device, scenario, path, obj, test_report)
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
            drilldown(device, scenario, path, name, child, test_report)

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
                drilldown(device, scenario, path, name, children, test_report)
            else:
                child_count = len(children)
                print('Child Count: ' + str(child_count))

                child_index = 0
                for child in children:
                    print('child[' + str(child_index) + ']: ' + name)
                    print(type(child).__name__)
                    a_name = name + '[' + str(child_index) + ']'
                    drilldown(device, scenario, path, a_name, child, test_report)
                    child_index += 1

    else:
        print('Unknown Object')

    return


def verify_equlibirium_COCOS(imas_obj) -> bool:
    # Verify the EQUILIBRIUM IDS is COCOS compliant

    ids = getattr(imas_obj, 'equilibrium')
    ids.get()

    ids_mems = remove_methods(ids)

    print('Equilibrium IDS Data Entity Count: ' + str(len(ids_mems)))
    print(str(ids_mems))

    time_slice = ids.time_slice

    compliance = True

    for a_index in range(len(time_slice)):

        # if a_index == 0: print(time_slice[a_index])

        ip = time_slice[a_index].global_quantities.ip
        sigma_ip = +1
        if not is_missing(ip):
            if ip < 0.0:
                sigma_ip = -1
        else:
            print('Unable to verify COCOS compliance: missing plasma current')
            compliance = False
            return compliance

        b0 = time_slice[a_index].global_quantities.magnetic_axis.b_field_tor
        sigma_b0 = +1
        if not is_missing(b0):
            if b0 < 0.0: sigma_b0 = -1
        else:
            b0 = ids.vacuum_toroidal_field.b0  # array of length ids.time
            if not is_missing(b0):
                t = time_slice[a_index].time
                tvec = ids.time
                if not is_missing(tvec):
                    b0_t = 0.0
                    for t_index in range(len(tvec)):
                        if t >= tvec[t_index]:
                            b0_t = b0[t_index]
                            break
                    if b0_t == 0.0: b0_t = b0.mean()
                    if b0_t < 0.0: sigma_b0 = -1
            else:
                print('Unable to verify COCOS compliance: missing toroidal magnetic field')
                compliance = False
                return compliance

        f = time_slice[a_index].profiles_1d.f
        sign_f = +1
        if not is_missing(f):
            for f_index in range(len(f)):
                if f[f_index] < 0.0:
                    sign_f = -1
                    break
        else:
            print('Unable to verify COCOS compliance: missing diamagentic function F profile')
            compliance = False
            return compliance

        phi = time_slice[a_index].profiles_1d.phi
        sign_phi = +1
        if not is_missing(phi):
            for p_index in range(len(phi)):
                if phi[p_index] < 0.0:
                    sign_phi = -1
                    break
        else:
            print('Unable to verify COCOS compliance: missing toroidal flux profile')
            compliance = False
            return compliance

        psi_axis = time_slice[a_index].global_quantities.psi_axis
        psi_bnd = time_slice[a_index].global_quantities.psi_boundary
        sign_psi = +1
        if not is_missing(psi_axis) and not is_missing(psi_bnd):
            if psi_bnd - psi_axis < 0.0: sign_psi = -1
        else:
            psi = time_slice[a_index].profiles_1d.psi  # Read profile
            if not is_missing(psi):
                psi_axis = psi[0]
                psi_bnd = psi[len(psi) - 1]
                if psi_bnd - psi_axis < 0.0: sign_psi = -1
            else:
                print('Unable to verify COCOS compliance: missing poloidal flux profile')
                compliance = False
                return compliance

        pprime = time_slice[a_index].profiles_1d.dpressure_dpsi
        sign_pprime = +1
        sign_vote = 0
        if not is_missing(pprime):
            for p_index in range(len(pprime)):
                if pprime[p_index] < 0.0:  # Use the 'Main" sign of pprime
                    sign_vote = sign_vote - 1
                else:
                    sign_vote = sign_vote + 1
            if sign_vote < 0: sign_pprime = -1
        else:
            print('Unable to verify COCOS compliance: missing pprime profile')
            compliance = False
            return compliance

        jtor = time_slice[a_index].profiles_1d.j_tor
        sign_jtor = +1
        if not is_missing(jtor):
            for j_index in range(len(jtor)):
                if jtor[j_index] < 0.0:
                    sign_jtor = -1
                    break
        else:
            print('Unable to verify COCOS compliance: missing toroidal current density profile')
            compliance = False
            return compliance

        q = time_slice[a_index].profiles_1d.q  # Read profile
        sign_q = +1
        if not is_missing(q):
            for q_index in range(len(q)):
                if q[q_index] < 0.0:
                    sign_q = -1
                    break
        else:
            q_axis = time_slice[a_index].global_quantities.q_axis
            q_95 = time_slice[a_index].global_quantities.q_95
            if not is_missing(q_axis) and not is_missing(q_axis):
                if q_95 < 0.0: sign_q = -1
            else:
                print('Unable to verify COCOS compliance: missing q profile')
                compliance = False
                return compliance

        # Compliance verification for COCOS == 11
        sigma_bp11 = +1
        sigma_rho_theta_phi = +1

        compliance = compliance and (sign_f == sigma_b0)
        if not compliance:
            print('COCOS compliance failed on sign(f) == sigma_b0')
            return compliance

        compliance = compliance and (sign_phi == sigma_b0)
        if not compliance:
            print('COCOS compliance failed on sign(phi) == sigma_b0')
            return compliance

        compliance = compliance and (sign_jtor == sigma_ip)
        if not compliance:
            print('COCOS compliance failed on sign(j) == sigma_ip')
            return compliance

        compliance = compliance and (sign_psi == sigma_ip * sigma_bp11)
        if not compliance:
            print('COCOS compliance failed on sign(psi) == sigma_ip*sigma_bp11')
            return compliance

        compliance = compliance and (sign_pprime == -sigma_ip * sigma_bp11)
        if not compliance:
            print('COCOS compliance failed on sign(pprime) == -sigma_ip*sigma_bp11')
            return compliance

        compliance = compliance and (sign_q == sigma_ip * sigma_b0 * sigma_rho_theta_phi)
        if not compliance:
            print('COCOS compliance failed on sign(q) == sigma_ip*sigma_b0*sigma_rho_theta_phi')
            return compliance

        compliance = compliance and (sign_q > 0)
        if not compliance:
            print('COCOS compliance failed on sign(q) > 0')
            return compliance

        compliance = compliance and (sign_pprime < 0)
        if not compliance:
            print('COCOS compliance failed on sign(pprime) < 0')
            return compliance

        compliance = compliance and (psi_bnd > psi_axis)  # increasing psi
        if not compliance:
            print('COCOS compliance failed on psi_bnd > psi_axis')
            return compliance

    return compliance


def find_IDSs(imas_obj):
    IDSs = []
    for name in dir(imas_obj):
        type_name = str(type(getattr(imas_obj, name)))
        if "instance" in type_name and "instancemethod" not in type_name:
            IDSs.append(name)
    return IDSs


def ids_targets():
    return ['*']  # ['bolometer'] #['equilibrium'] #['magnetics'] #[*]


def ids_excludes():
    return ['connected', 'expIdx', 'refRun', 'refShot', 'run', 'shot', 'treeName']


def validate_ids(device: str, scenario: str, imas_obj: Any, ids_name: str):
    print('IDS: ' + ids_name)

    if ids_name in ids_excludes():
        print('Excluding IDS: ' + ids_name + ' from Validation Testing')
        return

    if ids_name in ids_targets() and "*" not in ids_targets():
        print('IDS: ' + ids_name + ' is not a Targeted IDS for Validation Testing')
        return

    print('Validating IDS: ' + ids_name)

    try:
        ids = getattr(imas_obj, ids_name)
        ids.get()
    except AttributeError:
        print('ERROR: Unable to read IDS: ' + ids_name)
        return

    # ------------------------------------------------------------------------------
    # Loop over all  IDS data entities and validate values against expected values

    ids_mems = remove_methods(ids)

    print('IDS Data Entity Count: ' + str(len(ids_mems)))
    print(str(ids_mems))

    base_path = ''
    for name in ids_mems:
        if name == 'base_path':
            base_path = getattr(ids, 'base_path')  # the name of the parent object for drill down
            print('Base Path = ' + base_path)
            break

    if base_path == '':
        print('ERROR: BASE PATH NOT FOUND!')

    for ids_index, name in enumerate(ids_mems):
        # deconstruct each object into constituent data elements

        print('\n')
        print('[' + str(ids_index) + ']  ' + name)

        obj = getattr(ids, name)
        dtype = str(type(obj))

        # Scalar data in the IDS root
        if dtype.startswith("int"):
            print('Integer Object: ' + name + ' = ' + str(obj))
            continue
        elif dtype.startswith("float"):
            print('Float Object: ' + name + ' = ' + str(obj))
            continue
        elif dtype.startswith("str"):
            print('String Object: ' + name + ' = ' + str(obj))
            continue
        elif dtype == 'ndarray':
            rank = obj.ndim
            shape = obj.shape
            size = obj.size
            dtype = str(obj.dtype)
            if dtype.startswith("int") or dtype.startswith("float"):
                print('Atomic Array Object: ' + name)
                print(str(rank))    # Rank
                print(str(shape))   # Shape
                print(str(size))    # Number of elements
                print(str(dtype))   # Type

                if size > 0:
                    print(str(obj))
                continue

            print('Array of Structured Type: (' + name + ')  ' + dtype)
            continue

        print('Structured Type: (' + name + ')  ' + dtype)

        test_report = TestReport()

        drilldown(device, scenario, base_path, name, obj, test_report)

        if test_report.failures:
            print('Failures: %d' % len(test_report.failures))
            for (path, failures) in test_report.failures.items():
                print ('Path: ' + path)


def validate_imas(device: str, scenario: str, imas_obj: Any):
    IDSs = find_IDSs(imas_obj)
    for IDS in IDSs:
        validate_ids(device, scenario, imas_obj, IDS)


def load_imas(shot, run):
    import imas
    imas_obj = imas.ids(shot, run)
    imas_obj.open()
    return imas_obj

