variable "aws_region" {
  type        = string
  default     = "ap-south-1"
  description = "Primary region for Lambda, API Gateway, DynamoDB, and SQS."
}

variable "replica_region" {
  type        = string
  default     = "ap-southeast-1"
  description = "Optional DynamoDB Global Table replica region (read replica emulation)."
}

variable "enable_global_tables" {
  type        = bool
  default     = false
  description = "Keep false during the $0 hackathon window. Enable to add a Global Table replica."
}

variable "project" {
  type    = string
  default = "thermoguard"
}

variable "github_repository" {
  type        = string
  default     = "shivam499-pro/ThermoGuard"
  description = "owner/name used by Amplify Hosting GitOps (optional)."
}

variable "github_access_token" {
  type      = string
  default   = ""
  sensitive = true
}

variable "image_uri" {
  type        = string
  default     = ""
  description = "Unused. Kept so older tfvars files still apply. Lambdas now deploy from a zip."
}

variable "lambda_zip_path" {
  type        = string
  default     = ""
  description = "Optional absolute path to thermoguard.zip. Default is backend/dist/thermoguard.zip."
}

variable "bedrock_enabled" {
  type    = bool
  default = false
}

variable "bedrock_model_id" {
  type    = string
  default = "amazon.nova-lite-v1:0"
}
