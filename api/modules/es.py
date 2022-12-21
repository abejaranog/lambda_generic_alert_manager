import boto3
import logging
from uuid_by_string import generate_uuid
from modules.common import deploy_cfn, render_template, call_teams, init_logger, tag_resources, AWS_REGION, RP_ARN_BASE

es_client = boto3.client('es', region_name=AWS_REGION)

def es_alert():

    init_logger()
    es_domain_list=[]

    for domain in es_client.list_domain_names()['DomainNames']:
        es_domain = es_client.describe_elasticsearch_domain(DomainName=domain['DomainName'])['DomainStatus']
        es_domain['Tags'] = {}
        for tag in es_client.list_tags(ARN=es_domain['ARN'])['TagList']:
            es_domain['Tags'][tag['Key']] = tag['Value']
        es_domain_list.append(es_domain)

    es_domain_alerts=[]

    teams = call_teams('Teams')

    for domain in es_domain_list:
        if 'Tags' in domain.keys():
            if 'Owner' in domain['Tags']:
                if domain['Tags']['Owner'] in teams:
                    domain_alert = {
                        'AlarmName': domain['DomainName'].replace('-',''),
                        'DomainName': domain['DomainName'],
                        'ResponseARN': f"{RP_ARN_BASE}{domain['Tags']['Owner']}-Alert"
                    }
                    es_domain_alerts.append(domain_alert)
                    continue
                else:
                    logging.warning(f"Team {domain['Tags']['Owner']} was not found on teams api")
            else:
                logging.warning(f"ES Instance {domain} has no Owner")
        else:
            logging.warning(f"ES Instance {domain} has no Tags")

    if es_domain_alerts:
        rendered_template = render_template('ESAlert.yaml', {'ES': es_domain_alerts})
        if rendered_template:
            print(rendered_template)
            response = deploy_cfn(rendered_template, "ES-alerting-stack")
            tag_resources("ES-alerting-stack")
            return response
        else:
            logging.info("Cloudformation template can't be rendered")
            return 500
    else:
        logging.info("There are no ES ready to alert")
        return 200