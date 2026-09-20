output "api_gateway_url" {
  value       = aws_apigatewayv2_api.http.api_endpoint
  description = "HTTPS origin for the GIS dashboard (no naked uvicorn)."
}

output "lambda_zip" {
  value       = local.lambda_zip
  description = "Zip uploaded to both Ingress-Lambda and Worker-Lambda."
}

output "sqs_queue_url" {
  value = aws_sqs_queue.scoring.url
}

output "events_table" {
  value = aws_dynamodb_table.events.name
}

output "amplify_app_id" {
  value = aws_amplify_app.frontend.id
}

output "amplify_default_domain" {
  value = aws_amplify_app.frontend.default_domain
}

output "ingress_function_name" {
  value = aws_lambda_function.ingress.function_name
}

output "worker_function_name" {
  value = aws_lambda_function.worker.function_name
}
