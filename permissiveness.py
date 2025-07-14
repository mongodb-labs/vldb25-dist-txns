

import subprocess

base_config_params = {
    "init": "InitCatalogConstraintKeysOnDifferentShards",
    "next": "Next",
    "constraint": "StateConstraint",
    "symmetry": "Symmetry",
    "constants": {
        "RC": '"snapshot"',
        "IgnorePrepareBlocking": '"false"',
        "IgnoreWriteConflicts": '"false"',
        "Keys": "{k1,k2}",
        "TxId": "{t1,t2}",
        "NoValue": "NoValue",
        "Shard": "{s1,s2}",
        "Router": "{r1}",
        "MaxOpsPerTxn": "2",
        "Timestamps": "{1,2,3}",
    }
}

def compute_permissiveness(config_name, constant_overrides={}):
    tlc="java -cp lib/tla2tools-txn-ops-project.jar tlc2.TLC"

    #
    # Make TLC config file from base_config_params.
    #
    model_file = f"models/MC_permissiveness_{config_name}_gen.cfg"
    with open(model_file, "w") as f:
        f.write(f"INIT {base_config_params['init']}\n")
        f.write(f"NEXT {base_config_params['next']}\n")
        f.write(f"CONSTRAINT {base_config_params['constraint']}\n")
        if "symmetry" in base_config_params and base_config_params["symmetry"] is not None:
            f.write(f"SYMMETRY {base_config_params['symmetry']}\n")
        f.write(f"CONSTANTS\n")
        for c in base_config_params['constants']:
            if c in constant_overrides:
                f.write(f"{c} = {constant_overrides[c]}\n")
            else:
                f.write(f"{c} = {base_config_params['constants'][c]}\n")

    # Fix workers=1 for reproducibility with symmetry reduction.
    workers = 1
    cmd=f"{tlc} -deadlock -workers {workers} -config {model_file} -fp 1 MCMultiShardTxn.tla | tee logout"
    subprocess.run(cmd, shell=True)
    subprocess.run(f"grep 'fpl' logout | sort | uniq > permissiveness_{config_name}.txt", shell=True)

    lines = open(f"permissiveness_{config_name}.txt").read().splitlines()

    uniq_fps = {}
    for line in lines:
        elems = line.split("$")
        fp = elems[1]
        uniq_fps[fp] = elems[2]

    # print(config_name, len(uniq_fps))
    return uniq_fps

def strict_subset_ordered(a, b):
    return set(a.keys()).issubset(set(b.keys())) and not set(b.keys()).issubset(set(a.keys()))

models = {
    "with_prepare_block": {
        "RC": '"local"',
        "IgnorePrepareBlocking": '"false"',
        "IgnoreWriteConflicts": '"false"',
    },
    "no_prepare_block": {
        "RC": '"local"',
        "IgnorePrepareBlocking": '"force"',
        "IgnoreWriteConflicts": '"false"',
    }
}

schedules = {}
for m in models:
    schedules[m] = compute_permissiveness(m,constant_overrides=models[m])
    print(f"Schedules {m}", len(schedules[m]))

print("--------")
for m in models:
    print(f"Schedules for {m}: {len(schedules[m])}")










# exit(0)
# schedules_prepare = []
# # schedules_prepare = compute_permissiveness("MCMultiShardTxn_RC_with_prepare_block")
# # print("schedules_prepare", len(schedules_prepare))
# # exit(0)
# # schedules_no_prepare = compute_permissiveness("MCMultiShardTxn_RC_no_prepare_block")
# schedules_no_prepare = []
# # print("schedules_no_prepare", len(schedules_no_prepare))
# # exit(0)
# schedules_no_prepare_no_ww = compute_permissiveness("MCMultiShardTxn_RC_no_prepare_block_or_ww")
# print("schedules_no_prepare_no_ww", len(schedules_no_prepare_no_ww))
# exit(0)
# # Ensure one of these schedules is a strict subset of the other.
# ordered1 = strict_subset_ordered(schedules_prepare, schedules_no_prepare)
# ordered2 = strict_subset_ordered(schedules_no_prepare, schedules_no_prepare_no_ww)

# # assert ordered1 or ordered2

# diff = set(schedules_no_prepare.keys()).symmetric_difference(set(schedules_prepare.keys()))
# print(len(diff))
# print(diff)
# for d in diff:
#     if d in schedules_prepare:
#         print("schedules_prepare")
#         print(d, schedules_prepare[d])
#     if d in schedules_no_prepare:
#         print("schedules_no_prepare")
#         print(d, schedules_no_prepare[d])

# diff = set(schedules_no_prepare_no_ww.keys()).symmetric_difference(set(schedules_no_prepare.keys()))
# print(len(diff))
# print(diff)
# for d in diff:
#     if d in schedules_no_prepare_no_ww:
#         print("schedules_no_prepare_no_ww")
#         print(d, schedules_no_prepare_no_ww[d])
#     if d in schedules_no_prepare:
#         print("schedules_no_prepare")
#         print(d, schedules_no_prepare[d])

# print("schedules_prepare", len(schedules_prepare))
# print("schedules_no_prepare", len(schedules_no_prepare))
# print("schedules_no_prepare_no_ww", len(schedules_no_prepare_no_ww))

# print("ordered1", ordered1)
# print("ordered2", ordered2)

# -2478145200821578246 
# (t1 :> <<[op |-> "read", key |-> k2, value |-> NoValue], [op |-> "read", key |-> k2, value |-> t2]>> @@ 
#  t2 :> <<[op |-> "read", key |-> k1, value |-> NoValue], [op |-> "write", key |-> k2, value |-> t2]>>)


# 2793947217171754682 (
# t1 :> <<[op |-> "read", key |-> k2, value |-> NoValue], [op |-> "read", key |-> k2, value |-> t2]>> @@ 
# t2 :> <<[op |-> "write", key |-> k2, value |-> t2]>>
# )