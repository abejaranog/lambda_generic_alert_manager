import boto3
import os
import logging
import yaml
from jinja2 import Environment, FileSystemLoader
from uuid_by_string import generate_uuid

# Environment
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
S3_TEAMS = os.environ.get("S3_TEAMS")
TEMPLATE_S3=os.environ.get("TEMPLATE_S3")
AWS_REGION = os.environ.get("AWS_REGION")
AWS_ACCOUNT = boto3.client("sts").get_caller_identity()["Account"]
sqs_client = boto3.client("sqs", region_name=AWS_REGION)
sqs_collection = boto3.resource("sqs")
lambda_client = boto3.client("lambda", region_name=AWS_REGION)
cfn = boto3.client("cloudformation", region_name=AWS_REGION)
s3_client = boto3.client("s3", region_name=AWS_REGION)
templateEnv = Environment(loader=FileSystemLoader("./templates"))
logging.getLogger().setLevel(logging.getLevelName(LOG_LEVEL))

# Functions


def lambda_alert():
    lambda_list = []
    lambda_map = []
    teams = load_teams()
    if teams == 403:
        return 403

    # try:
    #     response=lambda_client.list_functions()['Functions']
    #     for item in response:
    #         lambda_list.append(item['FunctionName'])
    # except Exception as e:
    #     logging.error("There aren't any Lambda in this AWS Account")
    #     return 404

    if "Functions" in lambda_client.list_functions():
        paginator = lambda_client.get_paginator("list_functions")
        pages = paginator.paginate()
        lambda_list = []
        for page in pages:
            for function in page["Functions"]:
                lambda_list.append(function["FunctionName"])
    else:
        logging.warning("There aren't any Lambda in this AWS Account")
        return 404

    lambda_list = sorted(list(set(lambda_list)))
    for function in lambda_list:
        if "Tags" in lambda_client.list_tags(
            Resource = f"arn:aws:lambda:{AWS_REGION}:{AWS_ACCOUNT}:function:{function}"
        ):
            tags = lambda_client.list_tags(
                Resource=f"arn:aws:lambda:{AWS_REGION}:{AWS_ACCOUNT}:function:{function}"
            )["Tags"]
        else:
            logging.warning(f"Lambda: {function} does not have tags")
            tags = {}
        
        if 'snooze_alert' in tags:
            continue

        if "Owner" in tags:
            if 'snooze_alert' in tags:
                logging.warning(f"Lambda {function} is snoozed")
                continue
            elif tags["Owner"] in teams and teams[tags["Owner"]].get("lambda"):
                lambda_item = {
                    "LambdaName": function,
                    "ResponseARN": teams[tags["Owner"]]["lambda"],
                    "tags": tags,
                    "id": generate_uuid(function)[:8],
                }
                lambda_map.append(lambda_item)
        else:
            logging.warning(f"Lambda {function} has not Owner or Lambda Response Plan")

        # try:
        #     tags=lambda_client.list_tags(
        #             Resource=f"arn:aws:lambda:{AWS_REGION}:{AWS_ACCOUNT}:function:{item}"
        #             )['Tags']
        #     try:
        #         lambda_item = {
        #         "LambdaName": item,
        #         "ResponseARN": teams[tags['Owner']]['lambda'],
        #         "tags": tags
        #         }
        #         lambda_map.append(lambda_item)
        #     except:
        #         logging.warning(f"Lambda {item} has not Owner or Lambda Response Plan")
        # except Exception as e:
        #     logging.warning(f"Lambda: {item} does not have tags")

    logging.info("Lambda List to Alert: " + str(lambda_map))
    renderedTemplate = render_template("LambdaAlert.yaml", {"lambda": lambda_map})
    if renderedTemplate:
        response = deploy_cfn(renderedTemplate, "Lambda-alerting-stack")
        return response
    else:
        logging.info("Cloudformation template can't be rendered")
        return 500


def DLQalert():
    dlq_list = []
    dlq = []
    teams = load_teams()
    if teams == 403:
        return 403

    if list(sqs_collection.queues.all()):
        sqs_list = []
        for queue in sqs_collection.queues.all():
            sqs_list.append(queue.url)
    else:
        logging.warning("There aren't any SQS in this AWS Account")
        return 404

    for queue in sqs_list:
        queueArn = sqs_client.get_queue_attributes(
            QueueUrl=queue, AttributeNames=["QueueArn"]
        )["Attributes"]["QueueArn"]
        if "queueUrls" in sqs_client.list_dead_letter_source_queues(QueueUrl=queue):
            dlq_list.append(queueArn)
        else:
            logging.debug(f"SQS: {queueArn} does not have DLQ associated")
    # try:
    #     sqs_list = sqs_client.list_queues()['QueueUrls'] ## IF return marker, re-do
    #     for item in sqs_list:
    #         queueArn=sqs_client.get_queue_attributes(QueueUrl=item,AttributeNames=['QueueArn'])['Attributes']['QueueArn']
    #         try:
    #             sqs_dlq = sqs_client.list_dead_letter_source_queues(QueueUrl=item)['queueUrls']
    #             for item in sqs_dlq:
    #                 dlqArn=sqs_client.get_queue_attributes(QueueUrl=item,AttributeNames=['QueueArn'])['Attributes']['QueueArn']
    #                 dlq_list.append(dlqArn)
    #         except:
    #             logging.debug(f"SQS: {queueArn} does not have DLQ associated")
    # except:
    #     logging.warning("There aren't any SQS in this AWS Account")
    #     return 404

    if "Functions" in lambda_client.list_functions():
        paginator = lambda_client.get_paginator("list_functions")
        pages = paginator.paginate()
        lambda_list = []
        for page in pages:
            lambda_list = [*lambda_list, *page["Functions"]]
    else:
        logging.warning("There aren't any Lambda in this AWS Account")
        return 404

    if lambda_list:
        for function in lambda_list:
            if "DeadLetterConfig" in function:
                dlq_list.append(function["DeadLetterConfig"]["TargetArn"])
            else:
                logging.debug(
                    f"Lambda {function['FunctionName']} does not have DLQ associated"
                )

    # try:
    #     lambda_list=lambda_client.list_functions()['Functions'] ## If return Marker, re-do
    #     for item in lambda_list:
    #         try:
    #             dlq_list.append(item['DeadLetterConfig']['TargetArn'])
    #         except:
    #             logging.debug(f"Lambda {item['FunctionName']} does not have DLQ associated")
    # except Exception as e:
    #     logging.error("There aren't any Lambda in this AWS Account")
    #     return 404

    dlq_list = sorted(
        list(set(dlq_list))
    ) 
    for item in dlq_list:
        queueName = item.replace(f"arn:aws:sqs:{AWS_REGION}:{AWS_ACCOUNT}:", "")
        queueUrl = sqs_client.get_queue_url(QueueName=queueName)["QueueUrl"]
        if "Tags" in sqs_client.list_queue_tags(QueueUrl=queueUrl):
            tags = sqs_client.list_queue_tags(QueueUrl=queueUrl)["Tags"]
        else:
            logging.warning(f"Queue: {item} does not have tags")
            tags = {}

        if "Owner" in tags:
            if 'snooze_alert' in tags:
                logging.warning(f"DLQ {queueName} is snoozed")
                continue
            elif tags["Owner"] in teams and teams[tags["Owner"]].get("DLQ"):
                dlq_item = {
                    "QueueName": queueName,
                    "ResponseARN": teams[tags["Owner"]]["DLQ"],
                    "tags": tags,
                    "id": generate_uuid(queueName)[:8],
                }
                dlq.append(dlq_item)
        else:
            logging.warning(f"DLQ {queueName} has not Owner or DLQ Response Plan")

    logging.info("DLQ List to Alert: " + str(dlq))
    renderedTemplate = render_template("DLQalert.yaml", {"DLQ": dlq})
    if renderedTemplate:
        response = deploy_cfn(renderedTemplate, "DLQ-alerting-stack")
        return response
    else:
        logging.info("Cloudformation template can't be rendered")
        return 500


def deploy_cfn(template_file, stack_name):
    s3_client.put_object(Body=template_file, Bucket=TEMPLATE_S3, Key=f'templates/{stack_name}.yaml')
    kwargs = {
        "StackName": stack_name,
        "TemplateURL": f"https://{TEMPLATE_S3}.s3.{AWS_REGION}.amazonaws.com/templates/{stack_name}.yaml",
        "RoleARN": f"arn:aws:iam::{AWS_ACCOUNT}:role/CloudFormationDeploymentRole",
    }
    try:
        cfn.validate_template(TemplateURL=f"https://{TEMPLATE_S3}.s3.{AWS_REGION}.amazonaws.com/templates/{stack_name}.yaml")
    except AttributeError as e:
        logging.error(e)
        logging.error("Template not valid")
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


def main(event, context):
    dlq_status = DLQalert()
    lambda_status = lambda_alert()
    return f"""
    DLQ Response: {dlq_status}
    Lambda Response: {lambda_status}
    """


## Execution as main
if __name__ == "__main__":
    main(event, context)
