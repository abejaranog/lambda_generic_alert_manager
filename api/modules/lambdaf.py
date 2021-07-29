import boto3
import os
import logging
from uuid_by_string import generate_uuid
from modules.common import deploy_cfn, render_template, load_teams

# Environment
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
AWS_REGION = os.environ.get("AWS_REGION")
AWS_ACCOUNT = boto3.client("sts").get_caller_identity()["Account"]
lambda_client = boto3.client("lambda", region_name=AWS_REGION)
logging.getLogger().setLevel(logging.getLevelName(LOG_LEVEL))

def lambda_alert():
    lambda_list = []
    lambda_map = []
    teams = load_teams()
    if teams == 403:
        return 403

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
        lambda_tags=lambda_client.list_tags(
            Resource = f"arn:aws:lambda:{AWS_REGION}:{AWS_ACCOUNT}:function:{function}"
        )
        if "Tags" in lambda_tags:
            tags = lambda_tags["Tags"]
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

    logging.info("Lambda List to Alert: " + str(lambda_map))
    renderedTemplate = render_template("LambdaAlert.yaml", {"lambda": lambda_map})
    if renderedTemplate:
        response = deploy_cfn(renderedTemplate, "Lambda-alerting-stack")
        return response
    else:
        logging.info("Cloudformation template can't be rendered")
        return 500



