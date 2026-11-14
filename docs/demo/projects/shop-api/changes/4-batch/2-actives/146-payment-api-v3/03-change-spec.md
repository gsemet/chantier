# Change Specification: Move the payment provider integration to its v3 API

The integration calls the provider's v3 API for payments and refunds.

Refunds of orders paid before the switch keep using v2 for 30 days.
