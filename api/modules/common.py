import boto3
import botocore.exceptions
from botocore.config import Config
import os
import logging
from httplib2 import Http
from jinja2 import Environment, FileSystemLoader
from json import loads

# Environment
TEAMS_API_URL = os.environ.get("TEAMS_API_URL")
API_KEY_SECRET_NAME = os.environ.get("API_SECRET_NAME")
TEMPLATE_S3=os.environ.get("TEMPLATE_S3")
AWS_REGION = os.environ.get("AWS_REGION")
AWS_ACCOUNT = boto3.client("sts").get_caller_identity()["Account"]
RP_ARN_BASE = "arn:aws:ssm-incidents::932113703644:response-plan/"
cfn = boto3.client("cloudformation", region_name=AWS_REGION)
s3_client = boto3.client("s3", region_name=AWS_REGION)
template_env = Environment(loader=FileSystemLoader("./templates"), autoescape=True)
boto_config = Config(
        region_name = AWS_REGION,
        retries = {
            'max_attempts': 7,
            'mode': 'standard'
        }
    )


def init_logger():
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    logging.getLogger().setLevel(logging.getLevelName(LOG_LEVEL))


def deploy_cfn(template_file, stack_name):
    logging.info(TEMPLATE_S3)
    s3_client.put_object(Body=template_file, Bucket=TEMPLATE_S3, Key=f'templates/{stack_name}.yaml')
    kwargs = {
        "StackName": stack_name,
        "TemplateURL": f"https://{TEMPLATE_S3}.s3.{AWS_REGION}.amazonaws.com/templates/{stack_name}.yaml",
        "RoleARN": f"arn:aws:iam::{AWS_ACCOUNT}:role/CloudFormationDeploymentRole",
        "Tags":[
        {
            'Key': 'Owner',
            'Value': 'devops'
        },
    ],
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
            raise
    else:
        return 201


def check_stack(stack_name):
    # stacks = cfn.list_stacks()["StackSummaries"]
    # for stack in stacks:
    #     if stack["StackStatus"] == "DELETE_COMPLETE":
    #         continue
    #     if stack_name == stack["StackName"]:
    #         return True
    # return False
    try:
        cfn.describe_stacks(StackName=stack_name)
        return True
    except botocore.exceptions.ClientError:
        return False

def render_template(template_file, template_args):
    template = template_env.get_template(template_file)
    output_text = template.render(template_args)
    return output_text


# def load_teams():
#     teams_response = []
#     try:
#         s3_object = s3_client.get_object(Bucket=S3_TEAMS, Key="teams.yaml")
#         body = s3_object["Body"].read()
#     except Exception as e:
#         logging.error(f"{e}, Error obtaining object teams.yaml from {S3_TEAMS}")
#         return 403
#     teams_yaml = yaml.safe_load(body)
#     teams_info = teams_yaml["Teams"]
#     for key, value in teams_info.items():
#         teams_response.append(key)
#     return teams_response

def call_teams(*args):
    path = "/".join(args)
    logging.info(f"Calling Teams API for path {path}")
    http_client = Http()
    secret_manager = boto3.client("secretsmanager", region_name=AWS_REGION)
    api_key_secret = loads(secret_manager.get_secret_value(SecretId=f"arn:aws:secretsmanager:{AWS_REGION}:{AWS_ACCOUNT}:secret:{API_KEY_SECRET_NAME}")['SecretString'])
    response = http_client.request(
        uri=f"{TEAMS_API_URL}{path}",
        method='GET',
        headers={'x-api-key': f"{api_key_secret['x-api-key']}", 'Content-Type': 'application/json; charset=UTF-8'}
    )
    logging.info(f"API Response: {response[0]['status']}")
    ## Sustituir con match-case en python 3.10
    if response[0]['status'] == '404':
        json_resp = {}
        return json_resp
    else:
        json_resp = loads(response[1].decode('utf-8'))
        return json_resp['content']

def tag_resources(stack_name):
    tags = {
        'Owner': 'devops'
    }
    resources=[]
    tag = boto3.client('resourcegroupstaggingapi', config=boto_config)
    paginator = cfn.get_paginator('list_stack_resources')
    for page in paginator.paginate(StackName=stack_name):
        resources=[*resources, *page['StackResourceSummaries']]
    batch=split_list(resources, 9)
    for resource_list in batch:
        to_tag = []
        for resource in resource_list:
            arn = f"arn:aws:cloudwatch:{AWS_REGION}:{AWS_ACCOUNT}:alarm:{resource['PhysicalResourceId']}"
            to_tag.append(arn)
        tag.tag_resources(ResourceARNList=to_tag,Tags=tags)

def split_list(list, n):
    for i in range(0, len(list), n):
        yield list[i:i + n]