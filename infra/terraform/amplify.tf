resource "aws_amplify_app" "frontend" {
  name        = "${local.name}-web"
  description = "ThermoGuard GIS dashboard CDN (Amplify Hosting)"

  platform = "WEB"

  build_spec = <<-EOT
    version: 1
    frontend:
      phases:
        build:
          commands:
            - echo "Static frontend; injecting API Gateway origin"
            - |
              cat > frontend/config.js <<'CFG'
              window.THERMOGUARD_API_BASE = "${aws_apigatewayv2_api.http.api_endpoint}";
              CFG
      artifacts:
        baseDirectory: frontend
        files:
          - '**/*'
      cache:
        paths: []
  EOT

  custom_rule {
    source = "</^[^.]+$|\\.(?!(css|gif|ico|jpg|js|png|txt|svg|woff|woff2|ttf|map|json|webp)$)([^.]+$)/>"
    status = "200"
    target = "/index.html"
  }

  environment_variables = {
    THERMOGUARD_API_BASE = aws_apigatewayv2_api.http.api_endpoint
  }

  tags = {
    Project = local.name
    Pillar  = "cdn-amplify"
  }
}

resource "aws_amplify_branch" "main" {
  app_id      = aws_amplify_app.frontend.id
  branch_name = "main"
  stage       = "PRODUCTION"
  enable_auto_build = false
}
