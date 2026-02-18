# GitHub Actions Workflow Approvals

This document explains how the manual approval mechanism works for staging and production deployments in the `main-merged.yml` workflow.

## Overview

The deployment workflow uses **GitHub Environment Protection Rules** to require manual approval before deploying to staging and production environments. This is a built-in GitHub Actions feature that pauses workflow execution and requires designated reviewers to approve the deployment.

## How It Works

### Workflow Structure

When you trigger a deployment via `workflow_dispatch`:

1. **BUILD** → **DEV** → **DEV-WEBSITE** jobs run automatically
2. Workflow **pauses** at **STG-Approval** job
3. Designated reviewers receive a notification
4. Reviewers must **manually approve** the deployment in GitHub UI
5. After approval, **STG** → **STG-WEBSITE** jobs run
6. Workflow **pauses** at **PROD-Approval** job
7. Reviewers must **manually approve** the production deployment
8. After approval, **PROD** → **PROD-WEBSITE** jobs run

### The Environment Field

Each approval job includes an `environment` field:

```yaml
environment:
  name: stg  # or 'prod'
  url: https://github.com/${{ github.repository }}/actions/runs/${{ github.run_id }}
```

This tells GitHub Actions to enforce any protection rules configured for that environment.

## Configuring Environment Protection Rules

To enable the approval mechanism, you must configure environment protection rules in your GitHub repository settings.

### Step-by-Step Configuration

1. **Go to Repository Settings**
   - Navigate to your repository on GitHub
   - Click **Settings** tab
   - Click **Environments** in the left sidebar

2. **Create or Configure the Staging Environment**
   - Click **New environment** or select existing `stg` environment
   - Configure the following protection rules:

   **Required Reviewers**:
   - Enable "Required reviewers"
   - Add users or teams who can approve staging deployments
   - Recommended: At least 1-2 senior team members

   **Wait Timer** (Optional):
   - Set a wait timer if you want a minimum delay before deployment
   - Example: 5 minutes to allow for review

   **Deployment Branches** (Optional):
   - Restrict which branches can deploy to this environment
   - Recommended: Allow only `main` branch

3. **Create or Configure the Production Environment**
   - Click **New environment** or select existing `prod` environment
   - Configure the following protection rules:

   **Required Reviewers**:
   - Enable "Required reviewers"
   - Add users or teams who can approve production deployments
   - Recommended: At least 2-3 senior team members or leads

   **Wait Timer** (Optional):
   - Consider a longer wait timer for production (e.g., 10-15 minutes)
   - Gives time for stakeholders to review staging deployment

   **Deployment Branches**:
   - Strongly recommended: Allow only `main` branch

4. **Save Configuration**
   - Click **Save protection rules**

## Approving a Deployment

When a workflow is waiting for approval:

1. **Navigate to the Actions Tab**
   - Go to your repository on GitHub
   - Click the **Actions** tab

2. **Find the Waiting Workflow**
   - Look for a workflow run with status "Waiting"
   - It will show which environment is pending approval

3. **Review and Approve**
   - Click on the workflow run
   - Click **Review deployments** button
   - Select the environment(s) to approve
   - Optionally add a comment
   - Click **Approve and deploy**

4. **Monitor Progress**
   - The workflow will resume and complete the deployment
   - Check the logs to ensure successful deployment

## Rejection

If you need to reject a deployment:

1. Follow the same steps as approval
2. Instead of approving, click **Reject**
3. The workflow will be cancelled and deployment will not proceed

## Best Practices

### Reviewer Configuration

- **Staging**: Assign senior developers or team leads
- **Production**: Assign multiple reviewers including:
  - Technical lead
  - Product owner or manager
  - DevOps/Infrastructure team member

### Review Process

Before approving, reviewers should:

1. ✅ Verify that DEV deployment completed successfully
2. ✅ Check the changes being deployed (PR content)
3. ✅ Review any automated test results
4. ✅ Confirm the deployment timing is appropriate
5. ✅ For production: Verify staging deployment is stable

### Notifications

- Configure GitHub notifications to receive alerts when approval is needed
- Consider setting up Slack/Teams integration for deployment notifications
- Document the approval process in your team's runbook

## Troubleshooting

### Approval Jobs Not Pausing

**Problem**: The approval jobs run immediately without waiting.

**Solution**: Check that environment protection rules are configured correctly:
- Go to Settings → Environments → [environment name]
- Ensure "Required reviewers" is enabled
- Ensure at least one reviewer is added

### No Approval Button Visible

**Problem**: The "Review deployments" button doesn't appear.

**Solution**:
- Ensure you are listed as a required reviewer for the environment
- Check that you have the necessary repository permissions
- Try refreshing the page or clearing browser cache

### Workflow Hangs Indefinitely

**Problem**: Workflow is stuck waiting for approval.

**Solution**:
- An authorized reviewer must approve or reject the deployment
- If needed, repository admins can cancel the workflow run
- Check that reviewers received notifications and are available

## Additional Resources

- [GitHub Docs: Using environments for deployment](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment)
- [GitHub Docs: Reviewing deployments](https://docs.github.com/en/actions/managing-workflow-runs/reviewing-deployments)
- [GitHub Docs: Environment protection rules](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment#environment-protection-rules)
