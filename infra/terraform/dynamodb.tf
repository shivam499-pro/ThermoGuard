locals {
  name = var.project
}

resource "aws_dynamodb_table" "events" {
  name         = "${local.name}-events"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "event_id"

  attribute {
    name = "event_id"
    type = "S"
  }

  attribute {
    name = "risk_tier"
    type = "S"
  }

  attribute {
    name = "methodology_version"
    type = "S"
  }

  global_secondary_index {
    name            = "risk_tier-index"
    hash_key        = "risk_tier"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "methodology-index"
    hash_key        = "methodology_version"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = false
  }

  server_side_encryption {
    enabled = true
  }

  dynamic "replica" {
    for_each = var.enable_global_tables ? [var.replica_region] : []
    content {
      region_name = replica.value
    }
  }

  tags = {
    Project = local.name
    Pillar  = "database-clustering"
  }
}

resource "aws_dynamodb_table" "jobs" {
  name         = "${local.name}-jobs"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "job_id"

  attribute {
    name = "job_id"
    type = "S"
  }

  attribute {
    name = "event_id"
    type = "S"
  }

  global_secondary_index {
    name            = "event_id-index"
    hash_key        = "event_id"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Project = local.name
  }
}

resource "aws_dynamodb_table" "cache" {
  name         = "${local.name}-semantic-cache"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "cache_key"

  attribute {
    name = "cache_key"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Project = local.name
    Pillar  = "semantic-caching"
  }
}

resource "aws_dynamodb_table" "vectors" {
  name         = "${local.name}-vectors"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "event_id"

  attribute {
    name = "event_id"
    type = "S"
  }

  attribute {
    name = "risk_tier"
    type = "S"
  }

  global_secondary_index {
    name            = "risk_tier-index"
    hash_key        = "risk_tier"
    projection_type = "ALL"
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Project = local.name
    Pillar  = "vector-rag"
  }
}
