# Change Specification: Payment webhooks retry with a back-off

A webhook that fails is retried after 1 minute, 5 minutes and 30 minutes, then given up and listed in the admin console.

It does not change the payload.
