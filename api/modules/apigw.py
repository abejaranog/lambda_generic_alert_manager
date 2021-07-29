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
api_gw_client = boto3.client('apigateway', region_name=AWS_REGION)
logging.getLogger().setLevel(logging.getLevelName(LOG_LEVEL))

def api_gateway_alert():
    teams = load_teams()
    if teams == 403:
        return 403

    if "items" in api_gw_client.get_rest_apis():
        paginator = api_gw_client.get_paginator("get_rest_apis")
        pages = paginator.paginate()
        api_list = []
    else:
        logging.warning("There aren't any API Gateway in this AWS Account")
        return 404

    for page in pages:
        for api in page["items"]:
            if 'tags' in api:
                tags = api['tags']
                if 'Owner' in tags:
                    if tags["Owner"] in teams and teams[tags["Owner"]].get("API"):
                        api_item = {
                            "ApiName": api['name'],
                            "ResponseARN": teams[tags["Owner"]]["API"],
                            "tags": tags,
                            "id": generate_uuid(api['name'])[:8],
                        }
                        api_list.append(api_item)
                    else:
                        logging.warning(f"API Gateway {api['name']} has not Response Plan")
                else:
                    logging.warning(f"API Gateway {api['name']} has no Owner")
            else:
                logging.warning(f"API Gateway {api['name']} has no tags")

    api_list = sorted(list(set(api_list)))
    logging.info(f"API List to alert : {str(api_list)}")
    if api_list:
        renderedTemplate = render_template("ApiAlert.yaml", {"API": api_list})
        if renderedTemplate:
            response = deploy_cfn(renderedTemplate, "API-gw-alerting-stack")
            return response
        else:
            logging.info("Cloudformation template can't be rendered")
            return 500
    else:
        logging.info("There aren't APIS ready to alert")
        return 200