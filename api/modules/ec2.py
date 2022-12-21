import boto3
import logging
from uuid_by_string import generate_uuid
from modules.common import deploy_cfn, render_template, call_teams, init_logger, tag_resources, AWS_REGION, RP_ARN_BASE

def ec2_alert():
    thresholds = {
        "CPU":{
            "qa": 90,
            "prod": 75
        },
        "StatusCheck":{
            "qa": 2,
            "prod": 0
        },
        "RAM": {
            "qa": 80,
            "prod": 70
        },
        "Disk": {
            "qa": 80,
            "prod": 70
        }
    }
    ec2 = boto3.resource('ec2', region_name=AWS_REGION)
    ec2_client = boto3.client('ec2', region_name=AWS_REGION)
    ec2_id_list=[]
    ec2_map=[]
    init_logger()

    # Alarms for RAM
    ec2_ram_alarms=[]

    # Alarms for Disk
    ec2_disk_alarms=[]

    teams = call_teams("Teams")

    for instance in ec2.instances.all():
        ec2_id_list.append(instance.id)

    ec2_id_list = sorted(list(set(ec2_id_list)))
    for instance in ec2_id_list: 
        if 'Tags' in ec2_client.describe_tags(Filters=[{'Name':'resource-id', 'Values':[instance]}]):
            ec2_tags=ec2_client.describe_tags(Filters=[{'Name':'resource-id', 'Values':[instance]}])['Tags']
            tags={}
            for tag in ec2_tags:
                tags[tag['Key']]=tag['Value']
        else: 
            logging.warning(f"EC2 Instance: {instance} does not have tags")
            tags = {}

        if "aws:autoscaling:groupName" not in tags:
            if "Owner" in tags:
                if 'snooze_alert' in tags:
                    logging.warning(f"EC2 Instance {instance} is snoozed")
                elif tags["Owner"] in teams:
                    ec2_item = {
                        "InstanceId": instance,
                        "ResponseARN": f"{RP_ARN_BASE}{tags['Owner']}-Alert",
                        "tags": tags,
                        "id": generate_uuid(instance)[:8],
                        "CPUThreshold": thresholds["CPU"][tags.get("Environment", "prod")],
                        "StatusThreshold": thresholds["StatusCheck"][tags.get("Environment", "prod")]
                    }
                    ec2_map.append(ec2_item)
                else: 
                    logging.warning(f"Team {tags['Owner']} was not found on teams api")
            else:
                logging.warning(f"EC2 Instance {instance} has not Owner")
        else:
            logging.warning(f"EC2 Instance {instance} belongs to {tags['aws:autoscaling:groupName']} Autoscaling Group")

        # RAM Alerts
        if "Owner" in tags:
            if 'snooze_alert' in tags:
                logging.warning(f"EC2 Instance {instance} RAM Alarms is snoozed")
            elif tags["Owner"] in teams:
                ec2_item = {
                    "InstanceId": instance,
                    "ResponseARN": f"{RP_ARN_BASE}{tags['Owner']}-Alert",
                    "tags": tags,
                    "id": generate_uuid(instance)[:8],
                    "Threshold": thresholds["RAM"][tags.get("Environment", "prod")]
                }
                ec2_ram_alarms.append(ec2_item)
            else: 
                logging.warning(f"Team {tags['Owner']} was not found on teams api")

        # Disk Alerts
        if "Owner" in tags:
            if 'snooze_alert' in tags:
                logging.warning(f"EC2 Instance {instance} Disk Alarms is snoozed")
            elif tags["Owner"] in teams:
                ec2_item = {
                    "InstanceId": instance,
                    "ResponseARN": f"{RP_ARN_BASE}{tags['Owner']}-Alert",
                    "tags": tags,
                    "id": generate_uuid(instance)[:8],
                    "Threshold": thresholds["Disk"][tags.get("Environment", "prod")]
                }
                ec2_disk_alarms.append(ec2_item)
            else: 
                logging.warning(f"Team {tags['Owner']} was not found on teams api")

    logging.info("EC2 List to Alert: " + str(ec2_map))

    logging.info("EC2 RAM Alerts: " + str(ec2_ram_alarms))

    logging.info("EC2 Disk Alerts: " + str(ec2_disk_alarms))

    if ec2_map:
        rendered_template = render_template("EC2Alert.yaml", {"EC2": ec2_map, "EC2Alerts": { "RAM":ec2_ram_alarms, "Disk":ec2_disk_alarms }})
        if rendered_template:
            response = deploy_cfn(rendered_template, "EC2-alerting-stack")
            tag_resources("EC2-alerting-stack")
            return response
        else:
            logging.info("Cloudformation template can't be rendered")
            return 500
    else:
        logging.info("There are no EC2 ready to alert")
        return 200