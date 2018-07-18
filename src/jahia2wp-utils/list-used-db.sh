#!/bin/bash


# Check parameters

if [ "$1" == "" ]
then
    echo "Root path missing"
    exit 1
fi

ROOT_PATH=$1

for wpConfig in `find ${ROOT_PATH} -name "wp-config.php"`
do
    siteFolder=`echo ${wpConfig} | awk -F"/" '{print $(NF-1)}'`
    dbName=`grep "'DB_NAME'" ${wpConfig} | awk -F, '{print $2}' | awk -F\' '{print $2}'`
    dbName=`grep "'DB_HOST'" ${wpConfig} | awk -F, '{print $2}' | awk -F\' '{print $2}'`

    echo "${wpConfig},${dbName},${dbHost}"

done