resource "aws_cloudfront_distribution" "legacy" {
  enabled         = true
  is_ipv6_enabled = false
  comment         = "Legacy distribution — predates the HTTPS migration"

  origin {
    domain_name = "legacy-origin.example.com"
    origin_id   = "legacy"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "match-viewer"
      origin_ssl_protocols   = ["TLSv1"]
    }
  }

  default_cache_behavior {
    target_origin_id       = "legacy"
    viewer_protocol_policy = "allow-all"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}
