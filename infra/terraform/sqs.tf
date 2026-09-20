resource "aws_sqs_queue" "scoring_dlq" {
  name                      = "${local.name}-scoring-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "scoring" {
  name                       = "${local.name}-scoring"
  visibility_timeout_seconds = 90
  message_retention_seconds  = 86400
  sqs_managed_sse_enabled    = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.scoring_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Project = local.name
    Pillar  = "message-broker"
  }
}
