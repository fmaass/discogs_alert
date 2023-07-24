#!/bin/sh

set -e

. /home/discogs_alert/venv/bin/activate

exec python -m discogs_alert --alerter-type TELEGRAM -dt $DISCOGS_TOKEN --list-id $DISCOGS_LIST 
