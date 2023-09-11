#!/usr/bin/env bash

set -e

SCRIPT_DIR=$(dirname "$(realpath "$0")")
cd "$SCRIPT_DIR"/.. || exit 1
OUTPUT_FOLDER_NAME=discord
OUTPUT_DIR=$SCRIPT_DIR/structured-output/$OUTPUT_FOLDER_NAME
DOWNLOAD_DIR=$SCRIPT_DIR/download/$OUTPUT_FOLDER_NAME

if [ -z "$DISCORD_TOKEN" ]; then
   echo "Skipping Discord ingest test because the DISCORD_TOKEN env var is not set."
   exit 0
fi

PYTHONPATH=. ./unstructured/ingest/main.py \
    discord \
    --metadata-exclude coordinates,file_directory,metadata.data_source.date_processed,metadata.last_modified,metadata.detection_class_prob \
    --download-dir "$DOWNLOAD_DIR" \
    --preserve-downloads \
    --reprocess \
    --output-dir "$OUTPUT_DIR" \
    --verbose \
    --channels 1099442333440802930,1099601456321003600 \
    --token "$DISCORD_TOKEN" \

sh "$SCRIPT_DIR"/check-diff-expected-output.sh $OUTPUT_FOLDER_NAME