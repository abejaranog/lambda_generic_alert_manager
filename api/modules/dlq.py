import boto3
import os
import logging
from uuid_by_string import generate_uuid
from modules.common import deploy_cfn, render_template, load_teams

# Environment
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
AWS_REGION = os.environ.get("AWS_REGION")
AWS_ACCOUNT = boto3.client("sts").get_caller_identity()["Account"]
sqs_client = boto3.client("sqs", region_name=AWS_REGION)
sqs_collection = boto3.resource("sqs")
lambda_client = boto3.client("lambda", region_name=AWS_REGION)
logging.getLogger().setLevel(logging.getLevelName(LOG_LEVEL))


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