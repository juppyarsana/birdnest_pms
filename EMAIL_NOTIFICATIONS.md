# Email Notification System

This document explains how to set up and use the email notification system for reservation status changes.

## Features

- Automatic email notifications for reservation status changes:
  - **Pending**: When a new reservation is created
  - **Confirmed**: When a reservation is confirmed
  - **Expected Arrival**: When guest arrival is expected
  - **Expected Departure**: When guest departure is expected
- Mailgun integration for reliable email delivery
- Enable/disable functionality at global and per-notification-type level
- Email logging for tracking delivery status
- Admin panel management for settings
- Environment variable configuration support

## Setup Instructions

### 1. Install Dependencies

The required dependencies are already added to `requirements.txt`:
- `requests` (for Mailgun API)

### 2. Configure Mailgun

1. Sign up for a Mailgun account at https://www.mailgun.com/
2. Get your API key and domain from the Mailgun dashboard
3. Add your Mailgun credentials to your `.env` file:

```env
MAILGUN_API_KEY=your_mailgun_api_key_here
MAILGUN_DOMAIN=your_mailgun_domain_here
MAILGUN_FROM_EMAIL=noreply@your_mailgun_domain_here
```

### 3. Environment Configuration

Copy `.env.example` to `.env` and configure the following variables:

```env
# Django Settings
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# Mailgun Configuration
MAILGUN_API_KEY=your_mailgun_api_key_here
MAILGUN_DOMAIN=your_mailgun_domain_here
MAILGUN_FROM_EMAIL=noreply@your_mailgun_domain_here

# Email Notifications (can be overridden in admin panel)
EMAIL_NOTIFICATIONS_ENABLED=True

# Hotel Information (can be overridden in admin panel)
HOTEL_NAME=Bird Nest PMS
HOTEL_CONTACT=+62 123 456 7890 | info@birdnestpms.com
HOTEL_ADDRESS=Jl. Example Street No. 123, Bali, Indonesia
```

### 4. Database Migration

Run the migrations to create the email notification tables:

```bash
python manage.py migrate
```

### 5. Admin Panel Configuration

1. Access the Django admin panel
2. Go to **Email Notification Settings**
3. Create or edit the settings to configure:
   - Global email notifications (enabled/disabled)
   - Individual notification types (pending, confirmed, expected arrival, expected departure)
   - Hotel information for email templates

## Usage

### Automatic Notifications

Once configured, the system will automatically send emails when:

1. A new reservation is created (status: pending)
2. A reservation status changes to:
   - confirmed
   - expected_arrival
   - expected_departure

### Manual Testing

Use the management command to test email notifications:

```bash
# Test with a specific reservation ID
python manage.py test_email --reservation-id 1 --type pending

# Test with override email address
python manage.py test_email --reservation-id 1 --type confirmed --email test@example.com

# Available notification types: pending, confirmed, expected_arrival, expected_departure
```

### Email Templates

Email templates are located in `pms/templates/pms/emails/`:

- `reservation_pending.html` / `reservation_pending.txt`
- `reservation_confirmed.html` / `reservation_confirmed.txt`
- `reservation_expected_arrival.html` / `reservation_expected_arrival.txt`
- `reservation_expected_departure.html` / `reservation_expected_departure.txt`

You can customize these templates to match your hotel's branding.

## Configuration Options

### Environment Variables

- `MAILGUN_API_KEY`: Your Mailgun API key
- `MAILGUN_DOMAIN`: Your Mailgun domain
- `MAILGUN_FROM_EMAIL`: From email address for notifications
- `EMAIL_NOTIFICATIONS_ENABLED`: Global enable/disable (True/False)
- `HOTEL_NAME`: Hotel name for email templates
- `HOTEL_CONTACT`: Hotel contact information
- `HOTEL_ADDRESS`: Hotel address

### Database Settings (Admin Panel)

The `EmailNotificationSettings` model allows you to:

- Enable/disable email notifications globally
- Enable/disable specific notification types
- Configure hotel information for email templates
- Override environment variable settings

### Email Logging

All email attempts are logged in the `EmailLog` model, which tracks:

- Reservation details
- Notification type
- Recipient email
- Status (success, failed, skipped)
- Error messages (if any)
- Timestamp

## Troubleshooting

### Common Issues

1. **Emails not sending**
   - Check Mailgun credentials in `.env` file
   - Verify email notifications are enabled in admin panel
   - Check the email logs in admin panel for error messages

2. **Missing email templates**
   - Ensure all template files exist in `pms/templates/pms/emails/`
   - Check template syntax for errors

3. **Database errors**
   - Run `python manage.py migrate` to ensure all tables are created
   - Check that signals are properly registered in `pms/apps.py`

### Logs

Email activity is logged to:
- File: `logs/email_notifications.log`
- Console output (when DEBUG=True)

### Testing

Use the test command to verify your setup:

```bash
python manage.py test_email --reservation-id 1 --type pending --email your-test-email@example.com
```

## Security Notes

- Never commit your `.env` file to version control
- Keep your Mailgun API key secure
- Use environment variables for sensitive configuration
- Regularly monitor email logs for suspicious activity

## Support

For issues or questions about the email notification system, check:

1. Email logs in the admin panel
2. Application logs in `logs/email_notifications.log`
3. Mailgun dashboard for delivery statistics