# Answers

- The order is a query parameter of the list page: `?sort=`; the default is the oldest first, as today.
- Three orders: oldest, newest, title.
- An unknown order is a 400.
- The sort links mark the current order with `aria-current`.
- The sort combines with the other query parameters of the list page: each keeps the other.
