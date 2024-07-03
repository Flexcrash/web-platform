#! /usr/bin/env sh

echo "Running inside /app/src/prestart.sh"


# Gives the DB time to startup
echo "Wait 10 sec to let DB start up"
sleep 10

echo "Restoring the database from the dump file"
mariadb --host $MARIA_DB_HOST --port 3306 -u Flexcrash -p$(cat $MARIA_DB_PASSWORD_FILE) Flexcrash < dump.sql