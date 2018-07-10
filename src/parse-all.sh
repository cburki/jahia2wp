#!/usr/bin/env bash


ZIP_DIR="/srv/${WP_ENV}/jahia2wp/data/exports/"


for zipFile in `ls ${ZIP_DIR} | egrep ".zip$"`
do

    siteName=`echo ${zipFile} | awk -F"_" '{print $1}'`

    echo "Parsing ${siteName} ..."
    python jahia2wp.py parse ${siteName}

done

