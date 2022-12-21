import boto3
import logging
from uuid_by_string import generate_uuid
from modules.common import deploy_cfn, render_template, call_teams, init_logger, tag_resources, AWS_REGION, AWS_ACCOUNT, RP_ARN_BASE

def rds_alert():
    thresholds = {
        "CPU":{
            "qa": 90,
            "prod": 75
        },
        "FreeStorage":{
            "qa": 5737418240,
            "prod": 10737418240
        },
        "BurstBalance":{
            "qa": 10,
            "prod": 25
        }
    }
    rds_db_list=[]
    rds_map=[]
    rds = boto3.client('rds', region_name=AWS_REGION)
    init_logger()

    rds_list = rds.describe_db_instances()['DBInstances']
    if rds_list:
        for item in rds_list:
            rds_db_list.append(item['DBInstanceIdentifier'])

    rds_db_list = sorted(list(set(rds_db_list)))

    teams = call_teams("Teams")

    for instance in rds_db_list:
        if 'TagList' in rds.list_tags_for_resource(
            ResourceName = f"arn:aws:rds:{AWS_REGION}:{AWS_ACCOUNT}:db:{instance}"
        ):
            tag_list=rds.list_tags_for_resource(
            ResourceName = f"arn:aws:rds:{AWS_REGION}:{AWS_ACCOUNT}:db:{instance}"
        )['TagList']
            tags={}
            for tag in tag_list:
                tags[tag['Key']]=tag['Value']
        
            if "Owner" in tags:
                if 'snooze_alert' in tags and tags['snooze_alert'].lower() == "true":
                    logging.warning(f"RDS {instance} is snoozed")
                elif tags["Owner"] in teams:
                    rds_item = {
                    "DBIdentifier": instance,
                    "ResponseARN": f"{RP_ARN_BASE}{tags['Owner']}-Alert",
                    "tags": tags,
                    "id": generate_uuid(instance)[:8],
                    "CPUThreshold": thresholds["CPU"][tags.get("Environment", "prod")],
                    "StorageThreshold": thresholds["FreeStorage"][tags.get("Environment", "prod")],
                    "BurstThreshold": thresholds["BurstBalance"][tags.get("Environment", "prod")]
                    }
                    rds_map.append(rds_item)
                else:
                    logging.warning(f"Team {tags['Owner']} was not found on teams api")
            else:
                logging.warning(f"RDS {instance} has not Owner")
        else:
            logging.warning(f"RDS: {instance} does not have tags")
            tags = {}
        

    logging.info("RDS List to Alert: " + str(rds_map))
    if rds_map:
        rendered_template = render_template("RDSAlert.yaml", {"RDS": rds_map})
        if rendered_template:
            response = deploy_cfn(rendered_template, "RDS-alerting-stack")
            tag_resources("RDS-alerting-stack")
            return response
        else:
            logging.info("Cloudformation template can't be rendered")
            return 500
    else:
        logging.info("There are no RDS ready to alert")
        return 200