#!/bin/sh 

tlc="java -cp lib/tla2tools-v1.8.jar tlc2.TLC"

workers=6

# Check config for local read concern w/ no prepare blocking.
$tlc -workers $workers -deadlock -config models/MCMultiShardTxn_local_no_prepare_block.cfg MCMultiShardTxn

# Check config for local read concern w/ prepare blocking.
$tlc -workers $workers -deadlock -config models/MCMultiShardTxn_local_with_prepare_block.cfg MCMultiShardTxn

# Check config for snapshot isolation.
$tlc -workers $workers -deadlock -config models/MCMultiShardTxn_snapshot.cfg MCMultiShardTxn