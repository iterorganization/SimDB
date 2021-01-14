import sys
import numpy as np
from typing import Tuple, Dict, List, Any, Optional, IO
from collections import defaultdict
from enum import Enum, auto

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


def float_scalar_save_validation_parameters(device: str, scenario: str, path: str, obj: Any) -> None:
    db = get_local_db()

    test_params = TestParameters(False, (0, 0), (0, 0), (0, 0), (0, 0), [])

    if not is_missing(obj):
        test_params.mandatory = True
        test_params.range = (obj, obj)
        test_params.mean = (obj, obj)
        test_params.median = (obj, obj)
    else:
        test_params.mandatory = False

    db.insert_validation_parameters(test_params.to_db_parameters(device, scenario, path))

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


def float_array_save_validation_parameters(device: str, scenario: str, path: str, obj: Any) -> None:
    db = get_local_db()

    test_params = TestParameters(False, (0, 0), (0, 0), (0, 0), (0, 0), [])

    if len(obj):
        not_missing = True

        for el in obj:
            not_missing = not_missing and not is_missing(el)

        test_params.mean = (np.mean(obj), np.mean(obj))
        test_params.median = (np.median(obj), np.median(obj))
        test_params.max = (np.max(obj), np.max(obj))
        test_params.stdev = (np.std(obj), np.std(obj))
        test_params.mandatory = not_missing
        test_params.mandatory_tests = ["mean", "median", "max", "stdev", "mandatory"]
    else:
        test_params.mandatory = False
        test_params.mandatory_tests = ["mandatory"]

    db.insert_validation_parameters(test_params.to_db_parameters(device, scenario, path))

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


def string_scalar_save_validation_parameters(device: str, scenario: str, path: str, obj: Any) -> None:
    db = get_local_db()

    test_params = TestParameters(False, (0, 0), (0, 0), (0, 0), (0, 0), [])

    if not is_missing(obj):
        test_params.mandatory = True
    else:
        test_params.mandatory = False

    db.insert_validation_parameters(test_params.to_db_parameters(device, scenario, path))

    return


def int_scalar_validation_tests(device: str, scenario: str, path: str, obj: Any, test_report: TestReport) -> None:
    return


def int_array_validation_tests(device: str, scenario: str, path: str, obj: Any, test_report: TestReport) -> None:
    return


class RunMode(Enum):
    TEST = auto()
    SAVE = auto()


def drilldown(device: str, scenario: str, parent_path: str, obj_name: str, obj: Any, test_report: TestReport,
              mode: RunMode, out: IO):
    if ignore_entity(obj_name):
        return

    if obj_name.startswith('array['):  # strip out the array index value
        path = parent_path + '/' + obj_name[6:]
    else:
        path = parent_path + '/' + obj_name

    print('========', file=out)
    print('DRILLDOWN:' + path, file=out)

    dtype = type(obj).__name__
    print('Type: [' + str(dtype) + '][' + str(type(obj)) + ']', file=out)

    if dtype.startswith('int'):
        print('Integer Object: ' + obj_name + ' = ' + str(obj), file=out)
        int_scalar_validation_tests(device, scenario, path, obj, test_report)
        return

    if dtype.startswith('float'):
        print('Float Object: ' + obj_name + ' = ' + str(obj), file=out)
        if not not is_missing(obj): print('Missing Value!', file=out)
        if mode == RunMode.TEST:
            float_scalar_validation_tests(device, scenario, path, obj, test_report)
        elif mode == RunMode.SAVE:
            float_scalar_save_validation_parameters(device, scenario, path, obj)
        else:
            raise Exception("Uknown mode " + mode.name)
        return

    if dtype.startswith('str'):
        print('String Object: ' + obj_name + ' = ' + str(obj), file=out)
        if mode == RunMode.TEST:
            string_scalar_validation_tests(device, scenario, path, obj, test_report)
        elif mode == RunMode.SAVE:
            string_scalar_save_validation_parameters(device, scenario, path, obj)
        else:
            raise Exception("Uknown mode " + mode.name)
        return

    if dtype == 'ndarray':
        rank = obj.ndim
        shape = obj.shape
        size = obj.size

        if dtype.startswith('int') or dtype.startswith('float'):
            print('Atomic NUMPY Array Object: ' + obj_name, file=out)
            print('Rank = ' + str(rank), file=out)  # Rank
            print('Shape = ' + str(shape), file=out)  # Shape
            print('Size = ' + str(size), file=out)  # Number of elements
            print('Type = ' + str(dtype), file=out)  # Type

            if size > 0:
                print(str(obj))
                print('Maximum Value: ' + str(np.max(obj)), file=out)
                print('Minimum Value: ' + str(np.min(obj)), file=out)
                print('Sum Value: ' + str(np.sum(obj)), file=out)
                print('Std Value: ' + str(np.std(obj)), file=out)
                print('Var Value: ' + str(np.var(obj)), file=out)
                print('Mean Value: ' + str(np.mean(obj)), file=out)
                if dtype[0:5] == 'float':
                    missing = False
                    for item in obj:
                        missing = is_missing(item)
                        if missing:
                            break
                    if missing:
                        print('Missing Data in Float Array detected!', file=out)

                    if mode == RunMode.TEST:
                        float_array_validation_tests(device, scenario, path, obj, test_report)
                    elif mode == RunMode.SAVE:
                        float_array_save_validation_parameters(device, scenario, path, obj)
                    else:
                        raise Exception("Uknown mode " + mode.name)
                else:
                    if mode == RunMode.TEST:
                        int_array_validation_tests(device, scenario, path, obj, test_report)
                    elif mode == RunMode.SAVE:
                        pass
                    else:
                        raise Exception("Uknown mode " + mode.name)
            return

        print('Array of NUMPY Structured Type: (' + obj_name + ') ' + str(dtype), file=out)
        return

    print('Other Structured Type: (' + obj_name + ')  ' + str(dtype), file=out)

    s_mems = remove_methods(obj)

    print('Structure Data Entity Count: ' + str(len(s_mems)), file=out)
    print(str(s_mems), file=out)

    base_path = ''
    for mem in s_mems:
        if mem == 'base_path':
            base_path = getattr(obj, 'base_path')  # the name of the parent object for drill down
            print('Base Path = ' + base_path, file=out)
            break

    if base_path == '':
        print('ERROR: BASE PATH NOT FOUND!', file=out)

    print('Parent = ' + parent_path + '   Base_Path = ' + base_path + '  Name = ' + obj_name, file=out)

    if '__structure' in dtype or '__structArrayElement' in dtype or 'instance' in dtype:
        print('Structure Object', file=out)
        for name in s_mems:
            child = getattr(obj, name)
            print(name, file=out)
            print(type(child).__name__, file=out)
            drilldown(device, scenario, path, name, child, test_report, mode, out)

    elif '__structArray' in dtype:
        print('Structure Array Object', file=out)

        obj_count = len(obj)
        print('Array Count: ' + str(obj_count), file=out)

        for name in s_mems:
            children = getattr(obj, name)
            print(name, file=out)
            print(type(children).__name__, file=out)

            ctype = type(children).__name__
            if ctype in ['str', 'int', 'float', 'int32', 'float32', 'int64', 'float64']:
                child_count = 0
                drilldown(device, scenario, path, name, children, test_report, mode, out)
            else:
                child_count = len(children)
                print('Child Count: ' + str(child_count), file=out)

                child_index = 0
                for child in children:
                    print('child[' + str(child_index) + ']: ' + name, file=out)
                    print(type(child).__name__, file=out)
                    a_name = name + '[' + str(child_index) + ']'
                    drilldown(device, scenario, path, a_name, child, test_report, mode, out)
                    child_index += 1

    else:
        print('Unknown Object', file=out)

    return


def verify_equlibirium_COCOS(imas_obj: Any) -> bool:
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
        if sys.version_info.major < 3:
            if "instance" in type_name and "instancemethod" not in type_name:
                IDSs.append(name)
        elif "imas_" in type_name:
            IDSs.append(name)
    return IDSs


def ids_targets():
    return ['*']  # ['bolometer'] #['equilibrium'] #['magnetics'] #[*]


def ids_excludes():
    return ['connected', 'expIdx', 'refRun', 'refShot', 'run', 'shot', 'treeName']


def validate_ids(device: str, scenario: str, imas_obj: Any, ids_name: str, mode: RunMode,
                 ids_names: Optional[List[str]], out: IO):
    print('IDS: ' + ids_name, file=out)

    if ids_names and ids_name not in ids_names:
        print('Excluding IDS: ' + ids_name + ' from Validation Testing', file=out)
        return

    if ids_name in ids_excludes():
        print('Excluding IDS: ' + ids_name + ' from Validation Testing', file=out)
        return

    if ids_name in ids_targets() and "*" not in ids_targets():
        print('IDS: ' + ids_name + ' is not a Targeted IDS for Validation Testing', file=out)
        return

    print('Validating IDS: ' + ids_name, file=out)

    try:
        ids = getattr(imas_obj, ids_name)
        ids.get()
    except AttributeError:
        print('ERROR: Unable to read IDS: ' + ids_name, file=out)
        return

    # ------------------------------------------------------------------------------
    # Loop over all  IDS data entities and validate values against expected values

    ids_mems = remove_methods(ids)

    print('IDS Data Entity Count: ' + str(len(ids_mems)), file=out)
    print(str(ids_mems), file=out)

    base_path = ''
    for name in ids_mems:
        if name == 'base_path':
            base_path = getattr(ids, 'base_path')  # the name of the parent object for drill down
            print('Base Path = ' + base_path, file=out)
            break

    if base_path == '':
        print('ERROR: BASE PATH NOT FOUND!', file=out)

    test_report = TestReport()

    for ids_index, name in enumerate(ids_mems):
        # deconstruct each object into constituent data elements

        print('\n', file=out)
        print('[' + str(ids_index) + ']  ' + name, file=out)

        obj = getattr(ids, name)
        dtype = type(obj).__name__

        # Scalar data in the IDS root
        if dtype.startswith("int"):
            print('Integer Object: ' + name + ' = ' + str(obj), file=out)
            continue
        elif dtype.startswith("float"):
            print('Float Object: ' + name + ' = ' + str(obj), file=out)
            continue
        elif dtype.startswith("str"):
            print('String Object: ' + name + ' = ' + str(obj), file=out)
            continue
        elif dtype == 'ndarray':
            rank = obj.ndim
            shape = obj.shape
            size = obj.size
            dtype = str(obj.dtype)
            if dtype.startswith("int") or dtype.startswith("float"):
                print('Atomic Array Object: ' + name, file=out)
                print(str(rank), file=out)    # Rank
                print(str(shape), file=out)   # Shape
                print(str(size), file=out)    # Number of elements
                print(str(dtype), file=out)   # Type

                if size > 0:
                    print(str(obj), file=out)
                continue

            print('Array of Structured Type: (' + name + ')  ' + dtype, file=out)
            continue

        print('Structured Type: (' + name + ')  ' + dtype, file=out)

        drilldown(device, scenario, base_path, name, obj, test_report, mode, out)

    print("IDS:", ids_name)
    if test_report.failures:
        print('Failures: %d' % len(test_report.failures), file=out)
        for (path, failures) in test_report.failures.items():
            print('Path: ' + path, file=out)
    else:
        print("Success")


def validate_imas(device: str, scenario: str, imas_obj: Any):
    with open("./validate.out", "w") as f:
        IDSs = find_IDSs(imas_obj)
        for IDS in IDSs:
            validate_ids(device, scenario, imas_obj, IDS, RunMode.TEST, None, f)


def save_validation_parameters(device: str, scenario: str, imas_obj: Any, ids_names: List[str]):
    IDSs = find_IDSs(imas_obj)
    for IDS in IDSs:
        validate_ids(device, scenario, imas_obj, IDS, RunMode.SAVE, ids_names, sys.stderr)


def load_imas(shot, run):
    import imas
    imas_obj = imas.ids(shot, run)
    imas_obj.open()
    return imas_obj
