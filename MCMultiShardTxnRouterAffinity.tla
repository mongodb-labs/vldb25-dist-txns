--------------------- MODULE MCMultiShardTxnRouterAffinity ---------------------
EXTENDS MCMultiShardTxn

TransactionHasOneRouter ==
    \A tid \in TxId, r1, r2 \in Router :
        (rTxnReadTs[r1][tid] # NoValue /\ rTxnReadTs[r2][tid] # NoValue)
            => r1 = r2

=============================================================================
