import boto3
import logging
from uuid_by_string import generate_uuid
from modules.common import deploy_cfn, render_template, call_teams, init_logger, tag_resources, AWS_REGION, AWS_ACCOUNT, RP_ARN_BASE

def dlq_alert():
    thresholds = {
        "qa": 5,
        "prod": 1
    }
    sqs_client = boto3.client("sqs", region_name=AWS_REGION)
    sqs_collection = boto3.resource("sqs")
    lambda_client = boto3.client("lambda", region_name=AWS_REGION)
    dlq_list = []
    dlq = []
    init_logger()

    if list(sqs_collection.queues.all()):
        sqs_list = []
        for queue in sqs_collection.queues.all():
            sqs_list.append(queue.url)
    else:
        logging.warning("There aren't any SQS in this AWS Account")
        return 404

    for queue in sqs_list:
        queue_arn = sqs_client.get_queue_attributes(
            QueueUrl=queue, AttributeNames=["QueueArn"]
        )["Attributes"]["QueueArn"]
        if "queueUrls" in sqs_client.list_dead_letter_source_queues(QueueUrl=queue):
            dlq_list.append(queue_arn)
        else:
            logging.debug(f"SQS: {queue_arn} does not have DLQ associated")

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

    dlq_list = sorted(
        list(set(dlq_list))
    )

    teams = call_teams("Teams")

    for item in dlq_list:
        queue_name = item.replace(f"arn:aws:sqs:{AWS_REGION}:{AWS_ACCOUNT}:", "")
        queue_url = sqs_client.get_queue_url(QueueName=queue_name)["QueueUrl"]
        if "Tags" in sqs_client.list_queue_tags(QueueUrl=queue_url):
            tags = sqs_client.list_queue_tags(QueueUrl=queue_url)["Tags"]
        else:
            logging.warning(f"Queue: {item} does not have tags")
            tags = {}

        if "Owner" in tags:
            if 'snooze_alert' in tags:
                logging.warning(f"DLQ {queue_name} is snoozed")
            elif tags["Owner"] in teams:
                dlq_item = {
                    "QueueName": queue_name,
                    "ResponseARN": f"{RP_ARN_BASE}{tags['Owner']}-Alert",
                    "tags": tags,
                    "id": generate_uuid(queue_name)[:8],
                    "threshold": thresholds[tags.get("Environment", "prod")]
                }
                dlq.append(dlq_item)
            else:
                logging.warning(f"Team {tags['Owner']} was not found on teams api")
        else:
            logging.warning(f"DLQ {queue_name} has not Owner tag")

    logging.info("DLQ List to Alert: " + str(dlq))
    rendered_template = render_template("DLQalert.yaml", {"DLQ": dlq})
    if rendered_template:
        response = deploy_cfn(rendered_template, "DLQ-alerting-stack")
        tag_resources("DLQ-alerting-stack")
        return response
    else:
        logging.info("Cloudformation template can't be rendered")
        return 500