# Chaining a queued CR

You may chain a queued CR on another when that costs less than rebasing: small work, or two CRs whose specifications edit the same lines (one table, one template block), whose rebase would conflict anyway. A shared file alone is no reason, and a CR that has started is never chained.
Send `[foreman→chief-of-staff] chain <cr> after <cr>: <reason>` and leave the CR queued. The Chief of Staff records it with `order after` and `order note`, and the user may turn it off while the CR is queued. Once the CR has started, the chain stands until the stack driver restacks (in a series or a parallel batch, until its rebase note).
