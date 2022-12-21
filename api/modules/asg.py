import boto3
import logging
from uuid_by_string import generate_uuid
from modules.common import deploy_cfn, render_template, call_teams, init_logger, tag_resources, AWS_REGION, RP_ARN_BASE

def asg_alert():
    thresholds = {
        "qa": 90,
        "prod": 75
    }
    asg_list = []
    asg_client = boto3.client('autoscaling', region_name=AWS_REGION)
    init_logger()

    if 'AutoScalingGroups' in asg_client.describe_auto_scaling_groups():
        paginator = asg_client.get_paginator('describe_auto_scaling_groups')
        pages = paginator.paginate()

        teams = call_teams("Teams")

        for page in pages:
            for asg in page['AutoScalingGroups']:
                if 'Tags' in asg:
                    tags={}
                    for tag in asg['Tags']:
                        tags[tag['Key']]=tag['Value']
                    if 'Owner' in tags:
                        if 'snooze_alert' in tags:
                            logging.warning(f"ASG {asg['AutoScalingGroupName']} is snoozed")
                        elif tags["Owner"] in teams:
                            asg_item={
                                "ASGName": asg['AutoScalingGroupName'],
                                "ResponseARN": f"{RP_ARN_BASE}{tags['Owner']}-Alert",
                                "tags": tags,
                                "id": generate_uuid(asg['AutoScalingGroupName'])[:8],
                                "threshold": thresholds[tags.get("Environment", "prod")]
                            }
                            asg_list.append(asg_item)
                        else:
                            logging.warning(f"Team {tags['Owner']} was not found on teams api")
                    else:
                        logging.warning(f"Auto Scaling Group {asg['AutoScalingGroupName']} has not Owner")
                else:
                    logging.warning(f"Auto Scaling Group {asg['AutoScalingGroupName']} has not tags")
    else:
        logging.warning("There are no ASG in this AWS Account")

 
    logging.info("ASG List to Alert: " + str(asg_list))

    if asg_list:
        rendered_template = render_template("ASGAlert.yaml", {"ASG": asg_list})
        if rendered_template:
            response = deploy_cfn(rendered_template, "ASG-alerting-stack")
            tag_resources("ASG-alerting-stack")
            return response
        else:
            logging.info("Cloudformation template can't be rendered")
            return 500
    else:
        logging.info("There are no ASG ready to alert")
        return 200