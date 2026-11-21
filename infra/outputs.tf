output "site_url" {
  value = local.site_url
}

output "cloudfront_distribution_id" {
  value = aws_cloudfront_distribution.main.id
}

output "frontend_bucket" {
  value = aws_s3_bucket.frontend.bucket
}

output "uploads_bucket" {
  value = aws_s3_bucket.uploads.bucket
}

output "user_pool_id" {
  value = aws_cognito_user_pool.main.id
}

output "user_pool_client_id" {
  value = aws_cognito_user_pool_client.web.id
}

output "cognito_domain" {
  value = "https://${aws_cognito_user_pool_domain.main.domain}.auth.${var.region}.amazoncognito.com"
}

output "api_endpoint" {
  value = aws_apigatewayv2_api.http.api_endpoint
}

output "db_instance_id" {
  value = aws_db_instance.main.identifier
}

output "migrate_function" {
  value = aws_lambda_function.fn["migrate"].function_name
}

output "region" {
  value = var.region
}

output "api_function" {
  value = aws_lambda_function.fn["api"].function_name
}

output "dashboard_url" {
  value = "https://${var.region}.console.aws.amazon.com/cloudwatch/home?region=${var.region}#dashboards:name=${local.name}"
}

output "proxy_name" {
  value = aws_db_proxy.main.name
}

output "api_id" {
  value = aws_apigatewayv2_api.http.id
}
