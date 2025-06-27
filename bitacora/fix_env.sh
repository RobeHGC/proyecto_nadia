#!/bin/bash

# Fix for .env inline comments that break config parsing
# Run this script before starting any services

export TYPING_WINDOW_DELAY=1.5
export TYPING_DEBOUNCE_DELAY=60
export MIN_BATCH_SIZE=2
export MAX_BATCH_SIZE=5
export MAX_BATCH_WAIT_TIME=30.0

echo "✅ Environment variables cleaned"
echo "TYPING_WINDOW_DELAY=$TYPING_WINDOW_DELAY"
echo "TYPING_DEBOUNCE_DELAY=$TYPING_DEBOUNCE_DELAY"
echo "MIN_BATCH_SIZE=$MIN_BATCH_SIZE"
echo "MAX_BATCH_SIZE=$MAX_BATCH_SIZE"
echo "MAX_BATCH_WAIT_TIME=$MAX_BATCH_WAIT_TIME"