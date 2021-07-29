import boto3
import os
import logging
from uuid_by_string import generate_uuid
from modules.common import deploy_cfn, render_template, load_teams

# Environment
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
AWS_REGION = os.environ.get("AWS_REGION")
AWS_ACCOUNT = boto3.client("sts").get_caller_identity()["Account"]
ec2 = boto3.resource('ec2', region_name=AWS_REGION)
ec2_client = boto3.client('ec2', region_name=AWS_REGION)
logging.getLogger().setLevel(logging.getLevelName(LOG_LEVEL))


def ec2_alert():
    ec2_id_list=[]
    ec2_map=[]
    teams = load_teams()
    if teams == 403:
        return 403

    for instance in ec2.instances.all(): ## Handlear errores
        ec2_id_list.append(instance.id)

    ec2_id_list = sorted(list(set(ec2_id_list)))
    for instance in ec2_id_list: ## Handlear errores
        if 'Tags' in ec2_client.describe_tags(Filters=[{'Name':'resource-id', 'Values':[instance]}]):
            ec2_tags=ec2_client.describe_tags(Filters=[{'Name':'resource-id', 'Values':[instance]}])['Tags']
            tags={}
            for tag in ec2_tags:
                tags[tag['Key']]=tag['Value']
        else: 
            logging.warning(f"EC2 Instance: {instance} does not have tags")
            tags = {}
        
        if "Owner" in tags:
            if 'snooze_alert' in tags:
                logging.warning(f"EC2 Instance {instance} is snoozed")
                continue
            elif tags["Owner"] in teams and teams[tags["Owner"]].get("CPU"):
                ec2_item = {
                    "InstanceId": instance,
                    "ResponseARN": teams[tags["Owner"]]["CPU"],
                    "tags": tags,
                    "id": generate_uuid(instance)[:8],
                }
                ec2_map.append(ec2_item)
            else: 
                logging.warning(f"EC2 Instance {instance} has not Response Plan")
        else:
            logging.warning(f"EC2 Instance {instance} has not Owner")

    logging.info("EC2 List to Alert: " + str(ec2_map))
    if ec2_map:
        renderedTemplate = render_template("EC2Alert.yaml", {"EC2": ec2_map})
        if renderedTemplate:
            response = deploy_cfn(renderedTemplate, "EC2-alerting-stack")
            return response
        else:
            logging.info("Cloudformation template can't be rendered")
            return 500
    else:
        logging.info("There are no EC2 ready to alert")
        return 200