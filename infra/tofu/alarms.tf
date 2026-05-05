# CloudWatch alarms + SNS topic for the Lina sandbox.
#
# The single SNS topic is the delivery channel; subscribe an operator
# email out-of-band:
#   aws sns subscribe \
#     --topic-arn $(tofu output -raw alarms_topic_arn) \
#     --protocol email --notification-endpoint ops@example.com
#
# Default thresholds are sized for sandbox traffic (handful of requests
# per day from 1–2 trusted users). Tune via the `alarm_*` variables.

resource "aws_sns_topic" "alarms" {
  name = "${local.name_prefix}-alarms"
}

# ---------------------------------------------------------------------------
# Lambda errors — any unhandled exception or non-2xx graph result.
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${local.name_prefix}-lambda-errors"
  alarm_description   = "Chat Lambda raised one or more unhandled exceptions in 5 minutes."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  threshold           = 0
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  statistic           = "Sum"
  period              = 300
  dimensions = {
    FunctionName = aws_lambda_function.chat.function_name
  }
  treat_missing_data = "notBreaching"
  alarm_actions      = [aws_sns_topic.alarms.arn]
  ok_actions         = [aws_sns_topic.alarms.arn]
}

# ---------------------------------------------------------------------------
# Lambda duration approaching the API Gateway timeout. Fires before
# requests start timing out client-side so we get a heads-up.
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "lambda_duration_near_apigw_timeout" {
  alarm_name          = "${local.name_prefix}-lambda-duration-high"
  alarm_description   = "Chat Lambda p95 duration > 25 s (API Gateway integration timeout is 30 s)."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  threshold           = 25000 # ms
  namespace           = "AWS/Lambda"
  metric_name         = "Duration"
  extended_statistic  = "p95"
  period              = 300
  dimensions = {
    FunctionName = aws_lambda_function.chat.function_name
  }
  treat_missing_data = "notBreaching"
  alarm_actions      = [aws_sns_topic.alarms.arn]
}

# ---------------------------------------------------------------------------
# API Gateway 5xx — covers integration failures (Lambda crashes, gateway
# timeouts) that wouldn't necessarily show up in the Lambda-side metric.
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "apigw_5xx" {
  alarm_name          = "${local.name_prefix}-apigw-5xx"
  alarm_description   = "API Gateway 5xx responses on POST /ask in the last 5 minutes."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  threshold           = 0
  namespace           = "AWS/ApiGateway"
  metric_name         = "5xx"
  statistic           = "Sum"
  period              = 300
  dimensions = {
    ApiId = aws_apigatewayv2_api.this.id
    Stage = aws_apigatewayv2_stage.default.name
  }
  treat_missing_data = "notBreaching"
  alarm_actions      = [aws_sns_topic.alarms.arn]
  ok_actions         = [aws_sns_topic.alarms.arn]
}

# ---------------------------------------------------------------------------
# Authorizer failures — sustained spike means either the API key was
# leaked and rotated, or someone is brute-forcing.
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "authorizer_failures" {
  alarm_name          = "${local.name_prefix}-authorizer-failures"
  alarm_description   = "Authorizer Lambda errored or returned >5 unauthorized in 5 minutes."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  threshold           = 5
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  statistic           = "Sum"
  period              = 300
  dimensions = {
    FunctionName = aws_lambda_function.authorizer.function_name
  }
  treat_missing_data = "notBreaching"
  alarm_actions      = [aws_sns_topic.alarms.arn]
}
