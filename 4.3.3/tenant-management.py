import argparse
import json
import sys
import os

from novaclient.client import Client

from cloudify_rest_client import CloudifyClient
from cloudify_rest_client.client import DEFAULT_PROTOCOL, SECURED_PROTOCOL


def dep_list(host, tenant, user, password, ssl, cert, **kwargs):
    cm_client = CloudifyClient(host=host,
                               tenant=tenant,
                               username=user,
                               password=password,
                               protocol=SECURED_PROTOCOL if ssl else DEFAULT_PROTOCOL,
                               cert=cert)

    report = {}
    offset = 0
    while True:
        all_node_instances = cm_client.node_instances.list(_size=1000, _offset=offset)
        ni_count = len(all_node_instances)
        if not ni_count:
            break
        for node_instance in all_node_instances:
            dep_report = report.get(node_instance.deployment_id)
            if dep_report is None:
                dep_report = {'node_instances': list()}
                report[node_instance.deployment_id] = dep_report
            dep_node_instances = dep_report['node_instances']
            dep_node_instances.append(node_instance.id)
        offset += ni_count

    print(json.dumps(report, indent=True))


def openstack_report(**kwargs):
    username = os.environ['OS_USERNAME']
    password = os.environ['OS_PASSWORD']
    auth_url = os.environ['OS_AUTH_URL']
    tenant_id = os.environ['OS_TENANT_ID']
    os_client = Client('2', username=username, password=password, auth_url=auth_url,
                       project_id=tenant_id)
    all_servers = os_client.servers.list()
    server_names = { 'servers': [x.name for x in all_servers]}
    print(json.dumps(server_names, indent=True))


def reconcile(cfy_file, os_file, **kwargs):
    with open(cfy_file, 'r') as f:
        cfy_report = json.load(f)
    with open(os_file, 'r') as f:
        os_report = json.load(f)

    ni_to_dep = {}
    for d in cfy_report.keys():
        for ni in d['node_instances']:
            ni_to_dep[ni] = d

    for server_name in os_report['servers']:
        components = server_name.split('_')
        if len(components) != 3 or components[0] != 'server_':
            print("Warning: OpenStack server does not adhere to convention: {}".format(server_name))
            continue
        deployment_id = components[1]
        node_instance_id = components[2]

        # Is there such a node instance?
        if not node_instance_id in ni_to_dep:
            print("Error: OpenStack server '{}' implies node instance '{}', which doesn't exist on the manager".format(server_name, node_instance_id))
        # Is the node instance in the expected deployment?
        elif deployment_id != ni_to_dep[node_instance_id]:
            print("Error: OpenStack server '{}' implies deployment '{}' but in reality belongs to deployment '{}'")


parser = argparse.ArgumentParser()

cm_details_parser = argparse.ArgumentParser(add_help=False)
cm_details_parser.add_argument('--host', required=True, help='Cloudify Manager host/IP')
cm_details_parser.add_argument('--tenant', required=True, help='Tenant to use')
cm_details_parser.add_argument('--user', required=True, help='User to connect with')
cm_details_parser.add_argument('--password', required=True, help='Password to connect with')
cm_details_parser.add_argument('--ssl', required=False, action='store_true', default=False, help='Password to connect with')
cm_details_parser.add_argument('--cert', required=False, help="Cloudify's Manager certificate")

subparsers = parser.add_subparsers()
dep_list_parser = subparsers.add_parser('dep-list', parents=[cm_details_parser])
dep_list_parser.set_defaults(func=dep_list)

openstack_report_parser = subparsers.add_parser('openstack-report')
openstack_report_parser.set_defaults(func=openstack_report)

reconcile_parser = subparsers.add_parser('reconcile')
reconcile_parser.add_argument('--cfy-file', required=True, help='Cloudify report JSON obtained earlier by dep-list')
reconcile_parser.add_argument('--os-file', required=True, help='OpenStack report JSON obtained earlier by openstack-report')

reconcile_parser.set_defaults(func=reconcile)

args = parser.parse_args()

args.func(**vars(args))
