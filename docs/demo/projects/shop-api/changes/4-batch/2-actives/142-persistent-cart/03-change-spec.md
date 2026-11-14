# Change Specification: The cart keeps its items across sessions

The cart is stored on the server for signed-in customers and in a cookie for guests, and both merge at sign-in.

A cart untouched for 30 days is emptied.
