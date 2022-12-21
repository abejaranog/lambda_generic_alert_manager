from modules.dlq import dlq_alert
from modules.lambdaf import lambda_alert
from modules.apigw import api_gateway_alert
from modules.ec2 import ec2_alert
from modules.rds import rds_alert
from modules.asg import asg_alert
from modules.es import es_alert

def dlq(event, context):
    dlq_status = dlq_alert()
    return f"""
    DLQ Response: {dlq_status}
    """

def lambdaf(event, context):
    lambda_status = lambda_alert()
    return f"""
    Lambda Response: {lambda_status}
    """

def apigw(event, context):
    api_status = api_gateway_alert()
    return f"""
    API Gw Response: {api_status}
    """

def ec2(event, context):
    ec2_status = ec2_alert()
    return f"""
    EC2 Response: {ec2_status}
    """

def rds(event, context):
    rds_status = rds_alert()
    return f"""
    RDS Response: {rds_status}
    """

def asg(event, context):
    asg_status = asg_alert()
    return f"""
    ASG Response: {asg_status}
    """

def es(event, context):
    es_status = es_alert()
    return f"""
    EC2 Response: {es_status}
    """

## Execution as main
if __name__ == "__main__":
    dlq(event, context)
    lambdaf(event, context)
    apigw(event, context)
    ec2(event, context)
    rds(event, context)
    asg(event, context)
    es(event, context)