#!/bin/sh

 # /*******************************************************************************
 #  * Copyright 2009-2015 by Roger B. Leuthner
 #  *
 #  * This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
 #  * without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 #  * GNU General Public License for more details.
 #  *
 #  * Commercial Distribution License
 #  * If you would like to distribute OpenFlightGPS (or portions thereof) under a license other than
 #  * the "GNU General Public License, version 2", contact Roger B. Leuthner through GitHub.
 #  *
 #  * GNU Public License, version 2
 #  * All distribution of OpenFlightGPS must conform to the terms of the GNU Public License, version 2.
 #  ******************************************************************************/

if [ $# != 1 ]
then
    echo "Usage: update_multi <wac,tac,sectional>"
    exit
fi
VFR_PRODUCT=$1
export PROCESSING_ROOT="`pwd`"
export POINTER_BASE_PAGE="http://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/vfr/"
export ZOOMS="5-9"
export FAA_BASE_URL_SED="http:\/\/aeronav.faa.gov\/"
# Open flight map code depends upon this file being named
export MAP_METADATA_FILE="mapmetadata.html"
export PATH="${PROCESSING_ROOT}/bin:${PROCESSING_ROOT}/bin/ImageMagick-6.8.6-10:$PATH"

cd WORK_${VFR_PRODUCT}

# cleanup from last incremental
#rm -f DOWNLOAD_PAGE UPDATE_DOWNLOAD_PAGE UPDATE_PRODUCT_URLS TMP_PRODUCT_URLS

# get the URL for the chart list page, it depends upon the current cycle
#wget $POINTER_BASE_PAGE -O DOWNLOAD_POINTER_PAGE

#grep "${VFR_PRODUCT}_files" DOWNLOAD_POINTER_PAGE | grep -v PDFs | sed -e 's/.*<td><a href=\"'// -e 's/.zip.*/.zip/' > DOWNLOAD_PAGE

# get each zip file, expand and process tiffs in it, create resulting output zip file
# in groups of 5

i=0
#cat DOWNLOAD_PAGE | while read inline 
tail -1 DOWNLOAD_PAGE | while read inline
do
    ../bin/update_multi_worker.sh "${inline}" &
    
    if [ $i -eq 0 ]
    then
        export firstpid="${!}"
    fi
    
    if [ $i -lt 5 ]
    then
        i=`expr $i + 1`        
    else
        # issued a group, wait for the first one started to be done before starting a new pack
        i=0        
        wait $firstpid 
    fi 
done

cd ..


