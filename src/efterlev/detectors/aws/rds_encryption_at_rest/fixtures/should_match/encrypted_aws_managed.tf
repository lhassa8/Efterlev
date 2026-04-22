resource "aws_db_instance" "replica" {
  identifier        = "app-replica"
  engine            = "mysql"
  instance_class    = "db.t3.small"
  allocated_storage = 50
  storage_encrypted = true
}
