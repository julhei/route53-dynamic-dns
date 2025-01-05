import os
import logging
import boto3
import urllib3
import argparse
# from dotenv import load_dotenv

# Load environment variables from config.env during local development
# load_dotenv(dotenv_path="config.env")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize AWS Route53 client
route53 = boto3.client("route53")

# Initialize HTTP pool manager
http = urllib3.PoolManager()

# Argument parser
parser = argparse.ArgumentParser(prog=__name__)
parser.add_argument("action", choices=["install", "run"], help="Action to perform")

def get_my_ip():
    res = http.request("GET", "https://cloudflare.com/cdn-cgi/trace")
    for line in res.data.decode().splitlines():
        data = line.split("=")
        if data[0] == "ip":
            return data[1]
    return None

def get_route53_ip(hosted_zone_dns_name, my_dns_name):
    res = route53.list_hosted_zones_by_name(DNSName=hosted_zone_dns_name)
    hosted_zone_id = res["HostedZones"][0]["Id"]
    paginator = route53.get_paginator("list_resource_record_sets")
    for page in paginator.paginate(HostedZoneId=hosted_zone_id):
        for rrs in page["ResourceRecordSets"]:
            if rrs["Name"] == f"{my_dns_name}." and rrs["Type"] == "A":
                return rrs["ResourceRecords"][0]["Value"], hosted_zone_id
    return None, hosted_zone_id

def set_route53_ip(new_ip, my_dns_name, hosted_zone_id, ttl):
    route53_change = {
        "Action": "UPSERT",
        "ResourceRecordSet": {
            "Name": f"{my_dns_name}.",
            "Type": "A",
            "ResourceRecords": [{"Value": new_ip}],
            "TTL": ttl,
        },
    }
    res = route53.change_resource_record_sets(
        HostedZoneId=hosted_zone_id,
        ChangeBatch={"Changes": [route53_change]},
    )
    logger.info("Completed update: %s", res)

def run():
    HOSTED_ZONE_DNS_NAME = os.environ["ROUTE53_HOSTED_ZONE_DNS_NAME"]
    MY_DNS_NAME = os.environ["ROUTE53_MY_DNS_NAME"]
    TTL = int(os.environ["ROUTE53_TTL"])
    
    my_ip = get_my_ip()
    if not my_ip:
        logger.error("Failed to retrieve public IP.")
        return
    
    route53_ip, hosted_zone_id = get_route53_ip(
        hosted_zone_dns_name=HOSTED_ZONE_DNS_NAME, 
        my_dns_name=MY_DNS_NAME
    )
    
    if not route53_ip:
        logger.error("DNS record not found.")
        return
    
    if my_ip != route53_ip:
        logger.info(
            "Updating IP in %s (%s) for %s from %s to %s",
            HOSTED_ZONE_DNS_NAME,
            hosted_zone_id,
            MY_DNS_NAME,
            route53_ip,
            my_ip,
        )
        set_route53_ip(new_ip=my_ip, my_dns_name=MY_DNS_NAME, hosted_zone_id=hosted_zone_id, ttl=TTL)
    else:
        logger.info(
            "IP in %s (%s) for %s (%s) matches, nothing to do",
            HOSTED_ZONE_DNS_NAME, 
            hosted_zone_id, 
            MY_DNS_NAME, 
            my_ip
        )

def install():
    logger.info("Install action selected. Implement installation steps here.")

def main():
    args = parser.parse_args()
    if args.action == "run":
        run()
    elif args.action == "install":
        install()
    else:
        logger.error("Unknown action: %s", args.action)

if __name__ == "__main__":
    main()
