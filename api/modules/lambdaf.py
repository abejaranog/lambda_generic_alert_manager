import boto3

import logging
from uuid_by_string import generate_uuid
from modules.common import deploy_cfn, render_template, call_teams, init_logger, tag_resources, AWS_REGION, AWS_ACCOUNT, RP_ARN_BASE, boto_config


def lambda_alert():
    lambda_list = []
    lambda_map = []
    thresholds = {
        "error":{
            "qa": 5,
            "prod": 1
        },
        "throttles":{
            "qa": 25,
            "prod": 10
        }
    }

    lambda_client = boto3.client("lambda", config=boto_config)
    init_logger()

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

    teams = call_teams("Teams")

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
            elif tags["Owner"] in teams:
                lambda_item = {
                        "LambdaName": function,
                        "ResponseARN": f"{RP_ARN_BASE}{tags['Owner']}-Alert",
                        "tags": tags,
                        "id": generate_uuid(function)[:8],
                        "ErrorThreshold": thresholds["error"][tags.get("Environment", "prod")],
                        "ThrottlingThreshold": thresholds["throttles"][tags.get("Environment", "prod")]
                    }
                lambda_map.append(lambda_item)
            else:
                logging.warning(f"Team {tags['Owner']} was not found on teams api")
        else:
            logging.warning(f"Lambda {function} has not Owner tag")
    logging.info(f"{len(lambda_map)} resources to Alert: {lambda_map}")
    rendered_template = render_template("LambdaAlert.yaml", {"lambda": lambda_map})
    if rendered_template:
        response = deploy_cfn(rendered_template, "Lambda-alerting-stack")
        tag_resources("Lambda-alerting-stack")
        return response
    else:
        logging.info("Cloudformation template can't be rendered")
        return 500



