from modules.dlq import DLQalert
from modules.lambdaf import lambda_alert
from modules.apigw import api_gateway_alert
from modules.ec2 import ec2_alert

def main(event, context):
    dlq_status = DLQalert()
    lambda_status = lambda_alert()
    api_status = api_gateway_alert()
    ec2_status = ec2_alert()
    return f"""
    DLQ Response: {dlq_status}
    Lambda Response: {lambda_status}
    API Gw Response: {api_status}
    EC2 Response: {ec2_status}
    """


## Execution as main
if __name__ == "__main__":
    main(event, context)
