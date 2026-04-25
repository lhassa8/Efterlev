# Recorder without delivery channel — Config does nothing in this state.
resource "aws_config_configuration_recorder" "orphan" {
  name     = "orphan"
  role_arn = "arn:aws:iam::123456789012:role/config-role"

  recording_group {
    all_supported = true
  }
}
