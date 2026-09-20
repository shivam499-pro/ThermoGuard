data "aws_caller_identity" "current" {}

locals {
  lambda_zip = var.lambda_zip_path != "" ? var.lambda_zip_path : "${path.module}/../../backend/dist/thermoguard.zip"
}

resource "aws_cloudwatch_log_group" "ingress" {
  name              = "/aws/lambda/${local.name}-ingress"
  retention_in_days = 7
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/aws/lambda/${local.name}-worker"
  retention_in_days = 7
}

resource "aws_iam_role" "ingress" {
  name = "${local.name}-ingress-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role" "worker" {
  name = "${local.name}-worker-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "ingress" {
  name = "${local.name}-ingress-policy"
  role = aws_iam_role.ingress.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.ingress.arn}:*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          aws_dynamodb_table.events.arn,
          "${aws_dynamodb_table.events.arn}/index/*",
          aws_dynamodb_table.jobs.arn,
          "${aws_dynamodb_table.jobs.arn}/index/*",
          aws_dynamodb_table.cache.arn,
          aws_dynamodb_table.vectors.arn,
          "${aws_dynamodb_table.vectors.arn}/index/*"
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = aws_sqs_queue.scoring.arn
      }
    ]
  })
}

resource "aws_iam_role_policy" "worker" {
  name = "${local.name}-worker-policy"
  role = aws_iam_role.worker.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.worker.arn}:*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          aws_dynamodb_table.events.arn,
          "${aws_dynamodb_table.events.arn}/index/*",
          aws_dynamodb_table.jobs.arn,
          "${aws_dynamodb_table.jobs.arn}/index/*",
          aws_dynamodb_table.cache.arn,
          aws_dynamodb_table.vectors.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:ChangeMessageVisibility"
        ]
        Resource = aws_sqs_queue.scoring.arn
      },
      {
        Sid    = "BedrockInvokeOptional"
        Effect = var.bedrock_enabled ? "Allow" : "Deny"
        Action = ["bedrock:InvokeModel"]
        Resource = [
          "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.bedrock_model_id}",
          "arn:aws:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:inference-profile/*"
        ]
      }
    ]
  })
}

locals {
  lambda_env = {
    STORAGE_BACKEND     = "dynamodb"
    EVENTS_TABLE        = aws_dynamodb_table.events.name
    JOBS_TABLE          = aws_dynamodb_table.jobs.name
    CACHE_TABLE         = aws_dynamodb_table.cache.name
    VECTORS_TABLE       = aws_dynamodb_table.vectors.name
    SQS_QUEUE_URL       = aws_sqs_queue.scoring.url
    BEDROCK_ENABLED     = tostring(var.bedrock_enabled)
    BEDROCK_MODEL_ID    = var.bedrock_model_id
    JSON_LOGS           = "true"
    LOG_LEVEL           = "INFO"
  }
}

resource "aws_lambda_function" "ingress" {
  function_name    = "${local.name}-ingress"
  role             = aws_iam_role.ingress.arn
  filename         = local.lambda_zip
  source_code_hash = filebase64sha256(local.lambda_zip)
  runtime          = "python3.12"
  handler          = "lambda_handlers.ingress.handler"
  architectures    = ["x86_64"]
  timeout          = 15
  memory_size      = 512

  environment {
    variables = local.lambda_env
  }

  depends_on = [aws_cloudwatch_log_group.ingress]
}

resource "aws_lambda_function" "worker" {
  function_name    = "${local.name}-worker"
  role             = aws_iam_role.worker.arn
  filename         = local.lambda_zip
  source_code_hash = filebase64sha256(local.lambda_zip)
  runtime          = "python3.12"
  handler          = "lambda_handlers.worker.handler"
  architectures    = ["x86_64"]
  timeout          = 60
  memory_size      = 1024

  environment {
    variables = local.lambda_env
  }

  depends_on = [aws_cloudwatch_log_group.worker]
}

resource "aws_lambda_event_source_mapping" "scoring" {
  event_source_arn                   = aws_sqs_queue.scoring.arn
  function_name                      = aws_lambda_function.worker.arn
  batch_size                         = 1
  function_response_types            = ["ReportBatchItemFailures"]
  maximum_batching_window_in_seconds = 0
}
