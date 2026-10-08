output "public_ip" {
  value = aws_instance.this.public_ip
}

output "ssh" {
  value = "ssh -i ~/.ssh/id_ed25519 ubuntu@${aws_instance.this.public_ip}"
}

output "bootstrap_log" {
  value = "ssh ubuntu@${aws_instance.this.public_ip} 'tail -f /var/log/ai-sre-bootstrap.log'"
}

output "private_ip" {
  value = aws_instance.this.private_ip
}
