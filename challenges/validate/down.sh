#!/bin/bash

CONFIG_DIR="../ready/"
for category in $(ls $CONFIG_DIR); do
    for name in $(ls "$CONFIG_DIR/$category"); do
        if [ -f "$CONFIG_DIR/$category/$name/compose.yaml" ]; then
        docker compose -f "$CONFIG_DIR/$category/$name/compose.yaml" down
        fi
    done
done
