import importlib, logging, os
from contextlib import contextmanager
from tempfile import mkdtemp
import yaml
from datapackage_pipelines_knesset.common import object_storage
import json
import requests


@contextmanager
def temp_loglevel(level=logging.INFO):
    root_logging_handler = logging.root.handlers[0]
    old_level = root_logging_handler.level
    root_logging_handler.setLevel(level)
    yield
    root_logging_handler.setLevel(old_level)


def parse_import_func_parameter(value, *args):
    if value and isinstance(value, str) and value.startswith("(") and value.endswith(")"):
        cmdparts = value[1:-1].split(":")
        cmdmodule = cmdparts[0]
        cmdfunc = cmdparts[1]
        cmdargs = cmdparts[2] if len(cmdparts) > 2 else None
        func = importlib.import_module(cmdmodule)
        for part in cmdfunc.split("."):
            func = getattr(func, part)
        if cmdargs == "args":
            value = func(*args)
        else:
            value = func()
    return value


@contextmanager
def temp_dir(*args, **kwargs):
    dir = mkdtemp(*args, **kwargs)
    try:
        yield dir
    except Exception:
        if os.path.exists(dir):
            os.rmdir(dir)
        raise

@contextmanager
def temp_file(*args, **kwargs):
    with temp_dir(*args, **kwargs) as dir:
        file = os.path.join(dir, "temp")
        try:
            yield file
        except Exception:
            if os.path.exists(file):
                os.unlink(file)
            raise


def get_pipeline_run_step_parameters(pipeline_spec, pipeline_id, run_endswith, parameters_match=None):
    with open(os.path.join(os.path.dirname(__file__), "..", "..", pipeline_spec, "pipeline-spec.yaml")) as f:
        pipeline_spec = yaml.load(f.read())
    for step in pipeline_spec[pipeline_id]["pipeline"]:
        if step["run"].endswith(".{}".format(run_endswith)):
            if not parameters_match:
                parameters_match = {}
            mismatch = False
            for k, v in parameters_match.items():
                if step["parameters"].get(k) != v:
                    mismatch=True
                    break
            if not mismatch:
                return step["parameters"]
    raise Exception


def get_pipeline_schema(pipeline_spec, pipeline_id):
    if pipeline_id == 'committee_meeting_protocols_parsed':
        parameters = get_pipeline_run_step_parameters(pipeline_spec, "committee-meeting-protocols", "dump_to_sql",
                                                      parameters_match={"table": "committee_meeting_protocols_parsed"})
        bucket = parameters["schemas-bucket"]
        object_name = "table-schemas/{}.json".format(parameters["table"])
    else:
        parameters = get_pipeline_run_step_parameters(pipeline_spec, pipeline_id, "dump_to_sql",
                                                      parameters_match={"table": pipeline_id})
        bucket = parameters["schemas-bucket"]
        object_name = "table-schemas/{}.json".format(parameters["table"])
    s3 = object_storage.get_s3()
    if object_storage.exists(s3, bucket, object_name):
        return json.loads(object_storage.read(s3, bucket, object_name))
    else:
        logging.warning("Missing local table schema, trying from remote")
        url = "https://minio.oknesset.org/{}/table-schemas/{}.json".format(bucket, parameters["table"])
        res = requests.get(url)
        res.raise_for_status()
        return res.json()
