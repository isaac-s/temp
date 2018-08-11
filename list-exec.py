import argparse

from cloudify_rest_client import CloudifyClient
from cloudify_rest_client.executions import Execution

parser = argparse.ArgumentParser()
parser.add_argument('host', help="Cloudify Manager's host")
parser.add_argument('--dry-run', help="Dry run (don't change anything)", default=False, action='store_true')

args = parser.parse_args()

cm_host = args.host
dry_run = args.dry_run

print("{} on host: {}".format('Dry-running' if dry_run else 'Running', cm_host))

cm_client = CloudifyClient(host=cm_host)

all_executions = cm_client.executions.list(include_system_workflows=True)
deployments_to_delete = set()

for execution in all_executions:
    status = execution.status
    if status in [Execution.CANCELLING, Execution.FORCE_CANCELLING, Execution.PENDING, Execution.STARTED]:
        print("Execution {}: status is {}".format(execution.id, status))
        print("\t{} execution's status to '{}'".format('Would patch' if dry_run else 'Patching', Execution.CANCELLED))
        if not dry_run:
            cm_client.executions.update(execution.id, Execution.CANCELLED, error='Cancelled by 3.4.2 snapshot fixup')
        workflow_id = execution.workflow_id
        if workflow_id in ['deploy',
                           'teardown',
                           'uninstall',
                           'storm_uninstall',
                           'create_deployment_environment',
                           'delete_deployment_environment',
                           '_start_deployment_environment',
                           '_stop_deployment_environment']:
            deployment_id = execution.deployment_id
            print("\tWorkflow ID is '{}', so marking deployment '{}' for deletion".format(workflow_id, deployment_id))
            deployments_to_delete.add(deployment_id)

if deployments_to_delete:
    print("Deployments marked for deletion:\n\t{}".format('\n\t'.join(deployments_to_delete)))
    if not dry_run:
        for deployment in deployments_to_delete:
            print("Deleting deployment: {}".format(deployment.id))
            cm_client.deployments.delete(deployment.id, ignore_live_nodes=True)
