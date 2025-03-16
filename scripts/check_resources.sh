#!/bin/bash
# scripts/check_status.sh - Check resources for file-organizer app

# Force JSON output for AWS CLI and copilot commands
export AWS_CLI_AUTO_PROMPT=off
export AWS_PAGER=""

echo "===== ENVIRONMENT AND SERVICE STATUS ====="
echo "-----------------------------------------"

echo "Application Info:"
copilot app show -n file-organizer

echo -e "\nEnvironments:"
copilot env ls -a file-organizer

echo -e "\nServices:"
copilot svc ls -a file-organizer

echo -e "\n===== DETAILED STATUS BY ENVIRONMENT ====="
echo "-----------------------------------------"

# Get all environments (skip headers)
ENVIRONMENTS=$(copilot env ls -a file-organizer | grep -v "Name")
for env in $ENVIRONMENTS; do
  echo -e "\nEnvironment: $env"
  echo "-------------------"
  
  echo "Environment details:"
  copilot env show -n "$env" -a file-organizer
  
  # Get all services (skip headers)
  SERVICES=$(copilot svc ls -a file-organizer | grep -v "Name" | awk '{print $1}')
  for svc in $SERVICES; do
    echo -e "\nService status for $svc in $env environment:"
    copilot svc status -n "$svc" -e "$env" -a file-organizer

    echo -e "\nRecent logs for $svc in $env environment (last 3 min):"
    copilot svc logs -n "$svc" -e "$env" -a file-organizer --since 3m
  done
done

echo -e "\n===== AWS RESOURCES ====="
echo "-----------------------------------------"

echo "CloudFormation Stacks:"
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE --output json | \
  jq -r '.StackSummaries[] | select(.StackName | contains("file-organizer")) | .StackName + " (" + .StackStatus + ")"'

echo -e "\nECS Clusters:"
aws ecs list-clusters --output json | \
  jq -r '.clusterArns[] | select(contains("file-organizer"))'

echo -e "\nECS Services by Cluster:"
for cluster in $(aws ecs list-clusters --output json | jq -r '.clusterArns[] | select(contains("file-organizer"))'); do
  echo "  Cluster: $(basename $cluster)"
  aws ecs list-services --cluster $cluster --output json | \
    jq -r '.serviceArns[] // empty' | while read service; do
      if [ ! -z "$service" ]; then
        echo "    Service: $(basename $service)"
        aws ecs describe-services --cluster $cluster --services $(basename $service) --output json | \
          jq -r '.services[] | "      Status: " + .status + ", Running: " + (.runningCount|tostring) + "/" + (.desiredCount|tostring)'
      else
        echo "    No services found in this cluster"
      fi
    done
done

echo -e "\n===== DATABASE CONNECTIONS ====="
echo "-----------------------------------------"

echo "RDS Instances:"
aws rds describe-db-instances --output json | \
  jq -r '.DBInstances[] | select(.DBInstanceIdentifier | contains("files")) | 
    "ID: " + .DBInstanceIdentifier + 
    "\nStatus: " + .DBInstanceStatus + 
    "\nEndpoint: " + .Endpoint.Address + 
    "\nPort: " + (.Endpoint.Port|tostring)'

echo -e "\n===== SECURITY GROUPS FOR RDS ACCESS ====="
echo "-----------------------------------------"

for sg in sg-0fc9d35e72c3206f8 sg-01357db7771992d86 sg-0554ad948de7bc010; do
  echo "Security Group: $sg"
  aws ec2 describe-security-groups --group-ids $sg --output json | \
    jq -r '.SecurityGroups[0] | .GroupName + " - " + .Description'
  
  echo "  Inbound Rules:"
  aws ec2 describe-security-groups --group-ids $sg --output json | \
    jq -r '.SecurityGroups[0].IpPermissions[] | 
      "    Protocol: " + .IpProtocol + 
      ", Ports: " + (if .FromPort then (.FromPort|tostring) else "*" end) + 
      "-" + (if .ToPort then (.ToPort|tostring) else "*" end)'
done

echo -e "\n===== SERVICE TASKS ====="
echo "-----------------------------------------"

# Get all environments (skip headers)
ENVIRONMENTS=$(copilot env ls -a file-organizer | grep -v "Name")
for env in $ENVIRONMENTS; do
  echo -e "\nTasks in $env environment:"
  # Extract cluster name
  CLUSTER=$(aws ecs list-clusters --output json | jq -r '.clusterArns[] | select(contains("file-organizer-'$env'"))')
  
  if [ -n "$CLUSTER" ]; then
    TASK_ARNS=$(aws ecs list-tasks --cluster $CLUSTER --output json | jq -r '.taskArns[] // empty')
    
    if [ -n "$TASK_ARNS" ]; then
      echo "  Tasks:"
      for task_arn in $TASK_ARNS; do
        TASK=$(basename $task_arn)
        echo "    Task: $TASK"
        aws ecs describe-tasks --cluster $CLUSTER --tasks $task_arn --output json | \
          jq -r '.tasks[0] | 
            "      Status: " + .lastStatus + 
            ", Health: " + (.healthStatus // "unknown") + 
            ", CPU: " + .cpu + 
            ", Memory: " + .memory'
      done
    else
      echo "  No tasks running in this cluster"
    fi
  else
    echo "  No cluster found for $env environment"
  fi
done

echo -e "\n===== CHECKING COPILOT SERVICE DEPLOYMENT STATUS ====="
echo "-----------------------------------------"

# Get all environments (skip headers)
ENVIRONMENTS=$(copilot env ls -a file-organizer | grep -v "Name")
for env in $ENVIRONMENTS; do
  echo -e "\nDeployment status in $env environment:"
  
  # Get all services (skip headers)
  SERVICES=$(copilot svc ls -a file-organizer | grep -v "Name" | awk '{print $1}')
  for svc in $SERVICES; do
    # Force JSON output for copilot svc show
    DEPLOYMENT_INFO=$(copilot svc show -n "$svc" -a file-organizer --json 2>/dev/null)
    
    if [ -n "$DEPLOYMENT_INFO" ]; then
      echo "  Service: $svc"
      echo "$DEPLOYMENT_INFO" | jq -r --arg env "$env" '.environments[] | select(.name == $env) | 
        "    Environment: " + .name + 
        "\n    Status: " + .status + 
        "\n    Tasks: " + (.tasks|tostring) + 
        "\n    Last Deployment: " + (.deployments[0].time // "unknown")'
    else
      echo "  Service: $svc - No deployment info available"
    fi
  done
done

echo -e "\n===== CHECK COMPLETE ====="
