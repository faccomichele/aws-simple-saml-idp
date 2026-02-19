.PHONY: help init plan apply destroy clean build-layer generate-cert upload-static upload-cert add-user add-role logs

# Variables
PROJECT_NAME ?= simple-saml-idp
ENVIRONMENT ?= dev
AWS_REGION ?= us-east-1

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

init: ## Initialize Terraform
	terraform init

plan: ## Run Terraform plan
	terraform plan

apply: ## Apply Terraform configuration
	terraform apply

destroy: ## Destroy all Terraform resources
	terraform destroy

validate: ## Validate Terraform configuration
	terraform validate
	terraform fmt -check -recursive

format: ## Format Terraform files
	terraform fmt -recursive

clean: ## Clean build artifacts
	rm -rf .terraform/
	rm -f lambda/saml_processor.zip
	rm -f lambda/saml_processor-layer.zip
	rm -f lambda/manage_users_roles.zip
	rm -f lambda/manage_users_roles-layer.zip
	# Clean installed packages from lambda directories
	find lambda/saml_processor -mindepth 1 -maxdepth 1 ! -name 'index.py' ! -name 'requirements.txt' -exec rm -rf {} +
	find lambda/manage_users_roles -mindepth 1 -maxdepth 1 ! -name 'index.py' ! -name 'requirements.txt' -exec rm -rf {} +
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build-layer: ## Build Lambda functions and layer with dependencies
	./scripts/setup.sh

generate-cert: ## Generate SAML certificates
	./scripts/generate-saml-cert.sh

upload-static: ## Upload login page to S3
	@BUCKET_NAME=$$(terraform output -raw s3_bucket_name); \
	aws s3 cp static/index.html s3://$$BUCKET_NAME/index.html \
		--content-type "text/html" \
		--region $(AWS_REGION)
	@if terraform output cloudfront_distribution_id > /dev/null 2>&1; then \
		DIST_ID=$$(terraform output -raw cloudfront_distribution_id); \
		aws cloudfront create-invalidation \
			--distribution-id $$DIST_ID \
			--paths "/*"; \
	fi

upload-cert: ## Upload SAML certificates to SSM
	@aws ssm put-parameter \
		--name "/$(PROJECT_NAME)/$(ENVIRONMENT)/saml/private_key" \
		--value "$$(cat certs/saml-private-key.pem)" \
		--type SecureString \
		--overwrite \
		--region $(AWS_REGION)
	@aws ssm put-parameter \
		--name "/$(PROJECT_NAME)/$(ENVIRONMENT)/saml/certificate" \
		--value "$$(cat certs/saml-certificate.pem)" \
		--type String \
		--overwrite \
		--region $(AWS_REGION)
	@echo "Certificates uploaded to SSM Parameter Store"

add-user: ## Add a user (Usage: make add-user USERNAME=john.doe PASSWORD=secret)
	@if [ -z "$(USERNAME)" ] || [ -z "$(PASSWORD)" ]; then \
		echo "Error: USERNAME and PASSWORD are required"; \
		echo "Usage: make add-user USERNAME=john.doe PASSWORD=secret"; \
		exit 1; \
	fi
	@TABLE_NAME=$$(terraform output -raw dynamodb_users_table); \
	./scripts/add-user.sh $$TABLE_NAME $(USERNAME) $(PASSWORD)

add-role: ## Add a role mapping (Usage: make add-role USERNAME=john.doe ROLE_ARN=arn:aws:iam::123:role/Admin ACCOUNT_NAME="Prod" [ACS_URL="https://..."])
	@if [ -z "$(USERNAME)" ] || [ -z "$(ROLE_ARN)" ] || [ -z "$(ACCOUNT_NAME)" ]; then \
		echo "Error: USERNAME, ROLE_ARN, and ACCOUNT_NAME are required"; \
		echo "Usage: make add-role USERNAME=john.doe ROLE_ARN=arn:aws:iam::123:role/Admin ACCOUNT_NAME='Production' [ACS_URL='https://signin.aws.amazon.com/saml']"; \
		exit 1; \
	fi
	@TABLE_NAME=$$(terraform output -raw dynamodb_roles_table); \
	./scripts/add-role.sh $$TABLE_NAME $(USERNAME) $(ROLE_ARN) $(ACCOUNT_NAME) $(ACS_URL)

logs-lambda: ## Tail Lambda function logs
	@FUNCTION_NAME=$$(terraform output -raw api_gateway_url | grep -oP '(?<=https://).*?(?=\.)'); \
	aws logs tail /aws/lambda/$(PROJECT_NAME)-processor-$(ENVIRONMENT) --follow

logs-api: ## Tail API Gateway logs
	@aws logs tail /aws/apigateway/$(PROJECT_NAME)-$(ENVIRONMENT) --follow

outputs: ## Show Terraform outputs
	@terraform output

deploy: init apply upload-cert upload-static ## Full deployment (init, apply, upload certs and static files)
	@echo ""
	@echo "Deployment complete!"
	@echo ""
	@echo "Login URL: $$(terraform output -raw login_page_url)"
	@echo "API Gateway URL: $$(terraform output -raw api_gateway_url)"
	@echo "SAML Metadata URL: $$(terraform output -raw saml_metadata_url)"
	@echo ""
	@echo "Next steps:"
	@echo "1. Update static/index.html with the API Gateway URL"
	@echo "2. Run 'make upload-static' to upload the updated login page"
	@echo "3. Add users with 'make add-user USERNAME=john.doe PASSWORD=secret'"
	@echo "4. Add roles with 'make add-role USERNAME=john.doe ROLE_ARN=... ACCOUNT_NAME=...'"
