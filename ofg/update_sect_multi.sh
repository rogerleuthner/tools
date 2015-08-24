#!/bin/sh


if [ $# != 0 ]
then
	echo Usage: update_sect_multi
	exit
fi

export PROCESSING_ROOT="`pwd`"
# page from which to find href="/digital_enroute.asp?eff=11-18-2010&amp;end=01-13-2011"
export POINTER_BASE_PAGE="http://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/vfr/"
export BASE_PAGE="http://aeronav.faa.gov/sectional_files/"
export ZOOMS="6-10"
export FAA_BASE_URL_SED="http:\/\/aeronav.faa.gov\/"
# Open flight map code depends upon this file being named
export MAP_METADATA_FILE="mapmetadata.html"
export PATH="${PROCESSING_ROOT}/bin:${PROCESSING_ROOT}/bin/ImageMagick-6.8.6-10:$PATH"

cd WORK_sectional

# cleanup from last incremental
rm -f UPDATE_DOWNLOAD_PAGE UPDATE_PRODUCT_URLS TMP_PRODUCT_URLS CURRENT_DOWNLOAD_DIFFS

# get the URL for the chart list page, it depends upon the current cycle
wget $POINTER_BASE_PAGE -O DOWNLOAD_POINTER_PAGE

grep "sectional_files" DOWNLOAD_POINTER_PAGE | grep -v PDFs | sed -e 's/.*<td><a href=\"'// -e 's/.zip.*/.zip/' | grep -v Aleutian | grep -v Hawaii|grep -v Seward | grep -v Fairbanks | grep -v Whitehorse | grep -v Barrow | grep -v Nome |grep -v Juneau | grep -v Kodiak |grep -v Ketchikan|grep -v Dutch |grep -v Cold |grep -v Lisburne|grep -v Bethel|grep -v Dawson|grep -v Anchorage > DOWNLOAD_PAGE.$$

diff DOWNLOAD_PAGE.$$ DOWNLOAD_PAGE | grep "< " | sed 's/< //' > CURRENT_DOWNLOAD_DIFFS

# prepare for next time; DOWNLOAD_PAGE.$$ will have current processed contents (after finishing this processing session)
rm DOWNLOAD_PAGE
mv DOWNLOAD_PAGE.$$ DOWNLOAD_PAGE

# get each new zip file, expand and process tiffs in it, create resulting output zip file
# in groups of 5

i=0
cat CURRENT_DOWNLOAD_DIFFS | while read inline 
do
	# clean up the url
	inline=`echo $inline | sed 's/.*<td><cfoutput><a href=\"//'`

	../bin/update_sect_multi_worker.sh "${inline}" &
	
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


