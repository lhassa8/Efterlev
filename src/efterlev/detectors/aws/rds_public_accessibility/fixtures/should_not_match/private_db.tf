resource "aws_db_instance" "private" {
  identifier              = "internal-db"
  engine                  = "postgres"
  instance_class          = "db.t3.micro"
  allocated_storage       = 20
  publicly_accessible     = false
  skip_final_snapshot     = true
}
