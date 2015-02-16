#!/bin/bash

# Event Logging tables hold time-series data which is not updated, but may be purged.
# Every table includes an auto-inc id, a uuid, and a timestamp. The INSERT stream
# does not currently take advantage of bulk insert batching which often leads to
# replication lag. Adding DELETE into the mix makes it extra painful.
#
# This script sychronizes a slave using bulk inserts with mysqldump where id > N, and
# purges old data with throttled bulk deletes where id < N order by id limit M.
# Useful for creating a new slave, syncing a broken one, or replacing replication
# with a cron job.

db='log'
ls="regexp '^[A-Z0-9].*[0-9]+$'"
mhost='m2-master'
shost='dbstore1002'

slave="mysql -h $shost --compress --skip-column-names"
master="mysql -h $mhost --compress --skip-column-names"
dump="mysqldump -h $mhost --skip-opt --single-transaction --quick --skip-triggers"
dumpdata="$dump --no-create-info --order-by-primary --insert-ignore --extended-insert --compress --hex-blob"
querytables="select table_name from information_schema.tables where table_schema = '$db' and table_name"

script=$(basename ${BASH_SOURCE})
if [ $(ps ax | grep $script | grep -v grep | wc -l) -gt 2 ]; then
    echo "duplicate process" 1>&2
    exit 1
fi

set -e

for table in $($master $db -e "$querytables $ls"); do

    echo -n $table

    if [ $($slave $db -e "$querytables = '$table'" | wc -l) -eq 0 ]; then
        echo -n ", create"
        $dump --no-data $db $table | $slave $db
    fi

#    id=$($master $db -e "select min(id) from \`$table\`")
#
#    if [ ! $id = "NULL" ]; then
#        echo -n ", purge < $id"
#        $slave $db -e "delete from \`$table\` where id < $id order by id limit 100000"
#    fi

    ts=$($slave $db -e "select max(timestamp) from \`$table\`")

    if [ ! $ts = "NULL" ]; then
        echo -n ", load > $ts"
        $dumpdata --replace --where="timestamp >= $ts" $db $table | $slave $db
    else
        echo -n ", import"
        $dumpdata $db $table | $slave $db
    fi

    echo ", ok"

done

