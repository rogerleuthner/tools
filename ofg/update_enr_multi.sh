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

if [ $# != 0 ]
then
	echo Usage: process_enr
	exit
fi

export PROCESSING_ROOT="`pwd`"
# page from which to find href="/digital_enroute.asp?eff=11-18-2010&amp;end=01-13-2011"
export POINTER_BASE_PAGE="http://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/ifr/"
export BASE_PAGE="http://aeronav.faa.gov/enroute/"
export GREP_POINTER="\/enroute\/"
export ZOOMS="6-10"
export FAA_BASE_URL_SED="http:\/\/aeronav.faa.gov\/"
export SKIP="ENR_H ENR_P"
# Open flight map code depends upon this file being named
export MAP_METADATA_FILE="mapmetadata.html"
export PATH="${PROCESSING_ROOT}/bin:${PROCESSING_ROOT}/bin/ImageMagick-6.8.6-10:$PATH"

if [ ! -d WORK_enroute ]
then
	echo "Use for for updating already downloaded, WORK_enroute must exist"
	exit
fi

cd WORK_enroute

# cleanup from last incremental
rm -f DOWNLOAD_PAGE UPDATE_DOWNLOAD_PAGE UPDATE_PRODUCT_URLS TMP_PRODUCT_URLS

# get the URL for the chart list page, it depends upon the current cycle
wget $POINTER_BASE_PAGE -O DOWNLOAD_POINTER_PAGE

grep "aeronav.faa.gov/enroute" DOWNLOAD_POINTER_PAGE | grep enr_l | sed -e 's/.*<td><a href=\"'// -e 's/.zip.*/.zip/' > DOWNLOAD_PAGE
#http://aeronav.faa.gov/enroute/04-03-2014/enr_l34
#http://aeronav.faa.gov/enroute/04-03-2014/enr_l35
#http://aeronav.faa.gov/enroute/04-03-2014/enr_l36
export DATE_EFF=`tail -1 DOWNLOAD_PAGE | sed -e 's/.*enroute\///' -e 's/\/.*//'`
#04-03-2014
# 'ELUS10' just a convenient entry
VAR=`grep "<td>ELUS10" DOWNLOAD_POINTER_PAGE | sed -e 's/.*<td>ELUS10 //' -e 's/<\/td>//'`
# May 29 2014

MONTH=`echo $VAR | sed 's/ .*//'`
case "${MONTH}" in
 Jan*) MONTH=01;;
 Feb*) MONTH=02;;
 Mar*) MONTH=03;;
 Apr*) MONTH=04;;
 May*) MONTH=05;;
 Jun*) MONTH=06;;
 Jul*) MONTH=07;;
 Aug*) MONTH=08;;
 Sep*) MONTH=09;;
 Oct*) MONTH=10;;
 Nov*) MONTH=11;;
 Dec*) MONTH=12;;
esac

set $VAR
export DATE_EXP="${MONTH}-${2}-${3}"

# get each zip file, expand and process tiffs in it, create resulting output zip file
# in groups of 5

i=0
cat DOWNLOAD_PAGE | while read inline 
do

	../bin/update_enr_multi_sub.sh "${inline}" &
	
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


