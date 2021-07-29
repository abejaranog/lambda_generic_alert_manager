import boto3
import os
import logging
import yaml
from jinja2 import Environment, FileSystemLoader

# Environment
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
S3_TEAMS = os.environ.get("S3_TEAMS")
TEMPLATE_S3=os.environ.get("TEMPLATE_S3")
AWS_REGION = os.environ.get("AWS_REGION")
AWS_ACCOUNT = boto3.client("sts").get_caller_identity()["Account"]
cfn = boto3.client("cloudformation", region_name=AWS_REGION)
s3_client = boto3.client("s3", region_name=AWS_REGION)
templateEnv = Environment(loader=FileSystemLoader("./templates"))
logging.getLogger().setLevel(logging.getLevelName(LOG_LEVEL))



def deploy_cfn(template_file, stack_name):
    s3_client.put_object(Body=template_file, Bucket=TEMPLATE_S3, Key=f'templates/{stack_name}.yaml')
    kwargs = {
        "StackName": stack_name,
        "TemplateURL": f"https://{TEMPLATE_S3}.s3.{AWS_REGION}.amazonaws.com/templates/{stack_name}.yaml",
        "RoleARN": f"arn:aws:iam::{AWS_ACCOUNT}:role/CloudFormationDeploymentRole",
    }
    try:
        cfn.validate_template(TemplateURL=f"https://{TEMPLATE_S3}.s3.{AWS_REGION}.amazonaws.com/templates/{stack_name}.yaml")
    except Exception as e:
        logging.error(f"Template not valid: {stack_name}")
        logging.error(e)
        return 400
    try:
        if check_stack(stack_name):
            logging.info(f"Stack {stack_name} exists, updating...")
            cfn.update_stack(**kwargs)
            waiter = cfn.get_waiter("stack_update_complete")
        else:
            logging.info(f"Creating stack: {stack_name}.")
            cfn.create_stack(**kwargs)
            waiter = cfn.get_waiter("stack_create_complete")
        logging.info("Waiting stack to be ready")
        waiter.wait(StackName=stack_name)
    except Exception as e:
        try:
            error_msg = e.response["Error"]["Message"]
            if error_msg == "No updates are to be performed.":
                logging.info(e.response["Error"]["Message"])
                return 200
            else:
                raise
        except:
            logging.error(e.response)
    else:
        return 201


def check_stack(stack_name):
    stacks = cfn.list_stacks()["StackSummaries"]
    for stack in stacks:
        if stack["StackStatus"] == "DELETE_COMPLETE":
            continue
        if stack_name == stack["StackName"]:
            return True
    return False


def render_template(template_file, template_args):
    template = templateEnv.get_template(template_file)
    outputText = template.render(template_args)
    return outputText


def load_teams():
    teams_response = {}
    try:
        s3_object = s3_client.get_object(Bucket=S3_TEAMS, Key="teams.yaml")
        body = s3_object["Body"].read()
    except Exception as e:
        logging.error(f"{e}, Error obtaining object teams.yaml from {S3_TEAMS}")
        return 403
    teams_info = yaml.safe_load(body)
    del teams_info["DeploymentTargets"]
    for key, value in teams_info.items():
        if 'ResponsePlanARN' in value:
            teams_response[key] = value["ResponsePlanARN"]
    return teams_response
