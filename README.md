# Specification of Distributed Transactions in MongoDB

This directory contains formal specifications that model the high level behavior of the [distributed, cross-shard transactions protocol in MongoDB](https://github.com/mongodb/mongo/blob/master/src/mongo/db/s/README_sessions_and_transactions.md#transactions). The main specification resides in [`MultiShardTxn.tla`](MultiShardTxn.tla), which models MongoDB's distributed, multi-document transaction protocol. As a sub-component of this distributed transactions spec, there is a separate specification of the WiredTiger storage layer interface in [`Storage.tla`](Storage.tla).

You can interact with some concrete models of these specifications in the browser here: 

- [MultiShardTxn](https://will62794.github.io/spectacle/#!/home?specpath=https://raw.githubusercontent.com/mongodb-labs/vldb25-dist-txns/refs/heads/main/MultiShardTxn.tla&constants%5BKeys%5D=%7Bk1%2Ck2%7D&constants%5BTxId%5D=%7Bt1%2Ct2%7D&constants%5BShard%5D=%7Bs1%2Cs2%7D&constants%5BNoValue%5D=%22NoVal%22&constants%5BWC%5D=%22majority%22&constants%5BRC%5D=%22snapshot%22&constants%5BMaxOpsPerTxn%5D=2&constants%5BRouter%5D=%7Br1%7D&constants%5BPrepareBlocksReads%5D=TRUE&constants%5BTimestamps%5D=%7B1%2C2%2C3%7D&constants%5BIgnorePrepareBlocking%5D=FALSE&constants%5BIgnoreWriteConflicts%5D=FALSE&hiddenVars=epoch%2CcommitIndex%2Caborted&explodedConstantExpr=Shard) (2 keys, 2 transactions, 2 shards)
- [Storage](https://will62794.github.io/spectacle/#!/home?specpath=https://raw.githubusercontent.com/mongodb-labs/vldb25-dist-txns/refs/heads/main/Storage.tla&constants%5BWC%5D=%22majority%22&constants%5BMaxTimestamp%5D=3&constants%5BRC%5D=%22snapshot%22&constants%5BKeys%5D=%7Bk1%2Ck2%7D&constants%5BNoValue%5D=%22NoValue%22&constants%5BMTxId%5D=%7Bt1%2Ct2%7D&constants%5BNil%5D=%22Nil%22&constants%5BNode%5D=%7Bn%7D&constants%5BTimestamps%5D=%7B1%2C2%2C3%7D) (2 transactions, 2 keys)

This repo also serves as a static artifact to accompany the VLDB 2025 paper *Design and Modular Verification of Distributed Transactions in MongoDB*.

## Specification Overview

At a high level, the protocol modeled here is a distributed transaction protocol that implements snapshot isolation. This is acheived this by running a two-phase commit style protocol against shards that individually implement snapshot isolated key-value stores, while also maintaining causally consistent timestamps across the cluster which are used to manage ordering and visibility between transactions. In practice, each shard is operated as a MongoDB replica set, providing fault tolerance. 

The main logical participants of the protocol consist of *client*, *router*, and *shard* roles, and currently utilizes the following constant parameters:
-  `Shard`: a fixed set of shards. 
-  `Router`: a set of routers. 
-  `TxId`: a set of unique transaction ids. 
-  `Key`: a set of collection keys. 
-  `RC`: a global read concern parameter for all transactions (i.e. `"local"` or `"snapshot"`).

### Routers

Routers, of which there may be several, handle incoming transaction operations issued to them by clients. In the current model, clients are not represented explicitly, but we represent a client operation occurring at the router in the router specific actions for starting or continuing a transaction with a specified operation type and key.

Routers forward transaction operations to shards in an interactive fashion, and individual shards are responsible for executing transaction operations as they receive them, reporting their responses back to a router. If errors or conflicts occur at local shards, this is also reported back to the router, which can initiate a global abort process. In the current specification, we represent this messaging as an RPC based mechanism. Routers push new operations onto a queue that is maintained at each shard, for each transaction id, and shards process new operations from this queue one at a time. That is, routers wait until a shard has processed a transaction operation before sending the next one, in an effort to simulate a synchronous RPC semantics. We may consider generalizing this messaging semantics in future (e.g. to a more asynchronous, out-of-order model).  

After issuing the last operation of a transaction, if all operations have completed successfully, a client may then issue a transaction commit operation, prompting the router to initiate a two-phase commit procedure across all participant shards. The router may does this by handing off responsbility to a *coordinator* shard, which coordinates the two-phase commit process across all participant shards. Our specification also currently models a few special cases where full 2PC can be bypassed, allowing thee router to go ahead and send commit operations directly to each shard e.g. for read-only or single shard transactions.


### Shards

Each shard passively waits for transaction operations to be sent from the router, and processes these incrementally by pulling the ops off of its incoming request queue for each transaction at that shard. After starting a transaction on a shard in response to the first statement of a transaction, it processes different types of operations accordingly as the transaction executes. This includes, for example, the behavior to abort if a write conflict occurs on that shard.


When a router initiates two-phase commit for a transaction, as described above, it hands off this responsibility to a coordinator shard, which is responsible for coordinating the commit process across all participant shards. The coordinator shard then sends *prepare* messages to all participant shards that were involved in the transaction, waits for affirmative responses from all shards, and then makes a decision to commit the transaction, sending out a message indicating this to all shards, which can then individually commit the transaction on that shard. Two-phase commit messages are then exchanged between coordinator and participant shards to drive the transaction to commit.

### Cluster Timestamp Semantics

Timestamps are used in the sharded transaction protocol to manage ordering and visibility of transactions across the cluster. Timestamps are used in global transaction *read timestamps*, and also for *prepare* and *commit* timestamps in the two-phase commit protocol. We currently try to model things in as general a way as possible, so we allow routers, for example, to [select any read timestamp](MultiShardTxn.tla#L542) within the range of current timestamp history, even though the implementation may select timestamps more strictly e.g. based on the latest cluster timestamp it knows about. 

## Checking Isolation Properties

We currently check high level isolation safety properties of the transaction protocol specification. In MongoDB, consistency/isolation of a multi-document transaction is [determined by its read/write concern parameters](https://www.mongodb.com/docs/manual/core/transactions/), so we try to reflect those settings in our model and check them against standard isolation levels. 

Essentially, MongoDB provides associated guarantees for a transaction only if it commits at `w:majority`, so in practice it is the selection of `readConcern` that determines the transaction's consistency semantics. Furthermore, due to the implementation of [*speculative majority*](https://github.com/mongodb/mongo/blob/2aaaa4c0ca6281088d766def53e86b01c99a8dba/src/mongo/db/repl/README.md#read-concern-behavior-within-transactions), "local" and "majority" read concern behave in the same way during establishment of the transaction on each shard (i.e. they don't read from a consistent timestamp across shards). So, we focus on two distinct classes of guarantees:

1. `{readConcern: "snapshot", writeConcern: "majority"}`
2. `{readConcern: "local", writeConcern: "majority"}`

where we expect (1) to satisfy [snapshot isolation](https://jepsen.io/consistency/models/snapshot-isolation) and (2) to satisfy something weaker than snapshot isolation, closer to [read committed](https://jepsen.io/consistency/models/read-committed) semantics. Note that we expect (2) to currently provide at least repeatable reads but not snapshot isolation, since transactions will execute on each shard (locally) at snapshot isolation, but may not read from a consistent snapshot across shards. 

We verify these isolation properties using the [client-centric isolation model of Crooks](https://www.cs.cornell.edu/lorenzo/papers/Crooks17Seeing.pdf), and utilizing the [formalization of this in TLA+](ClientCentric.tla) by [Soethout](https://link.springer.com/chapter/10.1007/978-3-030-67220-1_4). To check isolation, we use a global history of transaction operations maintained in the [`ops`](MultiShardTxn.tla#L87) map. The formal definitions of [snapshot isolation](ClientCentric.tla#L177-L178) and other isolation levels are given in the [`ClientCentric.tla`](ClientCentric.tla) file. You can also see some concrete isolation tests defined in [`ClientCentricTests.tla`](ClientCentricTests.tla).

So far we have checked small models for correctness, using the `MaxOpsPerTxn` parameter and `StateConstraint` constraint to bound the maximum number of operations run by each transaction. You can see and check the models we have run so far by running
```bash
./check_models.sh
```
which will run TLC to check models with varying isolation properties, including snapshot isolation and read committed.

## Computing Permissiveness

We also compute *permissiveness* metrics for this transactions protocol specification. Essentially, this gives a finer-grained way to measure the amount of concurrency permitted by a protocol with respect to a given isolation level. These metrics are computed by running 
```bash
python3 permissiveness.py
```
This script utilizes a modified version of TLC to compute the reachable state graph projected down to the `ops` state variable, which records the history of each transaction's operations. The cardinality of this set over the reachable states is then used as the permissiveness metric. For now we only compute this metric over fixed, small, finite models.


## Model-Based Testing of the Storage Layer

The current specification models the storage layer (e.g. abstract WiredTiger semantics) at each shard in a modular way. This is done by having `Storage` encapsulate most of the storage/replication specific logic, and [instantiating one of these modules per shard](MultiShardTxn.tla#L116-L129). The idea is that `Storage` can be considered as an independent state machine that composes synchronously with `MultiShardTxn` via joint actions. 

We utilize this independent storage layer specification for automated, model-based test case generation of WiredTiger i.e. to check that the WiredTiger implementation conforms to this [`Storage.tla`](Storage.tla) specification. Essentially, we generate WiredTiger unit test cases by computing path coverings of the reachable state space of the `Storage` model, and then use these test cases to check that the implementation conforms to the `Storage` model. 

The basic workflow to generate these test cases from the storage model is implemented in the [`testgen.py`](testgen.py) script, which depends on the `networkx` library (`pip install networkx`). You can run test case generation for a small model with 2 transactions and 2 keys with the following command:

```bash
python3 testgen.py --parallel_test_split 4 --compact --constants MTxId "{t1,t2}" Keys "{k1,k2}" Timestamps "{1,2,3}" IgnorePrepareOptions '{"false","true","force"}' --coverage_pct 1.0
```
this will generate WiredTiger unit tests files in `model_tests/test_txn_model_traces_*.py` files, which can be directly run against a WiredTiger build. For example, on a workstation with a WiredTiger source directory in `~/wiredtiger`, you can copy these generated test files over to  `~/wiredtiger/test/suite`, and then, from inside the `build` directory, run them with a command like:
```bash
python3 ../test/suite/run.py -v 2 -j 4 model_tests_1 model_tests_2 model_tests_3 model_tests_4
```
Note that the test case generation script also makes use of a modified build of TLC whose code lives on [this branch](https://github.com/will62794/tlaplus/tree/multi-inv-checking-et-al).


