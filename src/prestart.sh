#! /usr/bin/env sh

echo "Running inside /app/prestart.sh"


# Gives the DB time to startup
echo "Wait 10 sec to let DB start up"
sleep 10

# Make sure the DB is in the latest form - Use Alembic for more complex updates
echo "Adding is_admin column to User table."
mariadb --host $MARIA_DB_HOST --port 3306 -u Flexcrash -p$(cat $MARIA_DB_PASSWORD_FILE) -e "ALTER TABLE User ADD COLUMN IF NOT EXISTS is_admin tinyint(1) DEFAULT 0;" Flexcrash

echo "Adding is_active column to Mixed_TrafficMixed_Traffic_Scenario_Template table."
mariadb --host $MARIA_DB_HOST --port 3306 -u Flexcrash -p$(cat $MARIA_DB_PASSWORD_FILE) -e "ALTER TABLE Mixed_Traffic_Scenario_Template ADD COLUMN IF NOT EXISTS is_active tinyint(1) DEFAULT 1;" Flexcrash
