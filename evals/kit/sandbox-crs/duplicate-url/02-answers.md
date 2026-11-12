# Answers

- Two URLs are the same after trimming, ignoring the case of the scheme and the host and one trailing `/`; the path stays case-sensitive.
- An item with no URL never clashes.
- The refusal is a 400 on the list page, with the values entered and a link to the existing item.
- The same check applies to the edit form, where an item's own URL is not a clash.
