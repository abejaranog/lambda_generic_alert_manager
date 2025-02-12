import moto, boto3, os, sys
from importlib import reload
from jinja2 import Environment, FileSystemLoader
import pytest
from subprocess import call
sys.path.append(
    os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api/modules")
    )
)
with moto.mock_sts():
    import common

# Environment
templateEnv = Environment(loader=FileSystemLoader("./templates"), autoescape=True)
test_template = "TestTemplate.yaml"
template_base = """---
AWSTemplateFormatVersion: "2010-09-09"
Description: "AWS CloudFormation Sample Template to alarm an application-sam model"
Resources: 
  LambdaErrorAlarmTestName:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: "TestName-LambdaErrors"
      AlarmActions:
        - TestName
      ComparisonOperator: GreaterThanOrEqualToThreshold
      Dimensions:
        - Name: FunctionName
          Value: TestName
      EvaluationPeriods: 1
      MetricName: Errors
      Namespace: AWS/Lambda
      Period: 60
      Statistic: Sum
      Threshold: 1

  """
# Tests
def test_render_template_ok():
    template = common.render_template(test_template, {"Test": ["TestName"]})
    assert template == template_base

@pytest.mark.filterwarnings("ignore:Tried to parse AWS::")
@moto.mock_cloudformation
def test_check_existent_stack():
    cfn = boto3.resource("cloudformation")
    kwargs = {
        "StackName": "true_stack",
        "TemplateBody": template_base,
    }
    cfn.create_stack(**kwargs)

    assert common.check_stack("true_stack") == True

@moto.mock_cloudformation
def test_check_non_existent_stack():
    assert common.check_stack("non-existent-stack") == False

@pytest.mark.filterwarnings("ignore:Tried to parse AWS::")
@moto.mock_cloudformation
@moto.mock_s3
def test_deploy_cfn_ok(monkeypatch):
    monkeypatch.setenv('TEMPLATE_S3', 'test-bucket')
    with moto.mock_sts():
        reload(common)

    conn = boto3.resource('s3', region_name='us-east-1')
    conn.create_bucket(Bucket="test-bucket")
    template = common.render_template(test_template, {"Test": ["TestName"]})

    assert common.deploy_cfn(template, "TestTemplate") == 201
    call('rm -rf file.tmp', shell=True)

@moto.mock_s3
@moto.mock_cloudformation
def test_deploy_cfn_fail(monkeypatch):
    monkeypatch.setenv('TEMPLATE_S3', 'test-bucket')
    with moto.mock_sts():
        reload(common)

    conn = boto3.resource('s3', region_name='us-east-1')
    conn.create_bucket(Bucket="test-bucket")
    empty_template = common.render_template(test_template, {})
    
    assert common.deploy_cfn(empty_template, "TestTemplate") == 400
    call('rm -rf file.tmp', shell=True)

