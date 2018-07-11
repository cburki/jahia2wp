#!/usr/bin/env bash

# Consolidate information about my/documents.epfl.ch URL for each site
# 1. Cross check with "migrations.csv" content to select only sites to migrate
# 2. Rename file (because called like zip) to real site name

MIGRATION_CSV="../data/csv/migrations.csv"
# wp_site_url,wp_tagline,wp_site_title,site_type,openshift_env,category,theme,theme_faculty,status,installs_locked,updates_automatic,langs,unit_name,Jahia_zip,comment



if [ "$1" == "" ]
then
    echo "Input folder missing"
    exit 1
fi

INPUT_FOLDER=$1
OUTPUT_FOLDER="_${INPUT_FOLDER}"

if [ ! -e ${INPUT_FOLDER} ]
then
    echo "Input folder (${INPUT_FOLDER}) doesn't exists!"
    exit 1
fi


if [ -e ${OUTPUT_FOLDER} ]
then

    rm -rf ${OUTPUT_FOLDER}

fi
mkdir ${OUTPUT_FOLDER}


for zipName in `ls ${INPUT_FOLDER}`
do
    echo -n "${zipName}... "

    siteName=`cat ${MIGRATION_CSV} | awk -F, '{if($14=="'${zipName}'") print $1}' | awk -F"/" '{print $NF}'`

    if [ "${siteName}" = "" ]
    then
        echo "Empty site name... skipping!"
        continue
    fi
    echo -n "${siteName}... "

    cat "${INPUT_FOLDER}${zipName}" | egrep -v "help-my.epfl.ch|http(s)?://my.epfl.ch(/)?$|http(s)?://documents.epfl.ch(/)?$" | sort | uniq > "${OUTPUT_FOLDER}${siteName}"

    # remove if empty
    if [ "`cat ${OUTPUT_FOLDER}${siteName} | wc -l`" = "0" ]
    then
        rm ${OUTPUT_FOLDER}${siteName}
    fi

    echo "done"

done