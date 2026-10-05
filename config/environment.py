import os

DATABASE_URL = os.getenv('DATABASE_URL')
JWT_SECRET = os.getenv('JWT_SECRET')

# Email (forgot password). If these are empty the link is printed in the terminal instead.
SMTP_HOST = os.getenv('SMTP_HOST')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:5173')