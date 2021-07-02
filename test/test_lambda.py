import moto, boto3, os, sys
from json import dumps
from jinja2 import Environment, FileSystemLoader
import pytest

sys.path.append(
    os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api")
    )
)
with moto.mock_sts():
    import alerting

# Environment
templateEnv = Environment(loader=FileSystemLoader("./templates"))


@moto.mock_cloudformation
def test_check_stack():
    cfn = boto3.resource("cloudformation")
    kwargs = {
        "StackName": "true_stack",
        "TemplateBody": dumps(
            {
                "AWSTemplateFormatVersion": "2010-09-09",
                "Description": "CloudFormation exports",
                "Resources": {},
            }
        ),
    }
    cfn.create_stack(**kwargs)
    assert alerting.check_stack("true_stack") == True
    assert alerting.check_stack("false-stack") == False


def test_render_template():
    template = alerting.render_template("TestTemplate.yaml", {"Test": ["TestName"]})
    assert is_empty(template) == False


@pytest.mark.filterwarnings("ignore:Tried to parse AWS::")
@moto.mock_cloudformation
def test_deploy_cfn():
    template = alerting.render_template("TestTemplate.yaml", {"Test": ["TestName"]})
    assert alerting.deploy_cfn(template, "TestTemplate") == 201
    template = alerting.render_template("TestTemplate.yaml", {})
    assert alerting.deploy_cfn(template, "TestTemplate") == 400


### Aux Functions
def is_empty(text):
    if text:
        return False
    else:
        return True
