import boto3
import logging
from uuid_by_string import generate_uuid
from modules.common import deploy_cfn, render_template, call_teams, init_logger, tag_resources, AWS_REGION, RP_ARN_BASE

def api_gateway_alert():
    thresholds = {
        "qa": 5,
        "prod": 1
    }
    api_gw_client = boto3.client('apigateway', region_name=AWS_REGION)
    init_logger()

    if "items" in api_gw_client.get_rest_apis():
        paginator = api_gw_client.get_paginator("get_rest_apis")
        pages = paginator.paginate()
        api_list = []
    else:
        logging.warning("There aren't any API Gateway in this AWS Account")
        return 404

    teams = call_teams("Teams")

    for page in pages:
        for api in page["items"]:
            if 'tags' in api:
                tags = api['tags']
                if 'Owner' in tags:
                    if 'snooze_alert' in tags:
                        logging.warning(f"API {api['name']} is snoozed")
                    elif tags["Owner"] in teams:
                        api_item = {
                            "ApiName": api['name'],
                            "ResponseARN": f"{RP_ARN_BASE}{tags['Owner']}-Alert",
                            "tags": tags,
                            "id": generate_uuid(api['name'])[:8],
                            "threshold": thresholds[tags.get("Environment", "prod")]
                        }
                        api_list.append(api_item)
                    else:
                        logging.warning(f"Team {tags['Owner']} was not found on teams api")
                else:
                    logging.warning(f"API Gateway {api['name']} has no Owner")
            else:
                logging.warning(f"API Gateway {api['name']} has no tags")

    logging.info(f"API List to alert : {str(api_list)}")
    if api_list:
        rendered_template = render_template("ApiAlert.yaml", {"API": api_list})
        if rendered_template:
            response = deploy_cfn(rendered_template, "API-gw-alerting-stack")
            tag_resources("API-gw-alerting-stack")
            return response
        else:
            logging.info("Cloudformation template can't be rendered")
            return 500
    else:
        logging.info("There aren't APIS ready to alert")
        return 200